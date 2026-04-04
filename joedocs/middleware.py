# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
from django.shortcuts import render

class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        if getattr(settings, 'MAINTENANCE_MODE', False):
            if not request.path.startswith('/admin'):
                return render(request, 'maintenance.html', status=503)
        return self.get_response(request)