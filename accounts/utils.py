# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
import secrets
import string
from django.contrib.auth import get_user_model

User = get_user_model()

_DIGITS = string.digits
_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{}:,.?"


def _random_digits(n: int) -> str:
    return "".join(secrets.choice(_DIGITS) for _ in range(n))


def generate_unique_org_id() -> str:
    from .models import Organization
    while True:
        x = _random_digits(10)
        if not Organization.objects.filter(org_id=x).exists():
            return x


def generate_unique_user_id(org) -> str:
    while True:
        x = _random_digits(10)
        if not User.objects.filter(organization=org, username=x).exists():
            return x


def generate_password(length: int = 12) -> str:
    if length < 12:
        raise ValueError("Password length must be at least 12.")
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


def log_activity(user, action, performed_by=None, details="", request=None):
    """Log user activity"""
    from .models import UserActivityLog
    
    ip_address = None
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')
    
    UserActivityLog.objects.create(
        user=user,
        action=action,
        performed_by=performed_by,
        details=details,
        ip_address=ip_address
    )


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip