import os
import logging
from google import genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_client():
    """Returns a Gemini client instance."""
    if not GEMINI_API_KEY:
        return None
    try:
        return genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")
        return None

def call_gemini(prompt: str, model_name: str = "gemini-2.0-flash", config: dict = None) -> str:
    """Calls Gemini API with a prompt and returns the text response."""
    client = get_client()
    if not client:
        logger.warning("Gemini client not initialized (check GEMINI_API_KEY).")
        raise ValueError("Gemini API key not configured.")
    
    try:
        # The new SDK uses client.models.generate_content
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config
        )
        return response.text
    except Exception as e:
        logger.error(f"Error calling Gemini: {e}")
        raise
