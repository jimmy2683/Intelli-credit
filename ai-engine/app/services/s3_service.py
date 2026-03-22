"""
S3 service: downloads files from S3 to local temp directory.
"""
import boto3
import os
import logging
import threading
from typing import Optional, Any
from botocore.exceptions import ClientError
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

# FIX S1: Directory creation deferred to first use, not import time.
# TEMP_DIR.mkdir() at import time crashes the whole module if /tmp is read-only.
TEMP_DIR = Path("/tmp/credit_intel_downloads")

# FIX S2: Cache S3 client — boto3 client creation is expensive (SSL handshake,
# credential resolution). Creating it on every download call wastes ~50ms each time.
_s3_client_cache: Optional[Any] = None
_s3_client_lock = threading.Lock()


def _ensure_temp_dir() -> None:
    """Create temp dir on first use, not at import time."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


def get_s3_client():
    """Get or create a cached S3 client."""
    global _s3_client_cache
    with _s3_client_lock:
        if _s3_client_cache is not None:
            return _s3_client_cache

        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region     = os.getenv("AWS_REGION", "ap-southeast-2")

        if not aws_access_key or not aws_secret_key:
            logger.warning("AWS credentials missing. S3 downloads will fail.")
            return None

        _s3_client_cache = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region,
        )
        return _s3_client_cache


def invalidate_s3_client() -> None:
    """Force client re-creation (e.g. after credential rotation)."""
    global _s3_client_cache
    with _s3_client_lock:
        _s3_client_cache = None


def download_from_s3(s3_uri: str) -> str:
    """
    Download a file from S3 to a local temp path.
    Returns local path on success, original URI on failure.

    FIX S1: mkdir() called here, not at import.
    FIX S3: Check if file already exists before downloading (avoids redundant
            network calls when the same document is requested multiple times in
            one pipeline run, e.g. identity check then extraction).
    FIX S4: Use a case-specific subdirectory derived from the S3 key to avoid
            filename collisions between different cases.
    """
    if not s3_uri.startswith("s3://"):
        return s3_uri

    s3_client = get_s3_client()
    if not s3_client:
        return s3_uri

    try:
        parts = s3_uri[5:].split("/", 1)
        if len(parts) < 2:
            logger.error("Invalid S3 URI format: %s", s3_uri)
            return s3_uri

        bucket = parts[0]
        key    = parts[1]

        # FIX S4: Preserve path structure inside TEMP_DIR to avoid collisions.
        # s3://bucket/uploads/case_123/file.pdf  →  /tmp/.../uploads/case_123/file.pdf
        local_path = TEMP_DIR / key.lstrip("/")

        # FIX S1: lazy mkdir
        _ensure_temp_dir()
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # FIX S3: Skip download if already cached locally
        if local_path.exists() and local_path.stat().st_size > 0:
            logger.debug("S3 cache hit: %s -> %s", s3_uri, local_path)
            return str(local_path)

        logger.info("Downloading: %s -> %s", s3_uri, local_path)
        s3_client.download_file(bucket, key, str(local_path))
        logger.info("S3 download successful: %s (%d bytes)", local_path.name, local_path.stat().st_size)
        return str(local_path)

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error("S3 ClientError [%s] for %s: %s", error_code, s3_uri, e)
        # Invalidate cached client on auth errors so next call re-initialises
        if error_code in ("InvalidAccessKeyId", "SignatureDoesNotMatch", "ExpiredToken"):
            invalidate_s3_client()
        return s3_uri

    except Exception as e:
        logger.error("Unexpected S3 error for %s: %s", s3_uri, e)
        return s3_uri