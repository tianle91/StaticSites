"""Nominatim client setup; address cleanup and geographic fallbacks stay local."""
def nominatim(user_agent, *, timeout=30, delay=1.1):
    from geopy.geocoders import Nominatim
    from geopy.extra.rate_limiter import RateLimiter
    if delay < 1:
        raise ValueError("Nominatim requests must be at least one second apart")
    client = Nominatim(user_agent=user_agent, timeout=timeout)
    return client, RateLimiter(client.geocode, min_delay_seconds=delay, swallow_exceptions=False)
