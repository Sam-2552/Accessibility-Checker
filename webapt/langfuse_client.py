"""Langfuse observability client."""

_client = None


def get_langfuse_client(config=None):
    """Initialize and return the Langfuse client (singleton).

    Returns None if Langfuse is disabled or keys are not configured.
    """
    global _client
    if _client is None and config and config.langfuse_enabled and config.langfuse_public_key:
        try:
            from langfuse import Langfuse
            _client = Langfuse(
                public_key=config.langfuse_public_key,
                secret_key=config.langfuse_secret_key,
                host=config.langfuse_host,
            )
        except ImportError:
            pass  # langfuse not installed — tracing disabled silently
    return _client


def flush():
    """Flush any pending Langfuse events."""
    if _client:
        _client.flush()
