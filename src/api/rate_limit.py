"""Rate limiting for the paid search endpoints.

Dealo's search is open to the internet with no account behind it, and every
search spends real money: SearchApi for the lookup, then Crawlbase/Apify to
read the store pages. Unmetered, one loop left running — a scraper, a broken
retry, someone curious with a shell — bills us for as long as it runs.

Three limits, deliberately layered:

  per IP, per minute   stops hammering the moment it starts
  per IP, per hour     bounds what any one source can spend in a sitting
  everyone, per hour   a ceiling on the bill no matter how the traffic arrives

The first two are set far above anything a shopper does. The third exists
because the first two can be walked around by changing IP address, and a
spend ceiling that only holds when the attacker cooperates isn't a ceiling.
It is high enough that it should only ever be reached by something going
wrong, and reaching it is worth knowing about — hence the log line.

Counters live in this process's memory (workers = 1 in gunicorn.conf.py, so
that is the whole service) and reset when it restarts. Good enough for the
job: this is a cost guard, not a security boundary.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException, Request

from ..cache import RateLimiter
from ..config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

_per_minute = RateLimiter(
    max_per_window=_settings.SEARCH_MAX_PER_MINUTE_PER_IP, window_seconds=60,
)
_per_hour = RateLimiter(
    max_per_window=_settings.SEARCH_MAX_PER_HOUR_PER_IP, window_seconds=3600,
)
_global_per_hour = RateLimiter(
    max_per_window=_settings.SEARCH_MAX_PER_HOUR_TOTAL, window_seconds=3600,
)

_GLOBAL_KEY = "__all__"

TOO_MANY_REQUESTS_MSG = (
    "That's a lot of searches in a short time. Give it a minute and try again."
)
BUSY_MSG = (
    "Dealo is unusually busy right now. Please try again in a few minutes."
)


def client_ip(request: Request) -> str:
    """The requesting client's address, as best it can be known.

    Render puts the service behind its own proxy, so request.client.host is
    the proxy and the real address arrives in X-Forwarded-For. We take the
    *last* entry, not the first. The header is a list that each hop appends
    to, so a client that sends its own X-Forwarded-For has that value sitting
    at the front with the address Render actually saw appended after it —
    reading the first entry would let anyone hand us whichever address they
    liked and get a fresh allowance for each one.

    This is still a best effort, not proof of identity, which is exactly why
    the global ceiling above doesn't depend on getting it right.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else "unknown"


def enforce_search_rate_limit(request: Request) -> None:
    """FastAPI dependency for the endpoints that cost money to serve.

    Answers 429 with a plain sentence rather than a status code alone: the
    frontend shows `detail` to the user as-is (see react/src/utils/errors.js),
    so whatever is written here is what a real person reads.
    """
    ip = client_ip(request)

    for limiter in (_per_minute, _per_hour):
        if not limiter.allow(ip):
            logger.info("[rate-limit] %s blocked (%s per %ss)", ip, limiter.max_per_window, int(limiter.window_seconds))
            raise HTTPException(
                status_code=429,
                detail=TOO_MANY_REQUESTS_MSG,
                headers={"Retry-After": str(limiter.seconds_until_reset(ip))},
            )

    if not _global_per_hour.allow(_GLOBAL_KEY):
        # Worth alerting on if this ever fires: either Dealo got popular in the
        # space of an hour, or something is wrong.
        logger.warning(
            "[rate-limit] GLOBAL ceiling of %s searches/hour reached — traffic refused",
            _global_per_hour.max_per_window,
        )
        raise HTTPException(
            status_code=429,
            detail=BUSY_MSG,
            headers={"Retry-After": str(_global_per_hour.seconds_until_reset(_GLOBAL_KEY))},
        )
