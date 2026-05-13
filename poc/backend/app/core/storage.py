"""录音存储抽象。

通过 STORAGE_BACKEND 环境变量切换：
  - local: 本机文件系统 + FastAPI serve 签名URL（最简，PoC 默认）
  - minio: 自托管 S3
  - oss:   阿里云 OSS，生产推荐（与 DashScope 同区域走内网，零拉取成本）

切换不需要改业务代码：calls.py 等只调用 `storage` 单例的统一接口。
"""

import os
from abc import ABC, abstractmethod
from io import BytesIO

from .config import settings
from .signing import make_token


class StorageBackend(ABC):
    @abstractmethod
    def put_object(self, object_key: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    def get_url(self, object_key: str) -> str:
        """返回 ASR 可访问的 URL；私有桶返回带签名的临时 URL。"""

    @abstractmethod
    def get_bytes(self, object_key: str) -> bytes:
        """Return raw bytes of stored object. Raises on failure."""

    @abstractmethod
    def name(self) -> str: ...


class MinIOStorage(StorageBackend):
    def __init__(self) -> None:
        from minio import Minio

        self._client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._bucket = settings.minio_bucket

    def put_object(self, object_key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            self._bucket,
            object_key,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    def get_url(self, object_key: str) -> str:
        scheme = "https" if settings.minio_secure else "http"
        return f"{scheme}://{settings.minio_public_host}/{self._bucket}/{object_key}"

    def get_bytes(self, object_key: str) -> bytes:
        response = self._client.get_object(self._bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def name(self) -> str:
        return "minio"


class OSSStorage(StorageBackend):
    def __init__(self) -> None:
        import oss2

        if not (
            settings.oss_access_key_id and settings.oss_access_key_secret and settings.oss_bucket
        ):
            raise RuntimeError(
                "STORAGE_BACKEND=oss 但 OSS_* 配置不完整：需要 OSS_ACCESS_KEY_ID / "
                "OSS_ACCESS_KEY_SECRET / OSS_BUCKET / OSS_ENDPOINT"
            )
        self._auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
        # endpoint 例：oss-cn-hangzhou.aliyuncs.com（公网） / oss-cn-hangzhou-internal.aliyuncs.com（同区内网）
        self._bucket = oss2.Bucket(self._auth, settings.oss_endpoint, settings.oss_bucket)

    def put_object(self, object_key: str, data: bytes, content_type: str) -> None:
        self._bucket.put_object(object_key, data, headers={"Content-Type": content_type})

    def get_url(self, object_key: str) -> str:
        if settings.oss_use_signed_url:
            return self._bucket.sign_url(
                "GET",
                object_key,
                settings.oss_signed_url_expires_sec,
                slash_safe=True,
            )
        return f"https://{settings.oss_bucket}.{settings.oss_endpoint}/{object_key}"

    def get_bytes(self, object_key: str) -> bytes:
        result = self._bucket.get_object(object_key)
        return result.read()

    def name(self) -> str:
        return "oss"


class LocalFileStorage(StorageBackend):
    """本机磁盘 + FastAPI serve；URL 形如：
    {public_base}/api/recordings/raw?key=calls/12/xxx.m4a&exp=1730000000&token=...
    """

    def __init__(self) -> None:
        self._root = settings.local_storage_root
        self._public_base = settings.local_storage_public_base.rstrip("/")
        os.makedirs(self._root, exist_ok=True)

    def put_object(self, object_key: str, data: bytes, content_type: str) -> None:
        path = os.path.join(self._root, object_key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    def get_url(self, object_key: str) -> str:
        token, exp = make_token(object_key, expires_sec=3600)
        from urllib.parse import quote

        return (
            f"{self._public_base}/api/recordings/raw"
            f"?key={quote(object_key, safe='')}&exp={exp}&token={token}"
        )

    def get_bytes(self, object_key: str) -> bytes:
        path = self.local_path(object_key)
        with open(path, "rb") as f:
            return f.read()

    def local_path(self, object_key: str) -> str:
        return os.path.join(self._root, object_key)

    def name(self) -> str:
        return "local"


def _build() -> StorageBackend:
    backend = settings.storage_backend.lower()
    if backend == "oss":
        return OSSStorage()
    if backend == "minio":
        return MinIOStorage()
    if backend == "local":
        return LocalFileStorage()
    raise RuntimeError(f"unknown STORAGE_BACKEND: {settings.storage_backend}")


storage: StorageBackend = _build()
