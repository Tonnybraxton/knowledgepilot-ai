import hashlib
from typing import cast

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.errors import AppError


def redis_client() -> Redis:
    return Redis.from_url(settings().redis_url, socket_connect_timeout=3, socket_timeout=3)


def rate_limit(key: str, maximum: int, seconds: int = 60) -> None:
    key = "limit:" + hashlib.sha256(key.encode()).hexdigest()
    try:
        count = redis_client().eval(
            "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n",
            1,
            key,
            str(seconds),
        )
    except RedisError as exc:
        raise AppError(
            503, "unavailable", "Service temporarily unavailable. Please retry shortly."
        ) from exc
    if int(cast(str, count)) > maximum:
        raise AppError(429, "rate_limit", "Too many requests. Please wait a minute and retry.")
