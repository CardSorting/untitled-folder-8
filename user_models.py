from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship, Session
from datetime import datetime
from database import Base
from websocket_manager import websocket_manager

class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    firebase_id = Column(String, unique=True, index=True)
    email = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_admin = Column(Boolean, default=False)
    credits = Column(Integer, default=0)
    
    # Relationships
    cards = relationship("CardModel", back_populates="user")
    claimed_cards = relationship("UnclaimedCard", back_populates="claimed_by")
    credit_transactions = relationship("CreditTransaction", back_populates="user")
    
    async def has_enough_credits(self, amount: int) -> bool:
        """Check if user has enough credits."""
        return self.credits >= amount
    
    async def add_credits(self, db: "Session", amount: int, description: str, transaction_type: str):
        """Add credits to user account."""
        from models import CreditTransaction
        
        self.credits += amount
        transaction = CreditTransaction(
            user_id=self.firebase_id,
            amount=amount,
            description=description,
            transaction_type=transaction_type
        )
        db.add(transaction)
        
        # Broadcast credit update via WebSocket
        await websocket_manager.broadcast_to_user(
            self.firebase_id,
            {
                "type": "credit_update",
                "credits": self.credits,
                "transaction": {
                    "amount": amount,
                    "description": description,
                    "type": transaction_type
                }
            }
        )
    
    async def spend_credits(self, db: "Session", amount: int, description: str, transaction_type: str) -> bool:
        """
        Attempt to spend credits. Returns True if successful.
        """
        if not await self.has_enough_credits(amount):
            return False
            
        from models import CreditTransaction
        
        self.credits -= amount
        transaction = CreditTransaction(
            user_id=self.firebase_id,
            amount=-amount,  # Negative amount for spending
            description=description,
            transaction_type=transaction_type
        )
        db.add(transaction)
        
        # Broadcast credit update via WebSocket
        await websocket_manager.broadcast_to_user(
            self.firebase_id,
            {
                "type": "credit_update",
                "credits": self.credits,
                "transaction": {
                    "amount": -amount,
                    "description": description,
                    "type": transaction_type
                }
            }
        )
        
        return True
