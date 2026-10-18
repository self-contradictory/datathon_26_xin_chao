from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DATABASE_PATH: Path = BACKEND_DIR / "var" / "app.db"
    UPLOAD_DIR: Path = BACKEND_DIR / "var" / "uploads"
    JOB_WORKERS: int = 1
    API_KEYS: dict[str, str] = {}
    MODEL: str = "timelens4b"
    MODEL_PATH: Path | None = None
    MODEL_DEVICE: str | None = None
    MODEL_QUANTIZATION: Literal["none", "4bit"] = "none"
    SAMPLE_FPS: float = 1.0
    IMAGE_TOKENS: int = 256
    RULE_MODE: Literal["production", "shadow"] = "shadow"
    # Structured-JSON follow-ups and the cash provenance scan are off by default: with the
    # 2B model most of these calls ran out of tokens on invalid JSON and took ~150s each.
    FOLLOWUP_MAX_CALLS: int = 0
    FOLLOWUP_MAX_FRAMES: int = 8
    TEMPORAL_SCAN: bool = False
    # Fuse zoomed region probes, body keypoints and local patch motion into the timeline.
    PERCEPTION: bool = True
    POSE_DEVICE: str | None = None
    TIMELINE_DIR: Path = BACKEND_DIR / "var" / "timelines"


settings = Settings()
