from database import engine
from models import Base
from models import CardModel, UnclaimedCard, CreditTransaction
from user_models import UserModel

def reset_database():
    """Drop all tables and recreate them with the latest schema."""
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("Creating all tables with latest schema...")
    Base.metadata.create_all(bind=engine)
    print("Database reset complete!")

if __name__ == "__main__":
    reset_database()