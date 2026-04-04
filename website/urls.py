# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
# website/urls.py

from django.urls import path
from . import views

app_name = "website"

urlpatterns = [
    path("",                         views.HomeView.as_view(),             name="home"),
    path("plans/",                   views.PlanListView.as_view(),         name="plans"),
    path("create-organization/",     views.OrgRequestCreateView.as_view(), name="create_organization"),
    path("thank-you/",               views.ThankYouView.as_view(),         name="thank_you"),
    path("download/",                views.DownloadView.as_view(),         name="download"),
    path("contact/",                 views.ContactView.as_view(),          name="contact"),
]