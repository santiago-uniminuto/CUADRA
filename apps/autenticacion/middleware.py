import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect


class InactivityTimeoutMiddleware:
    """HU002 — close the session after SESSION_INACTIVITY_TIMEOUT seconds
    (3 minutes by default) without activity, and tell the user why.

    Why a middleware and not only SESSION_COOKIE_AGE: when the cookie itself
    expires, the browser simply stops sending it and the server cannot tell
    "expired by inactivity" apart from "never logged in", so it could not show
    the notice. Here the cookie lives longer (SESSION_COOKIE_AGE is only a hard
    upper limit) and this middleware enforces the real 3-minute rule.

    Must be placed AFTER AuthenticationMiddleware and MessageMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = time.time()
            timeout = getattr(settings, "SESSION_INACTIVITY_TIMEOUT", 180)
            last_activity = request.session.get("last_activity")
            if last_activity is not None and now - last_activity > timeout:
                logout(request)
                messages.warning(request, "Your session was closed due to inactivity")
                return redirect("autenticacion:login")
            request.session["last_activity"] = now
        return self.get_response(request)
