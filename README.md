# Magic Card Generator

## Overview
A FastAPI-based web application that generates Magic: The Gathering cards using AI and provides a web interface for card generation.

## Prerequisites
- Python 3.9+
- OpenAI API Key

## Setup

1. Clone the repository
2. Create a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Set up OpenAI API Key
```bash
export OPENAI_API_KEY='your_api_key_here'
```

## Running the Application
```bash
uvicorn main:app --reload
```

Navigate to `http://localhost:8000` in your browser.

## Features
- Generate random Magic cards
- Select card rarity
- View generated card details
- Persistent card storage

## Technologies
- FastAPI
- SQLAlchemy
- SQLite
- Jinja2
- OpenAI GPT-4
