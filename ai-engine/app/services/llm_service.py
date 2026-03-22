"""
Unified LLM service — Ollama (local) first, Mistral (cloud) fallback.

Priority:
  1. Ollama   — fast, free, no rate limits, runs locally
  2. Mistral  — cloud fallback when Ollama is unavailable

Supported Ollama models (best-fit for financial JSON extraction):
  - qwen2.5:7b        <- RECOMMENDED — best JSON adherence, fast (~2-3s/call)
  - qwen2.5:14b       <- higher accuracy if you have VRAM
  - llama3.1:8b       <- strong general-purpose alternative
  - mistral:7b        <- familiar family, decent JSON
  - phi3.5:3.8b       <- very fast on CPU, lower accuracy

Environment variables:
  OLLAMA_HOST       base URL for Ollama API  (default: http://localhost:11434)
  OLLAMA_MODEL      model to use             (default: qwen2.5:7b)
  MISTRAL_API_KEY   Mistral cloud API key    (required for fallback)
  LLM_PROVIDER      "ollama" | "mistral" | "auto"  (default: auto)
"""
from __future__ import annotations

import logging
import os
import random
import threading
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_HOST  = os.environ.get("OLLAMA_HOST",  "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "auto").lower()

# Cloud model names that must never be forwarded to Ollama
_MISTRAL_MODEL_NAMES = {
    "mistral-large-latest", "mistral-large-2411", "mistral-large-2407",
    "mistral-medium-latest", "mistral-small-latest", "open-mistral-nemo",
    "mistral-tiny", "mistral-embed",
}

# ---------------------------------------------------------------------------
# Token bucket rate limiter for Mistral
# ---------------------------------------------------------------------------

class _TokenBucket:
    def __init__(self, rate: float = 0.8, capacity: float = 2.0):
        self._rate = rate
        self._capacity = capacity
        self._tokens = capacity
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> float:
        with self._lock:
            now = time.monotonic()
            self._tokens = min(self._capacity, self._tokens + (now - self._last) * self._rate)
            self._last = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return 0.0
            wait = (1.0 - self._tokens) / self._rate
            self._tokens = 0.0
        time.sleep(wait)
        return wait


_mistral_rate_limiter = _TokenBucket(rate=0.8, capacity=2.0)
_mistral_semaphore    = threading.Semaphore(2)

# ---------------------------------------------------------------------------
# Ollama provider
# ---------------------------------------------------------------------------

def _ollama_is_available() -> bool:
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _ollama_model_available(model: str) -> bool:
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        if r.status_code != 200:
            return False
        model_base = model.split(":")[0]
        for m in r.json().get("models", []):
            name = m.get("name", "")
            if name == model or name.split(":")[0] == model_base:
                return True
        return False
    except Exception:
        return False


def _call_ollama(prompt: str, json_mode: bool = False, timeout: int = 180) -> str:
    """
    Call Ollama. Always uses OLLAMA_MODEL — never cloud model names.

    ROOT CAUSE FIX: Previously model_name was forwarded from callers.
    Callers pass model_name="mistral-large-latest" (Mistral default).
    Ollama has no such model -> 404. Fix: model is always OLLAMA_MODEL.
    """
    model = OLLAMA_MODEL

    # 1. Try OpenAI-compatible endpoint (available in Ollama >= 0.1.24)
    url = f"{OLLAMA_HOST}/v1/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": 0.0,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        r = requests.post(url, json=payload, timeout=timeout)
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"]
            if content:
                return content.strip()
            raise ValueError("Empty content from Ollama /v1/chat/completions")
        if r.status_code == 400:
            raise RuntimeError(
                f"Ollama 400 Bad Request — check OLLAMA_MODEL='{model}': {r.text[:200]}"
            )
        if r.status_code != 404:
            raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text[:200]}")
        # 404 means this Ollama build doesn't have the OpenAI compat endpoint; fall through
        logger.debug("Ollama /v1/chat/completions not found, trying /api/generate")
    except (requests.ConnectionError, requests.Timeout) as e:
        raise ConnectionError(f"Cannot reach Ollama at {OLLAMA_HOST}: {e}") from e

    # 2. Native /api/generate fallback (always available)
    native_url = f"{OLLAMA_HOST}/api/generate"
    native_payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0},
    }
    if json_mode:
        native_payload["format"] = "json"

    try:
        r = requests.post(native_url, json=native_payload, timeout=timeout)
        if r.status_code == 404:
            raise RuntimeError(
                f"Ollama 404 on /api/generate — model '{model}' may not be pulled. "
                f"Run: ollama pull {model}"
            )
        r.raise_for_status()
        content = r.json().get("response", "").strip()
        if not content:
            raise ValueError("Empty response from Ollama /api/generate")
        return content
    except (requests.ConnectionError, requests.Timeout) as e:
        raise ConnectionError(f"Cannot reach Ollama at {OLLAMA_HOST}: {e}") from e


# ---------------------------------------------------------------------------
# Mistral provider
# ---------------------------------------------------------------------------

def _call_mistral_direct(
    prompt: str,
    model_name: str = "mistral-large-latest",
    response_format: dict | None = None,
    max_retries: int = 5,
) -> str:
    if not MISTRAL_API_KEY:
        raise ValueError(
            "MISTRAL_API_KEY not set. Start Ollama: ollama serve && ollama pull qwen2.5:7b"
        )
    from mistralai import Mistral
    client = Mistral(api_key=MISTRAL_API_KEY)
    base_delay = 2.0

    for attempt in range(max_retries):
        wait = _mistral_rate_limiter.acquire()
        if wait > 0:
            logger.debug("Mistral rate limiter waited %.2fs", wait)
        try:
            with _mistral_semaphore:
                response = client.chat.complete(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    response_format=response_format,
                )
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty response from Mistral")
                return content
        except Exception as e:
            err = str(e).lower()
            if "status 400" in err or "invalid_request_error" in err:
                raise
            if attempt < max_retries - 1:
                if "429" in err or "rate limit" in err or "1300" in err:
                    delay = (base_delay * (2 ** attempt)) + (random.random() * 2.0)
                    logger.warning("Mistral rate limit — backing off %.2fs (%d/%d)", delay, attempt+1, max_retries)
                    time.sleep(delay)
                else:
                    logger.warning("Mistral transient error (%d/%d): %s", attempt+1, max_retries, e)
                    time.sleep(1.5)
                continue
            logger.error("Mistral failed after %d attempts: %s", max_retries, e)
            raise
    raise RuntimeError("Mistral call failed after all retries")


# ---------------------------------------------------------------------------
# Availability cache
# ---------------------------------------------------------------------------

_ollama_available: bool | None = None
_ollama_check_lock = threading.Lock()


def _get_ollama_status() -> bool:
    global _ollama_available
    with _ollama_check_lock:
        if _ollama_available is None:
            _ollama_available = _ollama_is_available()
            if _ollama_available and not _ollama_model_available(OLLAMA_MODEL):
                logger.warning(
                    "Ollama running but model '%s' not pulled. Run: ollama pull %s",
                    OLLAMA_MODEL, OLLAMA_MODEL,
                )
        return _ollama_available


def reset_ollama_cache() -> None:
    """Force re-check on next call (e.g. after ollama pull)."""
    global _ollama_available
    with _ollama_check_lock:
        _ollama_available = None


# ---------------------------------------------------------------------------
# Public API — single entry point for all LLM calls
# ---------------------------------------------------------------------------

def call_llm(
    prompt: str,
    model_name: str | None = None,
    response_format: dict | None = None,
) -> str:
    """
    Route a prompt to the best available LLM.

    CRITICAL: model_name is treated as a HINT only.
      - Ollama:  always uses OLLAMA_MODEL env var regardless of model_name.
                 This prevents "mistral-large-latest" from being sent to Ollama.
      - Mistral: uses model_name if it's a valid Mistral model, else default.
    """
    json_mode = isinstance(response_format, dict) and response_format.get("type") == "json_object"
    provider  = LLM_PROVIDER

    if provider == "auto":
        provider = "ollama" if _get_ollama_status() else "mistral"
        if provider == "mistral" and not MISTRAL_API_KEY:
            raise RuntimeError(
                "No LLM available.\n"
                "  Option A: ollama serve && ollama pull qwen2.5:7b\n"
                "  Option B: set MISTRAL_API_KEY in .env"
            )

    if provider == "ollama":
        logger.debug("LLM -> Ollama [%s] json=%s len=%d", OLLAMA_MODEL, json_mode, len(prompt))
        try:
            return _call_ollama(prompt, json_mode=json_mode)
        except ConnectionError:
            reset_ollama_cache()
            if LLM_PROVIDER == "auto" and MISTRAL_API_KEY:
                logger.warning("Ollama connection lost — falling back to Mistral")
                return _call_mistral_direct(prompt, _safe_mistral_model(model_name), response_format)
            raise
        except Exception as e:
            logger.error("Ollama error: %s", e)
            if LLM_PROVIDER == "auto" and MISTRAL_API_KEY:
                logger.warning("Ollama failed — falling back to Mistral: %s", e)
                return _call_mistral_direct(prompt, _safe_mistral_model(model_name), response_format)
            raise

    elif provider == "mistral":
        m = _safe_mistral_model(model_name)
        logger.debug("LLM -> Mistral [%s] json=%s len=%d", m, json_mode, len(prompt))
        return _call_mistral_direct(prompt, m, response_format)

    raise ValueError(f"Unknown LLM_PROVIDER: '{provider}'. Use auto/ollama/mistral.")


def _safe_mistral_model(model_name: str | None) -> str:
    """Return model_name only if it's a valid Mistral model name."""
    if model_name and model_name in _MISTRAL_MODEL_NAMES:
        return model_name
    return "mistral-large-latest"


# ---------------------------------------------------------------------------
# Backward-compat shim — keeps call_mistral() working everywhere
# ---------------------------------------------------------------------------

def call_mistral(
    prompt: str,
    model_name: str = "mistral-large-latest",
    response_format: dict | None = None,
) -> str:
    """Drop-in replacement. All existing callers work unchanged."""
    return call_llm(prompt, model_name=model_name, response_format=response_format)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def check_llm_health() -> dict[str, Any]:
    ollama_up = _ollama_is_available()
    model_ok  = _ollama_model_available(OLLAMA_MODEL) if ollama_up else False
    if LLM_PROVIDER == "ollama":
        active = "ollama" if ollama_up else "unavailable"
    elif LLM_PROVIDER == "mistral":
        active = "mistral" if MISTRAL_API_KEY else "unavailable"
    else:
        active = "ollama" if (ollama_up and model_ok) else ("mistral" if MISTRAL_API_KEY else "none")
    return {
        "provider_setting": LLM_PROVIDER,
        "active_provider":  active,
        "ollama": {"available": ollama_up, "host": OLLAMA_HOST, "model": OLLAMA_MODEL, "model_pulled": model_ok},
        "mistral": {"configured": bool(MISTRAL_API_KEY), "key_preview": (MISTRAL_API_KEY[:8] + "...") if MISTRAL_API_KEY else None},
    }