from functools import lru_cache
from pathlib import Path
from typing import Protocol

import boto3
from botocore.config import Config

from app.core.config import settings


class Storage(Protocol):
    def save(self, key: str, content: bytes, mime: str) -> None: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def healthy(self) -> bool: ...


class S3Storage:
    def __init__(self) -> None:
        cfg = settings()
        self.bucket = cfg.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=cfg.s3_endpoint,
            aws_access_key_id=cfg.s3_access_key,
            aws_secret_access_key=cfg.s3_secret_key,
            config=Config(
                connect_timeout=5,
                read_timeout=20,
                retries={"max_attempts": 2},
                signature_version="s3v4",
            ),
        )

    def save(self, key: str, content: bytes, mime: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType=mime)

    def read(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def healthy(self) -> bool:
        self.client.head_bucket(Bucket=self.bucket)
        return True


class LocalStorage:
    """Explicit host-development/test adapter. Never enabled in production."""

    def __init__(self) -> None:
        self.root = Path(settings().storage_local_path).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError("Invalid storage key")
        return path

    def save(self, key: str, content: bytes, mime: str) -> None:
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def read(self, key: str) -> bytes:
        return self.path(key).read_bytes()

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)

    def healthy(self) -> bool:
        return self.root.is_dir()


@lru_cache
def storage() -> Storage:
    return LocalStorage() if settings().storage_backend == "local" else S3Storage()
