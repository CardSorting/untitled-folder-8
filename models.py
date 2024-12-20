from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class CardModel(Base):
    """Model for claimed cards that belong to users."""
    __tablename__ = "cards"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    card_data = Column(JSON)
    image_path = Column(String, nullable=True)
    rarity = Column(String)
    set_name = Column(String)
    card_number = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String, ForeignKey('users.firebase_id'))
    
    # Relationship to user
    user = relationship("UserModel", back_populates="cards")

class UnclaimedCard(Base):
    """Model for cards in the unclaimed pool."""
    __tablename__ = "unclaimed_cards"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    card_data = Column(JSON)
    image_path = Column(String, nullable=True)
    rarity = Column(String)
    set_name = Column(String)
    card_number = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_claimed = Column(Boolean, default=False)
    claimed_by_user_id = Column(String, ForeignKey('users.firebase_id'), nullable=True)
    claimed_at = Column(DateTime, nullable=True)
