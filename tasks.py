from typing import Dict, Any, List, Optional, Union
import logging
import random
import time
import asyncio
from datetime import datetime
from sqlalchemy import and_, func
from sqlalchemy.orm import Session
from celery import shared_task, group
import json

from models import UnclaimedCard, CardModel, UserModel
from database import SessionLocal
from celery_config import celery_app
from credit_manager import credit_manager
from generate_card_script import generate_card

logger = logging.getLogger(__name__)

# Pack configuration
PACK_CONFIG = {
    "cost": 100,  # Credits cost per pack
    "contents": {
        "rare_mythic": 1,  # One rare or mythic per pack
        "uncommon": 3,     # Three uncommons per pack
        "common": 5        # Five commons per pack
    },
    "rarities": {
        "mythic_rate": 0.07,  # 7% chance for mythic instead of rare
    },
    "max_retries": 3,      # Maximum retries for partial pack fills
    "retry_delay": 0.5     # Delay between retries in seconds
}

# Error messages
PACK_ERRORS = {
    "insufficient_credits": "Insufficient credits to open pack",
    "insufficient_cards": "Not enough cards available to create a pack",
    "user_not_found": "User not found",
    "transaction_failed": "Failed to process credit transaction",
    "claim_failed": "Error claiming card"
}

class PackError(Exception):
    """Custom exception for pack-related errors."""
    pass

def get_cards_by_rarity(
    db: Session,
    rarity: Union[str, List[str]],
    count: int,
    user_id: str,
    retries: int = 0,
    mythic_rate: Optional[float] = None
) -> List[UnclaimedCard]:
    """Get and claim specified number of cards of given rarity."""
    # Ensure random is properly seeded for this process
    random.seed()
    
    cards = []
    retry_count = 0
    claim_time = datetime.utcnow()
    
    while len(cards) < count and retry_count <= retries:
        if retry_count > 0:
            time.sleep(PACK_CONFIG["retry_delay"])
        
        if mythic_rate and isinstance(rarity, list) and 'Rare' in rarity:
            # Explicitly use Python's random module
            roll = random.random()
            if roll < mythic_rate:
                query_rarity = ['Mythic']
            else:
                query_rarity = ['Rare']
        else:
            query_rarity = rarity if isinstance(rarity, list) else [rarity]
            
        new_cards = (
            db.query(UnclaimedCard)
            .filter(
                and_(
                    UnclaimedCard.is_claimed == False,
                    UnclaimedCard.rarity.in_(query_rarity)
                )
            )
            .order_by(func.random())
            .with_for_update(skip_locked=True)
            .limit(count - len(cards))
            .all()
        )
        
        for card in new_cards:
            card.is_claimed = True
            card.claimed_by_user_id = user_id
            card.claimed_at = claim_time
        
        cards.extend(new_cards)
        retry_count += 1
        
    return cards

@shared_task(bind=True, max_retries=3)
def process_pack_opening(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Celery task to process a pack opening request.
    """
    db = SessionLocal()
    try:
        # Check if user has enough credits
        current_credits = credit_manager.get_balance(user_id)
        if current_credits < PACK_CONFIG["cost"]:
            raise PackError(PACK_ERRORS["insufficient_credits"])
        
        # Start transaction for pack opening
        pack_cards = []
        
        # Get rare/mythic with proper mythic rate
        rare_mythic = get_cards_by_rarity(
            db, 
            ['Rare', 'Mythic'], 
            PACK_CONFIG["contents"]["rare_mythic"],
            user_id,
            PACK_CONFIG["max_retries"],
            PACK_CONFIG["rarities"]["mythic_rate"]
        )
        pack_cards.extend(rare_mythic)
        
        # Get uncommons
        uncommons = get_cards_by_rarity(
            db, 
            'Uncommon', 
            PACK_CONFIG["contents"]["uncommon"],
            user_id,
            PACK_CONFIG["max_retries"]
        )
        pack_cards.extend(uncommons)
        
        # Get commons
        commons = get_cards_by_rarity(
            db, 
            'Common', 
            PACK_CONFIG["contents"]["common"],
            user_id,
            PACK_CONFIG["max_retries"]
        )
        pack_cards.extend(commons)
        
        total_expected = sum(PACK_CONFIG["contents"].values())
        if len(pack_cards) < total_expected:
            raise PackError(f"{PACK_ERRORS['insufficient_cards']} (got {len(pack_cards)}, need {total_expected})")
        
        # Deduct credits using Redis credit manager
        if not credit_manager.spend_credits(
            user_id=user_id,
            amount=PACK_CONFIG["cost"],
            description="Opened a booster pack",
            transaction_type="pack_opening"
        ):
            raise PackError(PACK_ERRORS["transaction_failed"])
        
        # Create claimed cards
        claimed_cards = []
        for card in pack_cards:
            claimed_card = CardModel(
                name=card.name,
                card_data=card.card_data,
                image_path=card.image_path,
                rarity=card.rarity,
                set_name=card.set_name,
                card_number=card.card_number,
                user_id=user_id
            )
            db.add(claimed_card)
            
            claimed_cards.append({
                'id': claimed_card.id,
                'name': claimed_card.name,
                'rarity': claimed_card.rarity,
                'image_path': claimed_card.image_path,
                'set_name': claimed_card.set_name
            })
        
        # Commit transaction
        db.commit()
        
        logger.info(f"User {user_id} successfully opened pack with {len(claimed_cards)} cards")
        return {
            "message": "Pack opened successfully",
            "cards": claimed_cards,
            "credits_remaining": credit_manager.get_balance(user_id)
        }
    
    except PackError as e:
        db.rollback()
        logger.warning(f"Pack opening failed for user {user_id}: {str(e)}")
        raise self.retry(exc=e, countdown=5)
    
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error processing pack opening for user {user_id}: {e}")
        logger.exception("Pack opening error details:")
        raise self.retry(exc=e, countdown=5)
    
    finally:
        db.close()

@shared_task(bind=True, max_retries=3)
def get_credit_balance(self, user_id: str) -> Dict[str, Any]:
    """
    Celery task to get user's credit balance from Redis.
    """
    try:
        balance = credit_manager.get_balance(user_id)
        return {
            "credits": balance,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting credit balance for user {user_id}: {e}")
        raise self.retry(exc=e, countdown=5)

@shared_task(bind=True, max_retries=3)
def claim_daily_credits(self, user_id: str) -> Dict[str, Any]:
    """
    Celery task to process daily credit claim.
    """
    try:
        result = credit_manager.claim_daily_credits(user_id)
        if result["success"]:
            logger.info(f"Daily credits claimed for user {user_id}: {result['amount']} credits")
        else:
            logger.warning(f"Daily credit claim failed for user {user_id}: {result['message']}")
        return result
    except Exception as e:
        logger.error(f"Error processing daily credit claim for user {user_id}: {e}")
        raise self.retry(exc=e, countdown=5)

@shared_task(bind=True, max_retries=3)
def spend_credits(self, user_id: str, amount: int, description: str, transaction_type: str) -> bool:
    """
    Celery task to handle credit spending using Redis.
    """
    try:
        success = credit_manager.spend_credits(
            user_id=user_id,
            amount=amount,
            description=description,
            transaction_type=transaction_type
        )
        
        if not success:
            raise ValueError("Credit transaction failed")
            
        return True
        
    except Exception as e:
        logger.error(f"Credit transaction failed for user {user_id}: {e}")
        raise self.retry(exc=e, countdown=5)

@shared_task(bind=True, max_retries=None)  # Allow unlimited retries
def generate_card_task(self, rarity: str = None) -> Dict[str, Any]:
    """
    Celery task to generate a card using the API.
    Uses exponential backoff for retries to handle rate limits.
    """
    try:
        # Initialize database
        db = SessionLocal()
        
        try:
            # Generate card through API
            card_data = asyncio.run(generate_card())
            
            if not card_data:
                raise ValueError("No card data received from API")
            
            # Add to unclaimed pool
            unclaimed_card = UnclaimedCard(
                name=card_data['name'],
                card_data=card_data,
                image_path=card_data.get('image_path'),
                rarity=card_data['rarity'],
                set_name=card_data['set_name'],
                card_number=card_data['card_number'],
                is_claimed=False
            )
            db.add(unclaimed_card)
            db.commit()
            
            logger.info(f"Generated {card_data['rarity']} card: {card_data['name']}")
            return card_data
            
        except Exception as e:
            db.rollback()
            # Use exponential backoff for retries
            countdown = min(2 ** (self.request.retries + 1), 300)  # Max 5 minutes
            logger.warning(f"Card generation failed, retrying in {countdown}s: {str(e)}")
            raise self.retry(exc=e, countdown=countdown)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Unhandled error in generate_card_task: {str(e)}")
        raise

@shared_task(bind=True)
def generate_initial_cards_task(self, batch_config: Dict[str, int]) -> None:
    """
    Celery task to generate a batch of initial cards.
    Schedules individual card generation tasks with delays to avoid rate limits.
    """
    try:
        total_delay = 0
        for rarity, count in batch_config.items():
            logger.info(f"Scheduling {count} {rarity} cards...")
            
            # Schedule tasks with increasing delays to avoid rate limits
            for i in range(count):
                generate_card_task.apply_async(
                    kwargs={'rarity': rarity},
                    countdown=total_delay + (i * 2)  # Space out requests by 2 seconds each
                )
            
            total_delay += count * 2  # Update total delay for next rarity
            logger.info(f"Scheduled {count} {rarity} card generation tasks")
        
        logger.info(f"All card generation tasks have been scheduled with delays")
        
    except Exception as e:
        logger.error(f"Error scheduling card generation tasks: {str(e)}")
        raise
