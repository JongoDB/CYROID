# cyroid/services/storage_service.py
"""MinIO storage service for artifact management."""
import hashlib
import io
import logging
from typing import Optional, BinaryIO
from minio import Minio
from minio.error import S3Error

from cyroid.config import get_settings

logger = logging.getLogger(__name__)


class StorageService:
    """Service for managing file storage with MinIO."""

    def __init__(self):
        settings = get_settings()
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self.bucket = settings.minio_bucket
        self._ensure_bucket()

    def _ensure_bucket(self):
        """Create bucket if it doesnt exist."""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created bucket: {self.bucket}")
        except S3Error as e:
            logger.error(f"Failed to ensure bucket: {e}")
            raise

    def upload_file(
        self,
        file_data: BinaryIO,
        object_name: str,
        content_type: str = "application/octet-stream",
    ) -> tuple[str, int]:
        """
        Upload a file to storage.

        Returns:
            Tuple of (sha256_hash, file_size)
        """
        # Read file data and calculate hash
        file_bytes = file_data.read()
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()
        file_size = len(file_bytes)

        # Upload to MinIO
        try:
            self.client.put_object(
                self.bucket,
                object_name,
                io.BytesIO(file_bytes),
                length=file_size,
                content_type=content_type,
            )
            logger.info(f"Uploaded file: {object_name} ({file_size} bytes)")
            return sha256_hash, file_size
        except S3Error as e:
            logger.error(f"Failed to upload file: {e}")
            raise

    def download_file(self, object_name: str) -> Optional[bytes]:
        """Download a file from storage."""
        try:
            response = self.client.get_object(self.bucket, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            if e.code == "NoSuchKey":
                return None
            logger.error(f"Failed to download file: {e}")
            raise

    def delete_file(self, object_name: str) -> bool:
        """Delete a file from storage."""
        try:
            self.client.remove_object(self.bucket, object_name)
            logger.info(f"Deleted file: {object_name}")
            return True
        except S3Error as e:
            logger.error(f"Failed to delete file: {e}")
            return False

    def get_presigned_url(
        self,
        object_name: str,
        expires_seconds: int = 3600,
    ) -> str:
        """Get a presigned URL for downloading a file."""
        from datetime import timedelta
        try:
            url = self.client.presigned_get_object(
                self.bucket,
                object_name,
                expires=timedelta(seconds=expires_seconds),
            )
            return url
        except S3Error as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

    def file_exists(self, object_name: str) -> bool:
        """Check if a file exists in storage."""
        try:
            self.client.stat_object(self.bucket, object_name)
            return True
        except S3Error:
            return False

    def list_files(self, prefix: str = "") -> list[str]:
        """List files with optional prefix."""
        try:
            objects = self.client.list_objects(self.bucket, prefix=prefix)
            return [obj.object_name for obj in objects]
        except S3Error as e:
            logger.error(f"Failed to list files: {e}")
            return []


# Singleton instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get the storage service singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
