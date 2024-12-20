from database import SessionLocal
from models import UserModel
from credit_manager import credit_manager

def add_credits_to_all_users():
    # Create a database session
    db = SessionLocal()
    try:
        # Get all users
        users = db.query(UserModel).all()
        
        # Add credits to each user using credit manager
        success_count = 0
        for user in users:
            success = credit_manager.add_credits(
                user_id=user.firebase_id,
                amount=10000,
                description="System-wide credit bonus",
                transaction_type="bonus"
            )
            if success:
                success_count += 1
        
        print(f"Successfully added 10000 credits to {success_count} out of {len(users)} users")
    
    except Exception as e:
        print(f"Error adding credits: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    add_credits_to_all_users()