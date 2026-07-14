import time
from functools import wraps

from groq import RateLimitError

RETRY_DELAYS = (1, 2, 4)


def retry_on_rate_limit(fn):
    """Retry a Groq call on RateLimitError with brief backoff (1s, 2s, 4s)
    before giving up and letting the final attempt's error propagate."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        for delay in RETRY_DELAYS:
            try:
                return fn(*args, **kwargs)
            except RateLimitError:
                time.sleep(delay)
        return fn(*args, **kwargs)

    return wrapper
