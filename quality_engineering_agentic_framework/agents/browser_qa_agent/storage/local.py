import os
import aiofiles
from .base import ArtifactStorage


class LocalStorage(ArtifactStorage):
    def __init__(self, base_path: str = "./artifacts"):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)

    def _full_path(self, key: str) -> str:
        path = os.path.join(self.base_path, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self._full_path(key)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        return f"file://{os.path.abspath(path)}"

    async def get_url(self, key: str) -> str:
        return f"file://{os.path.abspath(self._full_path(key))}"

    async def upload_file(self, key: str, file_path: str, content_type: str = "application/octet-stream") -> str:
        async with aiofiles.open(file_path, "rb") as f:
            data = await f.read()
        return await self.upload(key, data, content_type)
