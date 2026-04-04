# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
# docs/storage.py
"""
Storage usage helpers for the docs app.
Import and call get_org_storage_usage_mb() in any view that needs to
display storage consumption to the user.
"""

from django.db.models import Sum


def get_org_storage_usage_mb(organization) -> tuple[float, float, float]:
    """
    Returns (used_mb, limit_mb, percent_used) for the given organization.

    - used_mb     : sum of all non-deleted DocumentVersion file sizes, in MB.
    - limit_mb    : plan storage limit in MB, or 0.0 when there is no plan / limit.
    - percent_used: 0–100 float capped at 100; 0 when there is no limit.

    Never raises — missing plan, None values, and DB errors are all handled.
    """
    from .models import DocumentVersion

    try:
        result = DocumentVersion.objects.filter(
            document__organization=organization,
            document__is_deleted=False,
        ).aggregate(total=Sum("file_size"))
        used_bytes = result.get("total") or 0
    except Exception:
        used_bytes = 0

    used_mb = used_bytes / (1024 * 1024)

    # Resolve limit from the org's plan
    limit_mb = 0.0
    try:
        plan = getattr(organization, "plan", None)
        if plan:
            raw = getattr(plan, "storage_limit_mb", None)
            if raw:
                limit_mb = float(raw)
    except Exception:
        limit_mb = 0.0

    # Calculate percentage (only meaningful when there is a limit)
    if limit_mb > 0:
        percent_used = min((used_mb / limit_mb) * 100, 100.0)
    else:
        percent_used = 0.0

    return round(used_mb, 2), round(limit_mb, 2), round(percent_used, 1)