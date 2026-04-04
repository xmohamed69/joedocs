# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.shortcuts import redirect, render, get_object_or_404
from django.db import transaction
from django.contrib import messages
from django.conf import settings

import os
import subprocess
import tempfile
import csv as csv_mod
import html as html_mod

from .models import FolderGroup, Folder, Vault, Document, DocumentVersion
from .storage import get_org_storage_usage_mb
from .logging import log
from .permissions import (
    can_view_document,
    get_user_accessible_documents,
    get_available_tags,
    can_print_document,
    can_move_document,
    can_delete_document,
)
from django.utils.translation import gettext_lazy as _


# ============ HELPER FUNCTIONS ============

def _deny_admin_docs(user) -> bool:
    """ADMIN must not see docs at all."""
    return getattr(user, "role", None) == "ADMIN"


def _can_manage(user):
    """Only OWNER and EDITOR can manage structure"""
    return getattr(user, "role", None) in ("OWNER", "EDITOR")


def _can_upload(user):
    """Only OWNER and EDITOR can upload documents"""
    return getattr(user, "role", None) in ("OWNER", "EDITOR")


def _check_vault_access(request, vaultid):
    """Check if user has access to vault in session"""
    return request.session.get(f'vault_access_{vaultid}', False)


def _check_organization(request):
    """
    Check if user has an organization.
    Returns None if OK, or a redirect response if not.
    """
    if not request.user.organization:
        logout(request)
        messages.error(request, "You are not associated with any organization.")
        return redirect("accounts:login")
    return None


def _build_folder_tree(folders):
    """Build hierarchical folder tree for sidebar"""
    root_folders = []
    folder_dict = {f.id: {'folder': f, 'children': []} for f in folders}

    for folder in folders:
        if folder.parent_id:
            if folder.parent_id in folder_dict:
                folder_dict[folder.parent_id]['children'].append(folder)
        else:
            root_folders.append(folder)

    return root_folders


# ============ LIBREOFFICE PREVIEW HELPERS ============

MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB

# Supported file extensions
OFFICE_EXTENSIONS = {
    '.doc', '.docx',           # Word
    '.xls', '.xlsx',           # Excel
    '.ppt', '.pptx',           # PowerPoint
    '.odt', '.ods', '.odp',    # OpenDocument
    '.rtf',                    # Rich Text
}

TEXT_EXTENSIONS = {
    '.txt', '.md', '.log', '.rst', 
    '.json', '.xml', '.yaml', '.yml',
    '.py', '.js', '.css', '.html', '.htm',
    '.java', '.c', '.cpp', '.h', '.hpp',
    '.sh', '.bash', '.sql', '.ini', '.cfg',
}

IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', 
    '.bmp', '.webp', '.svg',
}


def _get_libreoffice_path() -> str | None:
    """Get the LibreOffice executable path."""
    # Check settings first
    soffice = getattr(
        settings,
        'LIBREOFFICE_PATH',
        None
    )
    
    if soffice and os.path.exists(soffice):
        return soffice
    
    # Check common paths
    common_paths = [
        # Windows
        r'C:\Program Files\LibreOffice\program\soffice.exe',
        r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
        # Linux
        '/usr/bin/soffice',
        '/usr/bin/libreoffice',
        '/usr/local/bin/soffice',
        '/usr/local/bin/libreoffice',
        # macOS
        '/Applications/LibreOffice.app/Contents/MacOS/soffice',
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    return None


def _convert_to_pdf_with_libreoffice(file_path: str) -> str | None:
    """
    Convert a document to PDF using LibreOffice.
    Returns the path to the cached PDF, or None if conversion failed.
    """
    cache_pdf = file_path + '.preview.pdf'
    
    # Return cached version if exists
    if os.path.exists(cache_pdf):
        return cache_pdf
    
    soffice = _get_libreoffice_path()
    
    if not soffice:
        return None
    
    try:
        out_dir = os.path.dirname(file_path)
        
        # Run LibreOffice conversion
        result = subprocess.run(
            [
                soffice,
                '--headless',
                '--invisible',
                '--nologo',
                '--nofirststartwizard',
                '--convert-to', 'pdf',
                '--outdir', out_dir,
                file_path
            ],
            timeout=120,  # 2 minutes for large files
            capture_output=True,
            cwd=out_dir,
        )
        
        # LibreOffice outputs <basename>.pdf in out_dir
        base = os.path.splitext(os.path.basename(file_path))[0]
        generated = os.path.join(out_dir, base + '.pdf')
        
        if os.path.exists(generated):
            # Rename to our cache name to avoid conflicts
            os.rename(generated, cache_pdf)
            return cache_pdf
            
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass
    
    return None


def _convert_to_text_with_libreoffice(file_path: str) -> str | None:
    """
    Convert a document to plain text using LibreOffice.
    Returns the extracted text, or None if conversion failed.
    Used for AI summarization of Office documents.
    """
    soffice = _get_libreoffice_path()
    
    if not soffice:
        return None
    
    try:
        out_dir = os.path.dirname(file_path)
        
        result = subprocess.run(
            [
                soffice,
                '--headless',
                '--invisible',
                '--nologo',
                '--nofirststartwizard',
                '--convert-to', 'txt:Text',
                '--outdir', out_dir,
                file_path
            ],
            timeout=60,
            capture_output=True,
            cwd=out_dir,
        )
        
        base = os.path.splitext(os.path.basename(file_path))[0]
        txt_path = os.path.join(out_dir, base + '.txt')
        
        if os.path.exists(txt_path):
            with open(txt_path, 'r', encoding='utf-8', errors='ignore') as fh:
                text = fh.read()
            
            # Clean up the temp file
            try:
                os.unlink(txt_path)
            except Exception:
                pass
            
            return text
            
    except Exception:
        pass
    
    return None


def _get_libreoffice_error_html(ext: str, reason: str = "not_configured") -> str:
    """Generate user-friendly error HTML for LibreOffice issues."""
    
    if reason == "not_configured":
        return f'''
        <div style="text-align:center;padding:48px 24px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
            <div style="font-size:48px;margin-bottom:16px;">📄</div>
            <p style="font-size:14px;color:#555;margin-bottom:8px;">
                <strong>LibreOffice is not configured.</strong>
            </p>
            <p style="font-size:13px;color:#999;max-width:400px;margin:0 auto;">
                To preview <code>{html_mod.escape(ext)}</code> files, install LibreOffice and set 
                <code>LIBREOFFICE_PATH</code> in your <code>.env</code> file.
            </p>
            <div style="margin-top:24px;">
                <a href="https://www.libreoffice.org/download/download/" 
                   target="_blank"
                   style="color:#0066cc;font-size:13px;">
                    Download LibreOffice →
                </a>
            </div>
        </div>
        '''
    
    elif reason == "conversion_failed":
        return f'''
        <div style="text-align:center;padding:48px 24px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
            <div style="font-size:48px;margin-bottom:16px;">⚠️</div>
            <p style="font-size:14px;color:#555;margin-bottom:8px;">
                <strong>Preview generation failed.</strong>
            </p>
            <p style="font-size:13px;color:#999;max-width:400px;margin:0 auto;">
                LibreOffice could not convert this <code>{html_mod.escape(ext)}</code> file. 
                The file may be corrupted or password-protected. 
                Please download it directly.
            </p>
        </div>
        '''
    
    return '<p style="color:#999;">Preview not available.</p>'


def _render_csv_preview(file_path: str) -> str:
    """Render CSV as HTML table (LibreOffice not needed for CSV)."""
    try:
        rows = []
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            # Try to detect delimiter
            sample = f.read(4096)
            f.seek(0)
            
            try:
                dialect = csv_mod.Sniffer().sniff(sample, delimiters=',;\t|')
            except csv_mod.Error:
                dialect = csv_mod.excel
            
            reader = csv_mod.reader(f, dialect)
            for i, row in enumerate(reader):
                if i > 500:
                    break
                rows.append(row)
        
        if not rows:
            return '<p style="color:#999;">Empty CSV file.</p>'
        
        parts = ['<div style="overflow-x:auto;">']
        parts.append('<table style="border-collapse:collapse;font-size:12px;min-width:100%;">')
        
        for ri, row in enumerate(rows):
            tag = "th" if ri == 0 else "td"
            bg = "#f5f5f5" if ri == 0 else ("" if ri % 2 == 0 else "#fafafa")
            row_style = f'background:{bg};' if bg else ""
            parts.append(f'<tr style="{row_style}">')
            
            for cell in row:
                cell_style = (
                    "padding:6px 10px;border:1px solid #e0e0e0;"
                    "white-space:nowrap;max-width:300px;overflow:hidden;text-overflow:ellipsis;"
                )
                if ri == 0:
                    cell_style += "font-weight:600;"
                parts.append(f'<{tag} style="{cell_style}">{html_mod.escape(str(cell))}</{tag}>')
            
            parts.append("</tr>")
        
        parts.append("</table></div>")
        
        if len(rows) >= 500:
            parts.append('<p style="font-size:11px;color:#bbb;margin-top:8px;">Showing first 500 rows.</p>')
        
        return "\n".join(parts)
        
    except Exception as e:
        return f'<p style="color:#c00;">Could not parse CSV: {html_mod.escape(str(e))}</p>'


def _render_text_preview(file_path: str, max_chars: int = 5000) -> str:
    """Render plain text files."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(max_chars)
        
        truncated = len(content) >= max_chars
        if truncated:
            content += "\n\n... (truncated)"
        
        escaped = html_mod.escape(content)
        return f'<pre style="white-space:pre-wrap;word-break:break-word;font-family:\'Consolas\',\'Monaco\',monospace;font-size:13px;line-height:1.5;margin:0;">{escaped}</pre>'
        
    except Exception as e:
        return f'<p style="color:#c00;">Could not read file: {html_mod.escape(str(e))}</p>'


def _wrap_html_response(body: str) -> HttpResponse:
    """Wrap HTML body in a complete HTML document."""
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        *, *::before, *::after {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 13px;
            color: #333;
            margin: 0;
            padding: 24px 28px;
            line-height: 1.6;
            background: #fff;
        }}
        table {{ border-collapse: collapse; }}
        pre {{ white-space: pre-wrap; word-break: break-word; }}
        code {{ 
            background: #f5f5f5; 
            padding: 2px 6px; 
            border-radius: 3px; 
            font-size: 12px;
        }}
    </style>
</head>
<body>
{body}
</body>
</html>"""
    return HttpResponse(full_html, content_type="text/html; charset=utf-8")


# ============ HOME / EXPLORER ============

@login_required
def home(request):
    """Windows Explorer-style home dashboard with search"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    org = request.user.organization

    # Get search query
    search_query = request.GET.get('q', '').strip()

    all_folders = Folder.objects.filter(organization=org).select_related('parent', 'group')
    folder_tree = _build_folder_tree(all_folders)

    root_folders = Folder.objects.filter(organization=org, parent=None)
    
    # Base document queryset
    if search_query:
        # Search across all documents in organization
        documents = Document.objects.filter(
            organization=org,
            is_deleted=False
        ).filter(
            Q(title__icontains=search_query) | Q(access_tags__icontains=search_query)
        )
    else:
        # Show only root-level documents (not in folders or vaults)
        documents = Document.objects.filter(
            organization=org,
            folder=None,
            vault=None,
            is_deleted=False
        )
    
    # Apply access control
    documents = get_user_accessible_documents(request.user, documents)

    vaults = Vault.objects.filter(organization=org)

    storage_used_mb, storage_limit_mb, storage_percent = get_org_storage_usage_mb(org)

    return render(request, "docs/home.html", {
        "current_folder": None,
        "current_vault": None,
        "folder_tree": folder_tree,
        "folders": root_folders,
        "documents": documents,
        "vaults": vaults,
        "can_upload": _can_upload(request.user),
        "can_manage": _can_manage(request.user),
        "search_query": search_query,
        "storage_used_mb": storage_used_mb,
        "storage_limit_mb": storage_limit_mb,
        "storage_percent": storage_percent,
    })


@login_required
def folder_view(request, folderid):
    """View contents of a specific folder with search"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    org = request.user.organization
    current_folder = get_object_or_404(Folder, pk=folderid, organization=org)

    # Get search query
    search_query = request.GET.get('q', '').strip()

    all_folders = Folder.objects.filter(organization=org).select_related('parent', 'group')
    folder_tree = _build_folder_tree(all_folders)

    folders = Folder.objects.filter(organization=org, parent=current_folder)
    
    # Base document queryset
    if search_query:
        # Search only within current folder
        documents = Document.objects.filter(
            organization=org,
            folder=current_folder,
            is_deleted=False
        ).filter(
            Q(title__icontains=search_query) | Q(access_tags__icontains=search_query)
        )
    else:
        documents = Document.objects.filter(
            organization=org,
            folder=current_folder,
            is_deleted=False
        )
    
    # Apply access control
    documents = get_user_accessible_documents(request.user, documents)

    vaults = Vault.objects.filter(organization=org)

    storage_used_mb, storage_limit_mb, storage_percent = get_org_storage_usage_mb(org)

    return render(request, "docs/home.html", {
        "current_folder": current_folder,
        "current_vault": None,
        "folder_tree": folder_tree,
        "folders": folders,
        "documents": documents,
        "vaults": vaults,
        "can_upload": _can_upload(request.user),
        "can_manage": _can_manage(request.user),
        "search_query": search_query,
        "storage_used_mb": storage_used_mb,
        "storage_limit_mb": storage_limit_mb,
        "storage_percent": storage_percent,
    })


# ============ DOCUMENT OPERATIONS ============

@login_required
def upload(request):
    """Document upload - ONLY for EDITOR and OWNER"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    org = request.user.organization

    if not _can_upload(request.user):
        return HttpResponseForbidden("Only Editors and Owners can upload documents.")

    if request.method == "GET":
        folders = Folder.objects.filter(organization=org)
        vaults = Vault.objects.filter(organization=org)
        available_tags = get_available_tags(org)
        storage_used_mb, storage_limit_mb, storage_percent = get_org_storage_usage_mb(org)

        return render(request, "docs/upload.html", {
            "folders": folders,
            "vaults": vaults,
            "available_tags": available_tags,
            "storage_used_mb": storage_used_mb,
            "storage_limit_mb": storage_limit_mb,
            "storage_percent": storage_percent,
        })

    # POST handling
    title = (request.POST.get("title") or "").strip()
    folder_id = request.POST.get("folder_id") or None
    vault_id = request.POST.get("vault_id") or None
    uploaded_file = request.FILES.get("file")
    access_tags = request.POST.get("access_tags", "").strip()
    
    # Per-document action flags (checkbox present = True, absent = False)
    flag_can_be_printed = "can_be_printed" in request.POST
    flag_can_be_moved = "can_be_moved" in request.POST
    flag_can_be_deleted = "can_be_deleted" in request.POST

    # File is required
    if not uploaded_file:
        folders = Folder.objects.filter(organization=org)
        vaults = Vault.objects.filter(organization=org)
        available_tags = get_available_tags(org)

        storage_used_mb, storage_limit_mb, storage_percent = get_org_storage_usage_mb(org)
        return render(request, "docs/upload.html", {
            "folders": folders,
            "vaults": vaults,
            "available_tags": available_tags,
            "error": "File is required.",
            "storage_used_mb": storage_used_mb,
            "storage_limit_mb": storage_limit_mb,
            "storage_percent": storage_percent,
        })

    # File size check
    if uploaded_file.size > MAX_UPLOAD_BYTES:
        folders = Folder.objects.filter(organization=org)
        vaults = Vault.objects.filter(organization=org)
        available_tags = get_available_tags(org)
        storage_used_mb, storage_limit_mb, storage_percent = get_org_storage_usage_mb(org)
        return render(request, "docs/upload.html", {
            "folders": folders,
            "vaults": vaults,
            "available_tags": available_tags,
            "error": "File exceeds the 500 MB maximum upload size.",
            "storage_used_mb": storage_used_mb,
            "storage_limit_mb": storage_limit_mb,
            "storage_percent": storage_percent,
        })

    # ------------------------------------------------------------------ #
    # AI: title suggestion + auto-folder selection (single metadata call) #
    # ------------------------------------------------------------------ #
    from .ai import ai_enabled_for_user, suggest_metadata, choose_destination_folder

    ai_enabled = ai_enabled_for_user(request.user)

    # Run metadata suggestion once; reuse for both title and folder logic
    ai_metadata = None
    if ai_enabled:
        tmp_path = None
        try:
            suffix = os.path.splitext(uploaded_file.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                for chunk in uploaded_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name
            uploaded_file.seek(0)  # reset so Django can still save the file
            ai_metadata = suggest_metadata(tmp_path, uploaded_file.name)
        except Exception:
            uploaded_file.seek(0)
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    # Track whether user left title blank (drives post-save AI refinement)
    title_was_empty = not bool(title)

    # Fill title if the user left it blank
    if not title:
        if ai_metadata:
            title = ai_metadata.get('suggested_title') or ''
            # Also pre-fill access_tags if user left them blank
            if not access_tags and ai_metadata.get('suggested_tags'):
                access_tags = ai_metadata['suggested_tags']
        if not title:
            title = os.path.splitext(uploaded_file.name)[0]
            title = title.replace('_', ' ').replace('-', ' ').title()

    # Resolve folder: user choice takes priority; AI auto-assigns only when
    # no folder was selected AND the user has permission to manage structure.
    folder = None
    if folder_id:
        folder = get_object_or_404(Folder, pk=folder_id, organization=org)
    elif ai_enabled and _can_manage(request.user):
        suggested_tags_str = (ai_metadata.get('suggested_tags') if ai_metadata else None) or access_tags or ''
        try:
            folder = choose_destination_folder(org, request.user, uploaded_file.name, suggested_tags_str)
            messages.info(request, f"AI placed this document in '{folder.group.name} / {folder.name}'.")
        except Exception:
            folder = None  # fall back to no folder silently

    vault = None
    if vault_id:
        vault = get_object_or_404(Vault, pk=vault_id, organization=org)

    doc = Document.objects.create(
        organization=org,
        folder=folder,
        vault=vault,
        title=title,
        owner=request.user,
        access_tags=access_tags,
        can_be_printed=flag_can_be_printed,
        can_be_moved=flag_can_be_moved,
        can_be_deleted=flag_can_be_deleted,
    )

    DocumentVersion.objects.create(
        document=doc,
        version=1,
        file=uploaded_file,
        file_size=uploaded_file.size,
        uploaded_by=request.user,
    )

    # ------------------------------------------------------------------ #
    # Post-save AI title refinement: now the file is on disk, re-run AI  #
    # with the real file path so it reads actual content, not filename.  #
    # ------------------------------------------------------------------ #
    if title_was_empty and ai_enabled:
        try:
            saved_version = doc.versions.order_by('-version').first()
            if saved_version and saved_version.file:
                real_path = saved_version.file.path
                refined = suggest_metadata(real_path, uploaded_file.name)
                refined_title = (refined.get('suggested_title') or '').strip()

                # Only apply if AI returned something meaningful — not blank,
                # and not just a reformatted version of the filename
                filename_base = os.path.splitext(uploaded_file.name)[0].lower().strip()
                refined_lower = refined_title.lower().strip()
                is_just_filename = (
                    refined_lower == filename_base
                    or refined_lower == filename_base.replace('_', ' ').replace('-', ' ')
                )
                if refined_title and not is_just_filename:
                    doc.title = refined_title
                    doc.save(update_fields=['title'])
                    title = refined_title  # keep in sync for the success message

                # Also update tags from content-aware pass if user left them blank
                if not access_tags and refined.get('suggested_tags'):
                    doc.access_tags = refined['suggested_tags']
                    doc.save(update_fields=['access_tags'])
        except Exception:
            pass  # never block the upload on AI failure

    log(org, request.user, "DOC_UPLOAD", target_type="Document", target_id=doc.id, title=title)
    messages.success(request, f"Document '{title}' uploaded successfully!")

    return redirect("docs:document_detail", docid=doc.id)


@login_required
def document_detail(request, docid):
    """Document detail view with AI summarization support"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    org = request.user.organization
    doc = get_object_or_404(Document, pk=docid, organization=org, is_deleted=False)

    if not can_view_document(request.user, doc):
        return HttpResponseForbidden("You don't have permission to view this document.")

    if doc.vault and not _check_vault_access(request, doc.vault.id):
        return redirect("docs:vault_access", vaultid=doc.vault.id)

    # Handle AI summarization request (legacy POST method - prefer AJAX endpoint)
    summary = None
    if request.method == "POST" and request.POST.get("action") == "summarize":
        from .ai import ai_enabled_for_user, summarize_document_text
        
        if ai_enabled_for_user(request.user):
            # Build text to summarize
            text_parts = [doc.title]
            
            if doc.access_tags:
                text_parts.append(f"Tags: {doc.access_tags}")
            
            if doc.folder:
                text_parts.append(f"Located in folder: {doc.folder.name}")
            
            if doc.vault:
                text_parts.append(f"Stored in secure vault: {doc.vault.name}")
            
            text_to_summarize = ". ".join(text_parts)
            summary = summarize_document_text(text_to_summarize)
        else:
            summary = "AI is not enabled for your account or plan."

    versions = doc.versions.all().order_by('-version')
    latest_version = versions.first() if versions else None

    all_folders = Folder.objects.filter(organization=org)
    all_vaults = Vault.objects.filter(organization=org)
    available_tags = get_available_tags(org)

    # Check if AI is enabled for this user
    from .ai import ai_enabled_for_user
    ai_enabled = ai_enabled_for_user(request.user)

    # Determine preview type from file extension
    preview_type = "none"
    preview_text = ""
    preview_error = False  # True when LibreOffice conversion is known to fail

    if latest_version:
        ext = os.path.splitext(latest_version.file.name)[1].lower()

        if ext == ".pdf":
            preview_type = "pdf"
        elif ext in IMAGE_EXTENSIONS:
            preview_type = "image"
        elif ext in TEXT_EXTENSIONS:
            preview_type = "text"
            try:
                with open(latest_version.file.path, "r", encoding="utf-8", errors="ignore") as fh:
                    preview_text = fh.read(5000)
            except Exception:
                preview_text = ""
        elif ext in OFFICE_EXTENSIONS or ext == '.csv':
            # For Office formats attempt a pre-flight conversion so the detail
            # page can show a clean "not available" banner instead of a broken
            # iframe — this is especially important for legacy .doc files.
            # CSV never needs LibreOffice so skip the pre-flight for it.
            preview_type = "office"
            if ext in OFFICE_EXTENSIONS:
                pdf_path = _convert_to_pdf_with_libreoffice(latest_version.file.path)
                if not pdf_path:
                    preview_error = True
        else:
            preview_type = "none"

    # Per-document action permission flags for template
    user_can_print = can_print_document(request.user, doc)
    user_can_move = can_move_document(request.user, doc)
    user_can_delete = can_delete_document(request.user, doc)

    return render(request, "docs/document_detail.html", {
        "document": doc,
        "versions": versions,
        "latest_version": latest_version,
        "can_edit": request.user.role in ("OWNER", "EDITOR"),
        "all_folders": all_folders,
        "all_vaults": all_vaults,
        "available_tags": available_tags,
        "summary": summary,
        "ai_enabled": ai_enabled,
        "preview_type": preview_type,
        "preview_text": preview_text,
        "preview_error": preview_error,
        "user_can_print": user_can_print,
        "user_can_move": user_can_move,
        "user_can_delete": user_can_delete,
    })


@login_required
def document_rename(request, docid):
    """Rename a document"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    org = request.user.organization
    doc = get_object_or_404(Document, pk=docid, organization=org, is_deleted=False)

    if request.user.role not in ("OWNER", "EDITOR"):
        return HttpResponseForbidden("Only Editors and Owners can rename documents.")

    if request.method == "POST":
        new_title = (request.POST.get("title") or "").strip()
        if new_title:
            doc.title = new_title
            doc.save()
            log(org, request.user, "DOC_RENAME", target_type="Document", target_id=doc.id)
            messages.success(request, "Document renamed!")

    return redirect("docs:document_detail", docid=doc.id)


@login_required
def document_move(request, docid):
    """Move a document to different folder/vault"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    org = request.user.organization
    doc = get_object_or_404(Document, pk=docid, organization=org, is_deleted=False)

    if request.user.role not in ("OWNER", "EDITOR"):
        return HttpResponseForbidden("Only Editors and Owners can move documents.")

    # Check document-level permission
    if not can_move_document(request.user, doc):
        return HttpResponseForbidden("This document cannot be moved.")

    if request.method == "POST":
        folder_id = request.POST.get("folder_id") or None
        vault_id = request.POST.get("vault_id") or None

        doc.folder = get_object_or_404(Folder, pk=folder_id, organization=org) if folder_id else None
        doc.vault = get_object_or_404(Vault, pk=vault_id, organization=org) if vault_id else None
        doc.save()

        log(org, request.user, "DOC_MOVE", target_type="Document", target_id=doc.id)
        messages.success(request, "Document moved!")

    return redirect("docs:document_detail", docid=doc.id)


@login_required
def document_copy(request, docid):
    """Copy a document"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    org = request.user.organization
    doc = get_object_or_404(Document, pk=docid, organization=org, is_deleted=False)

    if request.user.role not in ("OWNER", "EDITOR"):
        return HttpResponseForbidden("Only Editors and Owners can copy documents.")

    with transaction.atomic():
        new_doc = Document.objects.create(
            organization=org,
            folder=doc.folder,
            vault=doc.vault,
            title=f"{doc.title} (Copy)",
            owner=request.user,
            access_tags=doc.access_tags,
            can_be_printed=doc.can_be_printed,
            can_be_moved=doc.can_be_moved,
            can_be_deleted=doc.can_be_deleted,
        )

        for version in doc.versions.all():
            DocumentVersion.objects.create(
                document=new_doc,
                version=version.version,
                file=version.file,
                file_size=version.file_size,
                uploaded_by=request.user,
            )

        log(org, request.user, "DOC_COPY", target_type="Document", target_id=new_doc.id)
        messages.success(request, "Document copied!")

    return redirect("docs:document_detail", docid=new_doc.id)


@login_required
def document_delete(request, docid):
    """Soft delete a document"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    org = request.user.organization
    doc = get_object_or_404(Document, pk=docid, organization=org, is_deleted=False)

    if request.user.role not in ("OWNER", "EDITOR"):
        return HttpResponseForbidden("Only Editors and Owners can delete documents.")

    # Check document-level permission
    if not can_delete_document(request.user, doc):
        return HttpResponseForbidden("This document cannot be deleted.")

    if request.method == "POST":
        doc.is_deleted = True
        doc.save()
        log(org, request.user, "DOC_DELETE", target_type="Document", target_id=doc.id)
        messages.success(request, "Document deleted!")
        return redirect("docs:home")

    return redirect("docs:document_detail", docid=docid)


@login_required
def document_update_privacy(request, docid):
    """Update document access tags/privacy"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    org = request.user.organization
    doc = get_object_or_404(Document, pk=docid, organization=org, is_deleted=False)

    if request.user.role not in ("OWNER", "EDITOR"):
        return HttpResponseForbidden("Only Editors and Owners can update privacy.")

    if request.method == "POST":
        doc.access_tags = request.POST.get("access_tags", "").strip()
        doc.save()
        log(org, request.user, "DOC_PRIVACY_UPDATE", target_type="Document", target_id=doc.id)
        messages.success(request, "Privacy settings updated!")

    return redirect("docs:document_detail", docid=doc.id)


@login_required
def document_upload_version(request, docid):
    """Upload a new version of a document"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    org = request.user.organization
    doc = get_object_or_404(Document, pk=docid, organization=org, is_deleted=False)

    if request.user.role not in ("OWNER", "EDITOR"):
        return HttpResponseForbidden("Only Editors and Owners can upload versions.")

    if request.method == "GET":
        return render(request, "docs/document_upload_version.html", {"document": doc})

    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return render(request, "docs/document_upload_version.html", {
            "document": doc,
            "error": "File is required.",
        })

    if uploaded_file.size > MAX_UPLOAD_BYTES:
        return render(request, "docs/document_upload_version.html", {
            "document": doc,
            "error": "File exceeds the 500 MB maximum upload size.",
        })

    latest = doc.versions.order_by("-version").first()
    next_version = (latest.version + 1) if latest else 1

    DocumentVersion.objects.create(
        document=doc,
        version=next_version,
        file=uploaded_file,
        file_size=uploaded_file.size,
        uploaded_by=request.user,
    )

    log(org, request.user, "DOC_VERSION_UPLOAD", target_type="Document", target_id=doc.id)
    messages.success(request, f"Version {next_version} uploaded!")
    return redirect("docs:document_detail", docid=doc.id)


# ============ VAULT OPERATIONS ============

@login_required
def vault_access(request, vaultid):
    """Access a secure vault with PIN"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    org = request.user.organization
    vault = get_object_or_404(Vault, pk=vaultid, organization=org)

    if _check_vault_access(request, vaultid):
        return redirect("docs:vault_documents", vaultid=vaultid)

    if request.method == "GET":
        return render(request, "docs/vault_access.html", {"vault": vault})

    pin = request.POST.get("pin", "").strip()

    if vault.verify_pin(pin):
        request.session[f'vault_access_{vaultid}'] = True
        log(org, request.user, "VAULT_ACCESS", target_type="Vault", target_id=vault.id)
        messages.success(request, "Vault unlocked!")
        return redirect("docs:vault_documents", vaultid=vaultid)
    else:
        log(org, request.user, "VAULT_ACCESS_FAILED", target_type="Vault", target_id=vault.id)
        return render(request, "docs/vault_access.html", {
            "vault": vault,
            "error": "Invalid PIN."
        })


@login_required
def vault_documents(request, vaultid):
    """View documents in a vault"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    org = request.user.organization
    vault = get_object_or_404(Vault, pk=vaultid, organization=org)

    if not _check_vault_access(request, vaultid):
        return redirect("docs:vault_access", vaultid=vaultid)

    # Get search query
    search_query = request.GET.get('q', '').strip()

    all_folders = Folder.objects.filter(organization=org).select_related('parent', 'group')
    folder_tree = _build_folder_tree(all_folders)

    # Base document queryset
    documents = Document.objects.filter(organization=org, vault=vault, is_deleted=False)
    
    # Apply search filter if query exists
    if search_query:
        documents = documents.filter(
            Q(title__icontains=search_query) | Q(access_tags__icontains=search_query)
        )
    
    # Apply access control
    documents = get_user_accessible_documents(request.user, documents)

    vaults = Vault.objects.filter(organization=org)

    storage_used_mb, storage_limit_mb, storage_percent = get_org_storage_usage_mb(org)

    return render(request, "docs/home.html", {
        "current_folder": None,
        "current_vault": vault,
        "folder_tree": folder_tree,
        "folders": [],
        "documents": documents,
        "vaults": vaults,
        "can_upload": _can_upload(request.user),
        "can_manage": _can_manage(request.user),
        "search_query": search_query,
        "storage_used_mb": storage_used_mb,
        "storage_limit_mb": storage_limit_mb,
        "storage_percent": storage_percent,
    })


@login_required
def vault_reset_pin(request, vaultid):
    """Reset vault PIN - ONLY OWNER"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    org = request.user.organization
    vault = get_object_or_404(Vault, pk=vaultid, organization=org)

    if request.user.role != "OWNER":
        return HttpResponseForbidden("Only Owners can reset vault PINs.")

    if request.method == "GET":
        return render(request, "docs/vault_reset_pin.html", {"vault": vault})

    new_pin = request.POST.get("new_pin", "").strip()
    confirm_pin = request.POST.get("confirm_pin", "").strip()

    errors = []
    if not new_pin or len(new_pin) != 6 or not new_pin.isdigit():
        errors.append("PIN must be exactly 6 digits.")
    if new_pin != confirm_pin:
        errors.append("PINs do not match.")

    if errors:
        return render(request, "docs/vault_reset_pin.html", {
            "vault": vault,
            "errors": errors,
        })

    vault.pin_code = new_pin
    vault.save()

    request.session.pop(f'vault_access_{vaultid}', None)

    log(org, request.user, "VAULT_PIN_RESET", target_type="Vault", target_id=vault.id)
    messages.success(request, "Vault PIN reset successfully!")
    return redirect("docs:manage")


@login_required
def vault_delete(request, vaultid):
    """Delete a vault"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    if not _can_manage(request.user):
        return HttpResponseForbidden()

    org = request.user.organization
    vault = get_object_or_404(Vault, pk=vaultid, organization=org)

    if request.method == "POST":
        name = vault.name
        vault.delete()
        log(org, request.user, "VAULT_DELETED", target_type="Vault", name=name)
        messages.success(request, "Vault deleted!")

    return redirect("docs:manage")


# ============ STRUCTURE MANAGEMENT ============

@login_required
def manage(request):
    """Manage folders, groups, and vaults"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    if not _can_manage(request.user):
        return HttpResponseForbidden("Only Editors and Owners can manage structure.")

    org = request.user.organization
    groups = FolderGroup.objects.filter(organization=org)
    folders = Folder.objects.filter(organization=org, parent=None)
    vaults = Vault.objects.filter(organization=org)

    return render(request, "docs/manage.html", {
        "groups": groups,
        "folders": folders,
        "vaults": vaults,
        "is_owner": request.user.role == "OWNER",
    })


@login_required
def group_create(request):
    """Create a folder group"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    if not _can_manage(request.user):
        return HttpResponseForbidden()

    org = request.user.organization

    if request.method == "GET":
        return render(request, "docs/group_create.html")

    name = (request.POST.get("name") or "").strip()
    if not name:
        return render(request, "docs/group_create.html", {"error": "Name required."})

    FolderGroup.objects.create(organization=org, name=name)
    log(org, request.user, "GROUP_CREATED", target_type="FolderGroup", name=name)
    messages.success(request, f"Group '{name}' created!")
    return redirect("docs:manage")


@login_required
def group_delete(request, groupid):
    """Delete a folder group"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    if not _can_manage(request.user):
        return HttpResponseForbidden()

    org = request.user.organization
    group = get_object_or_404(FolderGroup, pk=groupid, organization=org)

    if request.method == "POST":
        name = group.name
        group.delete()
        log(org, request.user, "GROUP_DELETED", target_type="FolderGroup", name=name)
        messages.success(request, "Group deleted!")

    return redirect("docs:manage")


@login_required
def folder_create(request):
    """Create a folder"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    if not _can_manage(request.user):
        return HttpResponseForbidden()

    org = request.user.organization

    if request.method == "GET":
        groups = FolderGroup.objects.filter(organization=org)
        parents = Folder.objects.filter(organization=org)
        return render(request, "docs/folder_create.html", {
            "groups": groups,
            "parents": parents
        })

    name = (request.POST.get("name") or "").strip()
    group_id = request.POST.get("group_id")
    parent_id = request.POST.get("parent_id") or None

    if not name or not group_id:
        groups = FolderGroup.objects.filter(organization=org)
        parents = Folder.objects.filter(organization=org)
        return render(request, "docs/folder_create.html", {
            "groups": groups,
            "parents": parents,
            "error": "Name and group required."
        })

    group = get_object_or_404(FolderGroup, pk=group_id, organization=org)
    parent = get_object_or_404(Folder, pk=parent_id, organization=org) if parent_id else None

    Folder.objects.create(organization=org, group=group, parent=parent, name=name)
    log(org, request.user, "FOLDER_CREATED", target_type="Folder", name=name, group=group.name)
    messages.success(request, f"Folder '{name}' created!")
    return redirect("docs:manage")


@login_required
def folder_delete(request, folderid):
    """Delete a folder"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    if not _can_manage(request.user):
        return HttpResponseForbidden()

    org = request.user.organization
    folder = get_object_or_404(Folder, pk=folderid, organization=org)

    if request.method == "POST":
        name = folder.name
        folder.delete()
        log(org, request.user, "FOLDER_DELETED", target_type="Folder", name=name)
        messages.success(request, "Folder deleted!")

    return redirect("docs:manage")


@login_required
def vault_create(request):
    """Create a secure vault"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    if not _can_manage(request.user):
        return HttpResponseForbidden()

    org = request.user.organization

    if request.method == "GET":
        return render(request, "docs/vault_create.html")

    name = (request.POST.get("name") or "").strip()
    description = (request.POST.get("description") or "").strip()
    pin_code = (request.POST.get("pin_code") or "").strip()

    errors = []
    if not name:
        errors.append("Vault name required.")
    if not pin_code or len(pin_code) != 6 or not pin_code.isdigit():
        errors.append("PIN must be exactly 6 digits.")

    if errors:
        return render(request, "docs/vault_create.html", {
            "errors": errors,
            "name": name,
            "description": description
        })

    Vault.objects.create(
        organization=org,
        name=name,
        description=description,
        pin_code=pin_code
    )
    log(org, request.user, "VAULT_CREATED", target_type="Vault", name=name)
    messages.success(request, f"Vault '{name}' created!")
    return redirect("docs:manage")


# ============ AI AJAX ENDPOINTS ============

@login_required
def ai_suggest_title(request):
    """
    AJAX endpoint: accepts a file upload, returns AI-suggested title and tags.
    Called from the upload form when user clicks 'Suggest with AI'.
    """
    from .ai import ai_enabled_for_user, suggest_metadata

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    if not ai_enabled_for_user(request.user):
        return JsonResponse({"error": "AI not enabled for your account"}, status=403)

    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return JsonResponse({"error": "No file provided"}, status=400)

    if uploaded_file.size > MAX_UPLOAD_BYTES:
        return JsonResponse({"error": "File exceeds the 500 MB maximum upload size."}, status=413)

    suffix = os.path.splitext(uploaded_file.name)[1]
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        metadata = suggest_metadata(tmp_path, uploaded_file.name)
        return JsonResponse({
            "suggested_title": metadata.get("suggested_title", ""),
            "suggested_tags": metadata.get("suggested_tags", ""),
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


@login_required
def ai_summarize_document(request, docid):
    """
    AJAX endpoint: returns AI summary for a document.
    Called automatically when document_detail page loads (if AI enabled).
    """
    from .ai import ai_enabled_for_user, summarize_document_text

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    org_check = _check_organization(request)
    if org_check:
        return JsonResponse({"error": "No organization"}, status=403)

    org = request.user.organization
    doc = get_object_or_404(Document, pk=docid, organization=org, is_deleted=False)

    if not can_view_document(request.user, doc):
        return JsonResponse({"error": "Permission denied"}, status=403)

    if not ai_enabled_for_user(request.user):
        return JsonResponse({"error": "AI not enabled for your account"}, status=403)

    latest_version = doc.versions.order_by("-version").first()
    text_to_summarize = ""

    if latest_version and latest_version.file:
        file_path = latest_version.file.path
        ext = os.path.splitext(file_path)[1].lower()

        # For Office documents, convert to text using LibreOffice
        if ext in OFFICE_EXTENSIONS:
            text_to_summarize = _convert_to_text_with_libreoffice(file_path) or ""
            if text_to_summarize:
                text_to_summarize = text_to_summarize[:3000]  # Limit length
        elif ext in TEXT_EXTENSIONS:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as fh:
                    text_to_summarize = fh.read(3000)
            except Exception:
                pass
        elif ext == '.csv':
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as fh:
                    text_to_summarize = fh.read(3000)
            except Exception:
                pass
        else:
            # Try the AI extraction function as fallback
            try:
                from .ai import _extract_text_from_file
                text_to_summarize = _extract_text_from_file(file_path, max_chars=3000)
            except Exception:
                pass

    # Fallback to metadata if no text extracted
    if not text_to_summarize:
        text_parts = [f"Document title: {doc.title}"]
        if doc.access_tags:
            text_parts.append(f"Tags: {doc.access_tags}")
        if doc.folder:
            text_parts.append(f"Located in folder: {doc.folder.name}")
        if doc.vault:
            text_parts.append(f"Stored in secure vault: {doc.vault.name}")
        text_to_summarize = ". ".join(text_parts)

    summary = summarize_document_text(text_to_summarize)
    return JsonResponse({"summary": summary})


# ============ DOCUMENT RENDER PREVIEW ============

@login_required
@xframe_options_sameorigin
def document_render_preview(request, version_id):
    """
    Renders a server-side preview for documents.
    - Office documents (doc, docx, xls, xlsx, ppt, pptx, odt, etc.): Converted to PDF via LibreOffice
    - CSV: Rendered as HTML table
    - Text files: Rendered as preformatted text
    - Images: Returned directly
    - PDF: Returned directly
    
    Returns content suitable for embedding in an iframe.
    """
    version = get_object_or_404(DocumentVersion, pk=version_id)
    doc = version.document

    # ── Auth checks ─────────────────────────────────────────────────────────
    org_check = _check_organization(request)
    if org_check:
        return HttpResponseForbidden("No organization.")
    
    if doc.organization != request.user.organization:
        return HttpResponseForbidden("Access denied.")
    
    if not can_view_document(request.user, doc):
        return HttpResponseForbidden("Permission denied.")
    
    if doc.vault and not _check_vault_access(request, doc.vault.id):
        return HttpResponseForbidden("Vault access required.")

    # ── Determine file type ─────────────────────────────────────────────────
    file_path = version.file.path
    ext = os.path.splitext(file_path)[1].lower()

    # ── Handle Office documents via LibreOffice ─────────────────────────────
    if ext in OFFICE_EXTENSIONS:
        pdf_path = _convert_to_pdf_with_libreoffice(file_path)
        
        if pdf_path and os.path.exists(pdf_path):
            # Serve the PDF directly - browser will render it
            with open(pdf_path, 'rb') as pdf_fh:
                pdf_bytes = pdf_fh.read()
            return HttpResponse(pdf_bytes, content_type='application/pdf')
        
        # Conversion failed - check why
        soffice = _get_libreoffice_path()
        
        if not soffice:
            html_body = _get_libreoffice_error_html(ext, "not_configured")
        else:
            html_body = _get_libreoffice_error_html(ext, "conversion_failed")
        
        return _wrap_html_response(html_body)

    # ── Handle CSV (render as table, no LibreOffice needed) ─────────────────
    elif ext == '.csv':
        html_body = _render_csv_preview(file_path)
        return _wrap_html_response(html_body)

    # ── Handle text files ───────────────────────────────────────────────────
    elif ext in TEXT_EXTENSIONS:
        html_body = _render_text_preview(file_path)
        return _wrap_html_response(html_body)

    # ── Handle images (return image directly) ───────────────────────────────
    elif ext in IMAGE_EXTENSIONS:
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml',
        }
        try:
            with open(file_path, 'rb') as f:
                return HttpResponse(
                    f.read(), 
                    content_type=content_types.get(ext, 'application/octet-stream')
                )
        except Exception:
            return _wrap_html_response('<p style="color:#c00;">Could not load image.</p>')

    # ── Handle PDF (return directly) ────────────────────────────────────────
    elif ext == '.pdf':
        try:
            with open(file_path, 'rb') as f:
                return HttpResponse(f.read(), content_type='application/pdf')
        except Exception:
            return _wrap_html_response('<p style="color:#c00;">Could not load PDF.</p>')

    # ── Unsupported format ──────────────────────────────────────────────────
    else:
        html_body = f'''
        <div style="text-align:center;padding:48px 24px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
            <div style="font-size:48px;margin-bottom:16px;">📁</div>
            <p style="font-size:14px;color:#555;margin-bottom:8px;">
                <strong>Preview not available</strong>
            </p>
            <p style="font-size:13px;color:#999;">
                <code>{html_mod.escape(ext)}</code> files cannot be previewed. Please download the file to view it.
            </p>
        </div>
        '''
        return _wrap_html_response(html_body)


# ============ UTILITY VIEWS ============

@login_required
def document_download(request, version_id):
    """Download a specific version of a document"""
    from django.http import FileResponse
    
    version = get_object_or_404(DocumentVersion, pk=version_id)
    doc = version.document

    # Auth checks
    org_check = _check_organization(request)
    if org_check:
        return HttpResponseForbidden("No organization.")
    
    if doc.organization != request.user.organization:
        return HttpResponseForbidden("Access denied.")
    
    if not can_view_document(request.user, doc):
        return HttpResponseForbidden("Permission denied.")
    
    if doc.vault and not _check_vault_access(request, doc.vault.id):
        return HttpResponseForbidden("Vault access required.")

    # Get filename
    filename = os.path.basename(version.file.name)
    
    # Log download
    log(
        doc.organization, 
        request.user, 
        "DOC_DOWNLOAD", 
        target_type="Document", 
        target_id=doc.id,
        version=version.version
    )

    # Return file
    response = FileResponse(
        version.file.open('rb'),
        as_attachment=True,
        filename=filename
    )
    return response


@login_required
def document_print(request, docid):
    """Print a document (opens printable view)"""
    org_check = _check_organization(request)
    if org_check:
        return org_check

    if _deny_admin_docs(request.user):
        return HttpResponseForbidden("Admins cannot access documents.")

    org = request.user.organization
    doc = get_object_or_404(Document, pk=docid, organization=org, is_deleted=False)

    if not can_view_document(request.user, doc):
        return HttpResponseForbidden("Permission denied.")

    if not can_print_document(request.user, doc):
        return HttpResponseForbidden("This document cannot be printed.")

    if doc.vault and not _check_vault_access(request, doc.vault.id):
        return redirect("docs:vault_access", vaultid=doc.vault.id)

    latest_version = doc.versions.order_by("-version").first()
    
    if not latest_version:
        messages.error(request, "No document version available.")
        return redirect("docs:document_detail", docid=docid)

    # Log print action
    log(org, request.user, "DOC_PRINT", target_type="Document", target_id=doc.id)

    # For Office documents, convert to PDF and redirect
    ext = os.path.splitext(latest_version.file.name)[1].lower()
    
    if ext in OFFICE_EXTENSIONS:
        pdf_path = _convert_to_pdf_with_libreoffice(latest_version.file.path)
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'inline; filename="{doc.title}.pdf"'
                return response
    
    # For other files, just return the file inline
    response = HttpResponse(
        latest_version.file.open('rb').read(),
        content_type='application/octet-stream'
    )
    response['Content-Disposition'] = f'inline; filename="{os.path.basename(latest_version.file.name)}"'
    return response