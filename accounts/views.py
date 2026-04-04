# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
# accounts/views.py

import json
from pathlib import Path

_SESSION_FILE = Path.home() / ".joelinkAI" / "browser_profile" / "session.json"

def _persist_session(session_key: str, max_age_seconds: int = 60 * 60 * 24 * 30):
    """
    Save the session key and its server-side expiry time to disk.
    main.py reads this on startup to restore the session without relying
    on WebView2 persisting the cookie between runs.
    """
    import time
    try:
        _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SESSION_FILE.write_text(json.dumps({
            "session_key": session_key,
            "expires_at":  time.time() + max_age_seconds,
        }))
    except Exception:
        pass

def _clear_persisted_session():
    try:
        if _SESSION_FILE.exists():
            _SESSION_FILE.unlink()
    except Exception:
        pass

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_GET, require_http_methods

from .forms import OrgLoginForm, UserCreateForm, UserEditForm
from .models import Organization, UserActivityLog
from .utils import generate_unique_org_id, generate_unique_user_id, generate_password, log_activity

User = get_user_model()

from django.utils.translation import gettext_lazy as _


# -----------------------------------------------------------------------------
# Helper function for role-based redirects
# -----------------------------------------------------------------------------
def get_role_redirect(user):
    """Return the appropriate redirect URL based on user role."""
    if user.is_superuser:
        return redirect("admin:index")
    if user.role == "ADMIN":
        return redirect("accounts:user_list")
    return redirect("docs:home")


# -----------------------------------------------------------------------------
# Mixins
# -----------------------------------------------------------------------------
class AdminRequiredMixin(LoginRequiredMixin):
    """Only ADMIN (and platform superuser) may access these views."""

    def dispatch(self, request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        if user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        if getattr(user, "role", None) not in ["ADMIN", "OWNER"]:
            raise PermissionDenied("Only administrators may manage users.")

        if not getattr(user, "organization", None):
            raise PermissionDenied("You are not assigned to an organization.")

        return super().dispatch(request, *args, **kwargs)


class OwnerRequiredMixin(LoginRequiredMixin):
    """Only OWNER may access these views."""

    def dispatch(self, request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        if user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        if getattr(user, "role", None) != "OWNER":
            raise PermissionDenied("Only owners may access this page.")

        if not getattr(user, "organization", None):
            raise PermissionDenied("You are not assigned to an organization.")

        return super().dispatch(request, *args, **kwargs)


# -----------------------------------------------------------------------------
# User management (ADMIN only)
# -----------------------------------------------------------------------------
class OrgUserListView(AdminRequiredMixin, View):
    template_name = "accounts/user_list.html"

    def get(self, request):
        org = request.user.organization
        users = User.objects.filter(organization=org).order_by("-is_active", "role", "username")
        return render(request, self.template_name, {"users": users})


class OrgUserCreateView(AdminRequiredMixin, View):
    template_name = "accounts/user_create.html"

    def get(self, request):
        form = UserCreateForm(organization=request.user.organization)
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        org = request.user.organization
        form = UserCreateForm(request.POST, request.FILES, organization=org)

        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        # Quota enforcement
        active_users_count = User.objects.filter(organization=org, is_active=True).count()
        user_quota = getattr(org, "user_quota", None)

        if user_quota is not None and active_users_count >= user_quota:
            form.add_error(None, f"User quota exceeded ({active_users_count}/{user_quota}).")
            return render(request, self.template_name, {"form": form})

        # Get user_id and password from form, or generate if empty
        username = form.cleaned_data.get("user_id") or generate_unique_user_id(org)
        raw_password = form.cleaned_data.get("password") or generate_password()

        user = form.save(commit=False)
        user.organization = org
        user.username = username
        user.set_password(raw_password)
        user.save()

        # Log activity
        log_activity(
            user=user,
            action="CREATED",
            performed_by=request.user,
            details=f"User created by {request.user.username}",
            request=request
        )

        # Store credentials once in session
        session_key = f"user_credentials_{user.pk}"
        request.session[session_key] = {
            "user_pk": user.pk,
            "org_name": org.name,
            "org_id": org.org_id,
            "username": username,
            "password": raw_password,
        }
        request.session.modified = True

        return redirect("accounts:user_credentials", pk=user.pk)


class OrgUserEditView(AdminRequiredMixin, View):
    template_name = "accounts/user_edit.html"

    def get_object(self, request, pk):
        org = request.user.organization
        return get_object_or_404(User, pk=pk, organization=org)

    def get(self, request, pk):
        user_obj = self.get_object(request, pk)
        form = UserEditForm(instance=user_obj, request_user=request.user)
        return render(request, self.template_name, {"form": form, "user_obj": user_obj})

    def post(self, request, pk):
        user_obj = self.get_object(request, pk)

        # ADMIN can edit OWNER - no restriction
        form = UserEditForm(request.POST, request.FILES, instance=user_obj, request_user=request.user)
        if form.is_valid():
            form.save()
            log_activity(
                user=user_obj,
                action="UPDATED",
                performed_by=request.user,
                details=f"User profile updated by {request.user.username}",
                request=request
            )
            messages.success(request, "User updated successfully.")
            return redirect("accounts:user_list")

        return render(request, self.template_name, {"form": form, "user_obj": user_obj})


class OrgUserResetPasswordView(AdminRequiredMixin, View):
    template_name = "accounts/user_reset_password.html"

    def get_object(self, request, pk):
        org = request.user.organization
        user_obj = get_object_or_404(User, pk=pk, organization=org)
        # ADMIN can reset OWNER password - no restriction
        return user_obj

    def get(self, request, pk):
        user_obj = self.get_object(request, pk)
        return render(request, self.template_name, {"user_obj": user_obj})

    def post(self, request, pk):
        user_obj = self.get_object(request, pk)

        # Check if custom password was provided
        custom_password = request.POST.get("custom_password", "").strip()
        new_password = custom_password if custom_password else generate_password()
        
        user_obj.set_password(new_password)
        user_obj.save()

        log_activity(
            user=user_obj,
            action="PASSWORD_RESET",
            performed_by=request.user,
            details=f"Password reset by {request.user.username}",
            request=request
        )

        session_key = f"user_credentials_{user_obj.pk}"
        request.session[session_key] = {
            "user_pk": user_obj.pk,
            "org_name": user_obj.organization.name,
            "org_id": user_obj.organization.org_id,
            "username": user_obj.username,
            "password": new_password,
        }
        request.session.modified = True

        return redirect("accounts:user_credentials", pk=user_obj.pk)


class OrgUserSuspendView(AdminRequiredMixin, View):
    def post(self, request, pk):
        org = request.user.organization
        user_obj = get_object_or_404(User, pk=pk, organization=org)

        # Prevent self-suspension
        if user_obj.pk == request.user.pk:
            messages.error(request, "You cannot suspend your own account.")
            return redirect("accounts:user_list")

        if user_obj.is_suspended:
            # Reactivate
            user_obj.suspended_at = None
            user_obj.suspended_by = None
            user_obj.is_active = True
            user_obj.save()
            
            log_activity(
                user=user_obj,
                action="REACTIVATED",
                performed_by=request.user,
                details=f"Account reactivated by {request.user.username}",
                request=request
            )
            messages.success(request, f"User {user_obj.username} has been reactivated.")
        else:
            # Suspend
            user_obj.suspended_at = timezone.now()
            user_obj.suspended_by = request.user
            user_obj.is_active = False
            user_obj.save()
            
            log_activity(
                user=user_obj,
                action="SUSPENDED",
                performed_by=request.user,
                details=f"Account suspended by {request.user.username}",
                request=request
            )
            messages.success(request, f"User {user_obj.username} has been suspended.")

        return redirect("accounts:user_list")


class OrgUserDeleteView(AdminRequiredMixin, View):
    template_name = "accounts/user_delete.html"

    def get_object(self, request, pk):
        org = request.user.organization
        user_obj = get_object_or_404(User, pk=pk, organization=org)
        
        # Prevent self-deletion
        if user_obj.pk == request.user.pk:
            raise PermissionDenied("You cannot delete your own account.")
        
        return user_obj

    def get(self, request, pk):
        user_obj = self.get_object(request, pk)
        return render(request, self.template_name, {"user_obj": user_obj})

    def post(self, request, pk):
        user_obj = self.get_object(request, pk)
        username = user_obj.username
        
        log_activity(
            user=user_obj,
            action="DELETED",
            performed_by=request.user,
            details=f"User deleted by {request.user.username}",
            request=request
        )
        
        user_obj.delete()
        messages.success(request, f"User {username} has been deleted.")
        return redirect("accounts:user_list")


class OrgUserCredentialsView(AdminRequiredMixin, View):
    template_name = "accounts/user_credentials.html"

    def get_object(self, request, pk):
        org = request.user.organization
        return get_object_or_404(User, pk=pk, organization=org)

    def get(self, request, pk):
        user_obj = self.get_object(request, pk)
        session_key = f"user_credentials_{user_obj.pk}"
        data = request.session.get(session_key)

        if not data or data.get("user_pk") != user_obj.pk:
            messages.info(request, "No credentials to display.")
            return redirect("accounts:user_list")

        # Show once then remove
        request.session.pop(session_key, None)
        request.session.modified = True

        return render(request, self.template_name, {"credentials": data})


# -----------------------------------------------------------------------------
# Owner-only history view
# -----------------------------------------------------------------------------
class OrgHistoryView(OwnerRequiredMixin, View):
    template_name = "accounts/history.html"

    def get(self, request):
        org = request.user.organization
        
        # Get all users for filter dropdown
        all_users = User.objects.filter(organization=org).order_by("first_name", "last_name")
        
        # Start with base queryset
        logs = UserActivityLog.objects.filter(user__organization=org).select_related('user', 'performed_by')
        
        # Apply filters
        selected_user_id = request.GET.get('user_id', '')
        selected_action = request.GET.get('action', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        
        if selected_user_id:
            logs = logs.filter(user_id=selected_user_id)
        
        if selected_action:
            logs = logs.filter(action=selected_action)
        
        if date_from:
            from django.utils.dateparse import parse_date
            from_date = parse_date(date_from)
            if from_date:
                from datetime import datetime, time
                from django.utils import timezone as tz
                # Start of day
                start_datetime = tz.make_aware(datetime.combine(from_date, time.min))
                logs = logs.filter(timestamp__gte=start_datetime)
        
        if date_to:
            from django.utils.dateparse import parse_date
            to_date = parse_date(date_to)
            if to_date:
                from datetime import datetime, time
                from django.utils import timezone as tz
                # End of day
                end_datetime = tz.make_aware(datetime.combine(to_date, time.max))
                logs = logs.filter(timestamp__lte=end_datetime)
        
        # Limit to latest 200 records
        logs = logs[:200]
        
        return render(request, self.template_name, {
            "logs": logs,
            "all_users": all_users,
            "selected_user_id": selected_user_id,
            "selected_action": selected_action,
            "date_from": date_from,
            "date_to": date_to,
        })


# -----------------------------------------------------------------------------
# JSON generator endpoints
# -----------------------------------------------------------------------------
@login_required
@require_GET
def api_generate_org_id(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Forbidden")
    return JsonResponse({"org_id": generate_unique_org_id()})


@login_required
@require_GET
def api_generate_user_id(request):
    user = request.user

    if not (user.is_superuser or getattr(user, "role", None) in ["ADMIN", "OWNER"]):
        return HttpResponseForbidden("Forbidden")

    org = getattr(user, "organization", None)
    if not org:
        return HttpResponseForbidden("No organization associated with this user.")

    return JsonResponse({"user_id": generate_unique_user_id(org)})


@login_required
@require_GET
def api_generate_password(request):
    user = request.user

    if not (user.is_superuser or getattr(user, "role", None) in ["ADMIN", "OWNER"]):
        return HttpResponseForbidden("Forbidden")

    return JsonResponse({"password": generate_password()})


# -----------------------------------------------------------------------------
# App login / logout / home
# -----------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def org_login(request):
    # Already authenticated - redirect based on role
    if request.user.is_authenticated:
        return get_role_redirect(request.user)

    form = OrgLoginForm(request.POST or None)
    create_org_url = getattr(
        settings,
        "JOEDOCS_WEBSITE_CREATE_ORG_URL",
        "/website/create-organization/",
    )

    if request.method == "POST" and form.is_valid():
        org_id = form.cleaned_data["org_id"]
        user_id = form.cleaned_data["user_id"]
        password = form.cleaned_data["password"]

        # ------------------------------------------------------------------
        # 1. Platform superuser fast-path (org_id is ignored entirely)
        # ------------------------------------------------------------------
        candidate = authenticate(request, username=user_id, password=password)
        if candidate is not None and candidate.is_superuser:
            login(request, candidate)
            remember_me = request.POST.get("remember_me")
            if remember_me:
                max_age = 60 * 60 * 24 * 30  # 30 days
                request.session.set_expiry(max_age)
                _persist_session(request.session.session_key, max_age)
            else:
                request.session.set_expiry(0)  # expires on browser close
                _clear_persisted_session()      # don't restore on next open
            return redirect("admin:index")

        # ------------------------------------------------------------------
        # 2. Regular org-based authentication
        # ------------------------------------------------------------------
        org = Organization.objects.filter(org_id=org_id, is_active=True).first()
        if not org:
            messages.error(request, "Invalid organization ID.")
            return render(request, "accounts/login.html", {"form": form, "create_org_url": create_org_url})

        user = candidate
        if user is None:
            messages.error(request, "Invalid user ID or password.")
            return render(request, "accounts/login.html", {"form": form, "create_org_url": create_org_url})

        if user.organization_id != org.id:
            messages.error(request, "This user does not belong to that organization.")
            return render(request, "accounts/login.html", {"form": form, "create_org_url": create_org_url})

        if not user.is_active or user.is_suspended:
            messages.error(request, "Account is disabled or suspended.")
            return render(request, "accounts/login.html", {"form": form, "create_org_url": create_org_url})

        login(request, user)

        # "Remember me" controls session lifetime.
        remember_me = request.POST.get("remember_me")
        if remember_me:
            max_age = 60 * 60 * 24 * 30  # 30 days
            request.session.set_expiry(max_age)
            _persist_session(request.session.session_key, max_age)
        else:
            request.session.set_expiry(0)   # expires on browser close
            _clear_persisted_session()       # don't restore on next open

        log_activity(user=user, action="LOGIN", performed_by=user, request=request)

        # Redirect based on role
        return get_role_redirect(user)

    return render(request, "accounts/login.html", {"form": form, "create_org_url": create_org_url})


@login_required
def home(request):
    """Redirect to the appropriate home based on role."""
    return get_role_redirect(request.user)


@login_required
def org_logout(request):
    log_activity(user=request.user, action="LOGOUT", performed_by=request.user, request=request)
    _clear_persisted_session()
    logout(request)
    return redirect("accounts:login")


def inject_session(request):
    """
    Desktop app hits this URL to set the sessionid cookie on the correct
    origin (127.0.0.1:8000) then redirect to the app.
    Query params: key, next, max_age
    """
    from django.http import HttpResponse
    key     = request.GET.get("key", "")
    next_url = request.GET.get("next", "/docs/")
    max_age = request.GET.get("max_age", str(60 * 60 * 24 * 30))

    # Sanitize
    safe_key     = key.replace("'", "").replace('"', "").replace(";", "")[:200]
    safe_next    = next_url if next_url.startswith("/") else "/docs/"
    safe_max_age = max_age if max_age.isdigit() else str(60 * 60 * 24 * 30)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Restoring session\u2026</title>
<style>
  body{{font-family:'Segoe UI',sans-serif;display:flex;align-items:center;
       justify-content:center;height:100vh;margin:0;background:#f4f6fb;color:#374151}}
  p{{font-size:.9rem;color:#6b7280}}
</style></head>
<body><p>Restoring your session\u2026</p>
<script>
  document.cookie = 'sessionid={safe_key}; path=/; SameSite=Lax; Max-Age={safe_max_age}';
  window.location.replace('{safe_next}');
</script>
</body></html>"""
    return HttpResponse(html, content_type="text/html")


def session_ping(request):
    """Desktop app uses this to check if a saved session is still valid."""
    if request.user.is_authenticated:
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False}, status=403)


def autologin(request, session_key):
    """
    Desktop app hits this URL with the saved session key.
    We set the session cookie server-side and redirect to home.
    This bypasses the login form entirely.
    """
    from django.contrib.sessions.backends.db import SessionStore
    store = SessionStore(session_key=session_key)
    if not store.exists(session_key):
        _clear_persisted_session()
        return redirect("accounts:login")
    
    # Load the session into the request
    request.session = store
    uid = store.get("_auth_user_id")
    backend = store.get("_auth_user_backend")
    if not uid or not backend:
        _clear_persisted_session()
        return redirect("accounts:login")
    
    from django.contrib.auth import get_user_model, load_backend
    User = get_user_model()
    try:
        user = User.objects.get(pk=uid)
    except User.DoesNotExist:
        _clear_persisted_session()
        return redirect("accounts:login")
    
    user.backend = backend
    login(request, user)
    
    # Redirect based on role
    return get_role_redirect(user)