import logging
import requests
from typing import Dict, Any, Tuple, Optional
from openai_config import openai_client
from backblaze_config import upload_image

# Logging configuration
logger = logging.getLogger(__name__)

# Cache for DALL-E responses
_image_cache: Dict[str, Tuple[str, str]] = {}

def generate_card_image(card_data: Dict[str, Any]) -> Tuple[str, str]:
    """Generate artwork for the card using OpenAI's image generation API."""
    # Basic validation
    if not card_data or not isinstance(card_data, dict):
        raise ValueError("Invalid card data provided")
    
    name = card_data.get('name')
    if not name:
        raise ValueError("Card name is required")
    
    # Check cache
    cache_key = f"{name}_{card_data.get('set_name')}_{card_data.get('card_number')}"
    if cache_key in _image_cache:
        logger.info(f"Using cached image for {name}")
        return _image_cache[cache_key]
    
    logger.info(f"\n=== Generating image for card: {name} ===")
    
    try:
        # Get the focused prompt
        from generator.prompt_utils import create_dalle_prompt
        prompt = create_dalle_prompt(card_data)
        
        # Use prompt directly - it already contains all necessary context
        final_prompt = prompt
        
        # Log DALL-E request
        logger.info("\nSending request to DALL-E API:")
        logger.info(f"Model: dall-e-3")
        logger.info(f"Size: 1024x1024")
        logger.info(f"Quality: hd")
        logger.info(f"Style: natural")
        logger.info(f"Prompt: {final_prompt}")
        
        # Generate image with DALL-E
        dalle_response = openai_client.images.generate(
            model="dall-e-3",
            prompt=final_prompt,
            size="1024x1024",
            quality="hd",
            n=1,
            style="natural",
            user="mtg_card_artist",
            response_format="url"
        )
        
        # Get image URL
        if not dalle_response or not dalle_response.data:
            raise ValueError("Invalid response from DALL-E API")
        
        image_url = dalle_response.data[0].url
        if not image_url:
            raise ValueError("No image URL in DALL-E response")
            
        logger.info("\nReceived response from DALL-E API:")
        logger.info(f"Image URL: {image_url}")
        
        # Download image
        img_response = requests.get(image_url, timeout=60)
        img_response.raise_for_status()
        
        # Basic validation of image data
        if not img_response.content:
            raise ValueError("No image data received")
        
        # Upload to Backblaze
        filename = f"card_{card_data['set_name']}_{card_data['card_number']}.png"
        b2_url = upload_image(img_response.content, filename)
        if not b2_url:
            raise ValueError("Failed to upload image to Backblaze")
        
        # Cache the result
        _image_cache[cache_key] = (image_url, b2_url)
        return image_url, b2_url
        
    except Exception as e:
        logger.error(f"Failed to generate image: {str(e)}")
        raise ValueError(f"Image generation failed: {str(e)}")
