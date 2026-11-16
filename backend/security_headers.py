"""Response headers that make the browser enforce things the server cannot.

KRYteria had none of these. For most applications that is untidy; for one holding
somebody's private writing about their relationships it is a real gap, because several
of the attacks these prevent end with another person reading that writing.

Each header below is here for a reason specific to this app, not because a checklist
asked for it.
"""

from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

#: Content Security Policy.
#:
#: The front end is a built bundle served from this same origin, with no CDN, no inline
#: scripts and no third-party anything — so the policy can be strict without breaking
#: it, which is unusual and worth taking advantage of.
#:
#: `frame-ancestors 'none'` is the load-bearing one. It stops the app being framed, and
#: framing is how somebody with access to a shared device could overlay or observe this
#: interface. `form-action 'self'` and `base-uri 'none'` close the two usual routes for
#: turning an injected tag into an exfiltration channel.
#:
#: 'unsafe-inline' for styles only: the build inlines a small critical-CSS block. Scripts
#: get no such exception.
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "base-uri 'none'",
    "object-src 'none'",
])

HEADERS = {
    "Content-Security-Policy": CSP,

    # Redundant with frame-ancestors for modern browsers, and free.
    "X-Frame-Options": "DENY",

    # Stops a browser deciding for itself that a JSON response is really HTML.
    "X-Content-Type-Options": "nosniff",

    # A URL here can contain a route like /journal. Sending that to another site as a
    # Referer would leak which part of a relationship journal somebody was reading.
    "Referrer-Policy": "no-referrer",

    # This application needs none of these, and saying so means a compromised page
    # cannot quietly ask for them.
    "Permissions-Policy": (
        "geolocation=(), microphone=(), camera=(), payment=(), usb=(), "
        "accelerometer=(), gyroscope=(), magnetometer=()"
    ),

    # Opener isolation: a page this one opens cannot reach back into it.
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


class SecurityHeaders(BaseHTTPMiddleware):
    """Attach the headers above to every response.

    HSTS is added only when the deployment is actually serving https
    (``KRYTERIA_SECURE_COOKIES``), because sending it from a local http dev server would
    pin localhost to https in the developer's browser and be a genuine nuisance to undo.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.https = os.getenv("KRYTERIA_SECURE_COOKIES", "").lower() == "true"

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        for name, value in HEADERS.items():
            response.headers.setdefault(name, value)
        if self.https:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response
