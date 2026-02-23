"""Centralized configuration for WebAPT."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class WebAPTConfig:
    """All configuration for a WebAPT run."""

    # Model provider: "litellm" or "gemini"
    provider: str = "litellm"

    # LiteLLM settings
    litellm_api_key: str = ""
    litellm_base_url: str = "https://llmproxy.securin.io/"
    litellm_model_id: str = "azure/gpt-4.1"

    # Gemini settings
    gemini_api_key: str = ""
    gemini_model_id: str = "gemini-2.0-flash"

    # Project
    project_name: str = "web_analysis"
    output_root: Path = field(default_factory=lambda: Path("./outputs"))

    # Browser
    headless: bool = True

    # Langfuse observability
    langfuse_enabled: bool = True
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"

    @classmethod
    def from_env(cls, project_name: str | None = None) -> "WebAPTConfig":
        """Build config from environment variables."""
        load_dotenv()

        litellm_key = (
            os.environ.get("LITELLM_V_KEY")
            or os.environ.get("LITELLM_API_KEY")
            or ""
        ).strip()
        gemini_key = (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or ""
        ).strip()

        provider = os.environ.get("MODEL_PROVIDER", "").strip().lower()
        if provider not in ("litellm", "gemini"):
            if litellm_key and not gemini_key:
                provider = "litellm"
            elif gemini_key and not litellm_key:
                provider = "gemini"
            elif litellm_key and gemini_key:
                provider = "litellm"  # default to litellm when both present
            else:
                provider = "litellm"

        proj = project_name or os.environ.get("WEBAPT_PROJECT", "web_analysis")
        # Sanitize project name for filesystem use
        proj = re.sub(r"[^\w\-]", "_", proj.lower().replace(" ", "_"))
        proj = re.sub(r"_+", "_", proj).strip("_") or "web_analysis"

        return cls(
            provider=provider,
            litellm_api_key=litellm_key,
            litellm_base_url=os.environ.get("LITELLM_BASE_URL", "https://llmproxy.securin.io/"),
            litellm_model_id=os.environ.get("LITELLM_MODEL_ID", "azure/gpt-4.1"),
            gemini_api_key=gemini_key,
            gemini_model_id=os.environ.get("GEMINI_MODEL_ID", "gemini-2.0-flash"),
            project_name=proj,
            output_root=Path(os.environ.get("WEBAPT_OUTPUT_ROOT", "./outputs")),
            headless=os.environ.get("WEBAPT_HEADLESS", "true").lower() in ("true", "1", "yes"),
            langfuse_enabled=os.environ.get("LANGFUSE_ENABLED", "true").lower() in ("true", "1", "yes"),
            langfuse_public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
            langfuse_secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
            langfuse_host=os.environ.get("LANGFUSE_HOST", "http://localhost:3000"),
        )

    @property
    def project_dir(self) -> Path:
        return self.output_root / self.project_name

    @property
    def accessibility_reports_dir(self) -> Path:
        return self.project_dir / "accessibility_reports"

    @property
    def analysis_reports_dir(self) -> Path:
        return self.project_dir / "analysis_reports"

    @property
    def screenshots_dir(self) -> Path:
        return self.project_dir / "screenshots"

    @property
    def accessibility_screenshots_dir(self) -> Path:
        return self.screenshots_dir / "accessibility"

    @property
    def analysis_screenshots_dir(self) -> Path:
        return self.screenshots_dir / "analysis"

    @property
    def pdf_dir(self) -> Path:
        return self.project_dir / "pdf"

    @property
    def sessions_dir(self) -> Path:
        return self.project_dir / "sessions"

    def ensure_dirs(self) -> None:
        """Create all output directories."""
        for d in (
            self.accessibility_reports_dir,
            self.analysis_reports_dir,
            self.screenshots_dir,
            self.accessibility_screenshots_dir,
            self.analysis_screenshots_dir,
            self.pdf_dir,
            self.sessions_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    @property
    def api_key(self) -> str:
        """Return the active API key for the configured provider."""
        if self.provider == "gemini":
            return self.gemini_api_key
        return self.litellm_api_key
