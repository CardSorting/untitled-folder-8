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
from celery.result import AsyncResult

# Load environment variables
load_dotenv()

# Import database configuration
from database import SessionLocal, engine, init_db

# Import your existing card generation modules
from generator.card_generator import generate_card
from generator.card_data_utils import validate_card_data, standardize_card_data
from generator.image_utils import generate_card_image
from models import Base, CardModel, UnclaimedCard
from user_models import UserModel
from tasks import (
    process_pack_opening,
    get_credit_balance,
    claim_daily_credits,
    PACK_CONFIG,
    PACK_ERRORS,
    PackError
)
from credit_manager import credit_manager

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

# FastAPI App
app = FastAPI(title="Magic Card Generator")

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
    """Verify the Firebase JWT token and retrieve the current user."""
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
        logger.error(f"Error verifying Firebase token: {str(e)}")
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

@app.post("/packs/open")
async def open_pack(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit a pack opening task to Celery."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Check if user has enough credits in Redis
        current_credits = credit_manager.get_balance(current_user.firebase_id)
        if current_credits < PACK_CONFIG["cost"]:
            raise HTTPException(
                status_code=402,
                detail=PACK_ERRORS["insufficient_credits"]
            )
        
        # Submit pack opening task to Celery
        task = process_pack_opening.delay(current_user.firebase_id, {})
        
        return JSONResponse(
            status_code=202,
            content={
                "message": "Pack opening task submitted",
                "task_id": task.id
            }
        )
    
    except HTTPException:
        raise
    except PackError as e:
        logger.warning(f"Pack opening error for user {current_user.firebase_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error submitting pack opening task: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while opening the pack")

@app.get("/packs/status/{task_id}")
async def get_pack_status(
    task_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Get the status of a Celery pack opening task."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Get Celery task result
        task_result = AsyncResult(task_id)
        
        if not task_result.ready():
            status = "pending"
            result = None
            error = None
        else:
            if task_result.successful():
                status = "completed"
                result = task_result.get()
                error = None
            else:
                status = "failed"
                result = None
                error = str(task_result.result)
                # Map pack errors to user-friendly messages
                for err_key, err_msg in PACK_ERRORS.items():
                    if err_msg in error:
                        error = err_msg
                        break
        
        response = {
            "status": status,
            "created_at": task_result.date_done.isoformat() if task_result.date_done else None
        }
        
        if result:
            response["result"] = result
        if error:
            response["error"] = error
        
        return JSONResponse(status_code=200, content=response)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pack status: {e}")
        raise HTTPException(status_code=500, detail="Error getting pack status")

@app.post("/credits/start-balance-task")
async def start_balance_task(
    current_user: UserModel = Depends(get_current_user)
):
    """Start a Celery task to get credit balance."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        task = get_credit_balance.delay(current_user.firebase_id)
        return JSONResponse(
            status_code=202,
            content={
                "message": "Credit balance task started",
                "task_id": task.id
            }
        )
    except Exception as e:
        logger.error(f"Error starting credit balance task: {e}")
        raise HTTPException(status_code=500, detail="Error starting credit balance task")

@app.get("/credits/task-status/{task_id}")
async def get_balance_task_status(
    task_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Get the status of a credit balance task."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        task_result = AsyncResult(task_id)
        
        if not task_result.ready():
            status = "pending"
            result = None
            error = None
        else:
            if task_result.successful():
                status = "completed"
                result = task_result.get()
                error = None
            else:
                status = "failed"
                result = None
                error = str(task_result.result)
        
        return JSONResponse(
            status_code=200,
            content={
                "status": status,
                "result": result,
                "error": error
            }
        )
    except Exception as e:
        logger.error(f"Error getting balance task status: {e}")
        raise HTTPException(status_code=500, detail="Error getting task status")

@app.get("/credits/history")
async def get_credit_history(
    current_user: UserModel = Depends(get_current_user),
    page: int = 1,
    per_page: int = 10
):
    """Get user's credit transaction history from Redis."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        history = credit_manager.get_transaction_history(
            current_user.firebase_id,
            page=page,
            per_page=per_page
        )
        return JSONResponse(status_code=200, content=history)
    except Exception as e:
        logger.error(f"Error getting credit history: {e}")
        raise HTTPException(status_code=500, detail="Error getting credit history")

@app.get("/credits/can-claim")
async def can_claim_daily_credits(
    current_user: UserModel = Depends(get_current_user)
):
    """Check if user can claim daily credits."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        can_claim = credit_manager.can_claim_daily_credits(current_user.firebase_id)
        return JSONResponse(
            status_code=200,
            content={
                "can_claim": can_claim
            }
        )
    except Exception as e:
        logger.error(f"Error checking claim status: {e}")
        raise HTTPException(status_code=500, detail="Error checking claim status")

@app.post("/credits/claim-daily")
async def claim_daily_credits_endpoint(
    current_user: UserModel = Depends(get_current_user)
):
    """Claim daily credits."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        task = claim_daily_credits.delay(current_user.firebase_id)
        return JSONResponse(
            status_code=202,
            content={
                "message": "Daily credit claim task started",
                "task_id": task.id
            }
        )
    except Exception as e:
        logger.error(f"Error starting daily credit claim: {e}")
        raise HTTPException(status_code=500, detail="Error claiming daily credits")

@app.post("/credits/add")
async def add_credits(
    amount: int,
    user_id: str,
    current_user: UserModel = Depends(get_current_user)
):
    """Add credits to a user (admin only)."""
    if not current_user or not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        success = credit_manager.add_credits(
            user_id=user_id,
            amount=amount,
            description=f"Admin granted {amount} credits",
            transaction_type="admin_grant"
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Error adding credits")
        
        new_balance = credit_manager.get_balance(user_id)
        return JSONResponse(
            status_code=200,
            content={
                "message": f"Added {amount} credits to user",
                "new_balance": new_balance
            }
        )
    except Exception as e:
        logger.error(f"Error adding credits: {e}")
        raise HTTPException(status_code=500, detail="Error adding credits")

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time updates."""
    user_id = None
    try:
        await websocket.accept()
        
        # Wait for authentication message
        auth_data = await websocket.receive_json()
        if auth_data.get('type') != 'auth' or not auth_data.get('token'):
            await websocket.close(code=1008)  # Policy violation
            return
            
        # Verify token and get user
        decoded_token = verify_id_token(auth_data['token'])
        user_id = decoded_token.get("uid")
        
        if not user_id:
            await websocket.close(code=1008)  # Policy violation
            return
        
        # Connect to WebSocket manager
        await websocket_manager.connect(websocket, user_id)
        
        # Send initial credit balance
        balance = credit_manager.get_balance(user_id)
        await websocket.send_json({
            'type': 'credit_update',
            'credits': balance
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            message = await websocket.receive_json()
            if message.get('type') == 'ping':
                await websocket.send_json({'type': 'pong'})
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
        if user_id:
            websocket_manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.close(code=1011)  # Internal error
        except Exception:
            pass  # Ignore any errors during emergency close

# Add packs to protected routes
protectedRoutes = ['/generate', '/cards', '/packs']

# Optional: Add a health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    import logging
    
    # Configure uvicorn logging to be minimal
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    uvicorn.run(app, host="0.0.0.0", port=8000)
