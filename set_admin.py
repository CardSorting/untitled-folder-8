from sqlalchemy.orm import Session
from database import SessionLocal, init_db
from models import CardModel, UnclaimedCard, UserModel  # Import related models

def set_admin():
    """Set admin privileges for a specific user."""
    # Initialize database
    init_db()
    db = SessionLocal()
    
    try:
        # Find user by Firebase ID
        user = db.query(UserModel).filter(UserModel.firebase_id == "fhn34qtflHh9rVDJsrlDnlUxn3M2").first()
        
        if not user:
            # Create user if they don't exist
            user = UserModel(
                firebase_id="fhn34qtflHh9rVDJsrlDnlUxn3M2",
                email="willcruzdesigner@gmail.com",
                is_admin=True
            )
            db.add(user)
        else:
            # Update existing user
            user.is_admin = True
            user.email = "willcruzdesigner@gmail.com"  # Ensure email is set
        
        db.commit()
        print(f"Successfully set admin privileges for user: {user.email}")
        
    except Exception as e:
        db.rollback()
        print(f"Error setting admin privileges: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    set_admin()