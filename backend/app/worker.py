"""SEC Financial Intelligence Engine — Background Worker."""

from __future__ import annotations

import asyncio
import signal
from app.core.logging import get_logger

logger = get_logger(__name__)


async def run_worker() -> None:
    logger.info("SEC Financial Intelligence worker service started.")
    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received.")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except (NotImplementedError, AttributeError):
            # Windows signal handler limitations
            pass

    while not stop_event.is_set():
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            break

    logger.info("SEC Financial Intelligence worker stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Worker exited.")
