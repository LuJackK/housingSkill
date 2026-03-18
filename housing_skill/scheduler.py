"""Scheduler – runs the housing skill at regular intervals."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class ReportScheduler:
    """Runs a callback at a fixed interval and optionally saves reports to disk.

    Example usage::

        def my_callback():
            skill = HousingSkill()
            skill.run(criteria, output_dir=Path("reports"))

        scheduler = ReportScheduler(callback=my_callback, interval_seconds=3600)
        scheduler.start()
        # ... later ...
        scheduler.stop()
    """

    def __init__(
        self,
        callback: Callable[[], None],
        interval_seconds: int = 3600,
    ) -> None:
        self.callback = callback
        self.interval_seconds = interval_seconds
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the scheduler in a background thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Scheduler is already running.")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(
            "Scheduler started (interval=%ds).", self.interval_seconds
        )

    def stop(self) -> None:
        """Signal the scheduler to stop and wait for the thread to exit."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Scheduler stopped.")

    def run_once(self) -> None:
        """Execute the callback immediately (blocking)."""
        logger.info("Running scheduled callback once.")
        try:
            self.callback()
        except Exception as exc:
            logger.error("Scheduled callback failed: %s", exc)

    @property
    def is_running(self) -> bool:
        """Return ``True`` if the background thread is alive."""
        return bool(self._thread and self._thread.is_alive())

    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.callback()
            except Exception as exc:
                logger.error("Scheduled callback failed: %s", exc)
            self._stop_event.wait(timeout=self.interval_seconds)


def build_scheduler(
    skill: "HousingSkill",  # noqa: F821  – forward reference
    criteria,
    interval_seconds: int = 3600,
    output_dir: Optional[Path] = None,
) -> ReportScheduler:
    """Convenience factory that wires up a :class:`ReportScheduler` for a skill."""
    from housing_skill.skill import HousingSkill  # local import to avoid circularity

    def callback() -> None:
        skill.run(criteria, output_dir=output_dir)

    return ReportScheduler(callback=callback, interval_seconds=interval_seconds)
