# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
from django.contrib import admin, messages
from django.http import JsonResponse, HttpResponseForbidden
from django.urls import path
from django.contrib.auth import get_user_model
from django.shortcuts import redirect, get_object_or_404
from django.utils.html import format_html

from .models import Organization, Plan
from .forms import AdminUserCreateForm
from .utils import generate_unique_org_id, generate_unique_user_id, generate_password

User = get_user_model()


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "min_users",
        "max_users",
        "storage_limit_mb",
        "ai_enabled",
        "is_active",
        "price",
        "duration_months",
    )
    search_fields = ("name",)
    list_filter = ("ai_enabled", "is_active")
    fields = (
        "name",
        "min_users",
        "max_users",
        "storage_limit_mb",
        "ai_enabled",
        "is_active",
        "price",
        "duration_months",
    )


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "org_id", "plan", "user_quota", "is_active")
    search_fields = ("name", "org_id")
    list_filter = ("is_active", "plan")

    change_form_template = "admin/accounts/organization/change_form.html"

    class Media:
        js = ("accounts/js/admin_org_generators.js",)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "generate-org-id/",
                self.admin_site.admin_view(self.generate_org_id_view),
                name="accounts_organization_generate_org_id",
            ),
        ]
        return custom + urls

    def generate_org_id_view(self, request):
        if not request.user.is_superuser:
            return HttpResponseForbidden("Forbidden")
        return JsonResponse({"org_id": generate_unique_org_id()})

    def save_model(self, request, obj, form, change):
        if not obj.org_id:
            obj.org_id = generate_unique_org_id()
        super().save_model(request, obj, form, change)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    form = AdminUserCreateForm

    list_display = (
        "username",
        "first_name",
        "last_name",
        "organization",
        "role",
        "is_active",
        "is_superuser",
        "reset_password_link",
    )
    search_fields = ("username", "first_name", "last_name", "email")
    list_filter = ("organization", "role", "is_active")

    change_form_template = "admin/accounts/user/change_form.html"

    class Media:
        js = ("accounts/js/admin_user_generators.js",)

    def get_fields(self, request, obj=None):
        """Show different fields for add vs edit."""
        if obj is None:
            return (
                "first_name",
                "last_name",
                "birth_date",
                "organization",
                "role",
                "username",
                "raw_password",
                "is_active",
                "email",
                "can_use_ai",
            )
        return (
            "first_name",
            "last_name",
            "birth_date",
            "organization",
            "role",
            "username",
            "is_active",
            "email",
            "can_use_ai",
        )

    def get_readonly_fields(self, request, obj=None):
        return ()

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "generate-user-id/",
                self.admin_site.admin_view(self.generate_user_id_view),
                name="accounts_user_generate_user_id",
            ),
            path(
                "generate-password/",
                self.admin_site.admin_view(self.generate_password_view),
                name="accounts_user_generate_password",
            ),
            path(
                "<int:user_id>/reset-pwd/",
                self.admin_site.admin_view(self.reset_password_action),
                name="accounts_user_reset_pwd",
            ),
            # New AJAX endpoint for modal
            path(
                "<int:user_id>/reset-pwd-ajax/",
                self.admin_site.admin_view(self.reset_password_ajax),
                name="accounts_user_reset_pwd_ajax",
            ),
        ]
        return custom + urls

    def reset_password_link(self, obj):
        """Display reset password button in list view."""
        if obj.organization and not obj.is_superuser:
            return format_html(
                '<a class="button" style="padding:2px 8px;font-size:11px;" '
                'href="{}/reset-pwd/">Reset</a>',
                obj.pk
            )
        return "—"
    reset_password_link.short_description = "Password"

    def generate_user_id_view(self, request):
        """AJAX endpoint to generate unique user ID."""
        if not request.user.is_superuser:
            return HttpResponseForbidden("Forbidden")

        org_pk = request.GET.get("org_pk")
        if not org_pk:
            return JsonResponse({"error": "Missing org_pk."}, status=400)

        try:
            org = Organization.objects.get(pk=org_pk)
        except Organization.DoesNotExist:
            return JsonResponse({"error": "Organization not found."}, status=404)

        return JsonResponse({"user_id": generate_unique_user_id(org)})

    def generate_password_view(self, request):
        """AJAX endpoint to generate random password."""
        if not request.user.is_superuser:
            return HttpResponseForbidden("Forbidden")
        return JsonResponse({"password": generate_password()})

    def reset_password_ajax(self, request, user_id):
        """AJAX endpoint to reset password and return new password as JSON."""
        if not request.user.is_superuser:
            return JsonResponse({"error": "Forbidden"}, status=403)

        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)

        user_obj = get_object_or_404(User, pk=user_id)

        if not user_obj.organization:
            return JsonResponse(
                {"error": "Cannot reset password for non-organization users."}, 
                status=400
            )

        if user_obj.is_superuser:
            return JsonResponse(
                {"error": "Cannot reset password for superusers."}, 
                status=400
            )

        # Generate and set new password
        new_password = generate_password()
        user_obj.set_password(new_password)
        user_obj.save()

        return JsonResponse({
            "success": True,
            "username": user_obj.username,
            "password": new_password,
        })

    def save_model(self, request, obj, form, change):
        """Handle saving user with proper validation and password handling."""
        
        if not request.user.is_superuser:
            messages.error(request, "Forbidden.")
            return

        # FIXED: Check for correct role names (OWNER, ADMIN not ORG_OWNER, ORG_ADMIN)
        if obj.role not in ("OWNER", "ADMIN"):
            messages.error(
                request,
                "In Django admin you can only create OWNER or ADMIN users."
            )
            return

        is_org_user = obj.organization_id is not None and not obj.is_superuser

        if is_org_user and not obj.username:
            obj.username = generate_unique_user_id(obj.organization)

        raw_pw = form.cleaned_data.get("raw_password")
        
        if not change:
            if not raw_pw:
                raw_pw = generate_password()
            obj.set_password(raw_pw)
            messages.warning(
                request,
                format_html(
                    'Password for <strong>{}</strong>: <code style="background:#fff3cd;'
                    'padding:2px 8px;border-radius:3px;font-size:14px;">{}</code><br>'
                    '<strong>⚠️ Copy this password now! It will not be shown again.</strong>',
                    obj.username,
                    raw_pw,
                )
            )
        elif raw_pw:
            obj.set_password(raw_pw)
            messages.warning(
                request,
                format_html(
                    'Password updated for <strong>{}</strong>.',
                    obj.username,
                )
            )

        if is_org_user:
            obj.is_staff = False
            obj.is_superuser = False

        super().save_model(request, obj, form, change)

    def reset_password_action(self, request, user_id):
        """Reset password for a user (non-AJAX fallback)."""
        if not request.user.is_superuser:
            return HttpResponseForbidden("Forbidden")

        user_obj = get_object_or_404(User, pk=user_id)

        if not user_obj.organization:
            messages.error(
                request,
                "Cannot reset password for non-organization users."
            )
            return redirect("admin:accounts_user_changelist")

        if user_obj.is_superuser:
            messages.error(
                request,
                "Cannot reset password for superusers via this action."
            )
            return redirect("admin:accounts_user_changelist")

        new_password = generate_password()
        user_obj.set_password(new_password)
        user_obj.save()

        messages.success(
            request,
            format_html(
                '<div style="padding: 15px; background: #d4edda; border-radius: 8px;">'
                '<h3 style="margin: 0 0 10px 0; color: #155724;">🔑 Password Reset Successful!</h3>'
                '<p><strong>User:</strong> {}</p>'
                '<p><strong>New Password:</strong></p>'
                '<code style="background: #fff; padding: 10px 20px; border-radius: 4px; '
                'font-size: 18px; display: inline-block; border: 2px dashed #28a745; '
                'user-select: all;">{}</code>'
                '<p style="margin: 15px 0 0 0; color: #856404; background: #fff3cd; '
                'padding: 10px; border-radius: 4px;">'
                '<strong>⚠️ Copy this password now!</strong> It will not be shown again.</p>'
                '</div>',
                user_obj.username,
                new_password,
            ),
        )

        return redirect("admin:accounts_user_changelist")

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser