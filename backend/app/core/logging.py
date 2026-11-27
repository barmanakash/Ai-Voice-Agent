import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure console logging once for the whole application."""
    root = logging.getLogger()
    root.setLevel(level.upper())

    if not any(getattr(h, "_aria", False) for h in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler._aria = True  # type: ignore[attr-defined]
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%H:%M:%S")
        )
        root.addHandler(handler)

    # httpx logs every request at INFO, which is noisy for Ollama polling
    logging.getLogger("httpx").setLevel(logging.WARNING)
