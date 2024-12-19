from PIL import Image, ImageDraw, ImageFont
import os

# Create static directories
os.makedirs('static/card_images', exist_ok=True)

# Create a default card image
def create_default_card_image():
    # Create a white image
    image = Image.new('RGB', (300, 450), color='white')
    
    # Create a drawing context
    draw = ImageDraw.Draw(image)
    
    # Try to use a system font
    try:
        font = ImageFont.truetype("/Library/Fonts/Arial.ttf", 24)
    except IOError:
        font = ImageFont.load_default()
    
    # Draw text
    draw.text((50, 200), "Default Card", fill='black', font=font)
    
    # Save the image
    image.save('static/default-card.png')
    image.save('static/card_images/default-card.png')

if __name__ == '__main__':
    create_default_card_image()
