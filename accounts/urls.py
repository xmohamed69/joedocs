# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
# accounts/urls.py

from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    # Auth + app pages
    path("login/", views.org_login, name="login"),
    path("logout/", views.org_logout, name="logout"),
    path("", views.home, name="home"),

    # Desktop app session helpers
    path("session-ping/", views.session_ping, name="session_ping"),
    path("inject-session/", views.inject_session, name="inject_session"),
    path("autologin/<str:session_key>/", views.autologin, name="autologin"),

    # Owner-only history
    path("history/", views.OrgHistoryView.as_view(), name="history"),

    # User management (ADMIN only)
    path("users/", views.OrgUserListView.as_view(), name="user_list"),
    path("users/create/", views.OrgUserCreateView.as_view(), name="user_create"),
    path("users/<int:pk>/edit/", views.OrgUserEditView.as_view(), name="user_edit"),
    path("users/<int:pk>/reset-password/", views.OrgUserResetPasswordView.as_view(), name="user_reset_password"),
    path("users/<int:pk>/suspend/", views.OrgUserSuspendView.as_view(), name="user_suspend"),
    path("users/<int:pk>/delete/", views.OrgUserDeleteView.as_view(), name="user_delete"),
    path("users/<int:pk>/credentials/", views.OrgUserCredentialsView.as_view(), name="user_credentials"),

    # JSON API generators
    path("api/generate-org-id/", views.api_generate_org_id, name="api_generate_org_id"),
    path("api/generate-user-id/", views.api_generate_user_id, name="api_generate_user_id"),
    path("api/generate-password/", views.api_generate_password, name="api_generate_password"),
]