"""Minimal rate limiter for provider calls."""

import time


class Throttle:
    """Leaky-bucket throttle that respects a requests-per-minute limit.

    Call ``wait()`` before each provider request; it blocks if the minimum
    inter-request interval has not yet elapsed.
    """

    def __init__(self, rpm: int = 40) -> None:
        if rpm <= 0:
            raise ValueError("rpm must be positive")
        self._min_interval = 60.0 / rpm
        self._last_call: float = 0.0

    def wait(self) -> None:
        """Block if necessary to respect the RPM limit."""
        now = time.monotonic()
        elapsed = now - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()
