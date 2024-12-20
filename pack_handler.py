from typing import Dict, Any, List, Optional, Union
import logging
import time
import random
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime
from contextlib import contextmanager

from models import UnclaimedCard, CardModel, CreditTransaction
from user_models import UserModel
from database import SessionLocal

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
    """
    Get and claim specified number of cards of given rarity with retry logic.
    All operations are done in a single atomic transaction.
    """
    cards = []
    retry_count = 0
    claim_time = datetime.utcnow()
    
    while len(cards) < count and retry_count <= retries:
        if retry_count > 0:
            time.sleep(PACK_CONFIG["retry_delay"])
        
        # Apply mythic rate if specified (for rare/mythic slot)
        if mythic_rate and isinstance(rarity, list) and 'Rare' in rarity:
            if random.uniform(0.0, 1.0) < mythic_rate:
                query_rarity = ['Mythic']
            else:
                query_rarity = ['Rare']
        else:
            query_rarity = rarity if isinstance(rarity, list) else [rarity]
            
        # Get and claim cards in a single atomic operation
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
        
        # Immediately mark cards as claimed
        for card in new_cards:
            card.is_claimed = True
            card.claimed_by_user_id = user_id
            card.claimed_at = claim_time
        
        cards.extend(new_cards)
        retry_count += 1
        
    return cards

def process_pack_opening(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a pack opening request safely with proper transaction handling.
    
    Args:
        user_id: The ID of the user opening the pack
        data: Additional data for pack opening (reserved for future use)
        
    Returns:
        Dict containing the opened cards and status
        
    Raises:
        PackError: If pack opening fails due to insufficient cards or credits
    """
    db = SessionLocal()
    try:
        # Get user and validate credits in a transaction
        user = db.query(UserModel).filter(UserModel.firebase_id == user_id).with_for_update().first()
        if not user:
            raise PackError(PACK_ERRORS["user_not_found"])
            
        if user.credits < PACK_CONFIG["cost"]:
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
        
        # Deduct credits and record transaction
        user.credits -= PACK_CONFIG["cost"]
        credit_transaction = CreditTransaction(
            user_id=user_id,
            amount=-PACK_CONFIG["cost"],
            description="Opened a booster pack",
            transaction_type="pack_opening"
        )
        db.add(credit_transaction)
        
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
            "credits_remaining": user.credits
        }
    
    except PackError as e:
        db.rollback()
        logger.warning(f"Pack opening failed for user {user_id}: {str(e)}")
        raise
    
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error processing pack opening for user {user_id}: {e}")
        raise PackError("An unexpected error occurred while opening the pack")
    
    finally:
        db.close()
