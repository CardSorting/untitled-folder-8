from sqlalchemy import update
from database import SessionLocal, engine
from user_models import UserModel
from models import CreditTransaction

def add_credits_to_all_users():
    # Create a database session
    db = SessionLocal()
    try:
        # Get all users
        users = db.query(UserModel).all()
        
        # Add credits and create transactions for each user
        for user in users:
            user.credits += 10000
            transaction = CreditTransaction(
                user_id=user.firebase_id,
                amount=10000,
                description="System-wide credit bonus",
                transaction_type="bonus"
            )
            db.add(transaction)
        
        # Commit the changes
        db.commit()
        print(f"Successfully added 10000 credits to {len(users)} users")
    
    except Exception as e:
        db.rollback()
        print(f"Error adding credits: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    add_credits_to_all_users()