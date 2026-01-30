"""Cloudflare R2 storage client for personalized content.

Uses boto3 with S3-compatible API for R2 operations.
Content is stored as JSON files with the path pattern:
  library/{grade_level}/{lesson_id}/{interest_tag}/{media_type}.json
"""

import json
from datetime import datetime, timezone

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from .config import get_config


# Global client instance (singleton pattern)
_client = None


def _get_client():
    """Get or create the S3 client for R2.

    Returns:
        boto3 S3 client configured for Cloudflare R2.
    """
    global _client

    if _client is None:
        config = get_config()

        if not config.storage_enabled:
            raise RuntimeError(
                "R2 storage not configured. Set AGENTFACTORY_R2_ACCOUNT_ID, "
                "AGENTFACTORY_R2_ACCESS_KEY_ID, and AGENTFACTORY_R2_SECRET_ACCESS_KEY"
            )

        _client = boto3.client(
            "s3",
            endpoint_url=config.r2_endpoint,
            aws_access_key_id=config.r2_access_key_id,
            aws_secret_access_key=config.r2_secret_access_key,
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
            region_name="auto",  # R2 uses "auto" region
        )

    return _client


def get_storage_key(
    lesson_id: str, grade_level: str, interest_tag: str, media_type: str = "text"
) -> str:
    """Generate the R2 storage key for content.

    Path pattern: library/{grade_level}/{lesson_id}/{interest_tag}/{media_type}.json

    Args:
        lesson_id: Lesson identifier (e.g., "01-foundations/01-intro")
        grade_level: Grade level (e.g., "college", "high-school")
        interest_tag: Interest tag (e.g., "programming", "soccer")
        media_type: Media type (default: "text")

    Returns:
        Storage key string for R2.
    """
    # Sanitize lesson_id: replace slashes with dashes for flat storage
    safe_lesson_id = lesson_id.replace("/", "-")
    return f"library/{grade_level}/{safe_lesson_id}/{interest_tag}/{media_type}.json"


async def upload_content(
    storage_key: str,
    content: dict,
) -> bool:
    """Upload personalized content to R2.

    Args:
        storage_key: R2 object key (from get_storage_key)
        content: Content dictionary to store as JSON

    Returns:
        True if upload succeeded, False otherwise.
    """
    config = get_config()

    if not config.storage_enabled:
        # In development without R2, return success (mock)
        return True

    try:
        client = _get_client()

        # Add metadata
        content_with_meta = {
            **content,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

        # Upload as JSON
        client.put_object(
            Bucket=config.r2_bucket_name,
            Key=storage_key,
            Body=json.dumps(content_with_meta).encode("utf-8"),
            ContentType="application/json",
        )

        return True

    except ClientError as e:
        print(f"R2 upload error: {e}")
        return False


async def download_content(storage_key: str) -> dict | None:
    """Download personalized content from R2.

    Args:
        storage_key: R2 object key (from get_storage_key)

    Returns:
        Content dictionary if found, None otherwise.
    """
    config = get_config()

    if not config.storage_enabled:
        # In development without R2, return None (not found)
        return None

    try:
        client = _get_client()

        response = client.get_object(
            Bucket=config.r2_bucket_name,
            Key=storage_key,
        )

        content = json.loads(response["Body"].read().decode("utf-8"))
        return content

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code in ("NoSuchKey", "404"):
            return None
        print(f"R2 download error: {e}")
        return None


async def content_exists(storage_key: str) -> bool:
    """Check if content exists in R2.

    Args:
        storage_key: R2 object key (from get_storage_key)

    Returns:
        True if exists, False otherwise.
    """
    config = get_config()

    if not config.storage_enabled:
        return False

    try:
        client = _get_client()

        client.head_object(
            Bucket=config.r2_bucket_name,
            Key=storage_key,
        )
        return True

    except ClientError:
        return False


async def health_check() -> dict:
    """Check R2 storage health.

    Returns:
        Health status dict with status, backend, and optional error.
    """
    config = get_config()

    if not config.storage_enabled:
        return {
            "status": "disabled",
            "backend": "r2",
            "message": "R2 not configured (development mode)",
        }

    try:
        client = _get_client()

        # Try to list bucket (lightweight check)
        client.head_bucket(Bucket=config.r2_bucket_name)

        return {
            "status": "healthy",
            "backend": "r2",
            "bucket": config.r2_bucket_name,
        }

    except ClientError as e:
        return {
            "status": "unhealthy",
            "backend": "r2",
            "error": str(e),
        }
