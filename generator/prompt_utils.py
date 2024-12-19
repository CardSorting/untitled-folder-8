import random
from typing import Dict, Any, List
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

def generate_card_prompt(rarity: str = None) -> str:
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
    
    # Build the prompt with emphasis on concise, focused design
    prompt = (
        f"Design a focused Magic: The Gathering card with these specifications:\n"
        f"- Name: Brief, thematic name (max 40 chars) using elements from {', '.join(themes['creatures'][:2])}.\n"
        f"- ManaCost: {mana_cost_guidance if mana_cost_guidance else 'Balanced mana cost with curly braces {X}.'}\n"
        f"- Type: {card_type}\n"
        f"- Color: {color_str}\n"
        "- Abilities: Create 1-3 concise, synergistic abilities that:\n"
        f"  * Incorporate these keywords: {', '.join(random.sample(themes['keywords'], min(2, len(themes['keywords']))))}\n"
        "  * Focus on clear, direct effects\n"
        "  * Each ability should be under 150 characters\n"
        "  * Prefer established keyword mechanics when possible\n"
        "- PowerToughness: For creatures, use balanced stats matching the mana cost.\n"
        f"- FlavorText: One impactful sentence (max 120 chars) capturing the card's essence.\n"
        f"- Rarity: {rarity_prompt}\n"
        "Return a JSON object with these fields. Keep text concise and focused."
    )
    
    return prompt

def create_dalle_prompt(card_data: Dict[str, Any]) -> str:
    """Create a highly detailed DALL-E prompt that strongly adheres to the card's identity."""
    # Extract all relevant card details
    name = card_data.get('name', '')
    card_type = card_data.get('type', '')
    color = card_data.get('color', '')
    text = card_data.get('text', '')
    power = card_data.get('power', '')
    toughness = card_data.get('toughness', '')
    rarity = card_data.get('rarity', '')
    flavor_text = card_data.get('flavorText', '')
    color_str = '/'.join(color) if isinstance(color, list) else color
    
    # Initialize personality traits list
    personality_traits = []
    
    # Initialize lists for visual elements
    ability_visuals = []
    creature_types = []
    
    # Analyze text for ability-based visual elements first
    if text:
        if 'destroy' in text.lower():
            ability_visuals.append('emanating destructive energy')
        if 'draw' in text.lower():
            ability_visuals.append('surrounded by floating magical scrolls')
        if 'damage' in text.lower():
            ability_visuals.append('channeling aggressive energy')
        if 'heal' in text.lower() or 'life' in text.lower():
            ability_visuals.append('glowing with restorative energy')
        if 'counter' in text.lower():
            ability_visuals.append('radiating disruptive magical energy')
        if 'enters the battlefield' in text.lower():
            ability_visuals.append('materializing with powerful purpose')
    
    # Extract and infer creature types
    if 'type' in card_data:
        type_parts = card_data['type'].split('—')
        if len(type_parts) > 1:
            creature_types = [t.strip() for t in type_parts[1].split()]
        else:
            # Extract descriptive words from name for personality traits
            name_lower = name.lower()
            words = name_lower.replace("'s", '').split()
            
            # Build personality traits from name words
            for word in words:
                # Skip common words
                if word in ['the', 'of', 'and', 'in', 'on', 'at', 'to']:
                    continue
                    
                # Add word-based traits that enhance the character's identity
                if word in name_lower:
                    # Add the word itself as a trait if it's descriptive
                    personality_traits.append(word)
                    
                    # Add any ability-based visuals that match the word
                    if 'wisdom' in word or 'insight' in word:
                        ability_visuals.append('radiating mental energy')
                    elif 'flame' in word or 'fire' in word:
                        ability_visuals.append('emanating intense heat')
                    elif 'shadow' in word or 'dark' in word:
                        ability_visuals.append('wreathed in shadows')
                    elif 'light' in word or 'bright' in word:
                        ability_visuals.append('glowing with inner light')
                    elif 'storm' in word or 'thunder' in word:
                        ability_visuals.append('crackling with electric energy')
    
    # Extract mana cost details
    mana_cost = card_data.get('manaCost', '')
    mana_value = sum(c.isdigit() and int(c) or 1 for c in mana_cost if c.isdigit() or c in 'WUBRG')
    
    # Enhanced color-specific visual traits
    color_traits = {
        'White': 'radiating divine light, adorned with flowing robes and holy symbols, emanating purity and order',
        'Blue': 'surrounded by arcane runes, with mystical patterns and intellectual demeanor, showing deep wisdom',
        'Black': 'shrouded in dark energy, with sinister features and corrupted elements, exuding darkness',
        'Red': 'emanating fierce energy and primal power, with passionate expression and dynamic posture, burning with intensity',
        'Green': 'displaying natural vigor and primal strength, with organic features and earthen elements'
    }
    
    # Color-specific creature enhancements
    color_creature_traits = {
        'White': {
            'Angel': 'with majestic wings of pure light and divine armor',
            'Knight': 'in gleaming plate armor with holy symbols',
        },
        'Blue': {
            'Leviathan': 'with ancient wisdom in its eyes, covered in mystical runes',
            'Wizard': 'wielding complex magical implements and scholarly attire',
        },
        'Black': {
            'Demon': 'with corrupted features and malevolent presence',
            'Zombie': 'showing signs of undeath and decay',
        },
        'Red': {
            'Dragon': 'with scales of burning intensity and fierce expression',
            'Warrior': 'with battle-scarred armor and aggressive stance',
        },
        'Green': {
            'Beast': 'with primal strength and natural adaptations',
            'Elemental': 'formed from living natural elements',
        }
    }
    
    # Get color-specific visual elements
    color_visuals = []
    if isinstance(color, list):
        for c in color:
            if c in color_traits:
                color_visuals.append(color_traits[c])
    elif color in color_traits:
        color_visuals.append(color_traits[color])
    color_visual_desc = ', '.join(color_visuals) if color_visuals else ''
    
    # Extract keywords and abilities from text
    keywords = []
    if text:
        # Common MTG keywords and their visual representations
        keyword_visuals = {
            'Flying': 'with majestic wings spread wide, hovering gracefully',
            'First Strike': 'in an aggressive combat stance, weapon poised to strike',
            'Deathtouch': 'with deadly features like venomous fangs or toxic secretions',
            'Haste': 'caught in mid-sprint, body leaning forward with explosive energy',
            'Vigilance': 'in an alert defensive stance, eyes scanning for threats',
            'Trample': 'with massive, imposing physique and unstoppable momentum',
            'Lifelink': 'with ethereal life-essence flowing through their form',
            'Menace': 'with terrifying features and intimidating presence',
            'Reach': 'with elongated limbs or extraordinary height',
            'Flash': 'partially ethereal, as if materializing from thin air',
            'Defender': 'with defensive armor and protective stance',
            'Hexproof': 'surrounded by protective magical barriers',
            'Indestructible': 'with impossibly tough armor or crystalline skin',
            'Double Strike': 'dual-wielding weapons or with multiple striking limbs',
            'Scry': 'with glowing eyes showing prophetic vision',
            'Counter': 'radiating anti-magic energy',
            'Sacrifice': 'with dark ritualistic markings',
            'Transform': 'showing signs of metamorphosis'
        }
        keywords = [k for k in keyword_visuals.keys() if k.lower() in text.lower()]
        
    # Add more specific ability-based visual elements based on the card's identity
    if 'insight' in name.lower() or 'wisdom' in name.lower():
        ability_visuals.extend([
            'radiating waves of mental energy',
            'eyes glowing with ancient knowledge',
            'surrounded by floating mystical symbols'
        ])
    if 'damage' in text.lower() and 'enters the battlefield' in text.lower():
        ability_visuals.extend([
            'crackling with barely contained energy',
            'showing signs of imminent power release'
        ])
    
    # Get rarity-based style guidance
    rarity_style = {
        'Common': 'practical yet effective design, focusing on fundamental aspects',
        'Uncommon': 'distinctive and specialized design with unique characteristics',
        'Rare': 'elaborate and powerful design with complex, intricate details',
        'Mythic Rare': 'masterful and awe-inspiring design with extraordinary presence'
    }.get(rarity, 'distinctive design')
    
    # Add mechanical personality traits
    if mana_value <= 2:
        personality_traits.append('swift and agile')
    elif mana_value >= 6:
        personality_traits.append('powerful and commanding')
    if 'Legendary' in card_type:
        personality_traits.append('noble and distinguished')
    personality_desc = ', '.join(personality_traits) if personality_traits else ''
    
    # Start with the core subject description based on the card's complete identity
    if 'Creature' in card_type:
        creature_description = ' '.join(creature_types) if creature_types else card_type
        
        # Build enhanced physical description based on power/toughness and name
        physical_desc = ""
        if power and toughness:
            size_desc = ""
            if 'leviathan' in name.lower() or 'giant' in name.lower():
                size_desc = "massive and imposing, "
            elif 'tiny' in name.lower() or 'small' in name.lower():
                size_desc = "small but potent, "
                
            if int(power) > int(toughness):
                physical_desc = f"{size_desc}powerful and aggressive physique with prominent offensive features, showing clear signs of its combat prowess"
            elif int(power) < int(toughness):
                physical_desc = f"{size_desc}sturdy and resilient form with impressive defensive adaptations, built to endure"
            else:
                physical_desc = f"{size_desc}well-balanced and harmonious physical form, showing equal measures of strength and resilience"
        
        # Include keywords in visual description
        keyword_desc = ""
        if keywords:
            keyword_traits = [keyword_visuals[k] for k in keywords if k in keyword_visuals]
            if keyword_traits:
                keyword_desc = f", {', '.join(keyword_traits)}"
        
        # Add enhanced ability-based visual elements
        if ability_visuals:
            # Add intensity based on mana value
            intensity = "subtle" if mana_value <= 2 else "prominent" if mana_value <= 4 else "overwhelming"
            ability_visuals = [f"{intensity} {visual}" for visual in ability_visuals]
            ability_desc = f", {', '.join(ability_visuals)}"
        else:
            ability_desc = ""
            
        # Add color-specific creature enhancements if applicable
        creature_enhancement = ""
        if isinstance(color, list):
            for c in color:
                if c in color_creature_traits:
                    for creature_type in creature_types:
                        if creature_type in color_creature_traits[c]:
                            creature_enhancement = f", {color_creature_traits[c][creature_type]}"
                            break
        elif color in color_creature_traits:
            for creature_type in creature_types:
                if creature_type in color_creature_traits[color]:
                    creature_enhancement = f", {color_creature_traits[color][creature_type]}"
                    break
        
        # Incorporate flavor text for mood and personality
        mood_desc = f", expressing {flavor_text}" if flavor_text else ""
        personality_desc = f", appearing {personality_desc}" if personality_desc else ""
        
        # Add color-specific visual elements
        color_desc = f", {color_visual_desc}" if color_visual_desc else ""
        
        style = (
            f"Professional fantasy illustration of {name}, a {color_str} {creature_description} "
            f"with a {rarity_style}. Create a detailed character that perfectly embodies "
            f"'{name}' with {physical_desc}{keyword_desc}{ability_desc}{color_desc}"
            f"{creature_enhancement}{personality_desc}{mood_desc}. "
            f"The character should demonstrate its abilities: {text}. "
            "Character must be centered in frame against a pure white background, with strong "
            "attention to distinctive features, anatomy, and characteristic details. "
            "The character must be the ONLY element - NO background elements, "
            "NO special effects, NO decorative elements, NO patterns. "
            "Focus on making the character's identity immediately recognizable and "
            "ensuring every visual element reinforces their unique role and abilities."
        )
    else:
        # For non-creature cards, create more specific object representations
        if 'Enchantment' in card_type:
            style = (
                f"Professional illustration of {name}, a {color_str} magical enchantment with "
                f"a {rarity_style}. Create a mystical crystal or orb that embodies: {text}. "
                f"The object should express the essence of '{name}'{mood_desc}. "
                f"Incorporate {color_visual_desc} into the crystal/orb's appearance. "
                "Object must be floating in empty space, centered against a pure white background. "
                "NO effects, NO patterns, NO decorative elements. "
                "Think high-end jewelry photography with perfect lighting, ensuring the object's "
                "form clearly suggests its magical purpose."
            )
        elif 'Artifact' in card_type:
            style = (
                f"Professional illustration of {name}, a {color_str} magical artifact with "
                f"a {rarity_style}. Create a detailed magical object that embodies: {text}. "
                f"The artifact should clearly represent '{name}'{mood_desc}. "
                f"Design should suggest its function: {', '.join(ability_visuals) if ability_visuals else text}. "
                "Object must be floating in empty space, centered against a pure white background. "
                "NO effects, NO patterns, NO decorative elements. "
                "Think museum-quality artifact photography with perfect lighting, ensuring every "
                "detail of the artifact's construction suggests its magical purpose."
            )
        elif 'Instant' in card_type or 'Sorcery' in card_type:
            style = (
                f"Professional illustration of {name}, a {color_str} magical spell with "
                f"a {rarity_style}. Create a mystical rune or sigil that embodies: {text}. "
                f"The symbol should capture the essence of '{name}'{mood_desc}. "
                f"Incorporate {color_visual_desc} into the symbol's design. "
                f"The rune's form should suggest its effect: {', '.join(ability_visuals) if ability_visuals else text}. "
                "Symbol must be floating in empty space, centered against a pure white background. "
                "NO effects, NO patterns, NO decorative elements. "
                "Think ancient magical symbol with perfect clarity, where every line and curve "
                "suggests the spell's purpose and power."
            )
        else:
            style = (
                f"Professional illustration of {name}, a {color_str} magical object with "
                f"a {rarity_style}. Create a detailed magical item that embodies: {text}. "
                f"The object should perfectly represent '{name}'{mood_desc}. "
                f"Incorporate {color_visual_desc} into its design. "
                f"The object's form should suggest its purpose: {', '.join(ability_visuals) if ability_visuals else text}. "
                "Object must be floating in empty space, centered against a pure white background. "
                "NO effects, NO patterns, NO decorative elements. "
                "Focus on making the object's magical nature and purpose immediately recognizable "
                "through its form and details alone."
            )
    
    return style
