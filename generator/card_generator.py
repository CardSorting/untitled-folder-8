import random
import json
import logging
import re
from typing import Dict, Any, Tuple
from openai import OpenAIError
from openai_config import openai_client
from generator.card_data_utils import standardize_card_data, validate_card_data, get_rarity
from generator.prompt_utils import generate_card_prompt
from generator.image_utils import generate_card_image
from card_models import Rarity

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

def parse_card_data_from_text(text: str) -> Dict[str, Any]:
    """Parse card data from text when JSON parsing fails."""
    logger.warning(f"Attempting to parse card data from text: {text[:200]}...")
    
    # Extract name if present
    name_match = re.search(r'"name"\s*:\s*"([^"]+)"', text)
    name = name_match.group(1) if name_match else None
    
    if not name:
        raise ValueError("Could not extract card name from response")
    
    # Extract other fields if possible
    mana_cost_match = re.search(r'"manaCost"\s*:\s*"([^"]+)"', text)
    type_match = re.search(r'"type"\s*:\s*"([^"]+)"', text)
    text_match = re.search(r'"text"\s*:\s*"([^"]+)"', text)
    
    return {
        "name": name,
        "manaCost": mana_cost_match.group(1) if mana_cost_match else "{2}",
        "type": type_match.group(1) if type_match else "Creature",
        "text": text_match.group(1) if text_match else "",
        "power": "2",
        "toughness": "2",
        "rarity": "Common"
    }

def generate_card(rarity: str = None, name: str = None) -> Dict[str, Any]:
    """Generate a card with optional rarity and name."""
    # Ensure random is properly seeded for this process
    random.seed()
    
    # Validate rarity input
    if rarity and rarity not in [r.value for r in Rarity]:
        logger.warning(f"Invalid rarity provided: {rarity}. Defaulting to random.")
        rarity = None
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            # Generate card data
            logger.info(f"\n=== Generating card (Attempt {attempt + 1}/{max_attempts}) ===")
            prompt = generate_card_prompt(rarity)
            
            # Generate with GPT-4
            response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a Magic: The Gathering card designer. Create balanced and thematic cards that follow the game's rules and mechanics. Keep abilities clear and concise, using established keyword mechanics where possible. Limit flavor text to one or two impactful sentences."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.7,
            )
            
            # Parse response
            card_data_str = response.choices[0].message.content
            try:
                card_data = json.loads(card_data_str)
            except json.JSONDecodeError:
                card_data = parse_card_data_from_text(card_data_str)
            
            # Validate and standardize
            card_data = standardize_card_data(validate_card_data(card_data))
            
            # Add card details
            set_name, set_number, card_number = get_next_set_name_and_number()
            card_data.update({
                'set_name': set_name,
                'set_number': set_number,
                'card_number': f"{card_number:03d}",
                'rarity': rarity or get_rarity(set_number, card_number).value
            })
            
            # Ensure required fields
            for field in ['name', 'manaCost', 'type', 'text', 'power', 'toughness']:
                if field not in card_data:
                    card_data[field] = get_default_value_for_field(field)
            
            # Extract color from mana cost if needed
            if 'color' not in card_data and 'manaCost' in card_data:
                colors = []
                if '{W}' in card_data['manaCost']: colors.append('White')
                if '{U}' in card_data['manaCost']: colors.append('Blue')
                if '{B}' in card_data['manaCost']: colors.append('Black')
                if '{R}' in card_data['manaCost']: colors.append('Red')
                if '{G}' in card_data['manaCost']: colors.append('Green')
                if colors:
                    card_data['color'] = colors
            
            # Try to generate image
            try:
                dalle_url, b2_url = generate_card_image(card_data)
                image_success = True
            except ValueError as img_error:
                logger.error(f"Image generation failed: {img_error}")
                dalle_url = None
                b2_url = None
                image_success = False
            
            # Return final card data
            return {
                'id': card_data.get('id'),
                'name': card_data['name'],
                'manaCost': card_data['manaCost'],
                'type': card_data['type'],
                'text': card_data['text'],
                'rarity': card_data['rarity'],
                'power': card_data.get('power'),
                'toughness': card_data.get('toughness'),
                'set_name': card_data['set_name'],
                'card_number': card_data['card_number'],
                'dalle_url': dalle_url,
                'b2_url': b2_url,
                'image_path': b2_url
            }
            
        except Exception as e:
            logger.error(f"Card generation attempt {attempt + 1} failed: {e}")
            if attempt < max_attempts - 1:
                continue
            raise ValueError(f"Card generation failed after {max_attempts} attempts: {str(e)}")
    
    raise ValueError("Card generation failed for unknown reason")

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
