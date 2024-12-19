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
from firebase_admin import credentials, auth

from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.orm import Session

# Load environment variables
load_dotenv()


# Import your existing card generation modules
from generator.card_generator import generate_card
from generator.card_data_utils import validate_card_data, standardize_card_data
from generator.image_utils import generate_card_image
from models import Base
from user_models import UserModel

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    filename=os.getenv('LOG_FILE')
)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./card_generator.db')
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Image storage path
IMAGE_STORAGE_PATH = os.getenv('IMAGE_STORAGE_PATH', './generated_images/')
os.makedirs(IMAGE_STORAGE_PATH, exist_ok=True)

# Rate limiting configuration
MAX_CARDS_PER_DAY = int(os.getenv('MAX_CARDS_PER_DAY', 50))
MAX_GENERATIONS_PER_HOUR = int(os.getenv('MAX_GENERATIONS_PER_HOUR', 10))

# Database Model for Card
class CardModel(Base):
    __tablename__ = "cards"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    card_data = Column(JSON)
    image_path = Column(String, nullable=True)
    rarity = Column(String)
    set_name = Column(String)
    card_number = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# FastAPI App
app = FastAPI(title="Magic Card Generator")


# Setup static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize Firebase Admin SDK
cred = credentials.Certificate(os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH'))
firebase_admin.initialize_app(cred)

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
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        return None

    try:
        token = authorization.split(" ")[1]
        decoded_token = auth.verify_id_token(token)
        
        user_id = decoded_token.get("uid")
        email = decoded_token.get("email")
        
        if not user_id:
            return None
        
        user = db.query(UserModel).filter(UserModel.firebase_id == user_id).first()
        if not user:
            user = UserModel(firebase_id=user_id, email=email)
            db.add(user)
            db.commit()
            db.refresh(user)
        
        return user
    except Exception as e:
        logger.error(f"Error verifying Firebase token: {e}")
        return None

@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request, context: dict = Depends(get_template_context)):
    """Render the landing page."""
    return templates.TemplateResponse("landing.html", context)

@app.get("/generate", response_class=HTMLResponse)
async def generate_page(request: Request, context: dict = Depends(get_template_context)):
    """Render the card generation page."""
    return templates.TemplateResponse("index.html", context)

@app.get("/auth", response_class=HTMLResponse)
async def auth(request: Request, context: dict = Depends(get_template_context)):
    """Render the authentication page."""
    return templates.TemplateResponse("auth.html", context)

@app.post("/generate-card")
async def create_card(
    request: Request,
    current_user: Optional[UserModel] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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
            db_card = CardModel(
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

@app.get("/cards", response_class=HTMLResponse)
async def list_cards(
    request: Request, 
    page: int = 1, 
    per_page: int = 10,
    context: dict = Depends(get_template_context)
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
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Calculate offset for pagination
        offset = (page - 1) * per_page
        
        # Query cards with pagination
        total_cards = db.query(CardModel).count()
        total_pages = (total_cards + per_page - 1) // per_page
        
        # Fetch paginated cards, ordered by creation date (most recent first)
        cards = (
            db.query(CardModel)
            .order_by(CardModel.created_at.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )
        
        # Prepare card data for template
        card_list = []
        for card in cards:
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
            }
            card_list.append(card_data)
        
        # Render template with pagination context
        context.update({
            "cards": card_list,
            "current_page": page,
            "total_pages": total_pages,
            "per_page": per_page,
            "total_cards": total_cards
        })
        return templates.TemplateResponse("cards_list.html", context)
    
    except Exception as e:
        logger.error(f"Error retrieving cards: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving card list")
    finally:
        # Always close the database session
        db.close()

# Optional: Add a health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
