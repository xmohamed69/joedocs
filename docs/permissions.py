# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
"""
Permission helper functions for JoeDocs

Role matrix:
  OWNER  — file manager (view/upload/edit/delete) + history logs. NO user management.
  ADMIN  — user management only. NO file manager access, NO history.
  EDITOR — file manager (view/upload/edit/delete). NO users, NO history.
  VIEWER — file manager read-only (view/download/print if allowed). NO write actions.
"""


def is_admin(user) -> bool:
    """True if the user's role is ADMIN (the user-management role, no file access)."""
    return getattr(user, "role", None) == "ADMIN"


# ---------------------------------------------------------------------------
# File-manager access guards
# ---------------------------------------------------------------------------

def can_access_docs(user) -> bool:
    """
    OWNER, EDITOR and VIEWER may access the file manager.
    ADMIN may not — they are a user-management role only.
    """
    return getattr(user, "role", None) in ("OWNER", "EDITOR", "VIEWER")


def can_manage_structure(user) -> bool:
    """Only OWNER and EDITOR can create/delete folders, groups, vaults."""
    return getattr(user, "role", None) in ("OWNER", "EDITOR")


def can_upload_documents(user) -> bool:
    """Only OWNER and EDITOR can upload documents."""
    return getattr(user, "role", None) in ("OWNER", "EDITOR")


def can_manage_permissions(user) -> bool:
    """Only OWNER and EDITOR can manage document access permissions."""
    return getattr(user, "role", None) in ("OWNER", "EDITOR")


def can_delete_documents(user) -> bool:
    """Only OWNER and EDITOR can delete documents (subject to per-doc flag)."""
    return getattr(user, "role", None) in ("OWNER", "EDITOR")


def can_view_document(user, document) -> bool:
    """
    Check if user can view a specific document.
    ADMIN cannot view any document.
    OWNER and EDITOR can see everything.
    VIEWER can see documents they own, untagged docs, or docs whose tag matches
    their profession_tag.
    """
    if is_admin(user):
        return False

    # OWNER and EDITOR can see everything
    if user.role in ("OWNER", "EDITOR"):
        return True

    # VIEWER rules below
    # User can always see their own documents
    if document.owner_id == user.id:
        return True

    # Untagged documents are visible to everyone in the org
    doc_tags = document.get_tags_list()
    if not doc_tags:
        return True

    # Tagged docs: user's profession_tag must match at least one tag
    if user.profession_tag:
        user_tag = user.profession_tag.strip().lower()
        for doc_tag in doc_tags:
            if doc_tag.lower() == user_tag:
                return True

    return False


def can_print_document(user, document) -> bool:
    """
    OWNER and EDITOR can always print.
    VIEWER needs can_view AND the doc's can_be_printed flag.
    ADMIN cannot print.
    """
    if is_admin(user):
        return False
    if user.role in ("OWNER", "EDITOR"):
        return True
    # VIEWER
    if not getattr(document, "can_be_printed", True):
        return False
    return can_view_document(user, document)


def can_download_document(user, document) -> bool:
    """
    OWNER and EDITOR can always download.
    VIEWER can download if they can view the document.
    ADMIN cannot download.
    """
    if is_admin(user):
        return False
    if user.role in ("OWNER", "EDITOR"):
        return True
    return can_view_document(user, document)


def can_move_document(user, document) -> bool:
    """
    Only OWNER and EDITOR may move a document (and only if can_be_moved flag is set).
    VIEWER cannot move. ADMIN cannot move.
    """
    if user.role not in ("OWNER", "EDITOR"):
        return False
    return getattr(document, "can_be_moved", True)


def can_delete_document(user, document) -> bool:
    """
    Only OWNER and EDITOR may delete a document (and only if can_be_deleted flag is set).
    VIEWER cannot delete. ADMIN cannot delete.
    """
    if user.role not in ("OWNER", "EDITOR"):
        return False
    return getattr(document, "can_be_deleted", True)


def can_rename_document(user, document) -> bool:
    """Only OWNER and EDITOR can rename documents. VIEWER and ADMIN cannot."""
    return getattr(user, "role", None) in ("OWNER", "EDITOR")


def can_copy_document(user, document) -> bool:
    """Only OWNER and EDITOR can copy documents. VIEWER and ADMIN cannot."""
    return getattr(user, "role", None) in ("OWNER", "EDITOR")


def can_change_privacy(user, document) -> bool:
    """Only OWNER and EDITOR can change access tags / privacy. VIEWER and ADMIN cannot."""
    return getattr(user, "role", None) in ("OWNER", "EDITOR")


def can_upload_version(user, document) -> bool:
    """Only OWNER and EDITOR can upload new versions. VIEWER and ADMIN cannot."""
    return getattr(user, "role", None) in ("OWNER", "EDITOR")


# ---------------------------------------------------------------------------
# Administration guards
# ---------------------------------------------------------------------------

def can_manage_users(user) -> bool:
    """
    Only ADMIN can manage users (create, edit, reset password, suspend/delete).
    OWNER cannot manage users — they have history access instead.
    """
    return getattr(user, "role", None) == "ADMIN"


def can_view_logs(user) -> bool:
    """Only OWNER can view org-level activity history. ADMIN cannot."""
    return getattr(user, "role", None) == "OWNER"


def can_view_dashboard(user) -> bool:
    """OWNER and ADMIN can view the org dashboard (if one exists)."""
    return getattr(user, "role", None) in ("OWNER", "ADMIN")


# ---------------------------------------------------------------------------
# Queryset helpers
# ---------------------------------------------------------------------------

def get_user_accessible_documents(user, queryset):
    """
    Filter a documents queryset to only those the user can access.
    ADMIN gets nothing; OWNER/EDITOR get everything; VIEWER gets filtered set.
    """
    from django.db.models import Q

    if is_admin(user):
        return queryset.none()

    if user.role in ("OWNER", "EDITOR"):
        return queryset

    # VIEWER: own docs + untagged docs + docs tagged with their profession_tag
    conditions = Q(owner=user) | Q(access_tags="")
    if user.profession_tag:
        user_tag = user.profession_tag.strip().lower()
        conditions |= Q(access_tags__icontains=user_tag)

    return queryset.filter(conditions)


def get_available_tags(organization) -> list:
    """
    Return a sorted list of tag strings available within the organization,
    combining user profession tags with a set of common document tags.
    """
    from accounts.models import User

    tags = set()
    for u in User.objects.filter(organization=organization):
        if u.profession_tag:
            tag = u.profession_tag.strip()
            if tag:
                tags.add(tag)

    common_tags = [
        "finance", "hr", "executive", "sales",
        "marketing", "it", "operations", "legal",
    ]
    tags.update(common_tags)
    return sorted(tags)