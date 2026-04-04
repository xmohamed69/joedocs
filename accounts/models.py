# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
# accounts/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models

from django.utils.translation import gettext_lazy as _

class MyModel(models.Model):
    name = models.CharField(_("Name"), max_length=100)

class Plan(models.Model):
    name = models.CharField(max_length=100)
    min_users = models.IntegerField(default=1)
    max_users = models.IntegerField(null=True, blank=True)
    storage_limit_mb = models.IntegerField(null=True, blank=True)
    ai_enabled = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    duration_months = models.PositiveIntegerField(null=True, blank=True, help_text="Duration in months (e.g. 1, 2, 6, 12)")

    def __str__(self):
        return self.name


class Organization(models.Model):
    name = models.CharField(max_length=200)
    org_id = models.CharField(max_length=10, unique=True)
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True)
    user_quota = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.org_id})"


class User(AbstractUser):
    ROLE_CHOICES = [
        ("OWNER", "Owner"),
        ("ADMIN", "Administrator"),
        ("EDITOR", "Editor"),
        ("VIEWER", "Viewer"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="VIEWER")
    profession_tag = models.CharField(max_length=100, default="", blank=True)
    can_use_ai = models.BooleanField(default=False)
    birth_date = models.DateField(null=True, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspended_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='suspended_users'
    )

    def __str__(self):
        return self.username

    @property
    def is_suspended(self):
        return self.suspended_at is not None


class UserActivityLog(models.Model):
    ACTION_CHOICES = [
        ("LOGIN", "Login"),
        ("LOGOUT", "Logout"),
        ("CREATED", "User Created"),
        ("UPDATED", "User Updated"),
        ("PASSWORD_RESET", "Password Reset"),
        ("SUSPENDED", "Account Suspended"),
        ("REACTIVATED", "Account Reactivated"),
        ("DELETED", "User Deleted"),
        ("DOCUMENT_UPLOAD", "Document Uploaded"),
        ("DOCUMENT_VIEW", "Document Viewed"),
        ("DOCUMENT_EDIT", "Document Edited"),
        ("DOCUMENT_DELETE", "Document Deleted"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='performed_actions'
    )
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.action} at {self.timestamp}"