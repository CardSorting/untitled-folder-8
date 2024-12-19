from enum import Enum, auto

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
