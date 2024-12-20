from database import engine, Base
from models import CardModel, UnclaimedCard
from user_models import UserModel

def reset_database():
    """Drop all tables and recreate them."""
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    
    print("Creating new tables...")
    Base.metadata.create_all(bind=engine)
    
    print("Database reset complete!")

if __name__ == "__main__":
    reset_database()