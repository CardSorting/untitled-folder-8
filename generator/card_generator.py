import random
import json
import logging
import re
from typing import Dict, Any, Tuple
from tenacity import retry, stop_after_attempt, wait_random_exponential
from openai import OpenAIError
from openai_config import openai_client
from generator.card_data_utils import standardize_card_data, validate_card_data, get_rarity
from generator.prompt_utils import generate_card_prompt, create_dalle_prompt
from generator.image_utils import generate_card_image
from models import Rarity

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_SET_NAME = 'GEN'
CARD_NUMBER_LIMIT = 999

def get_next_set_name_and_number() -> Tuple[str, int, int]:
    """Get the next set name, set number, and card number."""
    set_number = random.randint(1, 10)
    return DEFAULT_SET_NAME, set_number, random.randint(1, CARD_NUMBER_LIMIT)

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(3))
def generate_card(rarity: str = None) -> Dict[str, Any]:
    """Generate a card with optional rarity."""
    # Validate rarity input
    if rarity and rarity not in [r.value for r in Rarity]:
        logger.warning(f"Invalid rarity provided: {rarity}. Defaulting to random.")
        rarity = None
    
    # Generate prompt with optional rarity
    try:
        prompt = generate_card_prompt(rarity)
        
        # Log that we're generating card data (not image)
        logger.info("Generating card data with GPT-4...")
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "system", "content": "You are a Magic: The Gathering card designer. Create balanced and thematic cards that follow the game's rules and mechanics. Keep abilities clear and concise, using established keyword mechanics where possible. Limit flavor text to one or two impactful sentences."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.7,
            )
            
            card_data_str = response.choices[0].message.content
            logger.debug(f"Raw card data from GPT: {card_data_str}")
        except Exception as openai_error:
            logger.error(f"OpenAI API error: {openai_error}")
            raise ValueError(f"Failed to generate card data: {str(openai_error)}")
        
        # Attempt to parse the card data
        try:
            card_data = json.loads(card_data_str)
        except json.JSONDecodeError:
            # If JSON parsing fails, try a more lenient parsing method
            card_data = parse_card_data_from_text(card_data_str)
        
        # Validate and standardize the card data
        try:
            validated_card_data = validate_card_data(card_data)
            card_data = standardize_card_data(validated_card_data)
        except Exception as validation_error:
            logger.warning(f"Card data validation failed: {validation_error}")
            raise ValueError(f"Card data validation failed: {str(validation_error)}")
        
        # Determine set and card details
        set_name, set_number, card_number = get_next_set_name_and_number()
        
        # Assign rarity if not specified
        if not rarity:
            card_rarity = get_rarity(set_number, card_number)
            card_data['rarity'] = card_rarity.value
        
        # Add set and card number information
        card_data['set_name'] = set_name
        card_data['set_number'] = set_number
        card_data['card_number'] = f"{card_number:03d}"
        
        # Ensure all required fields are present
        required_fields = [
            'name', 'manaCost', 'type', 'text', 
            'power', 'toughness', 'rarity', 
            'set_name', 'set_number', 'card_number'
        ]
        for field in required_fields:
            if field not in card_data:
                card_data[field] = get_default_value_for_field(field)
        
        try:
            # Log successful card data generation
            logger.info("Card data generated successfully")
            logger.debug(f"Final card data: {json.dumps(card_data, indent=2)}")
            
            # Try to generate the image
            dalle_url, b2_url = generate_card_image(card_data)
            
            # If we got here, both card data and image generation succeeded
            card_data['dalle_url'] = dalle_url
            card_data['b2_url'] = b2_url
            
            return card_data
            
        except Exception as img_error:
            logger.error(f"Error during image generation: {img_error}")
            raise ValueError(f"Image generation failed: {str(img_error)}")
    
    except Exception as e:
        logger.error(f"Unexpected error in card generation: {e}", exc_info=True)
        raise

def get_default_value_for_field(field: str) -> Any:
    """Provide default values for missing card fields."""
    default_values = {
        'name': 'Unnamed Card',
        'manaCost': '{1}',
        'type': 'Creature',
        'text': 'No special abilities.',
        'power': '1',
        'toughness': '1',
        'rarity': 'Common',
        'set_name': 'GEN',
        'set_number': 1,
        'card_number': '001'
    }
    return default_values.get(field, 'Unknown')

def parse_card_data_from_text(text: str) -> Dict[str, Any]:
    """
    Attempt to parse card data from a text response when JSON parsing fails.
    This method uses heuristics to extract card information.
    """
    logger.warning(f"Falling back to text parsing for card data: {text[:200]}...")
    
    # Simple heuristics to extract card data
    default_card = {
        "name": "Parsed Card",
        "manaCost": "{2}{R}",
        "type": "Creature",
        "text": "When this creature enters the battlefield, deal 2 damage to target creature or player.",
        "power": "2",
        "toughness": "2",
        "rarity": "Uncommon"
    }
    
    # Try to extract name from text
    name_match = re.search(r'"name"\s*:\s*"([^"]+)"', text)
    if name_match:
        default_card["name"] = name_match.group(1)
    
    return default_card

def generate_fallback_card(rarity: str = None) -> Dict[str, Any]:
    """
    Generate a fallback card when the primary generation method fails.
    Provides a more diverse set of fallback cards to prevent repetition.
    """
    fallback_cards = [
        {
            "name": "Resilient Survivor",
            "manaCost": "{1}{W}",
            "type": "Creature — Human Soldier",
            "text": "Whenever Resilient Survivor blocks, it gets +1/+1 until end of turn.",
            "power": "2",
            "toughness": "3",
            "rarity": rarity or Rarity.COMMON.value
        },
        {
            "name": "Temporal Anomaly",
            "manaCost": "{2}{U}",
            "type": "Instant",
            "text": "Return target creature to its owner's hand. Scry 2.",
            "rarity": rarity or Rarity.UNCOMMON.value
        },
        {
            "name": "Wildfire Elemental",
            "manaCost": "{3}{R}",
            "type": "Creature — Elemental",
            "text": "Haste. When Wildfire Elemental enters the battlefield, it deals 2 damage to each non-flying creature.",
            "power": "3",
            "toughness": "2",
            "rarity": rarity or Rarity.RARE.value
        }
    ]
    
    # Log the fallback card generation
    logger.warning(f"Generating fallback card with rarity: {rarity or 'unspecified'}")
    
    return random.choice(fallback_cards)
