"""Waiting on requests and tokens per minute, and the cap of requests per run."""

from collections import deque
from collections.abc import Callable

from evals.llm.errors import RequestCapReached

WINDOW_SECONDS = 60.0


class RequestBudget:
    """Counts the requests of a run and refuses the one past the cap.

    Share one instance between the clients (agent and judge) of a run.
    """

    def __init__(self, max_requests: int) -> None:
        self._max = max_requests
        self._used = 0

    @property
    def used(self) -> int:
        """Requests sent so far."""
        return self._used

    def take(self) -> None:
        """Spend one request.

        Raises:
            RequestCapReached: When the cap is already used up.
        """
        if self._used >= self._max:
            raise RequestCapReached(f"the run reached its cap of {self._max} requests")
        self._used += 1


class RateLimiter:
    """Sliding one-minute window over requests and tokens of one model.

    Args:
        requests_per_minute: Maximum requests in any 60 seconds.
        tokens_per_minute: Maximum tokens in any 60 seconds.
        clock: Returns the current time in seconds (injectable).
        sleep: Waits for the given seconds (injectable).
    """

    def __init__(
        self,
        requests_per_minute: int,
        tokens_per_minute: int,
        clock: Callable[[], float],
        sleep: Callable[[float], None],
    ) -> None:
        self._rpm = requests_per_minute
        self._tpm = tokens_per_minute
        self._clock = clock
        self._sleep = sleep
        self._events: deque[list[float]] = deque()  # each [time, tokens]

    def acquire(self, estimated_tokens: int) -> list[float]:
        """Wait until a request of about `estimated_tokens` fits both limits, then book it.

        A request bigger than the whole token limit goes alone, once the window is empty.

        Args:
            estimated_tokens: Expected tokens of the request.

        Returns:
            A ticket to pass to `settle` with the real token count.
        """
        while True:
            now = self._clock()
            self._purge(now)
            used = sum(event[1] for event in self._events)
            fits_requests = len(self._events) < self._rpm
            fits_tokens = not self._events or used + estimated_tokens <= self._tpm
            if fits_requests and fits_tokens:
                ticket = [now, float(estimated_tokens)]
                self._events.append(ticket)
                return ticket
            wait = self._events[0][0] + WINDOW_SECONDS - now
            self._sleep(max(wait, 0.001))

    def settle(self, ticket: list[float], actual_tokens: int) -> None:
        """Replace the estimate of a booked request with the tokens it really used."""
        ticket[1] = float(actual_tokens)

    def _purge(self, now: float) -> None:
        while self._events and now - self._events[0][0] >= WINDOW_SECONDS:
            self._events.popleft()
