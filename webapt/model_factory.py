"""Build LLM model instances from config."""

import os
import sys

from strands.models.openai import OpenAIModel

from .config import WebAPTConfig


def build_model(config: WebAPTConfig):
    """Build a Strands model from the given config.

    Returns an OpenAIModel (LiteLLM proxy) or GeminiModel depending on config.provider.
    Also configures LiteLLM Langfuse callbacks when Langfuse is enabled.
    """
    if not config.api_key:
        print(f"Error: No API key configured for provider '{config.provider}'.")
        print("Set LITELLM_V_KEY or GEMINI_API_KEY in your .env file.")
        sys.exit(1)

    if config.provider == "litellm":
        model = OpenAIModel(
            model_id=config.litellm_model_id,
            client_args={
                "api_key": "not-needed",
                "base_url": config.litellm_base_url,
                "default_headers": {"Authorization": f"Bearer {config.litellm_api_key}"},
            },
        )
    else:
        # Gemini
        try:
            from strands.models.gemini import GeminiModel
        except ImportError as e:
            if "google" in str(e).lower() or "genai" in str(e).lower():
                print("Gemini requires: pip install google-genai")
                sys.exit(1)
            raise

        model = GeminiModel(
            model_id=config.gemini_model_id,
            client_args={"api_key": config.gemini_api_key},
        )

    # Configure LiteLLM Langfuse callbacks when Langfuse is enabled
    if config.langfuse_enabled and config.langfuse_public_key:
        try:
            import litellm
            os.environ["LANGFUSE_PUBLIC_KEY"] = config.langfuse_public_key
            os.environ["LANGFUSE_SECRET_KEY"] = config.langfuse_secret_key
            os.environ["LANGFUSE_HOST"] = config.langfuse_host
            litellm.success_callback = ["langfuse"]
            litellm.failure_callback = ["langfuse"]
        except ImportError:
            pass  # litellm not available — skip Langfuse callback setup

    return model
