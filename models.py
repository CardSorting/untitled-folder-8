from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class UserModel(Base):
    """Model for user accounts."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    firebase_id = Column(String, unique=True, index=True)
    email = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_admin = Column(Boolean, default=False)
    
    # Relationships
    cards = relationship("CardModel", back_populates="user")
    unclaimed_cards = relationship("UnclaimedCard",
                                 foreign_keys="UnclaimedCard.claimed_by_user_id",
                                 back_populates="claimed_by")

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
    
    # Relationship to user who claimed the card
    claimed_by = relationship("UserModel",
                            foreign_keys=[claimed_by_user_id],
                            back_populates="unclaimed_cards")
