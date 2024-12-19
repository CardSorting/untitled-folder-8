from typing import Dict, Any
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from models import UnclaimedCard, CardModel
from database import SessionLocal

logger = logging.getLogger(__name__)

async def process_pack_opening(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a pack opening request safely with proper transaction handling.
    """
    db = SessionLocal()
    try:
        # Start transaction
        pack_cards = []
        
        # Get rare/mythic with row locking
        rare_mythic = (
            db.query(UnclaimedCard)
            .filter(
                UnclaimedCard.is_claimed == False,
                UnclaimedCard.rarity.in_(['Rare', 'Mythic'])
            )
            .order_by(func.random())
            .with_for_update(skip_locked=True)  # Skip rows locked by other transactions
            .first()
        )
        
        if rare_mythic:
            pack_cards.append(rare_mythic)
        
        # Get uncommons with row locking
        uncommons = (
            db.query(UnclaimedCard)
            .filter(
                UnclaimedCard.is_claimed == False,
                UnclaimedCard.rarity == 'Uncommon'
            )
            .order_by(func.random())
            .with_for_update(skip_locked=True)
            .limit(3)
            .all()
        )
        pack_cards.extend(uncommons)
        
        # Get commons with row locking
        commons = (
            db.query(UnclaimedCard)
            .filter(
                UnclaimedCard.is_claimed == False,
                UnclaimedCard.rarity == 'Common'
            )
            .order_by(func.random())
            .with_for_update(skip_locked=True)
            .limit(10)
            .all()
        )
        pack_cards.extend(commons)
        
        if len(pack_cards) < 14:
            raise ValueError("Not enough cards available to create a pack")
        
        # Claim all cards in the pack
        claimed_cards = []
        for card in pack_cards:
            # Create claimed card
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
            
            # Mark original card as claimed
            card.is_claimed = True
            card.claimed_by_user_id = user_id
            card.claimed_at = datetime.utcnow()
            
            claimed_cards.append({
                'id': claimed_card.id,
                'name': claimed_card.name,
                'rarity': claimed_card.rarity,
                'image_path': claimed_card.image_path
            })
        
        # Commit transaction
        db.commit()
        
        return {
            "message": "Pack opened successfully",
            "cards": claimed_cards
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing pack opening: {e}")
        raise
    
    finally:
        db.close()
