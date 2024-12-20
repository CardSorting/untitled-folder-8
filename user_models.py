from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
from websocket_manager import websocket_manager
from credit_manager import credit_manager

class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    firebase_id = Column(String, unique=True, index=True)
    email = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_admin = Column(Boolean, default=False)
    
    # Relationships
    cards = relationship("CardModel", back_populates="user")

    async def notify_credit_update(self, amount: int, description: str, transaction_type: str):
        """
        Send WebSocket notification about credit update.
        """
        try:
            current_credits = credit_manager.get_balance(self.firebase_id)
            await websocket_manager.broadcast_to_user(
                self.firebase_id,
                {
                    "type": "credit_update",
                    "credits": current_credits,
                    "transaction": {
                        "amount": amount,
                        "description": description,
                        "type": transaction_type
                    }
                }
            )
        except Exception:
            # WebSocket notification failure shouldn't affect the credit operation
            pass
