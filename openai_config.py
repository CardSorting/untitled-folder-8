import os
from dotenv import load_dotenv
from openai import OpenAI
import httpx

# Load environment variables from .env file
load_dotenv()

# Check for API key in environment variable
openai_api_key = os.getenv('OPENAI_API_KEY')

# Validate API key
if not openai_api_key or openai_api_key.startswith('sk-replace'):
    raise ValueError("Please set a valid OPENAI_API_KEY in the .env file")

# Initialize OpenAI client with explicit httpx client to avoid proxy issues
httpx_client = httpx.Client()
openai_client = OpenAI(api_key=openai_api_key, http_client=httpx_client)
