"""CLI entrypoint placeholder; use `uv run uvicorn src.api.app:app` for the API."""

from src.core.logging import configure_logging, get_logger

logger = get_logger("uvicorn.error")


def main() -> None:
    configure_logging()
    logger.info("Use: uv run uvicorn src.api.app:app --reload")


if __name__ == "__main__":
    main()
