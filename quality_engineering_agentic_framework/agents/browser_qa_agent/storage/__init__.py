from .base import ArtifactStorage
from .local import LocalStorage
from .s3 import S3Storage
from ..config import get_settings


def get_storage() -> ArtifactStorage:
    settings = get_settings()
    if settings.storage_backend == "s3":
        return S3Storage(
            bucket=settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
    return LocalStorage(base_path=settings.storage_local_path)


__all__ = ["ArtifactStorage", "LocalStorage", "S3Storage", "get_storage"]
