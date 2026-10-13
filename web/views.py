from pathlib import Path

from django.http import FileResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

SITE = Path(__file__).resolve().parent / "site" / "index.html"


@never_cache
@ensure_csrf_cookie
def index(request):
    """Serve the single-page website. It talks to the API under /api/."""
    return FileResponse(open(SITE, "rb"), content_type="text/html; charset=utf-8")
