"""Simple limits on login and sign-up attempts, so passwords can't be guessed quickly."""
from django.core.cache import cache


def client_ip(request):
    # Behind a proxy (e.g. on a hosting platform) the real address is in X-Forwarded-For.
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR", "")


def too_many(key, limit, window_seconds):
    """Count one attempt for `key`; return True once `limit` is exceeded within the window."""
    added = cache.add(key, 1, window_seconds)
    if added:
        return False
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, window_seconds)
        return False
    return count > limit


def reset(key):
    cache.delete(key)
