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
    # First run set_admin.py if needed
    admin = db.query(UserModel).filter(UserModel.firebase_id == ADMIN_FIREBASE_ID).first()
    if not admin or not admin.is_admin:
        print("Admin user not found or not admin. Running set_admin.py...")
        from set_admin import set_admin
        set_admin()
        # Refresh admin user
        admin = db.query(UserModel).filter(UserModel.firebase_id == ADMIN_FIREBASE_ID).first()
        if not admin or not admin.is_admin:
            raise Exception("Failed to set up admin user")
    
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
                # First verify the token works
                print("Verifying admin access...")
                try:
                    verify_response = await client.get(
                        "http://localhost:8000/credits/can-claim",
                        headers={"Authorization": f"Bearer {id_token}"}
                    )
                    verify_response.raise_for_status()
                except Exception as e:
                    print("Error verifying token. Try running set_admin.py again.")
                    raise

                print("Admin access verified. Generating card...")
                try:
                    response = await client.post(
                        "http://localhost:8000/admin/generate-card",
                        headers={"Authorization": f"Bearer {id_token}"}
                    )
                    response.raise_for_status()
                    card_data = response.json()
                    print(f"Generated card: {json.dumps(card_data, indent=2)}")
                    return card_data
                except httpx.ConnectError:
                    print("Error: Could not connect to server. Make sure the FastAPI server is running on localhost:8000")
                    raise
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        print("Error: The /admin/generate-card endpoint was not found. Make sure you're running the latest version of the server.")
                    elif e.response.status_code == 403:
                        print("\nError: Admin access denied. Please:")
                        print("1. Run 'python set_admin.py' to ensure admin privileges")
                        print("2. Restart the FastAPI server: uvicorn main:app --reload")
                        print("3. Try again\n")
                    else:
                        print(f"HTTP error during card generation: {str(e)}")
                        if hasattr(e.response, 'text'):
                            print(f"Response content: {e.response.text}")
                    raise
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
