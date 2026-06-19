from abc import ABC, abstractmethod


class ArtifactStorage(ABC):
    @abstractmethod
    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload bytes and return the public/accessible URL."""

    @abstractmethod
    async def get_url(self, key: str) -> str:
        """Return URL for an already-uploaded key."""

    @abstractmethod
    async def upload_file(self, key: str, file_path: str, content_type: str = "application/octet-stream") -> str:
        """Upload a local file by path and return its URL."""
