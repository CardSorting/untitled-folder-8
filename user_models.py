from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    firebase_id = Column(String, unique=True, index=True)
    email = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_admin = Column(Boolean, default=False)
    
    # Relationships
    cards = relationship("CardModel", back_populates="user")
    unclaimed_cards = relationship("UnclaimedCard", foreign_keys="UnclaimedCard.claimed_by_user_id")
