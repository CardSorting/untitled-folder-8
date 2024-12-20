import random
from typing import Dict, Any, List, Union
from card_models import Rarity

# Constants
DEFAULT_SET_NAME = 'GEN'
CARD_NUMBER_LIMIT = 999

# Color combinations
MONO_COLORS = ['White', 'Blue', 'Black', 'Red', 'Green']
GUILD_COLORS = [
    ('White', 'Blue'), ('Blue', 'Black'), ('Black', 'Red'), ('Red', 'Green'),
    ('Green', 'White'), ('White', 'Black'), ('Blue', 'Red'), ('Black', 'Green'),
    ('Red', 'White'), ('Green', 'Blue')
]
SHARD_COLORS = [
    ('White', 'Blue', 'Black'), ('Blue', 'Black', 'Red'), ('Black', 'Red', 'Green'),
    ('Red', 'Green', 'White'), ('Green', 'White', 'Blue')
]

# Common MTG themes by color
COLOR_THEMES = {
    'White': {
        'creatures': ['Angel', 'Knight', 'Soldier', 'Cleric', 'Bird', 'Cat', 'Unicorn', 'Griffin', 'Pegasus', 'Human'],
        'keywords': ['Vigilance', 'Protection', 'Lifelink', 'First Strike', 'Flying', 'Exile', 'Shield', 'Unity', 'Divine', 'Order']
    },
    'Blue': {
        'creatures': ['Wizard', 'Merfolk', 'Sphinx', 'Drake', 'Illusion', 'Serpent', 'Leviathan', 'Djinn', 'Shapeshifter', 'Elemental'],
        'keywords': ['Flying', 'Scry', 'Counter', 'Bounce', 'Draw', 'Control', 'Knowledge', 'Mind', 'Illusion', 'Manipulation']
    },
    'Black': {
        'creatures': ['Zombie', 'Vampire', 'Demon', 'Horror', 'Skeleton', 'Wraith', 'Shade', 'Specter', 'Rat', 'Nightmare'],
        'keywords': ['Deathtouch', 'Lifelink', 'Sacrifice', 'Destroy', 'Drain', 'Corrupt', 'Death', 'Decay', 'Dark', 'Torment']
    },
    'Red': {
        'creatures': ['Dragon', 'Goblin', 'Warrior', 'Phoenix', 'Elemental', 'Ogre', 'Devil', 'Giant', 'Shaman', 'Berserker'],
        'keywords': ['Haste', 'First Strike', 'Direct Damage', 'Trample', 'Fury', 'Rage', 'Burn', 'Chaos', 'Lightning', 'Fire']
    },
    'Green': {
        'creatures': ['Beast', 'Elf', 'Druid', 'Wurm', 'Hydra', 'Treefolk', 'Spider', 'Wolf', 'Bear', 'Dinosaur'],
        'keywords': ['Trample', 'Reach', 'Fight', 'Growth', 'Ramp', 'Natural', 'Wild', 'Primal', 'Forest', 'Strength']
    }
}

# Card type weights by rarity
TYPE_WEIGHTS = {
    Rarity.COMMON: {
        'Creature': 0.6,
        'Instant': 0.2,
        'Sorcery': 0.15,
        'Enchantment': 0.05
    },
    Rarity.UNCOMMON: {
        'Creature': 0.45,
        'Instant': 0.2,
        'Sorcery': 0.15,
        'Enchantment': 0.1,
        'Artifact': 0.1
    },
    Rarity.RARE: {
        'Creature': 0.35,
        'Instant': 0.15,
        'Sorcery': 0.15,
        'Enchantment': 0.15,
        'Artifact': 0.15,
        'Legendary Creature': 0.05
    },
    Rarity.MYTHIC: {
        'Legendary Creature': 0.3,
        'Planeswalker': 0.2,
        'Creature': 0.2,
        'Artifact': 0.15,
        'Enchantment': 0.15
    }
}

# Color weights by rarity
COLOR_WEIGHTS = {
    Rarity.COMMON: {'mono': 1.0},
    Rarity.UNCOMMON: {'mono': 0.8, 'guild': 0.2},
    Rarity.RARE: {'mono': 0.6, 'guild': 0.3, 'shard': 0.1},
    Rarity.MYTHIC: {'mono': 0.4, 'guild': 0.4, 'shard': 0.2}
}

def get_color_combination(rarity: Rarity) -> List[str]:
    """Get a color combination based on rarity weights."""
    weights = COLOR_WEIGHTS[rarity]
    combo_type = random.choices(
        list(weights.keys()),
        weights=list(weights.values())
    )[0]
    
    if combo_type == 'mono':
        return [random.choice(MONO_COLORS)]
    elif combo_type == 'guild':
        return list(random.choice(GUILD_COLORS))
    else:  # shard
        return list(random.choice(SHARD_COLORS))

def get_card_type(rarity: Rarity) -> str:
    """Get a card type based on rarity weights."""
    weights = TYPE_WEIGHTS[rarity]
    return random.choices(
        list(weights.keys()),
        weights=list(weights.values())
    )[0]

def get_themed_elements(colors: List[str]) -> Dict[str, Any]:
    """Get themed elements based on card colors."""
    creatures = []
    keywords = []
    
    # Gather themes from each color
    for color in colors:
        color_creatures = COLOR_THEMES[color]['creatures']
        color_keywords = COLOR_THEMES[color]['keywords']
        
        # Add 2-3 random creatures and keywords from each color
        creatures.extend(random.sample(color_creatures, min(random.randint(2, 3), len(color_creatures))))
        keywords.extend(random.sample(color_keywords, min(random.randint(2, 3), len(color_keywords))))
    
    # Remove duplicates while preserving order
    creatures = list(dict.fromkeys(creatures))
    keywords = list(dict.fromkeys(keywords))
    
    return {
        'creatures': creatures,
        'keywords': keywords,
        'colors': colors
    }

def generate_card_prompt(rarity: str = None, name: str = None) -> str:
    """Generate the GPT prompt for creating the card."""
    if not rarity:
        rarity_options = ', '.join([r.value for r in Rarity])
        rarity_prompt = f"Choose from: {rarity_options}"
    else:
        rarity_prompt = rarity
        rarity_enum = Rarity[rarity.upper().replace(' ', '_')]
    
    # Get card type and color combination if rarity is specified
    card_type = get_card_type(rarity_enum) if rarity else "any appropriate type"
    colors = get_color_combination(rarity_enum) if rarity else [random.choice(MONO_COLORS)]
    color_str = '/'.join(colors)
    
    # Get themed elements based on colors
    themes = get_themed_elements(colors)
    
    # Simple mana cost guidance
    mana_cost_guidance = ""
    if rarity:
        color_symbols = ''.join(f"{{{c[0]}}}" for c in colors)  # First letter of each color
        mana_cost_guidance = f"Use {' and '.join(colors)} mana symbols with optional generic mana. "
        mana_cost_guidance += f"Example: {'{2}' + color_symbols} for a 4-cost card."
    
    # Build the prompt with emphasis on using the provided name
    prompt = (
        f"Design a cohesive Magic: The Gathering card named '{name}':\n"
        f"- Name: {name}\n"
        f"- ManaCost: {mana_cost_guidance if mana_cost_guidance else 'Balanced mana cost with curly braces {X}.'}\n"
        f"- Type: {card_type}\n"
        f"- Color: {color_str}\n"
        f"- Abilities: Create abilities that reflect the name and theme:\n"
        "  * Each ability should relate to the card's name\n"
        "  * Keep abilities under 150 characters and use established mechanics\n"
        "- PowerToughness: Stats that fit the theme.\n"
        "- FlavorText: One sentence (max 120 chars) that captures the card's essence.\n"
        f"- Rarity: {rarity_prompt}\n"
        "Return a JSON object with these fields. Ensure every aspect of the card reinforces its identity based on the name."
    ) if name else (
        f"Design a cohesive Magic: The Gathering card centered around a {color_str} theme:\n"
        f"- Name: Create a thematic name (max 40 chars).\n"
        f"- ManaCost: {mana_cost_guidance if mana_cost_guidance else 'Balanced mana cost with curly braces {X}.'}\n"
        f"- Type: {card_type}\n"
        f"- Color: {color_str}\n"
        f"- Abilities: Create thematic abilities:\n"
        "  * Each ability should relate to the card's identity\n"
        "  * Keep abilities under 150 characters and use established mechanics\n"
        "- PowerToughness: Stats that fit the theme.\n"
        "- FlavorText: One sentence (max 120 chars) that captures the card's essence.\n"
        f"- Rarity: {rarity_prompt}\n"
        "Return a JSON object with these fields. Ensure every aspect of the card is thematically cohesive."
    )
    
    return prompt

def ability_to_visual(text: Union[str, List[Dict[str, str]]]) -> List[str]:
    """Convert card abilities into visual descriptions."""
    visuals = []
    
    # Handle text that's a list of ability objects
    if isinstance(text, list):
        text_str = ' '.join(ability['Text'] for ability in text)
    else:
        text_str = text
    
    text_lower = text_str.lower()
    
    # Movement and stance
    if 'flying' in text_lower:
        visuals.append('with graceful wings')
    if 'first strike' in text_lower:
        visuals.append('in dynamic pose')
    if 'deathtouch' in text_lower:
        visuals.append('with sharp features')
    if 'trample' in text_lower:
        visuals.append('with strong build')
    if 'vigilance' in text_lower:
        visuals.append('in ready stance')
    if 'haste' in text_lower:
        visuals.append('in swift motion')
    
    # Energy and aura
    if any(x in text_lower for x in ['destroy', 'damage']):
        visuals.append('with intense aura')
    if 'draw' in text_lower:
        visuals.append('with bright aura')
    if any(x in text_lower for x in ['heal', 'life']):
        visuals.append('with soft glow')
    if 'counter' in text_lower:
        visuals.append('with shimmering aura')
    if 'exile' in text_lower:
        visuals.append('with bright glow')
    if any(x in text_lower for x in ['dark', 'black']):
        visuals.append('with deep shadows')
    if 'scry' in text_lower:
        visuals.append('with glowing eyes')
    
    # State changes
    if 'transform' in text_lower:
        visuals.append('mid-transformation')
    if 'phase' in text_lower:
        visuals.append('partially transparent')
    
    return visuals

def extract_themes_from_name(name: str) -> List[str]:
    """Extract thematic elements from card name."""
    themes = []
    name_lower = name.lower()
    
    # Emotional/personality themes
    if any(word in name_lower for word in ['dreaded', 'dread', 'horror', 'terror', 'nightmare']):
        themes.append("terrifying")
        themes.append("inspiring fear")
        themes.append("with an aura of dread")
    if any(word in name_lower for word in ['ancient', 'elder', 'old', 'eternal']):
        themes.append("ancient")
        themes.append("weathered by time")
        themes.append("with archaic markings")
    if any(word in name_lower for word in ['primal', 'wild', 'savage', 'feral']):
        themes.append("primal")
        themes.append("untamed")
        themes.append("with raw, natural power")
    if any(word in name_lower for word in ['noble', 'royal', 'lord', 'sovereign']):
        themes.append("noble")
        themes.append("regal bearing")
        themes.append("with majestic presence")
    
    # Physical characteristics
    if any(word in name_lower for word in ['giant', 'colossal', 'titan', 'massive']):
        themes.append("enormous")
        themes.append("towering")
        themes.append("dominating the scene")
    if any(word in name_lower for word in ['swift', 'quick', 'rapid', 'nimble']):
        themes.append("agile")
        themes.append("in swift motion")
        themes.append("with fluid movement")
    if any(word in name_lower for word in ['shadow', 'dark', 'night', 'void', 'black']):
        themes.append("shrouded in darkness")
        themes.append("with deep shadows")
        themes.append("emanating dark energy")
    
    # Combat and power themes
    if any(word in name_lower for word in ['warrior', 'fighter', 'slayer', 'knight']):
        themes.append("battle-ready")
        themes.append("in combat stance")
    if any(word in name_lower for word in ['mage', 'wizard', 'sorcerer', 'mystic']):
        themes.append("channeling magical energy")
        themes.append("surrounded by arcane symbols")
    if any(word in name_lower for word in ['demon', 'devil', 'fiend', 'hell']):
        themes.append("with demonic features")
        themes.append("radiating malevolent energy")
    
    return themes

def create_dalle_prompt(card_data: Dict[str, Any]) -> str:
    """Create a highly detailed DALL-E prompt that strongly adheres to the card's identity."""
    # Extract themes from name without using the name itself
    name_themes = extract_themes_from_name(card_data.get('name', ''))
    card_type = card_data.get('type', '')
    color = card_data.get('color', '')
    text = card_data.get('text', '')
    power = card_data.get('power', '')
    toughness = card_data.get('toughness', '')
    rarity = card_data.get('rarity', '')
    color_str = '/'.join(color) if isinstance(color, list) else color
    
    # Get visual descriptions from abilities
    ability_visuals = ability_to_visual(text)
    
    # Extract creature types
    creature_types = []
    if 'type' in card_data:
        type_parts = card_data['type'].split('—')
        if len(type_parts) > 1:
            creature_types = [t.strip() for t in type_parts[1].split()]
    
    # Get color-based traits
    color_traits = {
        'White': 'glowing with bright light',
        'Blue': 'with mystical aura',
        'Black': 'with shadowy presence',
        'Red': 'with fiery energy',
        'Green': 'with natural strength'
    }
    
    color_visuals = []
    if isinstance(color, list):
        for c in color:
            if c in color_traits:
                color_visuals.append(color_traits[c])
    elif color in color_traits:
        color_visuals.append(color_traits[color])
    
    # Build physical description
    physical_desc = ""
    if power and toughness:
        if int(power) > int(toughness):
            physical_desc = "powerful and aggressive physique"
        elif int(power) < int(toughness):
            physical_desc = "sturdy and resilient form"
        else:
            physical_desc = "well-balanced physical form"
    
    # Get rarity-based style
    rarity_style = {
        'Common': 'practical yet effective',
        'Uncommon': 'distinctive and specialized',
        'Rare': 'elaborate and powerful',
        'Mythic Rare': 'masterful and awe-inspiring'
    }.get(rarity, 'distinctive')
    
    if 'Creature' in card_type:
        # Get creature type details
        creature_description = ' '.join(creature_types) if creature_types else card_type
        
        # Build detailed creature description
        creature_details = []
        
        # Add size and power description
        if power and toughness:
            if int(power) >= 6:
                creature_details.append("massive")
            elif int(power) >= 4:
                creature_details.append("powerful")
            if int(toughness) >= 6:
                creature_details.append("heavily armored")
            elif int(toughness) >= 4:
                creature_details.append("well-protected")
        
        # Add color-specific details
        if isinstance(color, list):
            for c in color:
                if c == 'White':
                    creature_details.append("radiating divine light")
                elif c == 'Blue':
                    creature_details.append("surrounded by arcane energy")
                elif c == 'Black':
                    creature_details.append("wreathed in dark shadows")
                elif c == 'Red':
                    creature_details.append("emanating fierce power")
                elif c == 'Green':
                    creature_details.append("pulsing with primal energy")
        
        # Add creature type specific details
        for ctype in creature_types:
            if ctype in ['Dragon', 'Angel']:
                creature_details.append("with majestic wings spread wide")
            elif ctype in ['Demon', 'Horror']:
                creature_details.append("with twisted, nightmarish features")
            elif ctype in ['Warrior', 'Knight']:
                creature_details.append("in ornate battle armor")
            elif ctype in ['Wizard', 'Shaman']:
                creature_details.append("wielding mystical energies")
            elif ctype == 'Rat':
                creature_details.append("with sharp fangs and glowing eyes")
            elif ctype == 'Giant':
                creature_details.append("towering and muscular")
        
        # Add ability-based details
        if ability_visuals:
            creature_details.extend(ability_visuals[:2])
        
        # Add name-derived themes
        creature_details.extend(name_themes)
        
        # Combine all details, removing duplicates while preserving order
        all_details = []
        seen = set()
        for detail in creature_details:
            if detail.lower() not in seen:
                all_details.append(detail)
                seen.add(detail.lower())
        
        details_str = ', '.join(filter(None, all_details))
        
        # Build final prompt with specific creature focus
        return f"Detailed fantasy concept art of a {creature_description.lower()}, {details_str}, dramatic lighting, intricate details, cinematic composition, professional quality. White background."
    else:
        # Handle non-creature cards with detailed descriptions
        spell_details = []
        
        # Add color-specific magical effects
        if isinstance(color, list):
            for c in color:
                if c == 'White':
                    spell_details.append("radiating pure white energy")
                elif c == 'Blue':
                    spell_details.append("swirling with mystical blue mist")
                elif c == 'Black':
                    spell_details.append("emanating dark tendrils of power")
                elif c == 'Red':
                    spell_details.append("crackling with intense red flames")
                elif c == 'Green':
                    spell_details.append("pulsing with vibrant natural energy")
        
        # Add type-specific details
        if 'Enchantment' in card_type:
            base_desc = "mystical crystalline formation"
            spell_details.append("floating in mid-air")
            spell_details.append("with ethereal wisps of energy")
        elif 'Artifact' in card_type:
            base_desc = "intricate magical artifact"
            spell_details.append("with ornate metalwork")
            spell_details.append("with glowing runes etched into its surface")
        elif 'Instant' in card_type:
            base_desc = "powerful magical sigil"
            spell_details.append("with explosive energy")
            spell_details.append("surrounded by arcane symbols")
        elif 'Sorcery' in card_type:
            base_desc = "complex magical ritual"
            spell_details.append("with swirling magical energies")
            spell_details.append("surrounded by floating runes")
        else:
            base_desc = "magical object"
            spell_details.append("with mysterious energies")
        
        # Add ability-based details
        if ability_visuals:
            spell_details.extend(ability_visuals[:2])
        
        # Add name-derived themes
        spell_details.extend(name_themes)
        
        # Combine all details, removing duplicates while preserving order
        all_details = []
        seen = set()
        for detail in spell_details:
            if detail.lower() not in seen:
                all_details.append(detail)
                seen.add(detail.lower())
        
        details_str = ', '.join(filter(None, all_details))
        
        # Build final prompt with specific magical focus
        return f"Detailed fantasy concept art of a {base_desc}, {details_str}, dramatic lighting, intricate details, cinematic composition, professional quality. White background."
