# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
# accounts/quotas.py

from django.core.exceptions import ValidationError
from django.db.models import Sum


def enforce_user_quota(organization):
    """Raise ValidationError if active users exceed organization.user_quota."""
    if not organization or organization.user_quota is None:
        return

    active_users = organization.users.filter(is_active=True).count()
    if active_users > organization.user_quota:
        raise ValidationError(
            {"organization": f"User quota exceeded ({active_users}/{organization.user_quota})."}
        )


def enforce_storage_quota(organization):
    """Raise ValidationError if org storage exceeds organization.plan.storage_limit_mb."""
    if not organization or not getattr(organization, "plan", None):
        return

    limit = organization.plan.storage_limit_mb
    if limit is None:
        return

    from docs.models import Document  # local import to avoid circulars

    total = (
        Document.objects.filter(organization=organization)
        .aggregate(total=Sum("size_mb"))
        .get("total")
        or 0
    )

    if total > limit:
        raise ValidationError(
            {"organization": f"Storage quota exceeded ({total} MB / {limit} MB)."}
        )
