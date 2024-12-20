from sqlalchemy.orm import Session
from database import SessionLocal, init_db
from models import UnclaimedCard, UserModel
import httpx
import asyncio
import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, auth
import json

load_dotenv()

ADMIN_FIREBASE_ID = "fhn34qtflHh9rVDJsrlDnlUxn3M2"
TIMEOUT = 120.0  # 120 seconds timeout for the long card generation process

async def ensure_admin_user(db: Session) -> UserModel:
    """Get the admin user and create a custom token."""
    admin = db.query(UserModel).filter(UserModel.firebase_id == ADMIN_FIREBASE_ID).first()
    if not admin:
        raise Exception(f"Admin user with Firebase ID {ADMIN_FIREBASE_ID} not found")
    
    # Initialize Firebase Admin SDK if not already initialized
    try:
        firebase_admin.get_app()
    except ValueError:
        cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH')
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    
    # Create a custom token for admin
    custom_token = auth.create_custom_token(ADMIN_FIREBASE_ID)
    return admin, custom_token.decode('utf-8')

async def generate_card():
    """Generate a card using the admin route."""
    # Initialize database
    init_db()
    db = SessionLocal()
    
    try:
        print("Getting admin user and token...")
        # Get admin user and token
        admin, custom_token = await ensure_admin_user(db)
        
        # Exchange custom token for ID token using Firebase REST API
        firebase_api_key = os.getenv('FIREBASE_API_KEY')
        if not firebase_api_key:
            raise Exception("FIREBASE_API_KEY environment variable not set")
            
        print("Exchanging custom token for ID token...")
        async with httpx.AsyncClient(timeout=30.0) as client:  # 30 second timeout for token exchange
            try:
                response = await client.post(
                    f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken",
                    params={"key": firebase_api_key},
                    json={"token": custom_token, "returnSecureToken": True}
                )
                response.raise_for_status()
                id_token = response.json()['idToken']
                print("Successfully obtained ID token")
            except httpx.HTTPError as e:
                print(f"HTTP error during token exchange: {str(e)}")
                if hasattr(response, 'text'):
                    print(f"Response content: {response.text}")
                raise
        
        print("Making request to generate card (this may take a few minutes)...")
        # Make request to generate card with ID token
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:  # Long timeout for card generation
            try:
                response = await client.post(
                    "http://localhost:8000/admin/generate-card",
                    headers={"Authorization": f"Bearer {id_token}"}
                )
                response.raise_for_status()
                card_data = response.json()
                print(f"Generated card: {json.dumps(card_data, indent=2)}")
                return card_data
            except httpx.HTTPError as e:
                print(f"HTTP error during card generation: {str(e)}")
                if hasattr(response, 'text'):
                    print(f"Response content: {response.text}")
                raise
            
    except Exception as e:
        print(f"Error generating card: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("Starting card generation script...")
    asyncio.run(generate_card())
