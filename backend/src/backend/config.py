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
    # Generated descriptions and follow-up answers are prose, followed by semantic matching.
    # This budget counts visual questions; vocabulary alignment has a separate bounded pass.
    # Off by default: on 4-bit 32B each visual follow-up is a ~18 s prose generation plus ~7 s of semantic
    # matching, about 45 s per video for two, and no run has shown that they change a verdict.
    FOLLOWUP_MAX_CALLS: int = 0
    FOLLOWUP_MAX_FRAMES: int = 2
    FOLLOWUP_CALL_SECONDS: float = 20.0
    # Off by default: the caption scan generates up to 96 tokens per 8 s window every 4 s, and 4-bit
    # Qwen3-VL-32B generated only ~2-5 tokens/s on the A6000, so the scan is estimated to take about as
    # long as all perception probes together. Its accuracy benefit is unmeasured; TEMPORAL_SCAN=true restores it.
    TEMPORAL_SCAN: bool = False
    # Fuse zoomed region probes, body keypoints and local patch motion into the timeline.
    PERCEPTION: bool = True
    POSE_DEVICE: str | None = None
    TIMELINE_DIR: Path = BACKEND_DIR / "var" / "timelines"


settings = Settings()
