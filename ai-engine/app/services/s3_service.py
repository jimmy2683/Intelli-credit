import boto3
import os
import logging
from botocore.exceptions import ClientError
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Ensure .env is loaded
load_dotenv()

# Common temporary directory
TEMP_DIR = Path("/tmp/credit_intel_downloads")
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def get_s3_client():
    # Read env variables at runtime (NOT at import)
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION", "ap-southeast-2")

    if not aws_access_key or not aws_secret_key:
        logger.warning("AWS credentials missing. S3 downloads will fail.")
        return None

    return boto3.client(
        "s3",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region,
    )


def download_from_s3(s3_uri: str) -> str:
    """
    Downloads a file from S3 to a local temporary path.
    s3_uri format: s3://bucket-name/key/path
    Returns: local file path or original URI if failed.
    """

    if not s3_uri.startswith("s3://"):
        return s3_uri

    s3_client = get_s3_client()
    if not s3_client:
        return s3_uri

    try:
        parts = s3_uri[5:].split("/", 1)
        if len(parts) < 2:
            logger.error("Invalid S3 URI format")
            return s3_uri

        bucket = parts[0]
        key = parts[1]

        local_filename = key.replace("/", "_")
        local_path = TEMP_DIR / local_filename

        logger.info(f"Downloading: {s3_uri} -> {local_path}")

        s3_client.download_file(bucket, key, str(local_path))

        logger.info("Download successful")
        return str(local_path)

    except ClientError as e:
        logger.error(f"S3 download error: {e}")
        return s3_uri

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return s3_uri