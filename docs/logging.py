# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
from .models import ActivityLog

def log(org, user, action, target_type=None, target_id=None, **metadata):
    ActivityLog.objects.create(
        organization=org,
        user=user,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        metadata=metadata or {},
    )
