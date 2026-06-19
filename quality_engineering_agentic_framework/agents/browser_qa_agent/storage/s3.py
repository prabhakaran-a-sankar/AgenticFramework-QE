import boto3
from botocore.exceptions import ClientError
import aiofiles
import asyncio
from .base import ArtifactStorage


class S3Storage(ArtifactStorage):
    def __init__(
        self,
        bucket: str,
        endpoint_url: str | None = None,
        aws_access_key_id: str = "",
        aws_secret_access_key: str = "",
        region_name: str = "us-east-1",
    ):
        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key_id or None,
            aws_secret_access_key=aws_secret_access_key or None,
            region_name=region_name,
        )

    def _public_url(self, key: str) -> str:
        # Works for AWS, R2, MinIO with public buckets
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=86400 * 7,  # 7 days
        )

    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            ),
        )
        return self._public_url(key)

    async def get_url(self, key: str) -> str:
        return self._public_url(key)

    async def upload_file(self, key: str, file_path: str, content_type: str = "application/octet-stream") -> str:
        async with aiofiles.open(file_path, "rb") as f:
            data = await f.read()
        return await self.upload(key, data, content_type)
