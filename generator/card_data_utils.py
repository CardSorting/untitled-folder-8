import random
import json
import logging
from typing import Dict, Any, List
from card_models import Rarity

# Logging configuration
logger = logging.getLogger(__name__)

BASE_RARITY_PROBABILITIES = {
    Rarity.COMMON: 0.714,     # ~10/14 cards in a booster
    Rarity.UNCOMMON: 0.214,   # ~3/14 cards in a booster
    Rarity.RARE: 0.062,       # ~7/8 of rare slots (7/8 * 1/14)
    Rarity.MYTHIC: 0.01       # ~1/8 of rare slots (1/8 * 1/14)
}

def extract_colors_from_mana_cost(mana_cost: str) -> List[str]:
    """Extract colors from a mana cost string."""
    color_map = {
        'W': 'White',
        'U': 'Blue',
        'B': 'Black',
        'R': 'Red',
        'G': 'Green'
    }
    colors = []
    for char in mana_cost:
        if char in color_map:
            colors.append(color_map[char])
    return list(dict.fromkeys(colors))  # Remove duplicates while preserving order

def standardize_card_data(card_data: Dict[str, Any]) -> Dict[str, Any]:
    """Standardizes card data fields and ensures all required fields are present with length validation."""
    # Character limits for different fields
    LIMITS = {
        'name': 40,
        'abilities': 150,  # per ability
        'flavorText': 120,
        'type': 50
    }
    
    # Extract colors from mana cost if color isn't explicitly set
    if 'color' not in card_data and 'manaCost' in card_data:
        card_data['color'] = extract_colors_from_mana_cost(card_data['manaCost'])
    
    mapping = {
        'Name': 'name',
        'ManaCost': 'manaCost',
        'Type': 'type',
        'Color': 'color',
        'Abilities': 'text',  # Changed from 'abilities' to match card generation
        'FlavorText': 'flavorText',
        'Rarity': 'rarity',
        'PowerToughness': 'powerToughness',
        'Power': 'power',
        'Toughness': 'toughness'
    }

    # Transfer uppercase values to lowercase fields if present
    for old_key, new_key in mapping.items():
        if old_key in card_data:
            card_data[new_key] = card_data.pop(old_key)
    
    # Handle text field that might be a list of ability objects
    if 'text' in card_data and isinstance(card_data['text'], list):
        # Convert list of ability objects to string
        text_parts = []
        for ability in card_data['text']:
            if isinstance(ability, dict) and 'Text' in ability:
                text_parts.append(ability['Text'])
        card_data['text'] = '\n'.join(text_parts) if text_parts else ''
    
    # Truncate fields to specified limits
    for field, limit in LIMITS.items():
        if field in card_data and card_data[field]:
            if isinstance(card_data[field], str):  # Only truncate string fields
                card_data[field] = card_data[field][:limit]
    
    # Ensure required fields have default values
    defaults = {
        'name': 'Unnamed Card',
        'manaCost': '{1}',
        'type': 'Creature',
        'text': '',
        'power': '1',
        'toughness': '1',
        'rarity': Rarity.COMMON.value
    }
    
    for key, default_value in defaults.items():
        if key not in card_data or not card_data[key]:
            card_data[key] = default_value
    
    return card_data

def validate_card_data(card_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the generated card data meets requirements and length limits."""
    try:
        # Validate name
        if not card_data.get('name') or len(card_data['name']) > 40:
            card_data['name'] = 'Unnamed Card'
        
        # Validate mana cost (simple validation)
        if not card_data.get('manaCost'):
            card_data['manaCost'] = '{1}'
        
        # Validate type
        if not card_data.get('type'):
            card_data['type'] = 'Creature'
        
        # Extract creature types
        creature_types = []
        if 'type' in card_data:
            type_parts = card_data['type'].split('—')
            if len(type_parts) > 1:
                creature_types = [t.strip() for t in type_parts[1].split()]
        
        # Validate power and toughness for creatures
        if 'Creature' in card_data.get('type', ''):
            # Default power/toughness based on creature type
            default_power = '2'
            default_toughness = '2'
            
            # Adjust based on creature type
            if any(t in ['Rat', 'Bird', 'Cat'] for t in creature_types):
                default_power = '1'
                default_toughness = '1'
            elif any(t in ['Dragon', 'Demon', 'Angel'] for t in creature_types):
                default_power = '4'
                default_toughness = '4'
            elif any(t in ['Giant', 'Wurm'] for t in creature_types):
                default_power = '5'
                default_toughness = '5'
            
            if not card_data.get('power'):
                card_data['power'] = default_power
            if not card_data.get('toughness'):
                card_data['toughness'] = default_toughness
            
            # Ensure text field reflects creature identity
            if not card_data.get('text'):
                # Generate basic ability based on creature type
                abilities = []
                if any(t in ['Dragon', 'Angel', 'Bird'] for t in creature_types):
                    abilities.append('Flying')
                if any(t in ['Rat', 'Cat'] for t in creature_types):
                    abilities.append('Deathtouch')
                if any(t in ['Giant', 'Wurm'] for t in creature_types):
                    abilities.append('Trample')
                
                card_data['text'] = ' '.join(abilities) if abilities else ''
        
        # Validate rarity
        if not card_data.get('rarity'):
            card_data['rarity'] = Rarity.COMMON.value
        
        return card_data
    except Exception as e:
        logger.error(f"Card data validation error: {e}")
        return card_data

def get_rarity(set_number: int, card_number: int) -> Rarity:
    """
    Determine card rarity based on set and card number.
    
    Args:
        set_number (int): The set number
        card_number (int): The card number within the set
    
    Returns:
        Rarity: Determined rarity for the card
    """
    # Use the rarity determination method from the Rarity enum
    return Rarity.get_rarity(set_number, card_number)
