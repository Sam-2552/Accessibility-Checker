"""Build LLM model instances from config."""

import sys

from strands.models.openai import OpenAIModel

from .config import WebAPTConfig


def build_model(config: WebAPTConfig):
    """Build a Strands model from the given config.

    Returns an OpenAIModel (LiteLLM proxy) or GeminiModel depending on config.provider.
    """
    if not config.api_key:
        print(f"Error: No API key configured for provider '{config.provider}'.")
        print("Set LITELLM_V_KEY or GEMINI_API_KEY in your .env file.")
        sys.exit(1)

    if config.provider == "litellm":
        return OpenAIModel(
            model_id=config.litellm_model_id,
            client_args={
                "api_key": "not-needed",
                "base_url": config.litellm_base_url,
                "default_headers": {"Authorization": f"Bearer {config.litellm_api_key}"},
            },
        )

    # Gemini
    try:
        from strands.models.gemini import GeminiModel
    except ImportError as e:
        if "google" in str(e).lower() or "genai" in str(e).lower():
            print("Gemini requires: pip install google-genai")
            sys.exit(1)
        raise

    return GeminiModel(
        model_id=config.gemini_model_id,
        client_args={"api_key": config.gemini_api_key},
    )
