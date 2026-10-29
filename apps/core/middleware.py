"""Middleware that gives signed-out visitors a temporary guest session."""

from django.contrib.auth import login

from apps.users.guests import create_guest_user

GUEST_EXEMPT_PREFIXES = (
    '/admin/',
    '/static/',
    '/media/',
    '/login/',
    '/register/',
    '/logout/',
)

GUEST_EXEMPT_PATHS = {
    '/favicon.ico',
    '/robots.txt',
}


def _is_browser_navigation(request):
    """Return True only for top-level pages a browser will actually render.

    Health checks, API clients, assets, and browser prefetches must never
    allocate guest accounts. Documents are identified by their HTML Accept
    header or by the Fetch Metadata navigation hint.
    """
    if request.headers.get('x-requested-with', '').lower() == 'xmlhttprequest':
        return False

    purpose = request.headers.get('sec-purpose', '').lower()
    if 'prefetch' in purpose or 'prerender' in purpose:
        return False

    accept = request.headers.get('accept', '').lower()
    if 'text/html' in accept or 'application/xhtml+xml' in accept:
        return True

    return request.headers.get('sec-fetch-dest', '').lower() == 'document'


class GuestSessionMiddleware:
    """Auto-create and sign in a guest for browser page requests.

    Registered users keep their normal session. Auth, admin, static, and media
    routes are exempt so they never create throwaway accounts.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._ensure_guest(request)
        return self.get_response(request)

    def _ensure_guest(self, request):
        if request.method != 'GET':
            return
        path = request.path or ''
        if path in GUEST_EXEMPT_PATHS or path.startswith(GUEST_EXEMPT_PREFIXES):
            return

        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            return

        if not _is_browser_navigation(request):
            return

        guest = create_guest_user()
        login(
            request,
            guest,
            backend='django.contrib.auth.backends.ModelBackend',
        )
