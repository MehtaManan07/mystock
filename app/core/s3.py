"""
Ultra-optimized, Type-Safe S3 Service for AWS Free Tier
Minimizes API calls, bandwidth, and storage costs.
"""

import hashlib
import io
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError
from app.core.config import config


class S3Service:
    """
    Generic, type-safe S3 service optimized for AWS Free Tier.

    Free Tier Limits (12 months):
    - 5 GB storage
    - 20,000 GET requests/month
    - 2,000 PUT requests/month
    - 15 GB data transfer OUT/month

    Design Principles:
    1. Write once, read many (immutable files)
    2. Minimize PUT requests (no overwrites)
    3. Use presigned URLs for direct downloads
    4. Keep metadata minimal
    5. Fail fast, return structured errors
    """

    _client: Optional[BaseClient] = None
    _bucket_name: str = config.s3_bucket_name

    @classmethod
    def _get_client(cls) -> BaseClient:
        """
        Lazy-load S3 client with connection pooling.
        Ensures connection reuse and minimal latency.
        """
        if cls._client is None:
            boto_config = Config(
                region_name=config.aws_region,
                retries={
                    "max_attempts": 2,
                    "mode": "standard",
                },
                max_pool_connections=5,
                connect_timeout=5,
                read_timeout=10,
            )

            cls._client = boto3.client(
                "s3",
                aws_access_key_id=config.aws_access_key_id,
                aws_secret_access_key=config.aws_secret_access_key,
                config=boto_config,
            )

        return cls._client

    @classmethod
    def upload_file(
        cls,
        file_content: bytes,
        file_key: str,
        content_type: str = "application/pdf",
        metadata: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, str]:
        """
        Upload a small file to S3 in a single PUT request.

        Returns:
            Tuple[str, str]: (file_url, checksum)
        Raises:
            Exception: On failure
        """
        client = cls._get_client()
        checksum: str = hashlib.md5(file_content).hexdigest()

        upload_params: Dict[str, Any] = {
            "Bucket": cls._bucket_name,
            "Key": file_key,
            "Body": io.BytesIO(file_content),
            "ContentType": content_type,
            "ServerSideEncryption": "AES256",
            "StorageClass": "STANDARD",
        }

        if metadata:
            upload_params["Metadata"] = {
                k: str(v)[:100] for k, v in list(metadata.items())[:3]
            }

        try:
            client.put_object(**upload_params)
            file_url: str = (
                f"https://{cls._bucket_name}.s3.{config.aws_region}.amazonaws.com/{file_key}"
            )
            return file_url, checksum
        except ClientError as e:
            error_code: str = e.response.get("Error", {}).get("Code", "Unknown")
            raise Exception(f"S3 upload failed [{error_code}]: {str(e)}") from e

    @classmethod
    def generate_presigned_url(
        cls,
        file_key: str,
        expiration: int = 3600,
    ) -> str:
        """
        Generate a temporary presigned URL for secure file download.

        Returns:
            str: Presigned URL
        Raises:
            Exception: On failure
        """
        client = cls._get_client()

        try:
            url: str = client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": cls._bucket_name,
                    "Key": file_key,
                },
                ExpiresIn=expiration,
            )
            return url
        except ClientError as e:
            raise Exception(f"Failed to generate presigned URL: {str(e)}") from e

    @classmethod
    def file_exists(cls, file_key: str) -> bool:
        """
        Check if file exists in S3.

        Returns:
            bool: True if file exists, False otherwise
        """
        client = cls._get_client()

        try:
            client.head_object(Bucket=cls._bucket_name, Key=file_key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise Exception(f"S3 existence check failed: {str(e)}") from e

    @classmethod
    def get_file_metadata(cls, file_key: str) -> Dict[str, Any]:
        """
        Retrieve metadata without downloading file content.

        Returns:
            Dict[str, Any]: Metadata with size, ETag, and timestamps
        """
        client = cls._get_client()

        try:
            response = client.head_object(Bucket=cls._bucket_name, Key=file_key)
            metadata: Dict[str, Any] = {
                "size": int(response.get("ContentLength", 0)),
                "etag": response.get("ETag", "").strip('"'),
                "last_modified": response.get("LastModified", datetime.now()),
                "content_type": response.get("ContentType", ""),
            }
            return metadata
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise Exception(f"File not found: {file_key}") from e
            raise Exception(f"Failed to get metadata: {str(e)}") from e

    @classmethod
    def delete_file(cls, file_key: str) -> None:
        """
        Delete a file from S3 (should be rarely used).

        Returns:
            None
        """
        client = cls._get_client()

        try:
            client.delete_object(Bucket=cls._bucket_name, Key=file_key)
        except ClientError as e:
            raise Exception(f"Failed to delete file: {str(e)}") from e
        
    @classmethod
    def get_file_url(cls, file_key: str) -> str:
        """
        Get the URL of a file in S3.
        Usage: S3Service.get_file_url("path/to/file.pdf")

        Returns:
            str: URL of the file
        """
        return f"https://{cls._bucket_name}.s3.{config.aws_region}.amazonaws.com/{file_key}"
