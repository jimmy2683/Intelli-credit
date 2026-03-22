import os
import logging
import time
import random
import threading
from mistralai import Mistral
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")

# Global semaphore to limit concurrent calls to Mistral
# Mistral's rate limits can be tight, so we limit to 2-3 concurrent calls.
_mistral_semaphore = threading.Semaphore(2)

def get_client():
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY not set")

    return Mistral(api_key=MISTRAL_API_KEY)


def call_mistral(prompt: str, model_name: str = "mistral-large-latest", response_format: dict = None) -> str:
    client = get_client()
    
    max_retries = 5
    base_delay = 2.0
    
    for attempt in range(max_retries):
        try:
            with _mistral_semaphore:
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
            err_msg = str(e).lower()
            # Check for rate limit (429) or other retryable errors
            is_rate_limit = "429" in err_msg or "rate limit" in err_msg
            
            if is_rate_limit and attempt < max_retries - 1:
                # Jittered exponential backoff
                wait_time = (base_delay * (2 ** attempt)) + (random.random() * 1.5)
                logger.warning(f"Mistral Rate Limit hit. Retrying in {wait_time:.2f}s (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
                continue
            
            logger.error(f"Mistral API error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise
            
            # For other errors, maybe short sleep and retry too? 
            # If it's a 400 Bad Request, we shouldn't retry.
            if "status 400" in err_msg or "invalid_request_error" in err_msg:
                 raise
                 
            time.sleep(1.0) # Short wait for other transient issues
            
    raise Exception("Mistral extraction failed after multiple retries")