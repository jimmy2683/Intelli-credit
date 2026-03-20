import os
import logging
from mistralai import Mistral
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")


def get_client():
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY not set")

    return Mistral(api_key=MISTRAL_API_KEY)


def call_mistral(prompt: str, model_name: str = "mistral-large-latest", response_format: dict = None) -> str:
    client = get_client()

    try:
        response = client.chat.complete(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format=response_format
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError("Empty response from Mistral")

        return content

    except Exception as e:
        logger.error(f"Mistral API error: {e}")
        raise