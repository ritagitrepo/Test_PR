import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    broker_url: str
    controller_url: str
    auth_token: str | None
    timeout_seconds: float

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            broker_url=os.getenv("PINOT_BROKER_URL", "http://localhost:8099").rstrip("/"),
            controller_url=os.getenv("PINOT_CONTROLLER_URL", "http://localhost:9000").rstrip("/"),
            auth_token=os.getenv("PINOT_AUTH_TOKEN") or None,
            timeout_seconds=float(os.getenv("PINOT_TIMEOUT_SECONDS", "10")),
        )
