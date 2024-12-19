from enum import Enum
from typing import Optional, Dict, Any

class Rarity(Enum):
    """
    Enum representing Magic: The Gathering card rarities.
    Each rarity has an associated probability and value.
    """
    COMMON = "Common"
    UNCOMMON = "Uncommon"
    RARE = "Rare"
    MYTHIC = "Mythic"

    @classmethod
    def get_rarity(cls, set_number: int, card_number: int) -> 'Rarity':
        """
        Determine card rarity based on set and card number.
        
        Args:
            set_number (int): The set number
            card_number (int): The card number within the set
        
        Returns:
            Rarity: Determined rarity for the card
        """
        # Simple deterministic rarity generation algorithm
        if card_number % 8 == 0:
            return cls.MYTHIC
        elif card_number % 3 == 0:
            return cls.RARE
        elif card_number % 2 == 0:
            return cls.UNCOMMON
        else:
            return cls.COMMON

class Card:
    """
    Class representing a generated Magic: The Gathering card.
    """
    def __init__(
        self,
        name: str,
        mana_cost: str,
        card_type: str,
        text: str,
        rarity: str,
        power: Optional[str] = None,
        toughness: Optional[str] = None,
        set_name: str = "GEN",
        set_number: int = 1,
        card_number: str = "001",
        dalle_url: Optional[str] = None,
        b2_url: Optional[str] = None
    ):
        self.name = name
        self.mana_cost = mana_cost
        self.type = card_type
        self.text = text
        self.rarity = rarity
        self.power = power
        self.toughness = toughness
        self.set_name = set_name
        self.set_number = set_number
        self.card_number = card_number
        self.dalle_url = dalle_url
        self.b2_url = b2_url

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Card':
        """
        Create a Card instance from a dictionary of card data.
        
        Args:
            data (Dict[str, Any]): Dictionary containing card data from generator
        
        Returns:
            Card: New Card instance with the provided data
        """
        return cls(
            name=data.get('name', 'Unnamed Card'),
            mana_cost=data.get('manaCost', '{1}'),
            card_type=data.get('type', 'Creature'),
            text=data.get('text', 'No special abilities.'),
            rarity=data.get('rarity', 'Common'),
            power=data.get('power'),
            toughness=data.get('toughness'),
            set_name=data.get('set_name', 'GEN'),
            set_number=data.get('set_number', 1),
            card_number=data.get('card_number', '001'),
            dalle_url=data.get('dalle_url'),
            b2_url=data.get('b2_url')
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the Card instance to a dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the card
        """
        data = {
            'name': self.name,
            'manaCost': self.mana_cost,
            'type': self.type,
            'text': self.text,
            'rarity': self.rarity,
            'set_name': self.set_name,
            'set_number': self.set_number,
            'card_number': self.card_number
        }
        
        # Add optional fields if they exist
        if self.power is not None:
            data['power'] = self.power
        if self.toughness is not None:
            data['toughness'] = self.toughness
        if self.dalle_url is not None:
            data['dalle_url'] = self.dalle_url
        if self.b2_url is not None:
            data['b2_url'] = self.b2_url
            
        return data

    def __str__(self) -> str:
        """String representation of the card."""
        card_str = f"{self.name} {self.mana_cost}\n"
        card_str += f"{self.type}\n"
        card_str += f"{self.text}\n"
        if self.power is not None and self.toughness is not None:
            card_str += f"{self.power}/{self.toughness}\n"
        card_str += f"{self.rarity}"
        return card_str
