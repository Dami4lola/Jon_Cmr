"""
AWS S3 utility for receipt image storage.
"""
import boto3
import uuid
import logging
from urllib.parse import urlparse

from botocore.exceptions import ClientError
from fastapi import HTTPException

from ..config import settings

logger = logging.getLogger(__name__)


def get_s3_client():
    """Create and return a boto3 S3 client using config credentials."""
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION,
    )


def upload_file_to_s3(
    file_bytes: bytes, filename: str, content_type: str, prefix: str = "receipts"
) -> str:
    """
    Upload a file to S3 and return the public URL.

    Args:
        file_bytes: Raw file content
        filename: Original filename
        content_type: MIME type (e.g. 'image/jpeg')
        prefix: S3 key prefix (default 'receipts')

    Returns:
        The public URL string for the uploaded object.
    """
    s3 = get_s3_client()
    key = f"{prefix}/{uuid.uuid4()}_{filename}"

    logger.info(f"Uploading to S3: bucket={settings.AWS_S3_BUCKET_NAME}, region={settings.AWS_S3_REGION}, key={key}, size={len(file_bytes)} bytes")

    try:
        s3.put_object(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
    except ClientError as e:
        logger.error(f"S3 upload failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="File upload failed. Please try again later.",
        )

    public_url = (
        f"https://{settings.AWS_S3_BUCKET_NAME}"
        f".s3.{settings.AWS_S3_REGION}.amazonaws.com/{key}"
    )
    logger.info(f"S3 upload success: {public_url}")
    return public_url


def generate_presigned_url(public_url: str, expiry: int = 3600) -> str:
    """
    Return a presigned GET URL for an S3 object given its public URL.
    Falls back to the original URL on error so photos degrade gracefully.
    """
    parsed = urlparse(public_url)
    key = parsed.path.lstrip("/")
    if not key:
        return public_url
    try:
        s3 = get_s3_client()
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_S3_BUCKET_NAME, "Key": key},
            ExpiresIn=expiry,
        )
    except ClientError as e:
        logger.warning(f"Failed to generate presigned URL for {key}: {e}")
        return public_url


def delete_file_from_s3(public_url: str) -> None:
    """
    Delete a file from S3 given its public URL.

    Extracts the object key from the URL and deletes it.
    """
    parsed = urlparse(public_url)
    # Key is the path without leading slash
    key = parsed.path.lstrip("/")
    if not key:
        return

    s3 = get_s3_client()
    s3.delete_object(
        Bucket=settings.AWS_S3_BUCKET_NAME,
        Key=key,
    )
