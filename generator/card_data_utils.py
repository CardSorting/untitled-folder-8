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

def standardize_card_data(card_data: Dict[str, Any]) -> Dict[str, Any]:
    """Standardizes card data fields and ensures all required fields are present with length validation."""
    # Character limits for different fields
    LIMITS = {
        'name': 40,
        'abilities': 150,  # per ability
        'flavorText': 120,
        'type': 50
    }
    
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
    
    # Truncate fields to specified limits
    for field, limit in LIMITS.items():
        if field in card_data and card_data[field]:
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
        
        # Validate power and toughness for creatures
        if 'Creature' in card_data.get('type', ''):
            if not card_data.get('power'):
                card_data['power'] = '1'
            if not card_data.get('toughness'):
                card_data['toughness'] = '1'
        
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
