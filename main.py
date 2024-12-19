import os
import logging
import random
from dotenv import load_dotenv
from typing import Optional, Dict
import asyncio
import re
from datetime import datetime
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin.auth import verify_id_token

from fastapi import FastAPI, Request, Form, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from websocket_manager import websocket_manager
from sqlalchemy import Column, Integer, String, JSON, DateTime, func
from sqlalchemy.orm import Session

# Load environment variables
load_dotenv()

# Import database configuration
from database import SessionLocal, engine, init_db

# Import your existing card generation modules
from generator.card_generator import generate_card
from generator.card_data_utils import validate_card_data, standardize_card_data
from generator.image_utils import generate_card_image
from models import Base, CardModel, UnclaimedCard, CreditTransaction
from user_models import UserModel

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    filename=os.getenv('LOG_FILE')
)
logger = logging.getLogger(__name__)

# Image storage path
IMAGE_STORAGE_PATH = os.getenv('IMAGE_STORAGE_PATH', './generated_images/')
os.makedirs(IMAGE_STORAGE_PATH, exist_ok=True)

# Rate limiting configuration
MAX_CARDS_PER_DAY = int(os.getenv('MAX_CARDS_PER_DAY', 50))
MAX_GENERATIONS_PER_HOUR = int(os.getenv('MAX_GENERATIONS_PER_HOUR', 10))

# Initialize database
init_db()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application startup and shutdown events."""
    # Startup: Start the task manager
    await task_manager.start()
    yield
    # Shutdown: Stop the task manager
    await task_manager.stop()

# FastAPI App with lifespan
app = FastAPI(
    title="Magic Card Generator",
    lifespan=lifespan
)

# Setup static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize Firebase Admin SDK
try:
    # Try to get default app if already initialized
    default_app = firebase_admin.get_app()
    logger.info("Firebase Admin SDK already initialized")
except ValueError:
    # Initialize if not already done
    cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH')
    if not cred_path:
        raise ValueError("FIREBASE_SERVICE_ACCOUNT_PATH environment variable not set")
    if not os.path.exists(cred_path):
        raise FileNotFoundError(f"Firebase credentials file not found at: {cred_path}")
    
    try:
        cred = credentials.Certificate(cred_path)
        default_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {str(e)}")
        logger.error(f"Credentials path: {cred_path}")
        raise

# Template context dependency
async def get_template_context(request: Request):
    return {
        "request": request,
        "firebase_config": {
            "apiKey": os.getenv("FIREBASE_API_KEY"),
            "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
            "projectId": os.getenv("FIREBASE_PROJECT_ID"),
            "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
            "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
            "appId": os.getenv("FIREBASE_APP_ID"),
            "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID")
        }
    }

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    """
    Verify the Firebase JWT token and retrieve the current user.
    """
    try:
        authorization = request.headers.get("Authorization")
        logger.debug("Checking authorization header")
        
        if not authorization or not authorization.startswith("Bearer "):
            logger.debug("No valid Authorization header found")
            return None

        token = authorization.split(" ")[1]
        decoded_token = verify_id_token(token)
        user_id = decoded_token.get("uid")
        email = decoded_token.get("email")
        
        logger.debug("Token verification successful")
        
        if not user_id:
            logger.debug("No user_id found in token")
            return None
        
        user = db.query(UserModel).filter(UserModel.firebase_id == user_id).first()
        if not user:
            user = UserModel(firebase_id=user_id, email=email)
            db.add(user)
            db.commit()
            db.refresh(user)
        
        return user
    except Exception as e:
        import traceback
        logger.error(f"Error verifying Firebase token: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        logger.error("Token verification failed")
        return None

@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request, context: dict = Depends(get_template_context)):
    """Render the landing page."""
    return templates.TemplateResponse("landing.html", context)

@app.get("/auth", response_class=HTMLResponse)
async def auth(request: Request, context: dict = Depends(get_template_context)):
    """Render the authentication page."""
    return templates.TemplateResponse("auth.html", context)

@app.get("/packs", response_class=HTMLResponse)
async def packs_page(request: Request, context: dict = Depends(get_template_context)):
    """Render the pack purchase page."""
    return templates.TemplateResponse("packs.html", context)

@app.post("/admin/generate-card")
async def create_card(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a new card (admin only)."""
    if not current_user or not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    """Generate a new card with optional rarity."""
    # Extremely verbose logging
    logger.setLevel(logging.DEBUG)
    
    try:
        # Capture and log all request details
        logger.debug("Starting card generation process")
        logger.debug(f"Request method: {request.method}")
        logger.debug(f"Request headers: {dict(request.headers)}")
        
        # Attempt to get form data
        try:
            # Read the request body manually
            body = await request.body()
            logger.debug(f"Raw request body: {body}")
            
            # Parse the multipart form data manually
            content_type = request.headers.get('content-type', '')
            logger.debug(f"Content-Type: {content_type}")
            
            # Extract rarity from body
            rarity = None
            if b'name="rarity"' in body:
                # Simple extraction of rarity value
                rarity_match = re.search(rb'name="rarity"\r\n\r\n([^\r\n]+)', body)
                if rarity_match:
                    rarity = rarity_match.group(1).decode('utf-8').strip()
            
            logger.debug(f"Extracted rarity: {rarity}")
        except Exception as form_error:
            logger.error(f"Error parsing form data: {form_error}", exc_info=True)
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid form data: {str(form_error)}"
            )
        
        # Log rarity parameter details
        logger.debug(f"Rarity parameter type: {type(rarity)}")
        logger.debug(f"Rarity parameter value: {rarity}")
        
        # Validate rarity if provided
        if rarity and rarity not in ['Common', 'Uncommon', 'Rare', 'Mythic']:
            logger.warning(f"Invalid rarity provided: {rarity}. Defaulting to random.")
            rarity = None
        
        # Generate card data with comprehensive error tracking
        try:
            logger.debug("Attempting to generate card data")
            card_data = generate_card(rarity)
            logger.debug(f"Card data generated: {card_data}")
        except Exception as gen_error:
            logger.error("Card generation failed", exc_info=True)
            raise HTTPException(
                status_code=400, 
                detail=f"Card generation failed: {str(gen_error)}"
            )
        
        # Validate and standardize card data
        try:
            logger.debug("Validating card data")
            validated_card_data = validate_card_data(card_data)
            logger.debug(f"Validated card data: {validated_card_data}")
            
            logger.debug("Standardizing card data")
            standardized_card_data = standardize_card_data(validated_card_data)
            logger.debug(f"Standardized card data: {standardized_card_data}")
        except Exception as validation_error:
            logger.error("Card data validation failed", exc_info=True)
            raise HTTPException(
                status_code=400, 
                detail=f"Card data validation failed: {str(validation_error)}"
            )
        
        # Generate card image
        try:
            logger.debug("Generating card image")
            dalle_url, b2_url = generate_card_image(standardized_card_data)
            image_path = b2_url
            logger.debug(f"Image generated at path: {image_path}")
        except Exception as img_error:
            logger.error("Image generation failed", exc_info=True)
            raise HTTPException(
                status_code=400, 
                detail=f"Image generation failed: {str(img_error)}"
            )
        
        # Prepare set and card number
        set_name, set_number, card_number = get_next_set_name_and_number()
        logger.debug(f"Set details - Name: {set_name}, Number: {set_number}, Card Number: {card_number}")
        
        # Save to database
        try:
            logger.debug("Preparing to save card to database")
            db_card = UnclaimedCard(
                name=standardized_card_data.get('name', 'Unnamed Card'),
                card_data=standardized_card_data,
                image_path=image_path,
                rarity=standardized_card_data.get('rarity', 'Common'),
                set_name=set_name,
                card_number=f"{set_number:03d}"
            )
            db.add(db_card)
            
            db.commit()
            db.refresh(db_card)
            
            logger.info(f"Card generated successfully: {db_card.name}")
            
            # Prepare response
            response_content = {
                "id": db_card.id,
                "name": db_card.name,
                "rarity": db_card.rarity,
                "set_name": db_card.set_name,
                "card_number": db_card.card_number,
                "image_path": db_card.image_path
            }
            logger.debug(f"Response content: {response_content}")
            
            return JSONResponse(
                status_code=200, 
                content=response_content
            )
        
        except Exception as db_error:
            db.rollback()
            logger.error("Database error during card generation", exc_info=True)
            raise HTTPException(
                status_code=500, 
                detail="Error saving card to database"
            )
    
    except HTTPException as http_error:
        # Re-raise HTTPException to preserve status code and detail
        logger.error(f"HTTP Exception: {http_error.detail}", exc_info=True)
        raise
    except Exception as e:
        logger.error("Unexpected error in card generation route", exc_info=True)
        raise HTTPException(
            status_code=400, 
            detail=f"Unexpected error: {str(e)}"
        )
    finally:
        # Reset logging level
        logger.setLevel(logging.INFO)

def get_next_set_name_and_number() -> tuple:
    """Get the next set name, set number, and card number."""
    default_set_name = 'GEN'
    set_number = random.randint(1, 10)
    return default_set_name, set_number, random.randint(1, 999)

@app.get("/collection", response_class=HTMLResponse)
async def view_collection(
    request: Request,
    page: int = 1,
    per_page: int = 10,
    context: dict = Depends(get_template_context),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve and render paginated list of generated cards.
    
    Args:
        request (Request): The incoming request
        page (int, optional): Current page number. Defaults to 1.
        per_page (int, optional): Number of cards per page. Defaults to 10.
    
    Returns:
        HTMLResponse: Rendered template with card list
    """
    # Validate page number
    page = max(1, page)
    per_page = max(1, min(per_page, 50))  # Limit per page between 1 and 50
    
    # Get token from header or cookie
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        token = request.cookies.get("firebaseToken")
        if token:
            authorization = f"Bearer {token}"
        else:
            logger.debug("No valid token found in header or cookie")
            return RedirectResponse(url="/auth", status_code=303)

    try:
        # Verify token and get user
        token = authorization.split(" ")[1]
        decoded_token = verify_id_token(token)
        user_id = decoded_token.get("uid")
        
        if not user_id:
            logger.debug("No user_id in token")
            return RedirectResponse(url="/auth", status_code=303)
            
        # Get user from database
        user = db.query(UserModel).filter(UserModel.firebase_id == user_id).first()
        if not user:
            logger.debug(f"User {user_id} not found in database")
            return RedirectResponse(url="/auth", status_code=303)

        # Validate page number
        page = max(1, page)
        per_page = max(1, min(per_page, 50))  # Limit per page between 1 and 50

        # Calculate offset for pagination
        offset = (page - 1) * per_page
        
        try:
            # Query user's claimed cards
            total_cards = (
                db.query(CardModel)
                .filter(CardModel.user_id == user.firebase_id)
                .count()
            )
            total_pages = (total_cards + per_page - 1) // per_page
            
            # Fetch user's claimed cards
            user_cards = (
                db.query(CardModel)
                .filter(CardModel.user_id == user.firebase_id)
                .order_by(CardModel.created_at.desc())
                .offset(offset)
                .limit(per_page)
                .all()
            )
            logger.debug(f"Found {total_cards} cards for user {user.firebase_id}")
        except Exception as e:
            logger.error(f"Database query error: {str(e)}")
            logger.error(f"User ID: {user.firebase_id}")
            raise HTTPException(status_code=500, detail="Error accessing card collection")
        
        # Prepare card data for template
        card_list = []
        for card in user_cards:
            card_data = {
                'id': card.id,
                'name': card.name,
                'rarity': card.rarity,
                'set_name': card.set_name,
                'card_number': card.card_number,
                'created_at': card.created_at,
                'type': card.card_data.get('type', 'Unknown'),
                'manaCost': card.card_data.get('manaCost', ''),
                'text': card.card_data.get('text', ''),
                'flavorText': card.card_data.get('flavorText', ''),
                'powerToughness': card.card_data.get('powerToughness', ''),
                'images': [{'backblaze_url': card.image_path}] if card.image_path else [],
                'is_claimed': False,
            }
            card_list.append(card_data)
        
        # Update context with user and pagination data
        context.update({
            "cards": card_list,
            "current_page": page,
            "total_pages": total_pages,
            "per_page": per_page,
            "total_cards": total_cards,
            "user": user,  # Add user to context for template
            "firebase_config": context.get("firebase_config", {})  # Preserve firebase config
        })
        return templates.TemplateResponse("collection.html", context)
    
    except Exception as e:
        logger.error(f"Error retrieving user's cards: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving your card collection")

@app.post("/cards/{card_id}/claim")
async def claim_card(
    card_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Claim an unclaimed card."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Find the unclaimed card
    unclaimed_card = (
        db.query(UnclaimedCard)
        .filter(UnclaimedCard.id == card_id, UnclaimedCard.is_claimed == False)
        .first()
    )
    
    if not unclaimed_card:
        raise HTTPException(status_code=404, detail="Card not found or already claimed")
    
    try:
        # Create a new claimed card
        claimed_card = CardModel(
            name=unclaimed_card.name,
            card_data=unclaimed_card.card_data,
            image_path=unclaimed_card.image_path,
            rarity=unclaimed_card.rarity,
            set_name=unclaimed_card.set_name,
            card_number=unclaimed_card.card_number,
            user_id=current_user.firebase_id
        )
        db.add(claimed_card)
        
        # Mark the unclaimed card as claimed
        unclaimed_card.is_claimed = True
        unclaimed_card.claimed_by_user_id = current_user.firebase_id
        unclaimed_card.claimed_at = datetime.utcnow()
        
        db.commit()
        
        return JSONResponse(
            status_code=200,
            content={"message": "Card claimed successfully", "card_id": claimed_card.id}
        )
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error claiming card: {e}")
        raise HTTPException(status_code=500, detail="Error claiming card")

from task_manager import task_manager

# Pack opening cost
PACK_COST = 100  # Credits required to open a pack

# Pack opening cost
PACK_COST = 100  # Credits required to open a pack

@app.post("/credits/add")
async def add_credits(
    amount: int,
    user_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add credits to a user (admin only)."""
    if not current_user or not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        user = db.query(UserModel).filter(UserModel.firebase_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        await user.add_credits(
            db=db,
            amount=amount,
            description=f"Admin granted {amount} credits",
            transaction_type="admin_grant"
        )
        
        db.commit()
        
        return JSONResponse(
            status_code=200,
            content={
                "message": f"Added {amount} credits to user",
                "new_balance": user.credits
            }
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding credits: {e}")
        raise HTTPException(status_code=500, detail="Error adding credits")

@app.get("/credits/balance")
async def get_credit_balance(
    current_user: UserModel = Depends(get_current_user)
):
    """Get current user's credit balance."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    return JSONResponse(
        status_code=200,
        content={"credits": current_user.credits}
    )

@app.get("/credits/history")
async def get_credit_history(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 10
):
    """Get user's credit transaction history."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Calculate offset for pagination
        offset = (page - 1) * per_page
        
        # Get total transactions
        total_transactions = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.user_id == current_user.firebase_id)
            .count()
        )
        
        # Get paginated transactions
        transactions = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.user_id == current_user.firebase_id)
            .order_by(CreditTransaction.created_at.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "transactions": [
                    {
                        "amount": t.amount,
                        "description": t.description,
                        "type": t.transaction_type,
                        "created_at": t.created_at.isoformat()
                    }
                    for t in transactions
                ],
                "total": total_transactions,
                "page": page,
                "per_page": per_page
            }
        )
    except Exception as e:
        logger.error(f"Error getting credit history: {e}")
        raise HTTPException(status_code=500, detail="Error getting credit history")

@app.post("/packs/open")
async def open_pack(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit a pack opening task to the queue."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check if user has enough credits
    if not await current_user.has_enough_credits(PACK_COST):
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. Pack opening costs {PACK_COST} credits."
        )
    
    try:
        # Deduct credits first
        success = await current_user.spend_credits(
            db=db,
            amount=PACK_COST,
            description="Opened a booster pack",
            transaction_type="pack_opening"
        )
        
        if not success:
            raise HTTPException(
                status_code=402,
                detail="Failed to deduct credits"
            )
        
        # Submit pack opening task
        task_id = await task_manager.submit_task(
            queue_name="pack_opening",
            task_type="open_pack",
            user_id=current_user.firebase_id,
            data={}
        )
        
        # Commit credit transaction
        db.commit()
        
        return JSONResponse(
            status_code=202,
            content={
                "message": "Pack opening task submitted",
                "task_id": task_id
            }
        )
    
    except Exception as e:
        logger.error(f"Error submitting pack opening task: {e}")
        raise HTTPException(status_code=500, detail="Error submitting pack opening task")

@app.get("/packs/status/{task_id}")
async def get_pack_status(
    task_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Get the status of a pack opening task."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        task = await task_manager.get_task_status("pack_opening", task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.user_id != current_user.firebase_id:
            raise HTTPException(status_code=403, detail="Not authorized to view this task")
        
        response = {
            "status": task.status,
            "created_at": task.created_at.isoformat()
        }
        
        if task.status == "completed":
            response["result"] = task.result
        elif task.status == "failed":
            response["error"] = task.error
        
        return JSONResponse(status_code=200, content=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pack status: {e}")
        raise HTTPException(status_code=500, detail="Error getting pack status")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    try:
        await websocket.accept()
        
        # Wait for authentication message
        auth_data = await websocket.receive_json()
        if auth_data.get('type') != 'auth' or not auth_data.get('token'):
            await websocket.close(code=1008)  # Policy violation
            return
            
        # Verify token and get user
        try:
            decoded_token = verify_id_token(auth_data['token'])
            user_id = decoded_token.get("uid")
            
            if not user_id:
                await websocket.close(code=1008)  # Policy violation
                return
            
            # Connect to WebSocket manager
            await websocket_manager.connect(websocket, user_id)
            
            # Keep connection alive and handle any incoming messages
            while True:
                await websocket.receive_text()  # Keep connection alive
                
        except WebSocketDisconnect:
            websocket_manager.disconnect(websocket, user_id)
            
    except Exception as e:
        logger.error("WebSocket error")  # Don't log the actual error to avoid token exposure
        await websocket.close(code=1011)  # Internal error

# Add packs to protected routes
protectedRoutes = ['/generate', '/cards', '/packs']

# Optional: Add a health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
