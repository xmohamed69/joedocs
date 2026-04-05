# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.

from django.shortcuts import render


class HealthcheckSSLBypassMiddleware:
    """
    Exempts the /health/ endpoint from Django's SECURE_SSL_REDIRECT.

    Railway's healthcheck probe hits /health/ over plain HTTP. When
    SECURE_SSL_REDIRECT=True (production), SecurityMiddleware would issue a
    301 redirect to HTTPS before the view can respond, causing the probe to
    fail. This middleware tricks SecurityMiddleware into believing the request
    already arrived over HTTPS for that path only, so it returns HTTP 200 "ok"
    without a redirect.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/health/":
            request.META["wsgi.url_scheme"] = "https"
        return self.get_response(request)


class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        if getattr(settings, 'MAINTENANCE_MODE', False):
            if not request.path.startswith('/admin'):
                return render(request, 'maintenance.html', status=503)
        return self.get_response(request)