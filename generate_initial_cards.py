import logging
import time
import httpx
from tasks import generate_initial_cards_task
from database import SessionLocal
from models import UnclaimedCard

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Number of cards to generate for each rarity
INITIAL_CARDS = {
    'Common': 4,      # Just enough for one pack
    'Uncommon': 2,    # Test a couple uncommons
    'Rare': 1,        # One rare
    'Mythic': 1       # One mythic
}

def check_server():
    """Check if the FastAPI server is running."""
    try:
        response = httpx.get('http://localhost:8000/health')
        return response.status_code == 200
    except Exception:
        return False

def monitor_progress():
    """Monitor the progress of card generation by checking the database."""
    db = SessionLocal()
    try:
        while True:
            # Get current counts by rarity
            counts = {}
            total_cards = 0
            for rarity in INITIAL_CARDS.keys():
                count = db.query(UnclaimedCard).filter(UnclaimedCard.rarity == rarity).count()
                counts[rarity] = count
                total_cards += count
            
            # Log progress
            logger.info("Current progress:")
            for rarity, count in counts.items():
                target = INITIAL_CARDS[rarity]
                logger.info(f"{rarity}: {count}/{target} cards generated")
            
            # Check if we're done
            if total_cards >= sum(INITIAL_CARDS.values()):
                logger.info("All cards have been generated!")
                break
                
            # Wait before checking again
            time.sleep(5)
            
    finally:
        db.close()

def generate_initial_cards():
    """Generate initial set of cards using Celery tasks."""
    try:
        logger.info("Checking if server is running...")
        if not check_server():
            logger.error("FastAPI server is not running! Please start the server with:")
            logger.error("uvicorn main:app --reload")
            return
            
        logger.info("Server is running. Starting initial card generation...")
        
        # Submit the batch generation task
        generate_initial_cards_task.delay(INITIAL_CARDS)
        logger.info("Card generation tasks have been scheduled")
        
        # Monitor progress
        monitor_progress()
        
    except Exception as e:
        logger.error(f"Error during card generation: {str(e)}")
        raise

if __name__ == "__main__":
    generate_initial_cards()