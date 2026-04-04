# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
# joedocs/urls.py
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("website/", include("website.urls")),
    path("accounts/", include("accounts.urls")),
    path("docs/", include("docs.urls")),
    path(
        "",
        RedirectView.as_view(pattern_name="website:home", permanent=False),
        name="root_redirect",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)