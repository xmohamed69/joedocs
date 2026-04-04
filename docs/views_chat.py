# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# docs/views_chat.py  —  drop this file in your docs/ app
#
# Wire in docs/urls.py:
#   from .views_chat import org_chat_page, org_chat_api
#   path('ai/chat/',      org_chat_page, name='org_chat_page'),
#   path('ai/chat/send/', org_chat_api,  name='org_chat'),

import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.shortcuts import render

from .ai import org_chat, ai_enabled_for_user, _extract_text_from_file


def _user_can_see_document(user, doc):
    if doc.is_deleted:
        return False
    if doc.vault is not None:
        return False  # never leak vault contents into chatbot
    if doc.organization_id != user.organization_id:
        return False
    return True


def _build_context(user):
    from .models import Document, Folder, FolderGroup, Vault

    org = getattr(user, 'organization', None)
    if not org:
        return "", "", 0, 0

    org_lines = [f"Organisation: {org.name} (ID: {org.org_id})"]
    if hasattr(org, 'plan') and org.plan:
        org_lines.append(f"Plan: {org.plan.name}")

    groups = FolderGroup.objects.filter(organization=org)
    if groups.exists():
        org_lines.append("Folder groups: " + ", ".join(g.name for g in groups))

    folders = Folder.objects.filter(organization=org).select_related('group', 'parent')
    folder_count = folders.count()
    if folders.exists():
        folder_lines = []
        for f in folders[:40]:
            parent_str = f" inside '{f.parent.name}'" if f.parent else ""
            folder_lines.append(f"  - [{f.group.name}] {f.name}{parent_str}")
        org_lines.append("Folders:\n" + "\n".join(folder_lines))

    vaults = Vault.objects.filter(organization=org)
    if vaults.exists():
        org_lines.append(
            f"Secure vaults ({vaults.count()}): " +
            ", ".join(v.name for v in vaults) +
            " - vault contents are private and not shown here."
        )

    org_context = "\n".join(org_lines)

    documents = (
        Document.objects
        .filter(organization=org, is_deleted=False, vault__isnull=True)
        .select_related('folder', 'owner')
        .prefetch_related('versions')
        .order_by('-created_at')
    )
    doc_count = documents.count()
    doc_lines = []

    for doc in documents[:50]:
        if not _user_can_see_document(user, doc):
            continue
        parts = [f'"{doc.title}"']
        if doc.folder:
            parts.append(f"folder: {doc.folder.name}")
        if doc.access_tags:
            parts.append(f"tags: {doc.access_tags}")
        if doc.owner:
            parts.append(f"owner: {doc.owner.get_full_name() or doc.owner.username}")

        content_snippet = ""
        latest = doc.versions.order_by('-version').first()
        if latest and hasattr(latest, 'file') and latest.file:
            try:
                content_snippet = _extract_text_from_file(latest.file.path, max_chars=600)
                content_snippet = " ".join(content_snippet.split())
            except Exception:
                pass

        line = "  - " + " | ".join(parts)
        if content_snippet:
            line += f"\n    Content preview: {content_snippet[:400]}"
        doc_lines.append(line)

    doc_context = (
        f"Documents accessible to this user ({len(doc_lines)}):\n" + "\n".join(doc_lines)
        if doc_lines else "No documents found."
    )

    return org_context, doc_context, doc_count, folder_count


@login_required
@ensure_csrf_cookie
def org_chat_page(request):
    _, _, doc_count, folder_count = _build_context(request.user)
    return render(request, 'docs/chat.html', {
        'doc_count': doc_count,
        'folder_count': folder_count,
        'ai_enabled': ai_enabled_for_user(request.user),
    })


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def org_chat_api(request):
    if not ai_enabled_for_user(request.user):
        return JsonResponse({'error': 'AI not enabled for your account.'}, status=403)

    try:
        body = json.loads(request.body)
        messages = body.get('messages', [])
        if not messages or not isinstance(messages, list):
            raise ValueError("messages must be a non-empty list")
        if messages[-1].get('role') != 'user':
            raise ValueError("Last message must be from the user")
    except (json.JSONDecodeError, ValueError) as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    org_context, doc_context, _, _ = _build_context(request.user)

    try:
        reply = org_chat(
            messages=messages,
            org_context=org_context,
            doc_context=doc_context,
            user=request.user,
        )
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=500)

    return JsonResponse({'reply': reply})