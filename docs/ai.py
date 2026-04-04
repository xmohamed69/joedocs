# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
"""
docs/ai.py - AI layer for JoeDocs

This module provides AI functionality with configurable backends.
Supports stub implementations (default) or real AI services (OpenAI, Anthropic, etc.)
"""

import os
import requests  # NEW: required for Groq HTTP calls
from typing import Dict, Optional
from django.conf import settings
from django.core.cache import cache


def _extract_text_from_file(file_path: str, max_chars: int = 1500) -> str:
    """
    Extract plain text from a file based on its extension.
    Supports: .txt .md .csv .html .xml .json .yaml .docx .xlsx .pdf
    Falls back to raw UTF-8 read for unknown text-like formats.
    Returns empty string if extraction fails or file is unreadable.
    """
    if not file_path or not os.path.exists(file_path):
        return ""

    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    try:
        # Word documents
        if ext == ".docx":
            try:
                from docx import Document as DocxDocument
                doc = DocxDocument(file_path)
                text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
                return text[:max_chars]
            except ImportError:
                pass  # python-docx not installed, fall through

        # Excel spreadsheets
        if ext in (".xlsx", ".xls"):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
                rows = []
                for sheet in wb.worksheets:
                    for row in sheet.iter_rows(values_only=True):
                        line = " | ".join(str(c) for c in row if c is not None)
                        if line.strip():
                            rows.append(line)
                        if sum(len(r) for r in rows) >= max_chars:
                            break
                return "\n".join(rows)[:max_chars]
            except ImportError:
                pass  # openpyxl not installed, fall through

        # PDF
        if ext == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(file_path)
                pages_text = []
                for page in reader.pages:
                    pages_text.append(page.extract_text() or "")
                    if sum(len(t) for t in pages_text) >= max_chars:
                        break
                return "\n".join(pages_text)[:max_chars]
            except ImportError:
                pass  # pypdf not installed, fall through

        # Plain text / markup formats
        BINARY_EXTENSIONS = {".docx", ".xlsx", ".xls", ".pdf",
                              ".png", ".jpg", ".jpeg", ".gif",
                              ".mp4", ".mp3", ".zip", ".rar"}
        if ext not in BINARY_EXTENSIONS:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(max_chars)

    except Exception:
        pass

    return ""


def suggest_metadata(file_path: Optional[str], filename: str) -> Dict[str, str]:
    """
    Suggest metadata (title, tags) based on the filename.
    
    This function respects the AI_SERVICE setting and can use:
    - 'stub': Local implementation (no external calls)
    - 'openai': OpenAI API
    - 'anthropic': Anthropic Claude API
    - 'custom': Your custom implementation
    
    Args:
        file_path: Path to the file (used by real AI services)
        filename: Name of the file
        
    Returns:
        Dictionary with 'suggested_title' and 'suggested_tags'
    """
    # Check if feature is enabled
    if not getattr(settings, 'AI_ENABLE_METADATA_SUGGESTIONS', True):
        return _fallback_metadata(filename)
    
    # Check cache first (if caching is enabled)
    if getattr(settings, 'AI_CACHE_RESULTS', False):
        cache_key = f'ai_metadata_{filename}'
        cached = cache.get(cache_key)
        if cached:
            return cached
    
    # Get AI service type
    ai_service = getattr(settings, 'AI_SERVICE', 'stub').lower()
    
    if ai_service == 'stub':
        result = _stub_suggest_metadata(file_path, filename)
    elif ai_service == 'openai':
        result = _openai_suggest_metadata(file_path, filename)
    elif ai_service == 'anthropic':
        result = _anthropic_suggest_metadata(file_path, filename)
    elif ai_service == 'groq':                                      # NEW
        result = _groq_suggest_metadata(file_path, filename)        # NEW
    elif ai_service == 'gemini':
        result = _gemini_suggest_metadata(file_path, filename)
    elif ai_service == 'custom':
        result = _custom_suggest_metadata(file_path, filename)
    else:
        # Unknown service, fall back to stub
        result = _stub_suggest_metadata(file_path, filename)
    
    # Cache the result if enabled
    if getattr(settings, 'AI_CACHE_RESULTS', False):
        cache_ttl = getattr(settings, 'AI_CACHE_TTL', 3600)
        cache.set(cache_key, result, cache_ttl)
    
    return result


def summarize_document_text(text: str) -> str:
    """
    Generate a summary of the document text.
    
    Respects AI_SERVICE setting for different backends.
    
    Args:
        text: The text to summarize
        
    Returns:
        A summary string
    """
    # Check if feature is enabled
    if not getattr(settings, 'AI_ENABLE_SUMMARIZATION', True):
        return "Summarization is currently disabled."
    
    # Check cache first
    if getattr(settings, 'AI_CACHE_RESULTS', False):
        cache_key = f'ai_summary_{hash(text)}'
        cached = cache.get(cache_key)
        if cached:
            return cached
    
    # Get AI service type
    ai_service = getattr(settings, 'AI_SERVICE', 'stub').lower()
    
    if ai_service == 'stub':
        result = _stub_summarize(text)
    elif ai_service == 'openai':
        result = _openai_summarize(text)
    elif ai_service == 'anthropic':
        result = _anthropic_summarize(text)
    elif ai_service == 'groq':              # NEW
        result = _groq_summarize(text)      # NEW
    elif ai_service == 'gemini':
        result = _gemini_summarize(text)
    elif ai_service == 'custom':
        result = _custom_summarize(text)
    else:
        result = _stub_summarize(text)
    
    # Cache the result if enabled
    if getattr(settings, 'AI_CACHE_RESULTS', False):
        cache_ttl = getattr(settings, 'AI_CACHE_TTL', 3600)
        cache.set(cache_key, result, cache_ttl)
    
    return result


def ai_enabled_for_user(user) -> bool:
    """
    Check if AI features are enabled for a specific user.
    
    This checks both the organization's plan and the user's individual AI permission.
    
    Args:
        user: The User model instance
        
    Returns:
        True if AI is enabled for this user, False otherwise
    """
    # Check if user has an organization
    if not hasattr(user, 'organization') or not user.organization:
        return False
    
    # Check if user has can_use_ai permission
    if not getattr(user, 'can_use_ai', False):
        return False
    
    # Check if the organization's plan has AI enabled
    org = user.organization
    if not org.plan:
        return False
    
    # Check the plan's ai_enabled field
    if not getattr(org.plan, 'ai_enabled', False):
        return False
    
    return True


# ============================================================================
# STUB IMPLEMENTATIONS (Local, no external API calls)
# ============================================================================

def _fallback_metadata(filename: str) -> Dict[str, str]:
    """Simple fallback when AI is disabled"""
    base_name = os.path.splitext(filename)[0]
    title = base_name.replace('_', ' ').replace('-', ' ').title()
    return {
        'suggested_title': title,
        'suggested_tags': ''
    }


def _stub_suggest_metadata(file_path: Optional[str], filename: str) -> Dict[str, str]:
    """
    Stub implementation: derives title and tags from filename + file content snippet.
    No external API calls.
    """
    # Remove file extension
    base_name = os.path.splitext(filename)[0]

    # Convert underscores and hyphens to spaces
    title = base_name.replace('_', ' ').replace('-', ' ')

    # Capitalize words appropriately
    title = title.title()

    # Pull a content snippet to improve tag heuristics (best-effort)
    content_snippet = ""
    if file_path:
        try:
            content_snippet = _extract_text_from_file(file_path, max_chars=500).lower()
        except Exception:
            pass

    # Combine filename and content for tag signals
    suggested_tags = []
    lower_name = filename.lower()
    signals = lower_name + " " + content_snippet
    
    # Common document type patterns (checked against both filename and content)
    if any(word in signals for word in ['report', 'quarterly', 'annual', 'financial']):
        suggested_tags.append('report')
    if any(word in signals for word in ['invoice', 'receipt', 'billing']):
        suggested_tags.append('finance')
    if any(word in signals for word in ['contract', 'agreement', 'legal']):
        suggested_tags.append('legal')
    if any(word in signals for word in ['hr', 'employee', 'hiring', 'onboarding']):
        suggested_tags.append('hr')
    if any(word in signals for word in ['memo', 'minutes', 'meeting']):
        suggested_tags.append('memo')
    if any(word in signals for word in ['confidential', 'private', 'secret']):
        suggested_tags.append('confidential')

    # Year detection for tags
    for year in range(2020, 2030):
        if str(year) in filename:
            suggested_tags.append(str(year))
            break
    
    return {
        'suggested_title': title,
        'suggested_tags': ', '.join(suggested_tags) if suggested_tags else ''
    }


def _stub_summarize(text: str) -> str:
    """
    Stub implementation: formal truncation-based executive summary.
    No external API calls.
    """
    max_length = 300

    cleaned = " ".join(text.split())  # normalise whitespace
    if len(cleaned) <= max_length:
        return f"Executive Summary: {cleaned}"

    snippet = cleaned[:max_length].rsplit(' ', 1)[0]  # break at word boundary
    return f"Executive Summary: {snippet}..."


# ============================================================================
# OPENAI IMPLEMENTATIONS (Requires openai package and API key)
# ============================================================================

def _openai_suggest_metadata(file_path: Optional[str], filename: str) -> Dict[str, str]:
    """
    OpenAI implementation for metadata suggestion.
    
    To use this:
    1. pip install openai
    2. Set AI_SERVICE='openai' in settings
    3. Set OPENAI_API_KEY in environment
    """
    try:
        import openai
        
        openai.api_key = getattr(settings, 'OPENAI_API_KEY', '')
        if not openai.api_key:
            return _stub_suggest_metadata(file_path, filename)
        
        content_preview = _extract_text_from_file(file_path, max_chars=1000) if file_path else ""

        prompt = f"""Analyze this document and suggest a concise title and relevant tags.
Detect the language of the content and respond in that same language.

Filename: {filename}
Content preview: {content_preview[:800] if content_preview else 'Not available'}

Respond in this format (in the document's language):
Title: [suggested title]
Tags: [comma-separated tags]"""
        
        response = openai.ChatCompletion.create(
            model=getattr(settings, 'AI_MODEL', 'gpt-4'),
            messages=[
                {"role": "system", "content": "You are a document metadata assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=getattr(settings, 'AI_MAX_TOKENS', 150),
            temperature=getattr(settings, 'AI_TEMPERATURE', 0.7),
            timeout=getattr(settings, 'AI_REQUEST_TIMEOUT', 30)
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Parse the response
        lines = result_text.split('\n')
        title = ""
        tags = ""
        
        for line in lines:
            if line.startswith('Title:'):
                title = line.replace('Title:', '').strip()
            elif line.startswith('Tags:'):
                tags = line.replace('Tags:', '').strip()
        
        return {
            'suggested_title': title or _fallback_metadata(filename)['suggested_title'],
            'suggested_tags': tags
        }
        
    except Exception as e:
        print(f"OpenAI API error: {e}")
        # Fall back to stub on error
        return _stub_suggest_metadata(file_path, filename)


def _openai_summarize(text: str) -> str:
    """OpenAI implementation for summarization"""
    try:
        import openai
        
        openai.api_key = getattr(settings, 'OPENAI_API_KEY', '')
        if not openai.api_key:
            return _stub_summarize(text)
        
        response = openai.ChatCompletion.create(
            model=getattr(settings, 'AI_MODEL', 'gpt-4'),
            messages=[
                {"role": "system", "content": "You are a document summarization assistant. Provide concise, informative summaries."},
                {"role": "user", "content": f"Summarize this document in 2-3 sentences:\n\n{text[:2000]}"}
            ],
            max_tokens=getattr(settings, 'AI_MAX_TOKENS', 150),
            temperature=getattr(settings, 'AI_TEMPERATURE', 0.7),
            timeout=getattr(settings, 'AI_REQUEST_TIMEOUT', 30)
        )
        
        summary = response.choices[0].message.content.strip()
        return f"Summary: {summary}"
        
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return _stub_summarize(text)


# ============================================================================
# ANTHROPIC IMPLEMENTATIONS (Requires anthropic package and API key)
# ============================================================================

def _anthropic_suggest_metadata(file_path: Optional[str], filename: str) -> Dict[str, str]:
    """
    Anthropic Claude implementation for metadata suggestion.
    
    To use this:
    1. pip install anthropic
    2. Set AI_SERVICE='anthropic' in settings
    3. Set ANTHROPIC_API_KEY in environment
    """
    try:
        import anthropic
        
        api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
        if not api_key:
            return _stub_suggest_metadata(file_path, filename)
        
        client = anthropic.Anthropic(api_key=api_key)
        
        content_preview = _extract_text_from_file(file_path, max_chars=1000) if file_path else ""

        prompt = f"""Analyze this document and suggest a concise title and relevant tags.
Detect the language of the content and respond in that same language.

Filename: {filename}
Content preview: {content_preview[:800] if content_preview else 'Not available'}

Respond in this format (in the document's language):
Title: [suggested title]
Tags: [comma-separated tags]"""
        
        message = client.messages.create(
            model=getattr(settings, 'AI_MODEL', 'claude-3-sonnet-20240229'),
            max_tokens=getattr(settings, 'AI_MAX_TOKENS', 150),
            messages=[{"role": "user", "content": prompt}]
        )
        
        result_text = message.content[0].text.strip()
        
        # Parse the response
        lines = result_text.split('\n')
        title = ""
        tags = ""
        
        for line in lines:
            if line.startswith('Title:'):
                title = line.replace('Title:', '').strip()
            elif line.startswith('Tags:'):
                tags = line.replace('Tags:', '').strip()
        
        return {
            'suggested_title': title or _fallback_metadata(filename)['suggested_title'],
            'suggested_tags': tags
        }
        
    except Exception as e:
        print(f"Anthropic API error: {e}")
        return _stub_suggest_metadata(file_path, filename)


def _anthropic_summarize(text: str) -> str:
    """Anthropic Claude implementation for summarization"""
    try:
        import anthropic
        
        api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
        if not api_key:
            return _stub_summarize(text)
        
        client = anthropic.Anthropic(api_key=api_key)
        
        message = client.messages.create(
            model=getattr(settings, 'AI_MODEL', 'claude-3-sonnet-20240229'),
            max_tokens=getattr(settings, 'AI_MAX_TOKENS', 150),
            messages=[{
                "role": "user",
                "content": f"Summarize this document in 2-3 sentences:\n\n{text[:2000]}"
            }]
        )
        
        summary = message.content[0].text.strip()
        return f"Summary: {summary}"
        
    except Exception as e:
        print(f"Anthropic API error: {e}")
        return _stub_summarize(text)


# ============================================================================
# GROQ IMPLEMENTATIONS (Uses requests; no extra package beyond 'requests')
# ============================================================================

def _groq_suggest_metadata(file_path: Optional[str], filename: str) -> Dict[str, str]:
    """
    Groq implementation for metadata suggestion.

    To use this:
    1. pip install requests
    2. Set AI_SERVICE='groq' in settings (or .env)
    3. Set GROQ_API_KEY in environment / .env
    4. Optionally set GROQ_API_BASE_URL and AI_MODEL
    """
    api_key = getattr(settings, 'GROQ_API_KEY', '')
    if not api_key:
        print("Groq API key missing – falling back to stub.")
        return _stub_suggest_metadata(file_path, filename)

    try:
        content_preview = _extract_text_from_file(file_path, max_chars=1000) if file_path else ""

        prompt = f"""You are a document analyst. Your job is to read the document content below and suggest a short, professional, human-readable title and relevant tags.

IMPORTANT RULES:
- Base the title on what the document is actually ABOUT, not just the filename.
- If the filename looks like a code or auto-generated name (e.g. "doc_20240101", "file_v2", "scan001"), ignore it entirely and derive the title from the content.
- The title should be concise (3-8 words), specific, and meaningful to a business reader.
- Detect the language of the content and respond in that same language.

Filename (for reference only): {filename}
Document content:
{content_preview[:1200] if content_preview else '(no content available — use filename as last resort)'}

Respond in this exact format (two lines only):
Title: [suggested title based on content]
Tags: [comma-separated tags]"""

        url = getattr(settings, 'GROQ_API_BASE_URL', 'https://api.groq.com/openai/v1/chat/completions')
        model = getattr(settings, 'AI_MODEL', 'llama-3.1-70b-versatile')
        timeout = getattr(settings, 'AI_REQUEST_TIMEOUT', 30)

        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a document metadata assistant."},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": getattr(settings, 'AI_MAX_TOKENS', 150),
                "temperature": getattr(settings, 'AI_TEMPERATURE', 0.7),
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()

        result_text = data["choices"][0]["message"]["content"].strip()

        title = ""
        tags = ""
        for line in result_text.split('\n'):
            if line.startswith('Title:'):
                title = line.replace('Title:', '').strip()
            elif line.startswith('Tags:'):
                tags = line.replace('Tags:', '').strip()

        return {
            'suggested_title': title or _fallback_metadata(filename)['suggested_title'],
            'suggested_tags': tags,
        }

    except Exception as e:
        print(f"Groq API error (suggest_metadata): {e}")
        return _stub_suggest_metadata(file_path, filename)


def _groq_summarize(text: str) -> str:
    """
    Groq implementation for document summarization.

    Falls back to stub if GROQ_API_KEY is missing or any error occurs.
    """
    api_key = getattr(settings, 'GROQ_API_KEY', '')
    if not api_key:
        print("Groq API key missing – falling back to stub.")
        return _stub_summarize(text)

    try:
        url = getattr(settings, 'GROQ_API_BASE_URL', 'https://api.groq.com/openai/v1/chat/completions')
        model = getattr(settings, 'AI_MODEL', 'llama-3.1-70b-versatile')
        timeout = getattr(settings, 'AI_REQUEST_TIMEOUT', 30)

        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a professional document analyst. "
                            "Produce formal, concise executive summaries suitable for business use. "
                            "Use clear, precise language. Avoid casual phrasing. "
                            "Always detect the language of the input and respond in that same language."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Write a formal executive summary of the following document in 2-3 sentences. "
                            f"Respond in the same language as the document. "
                            f"Begin your response with the words 'Executive Summary:'\n\n{text[:2000]}"
                        ),
                    },
                ],
                "max_tokens": getattr(settings, 'AI_MAX_TOKENS', 150),
                "temperature": getattr(settings, 'AI_TEMPERATURE', 0.7),
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()

        summary = data["choices"][0]["message"]["content"].strip()
        # Ensure consistent prefix regardless of model output variation
        if not summary.lower().startswith("executive summary"):
            summary = f"Executive Summary: {summary}"
        return summary

    except Exception as e:
        print(f"Groq API error (summarize): {e}")
        return _stub_summarize(text)


# ============================================================================
# GEMINI IMPLEMENTATIONS (Uses requests; no extra package beyond 'requests')
# ============================================================================

def _gemini_suggest_metadata(file_path: Optional[str], filename: str) -> Dict[str, str]:
    """
    Google Gemini implementation for metadata suggestion.

    To use this:
    1. Set AI_SERVICE='gemini' in .env
    2. Set GEMINI_API_KEY in .env
    3. Optionally set AI_MODEL (default: gemini-2.0-flash)
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        print("Gemini API key missing – falling back to stub.")
        return _stub_suggest_metadata(file_path, filename)

    try:
        content_preview = _extract_text_from_file(file_path, max_chars=1000) if file_path else ""
        model = getattr(settings, 'AI_MODEL', 'gemini-2.0-flash')
        timeout = getattr(settings, 'AI_REQUEST_TIMEOUT', 30)

        prompt = f"""You are a document analyst. Your job is to read the document content below and suggest a short, professional, human-readable title and relevant tags.

IMPORTANT RULES:
- Base the title on what the document is actually ABOUT, not just the filename.
- If the filename looks like a code or auto-generated name (e.g. "doc_20240101", "file_v2", "scan001"), ignore it entirely and derive the title from the content.
- The title should be concise (3-8 words), specific, and meaningful to a business reader.
- Detect the language of the content and respond in that same language.

Filename (for reference only): {filename}
Document content:
{content_preview[:1200] if content_preview else '(no content available — use filename as last resort)'}

Respond in this exact format (two lines only):
Title: [suggested title based on content]
Tags: [comma-separated tags]"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": getattr(settings, 'AI_MAX_TOKENS', 150),
                    "temperature": getattr(settings, 'AI_TEMPERATURE', 0.7),
                },
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()

        result_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()

        title = ""
        tags = ""
        for line in result_text.split('\n'):
            if line.startswith('Title:'):
                title = line.replace('Title:', '').strip()
            elif line.startswith('Tags:'):
                tags = line.replace('Tags:', '').strip()

        return {
            'suggested_title': title or _fallback_metadata(filename)['suggested_title'],
            'suggested_tags': tags,
        }

    except Exception as e:
        print(f"Gemini API error (suggest_metadata): {e}")
        return _stub_suggest_metadata(file_path, filename)


def _gemini_summarize(text: str) -> str:
    """
    Google Gemini implementation for document summarization.

    Falls back to stub if GEMINI_API_KEY is missing or any error occurs.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        print("Gemini API key missing – falling back to stub.")
        return _stub_summarize(text)

    try:
        model = getattr(settings, 'AI_MODEL', 'gemini-2.0-flash')
        timeout = getattr(settings, 'AI_REQUEST_TIMEOUT', 30)

        prompt = (
            "You are a professional document analyst. "
            "Write a formal executive summary of the following document in 2-3 sentences. "
            "Respond in the same language as the document. "
            "Begin your response with the words 'Executive Summary:'\n\n"
            f"{text[:2000]}"
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": getattr(settings, 'AI_MAX_TOKENS', 150),
                    "temperature": getattr(settings, 'AI_TEMPERATURE', 0.7),
                },
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()

        summary = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        if not summary.lower().startswith("executive summary"):
            summary = f"Executive Summary: {summary}"
        return summary

    except Exception as e:
        print(f"Gemini API error (summarize): {e}")
        return _stub_summarize(text)


# ============================================================================
# CUSTOM IMPLEMENTATIONS (Your own AI service)
# ============================================================================

def _custom_suggest_metadata(file_path: Optional[str], filename: str) -> Dict[str, str]:
    """
    Custom implementation placeholder.
    
    Implement your own AI service here.
    For example: your internal ML model, Azure OpenAI, etc.
    """
    # TODO: Implement your custom AI service
    # For now, fall back to stub
    return _stub_suggest_metadata(file_path, filename)


def _custom_summarize(text: str) -> str:
    """Custom summarization implementation placeholder"""
    # TODO: Implement your custom AI service
    return _stub_summarize(text)


# ============================================================================
# ORG CHATBOT  (chat with the organisation's docs / context)
# ============================================================================

def org_chat(
    messages: list,
    org_context: str = "",
    doc_context: str = "",
    user=None,
) -> str:
    """
    Conversational chatbot scoped to an organisation's documents and data.

    Args:
        messages:    List of dicts [{"role": "user"|"assistant", "content": "..."}]
                     The last item should be the user's latest message.
        org_context: Free-text description of the organisation (name, departments,
                     policies, etc.) injected into the system prompt.
        doc_context: Concatenated snippets from relevant documents retrieved for
                     the current query (e.g. from a vector search).
        user:        Optional User instance — used to gate access via
                     ai_enabled_for_user().

    Returns:
        The assistant's reply as a plain string.
        Falls back to a stub response if AI is disabled or an error occurs.
    """
    # Optional permission gate
    if user is not None and not ai_enabled_for_user(user):
        return (
            "AI features are not enabled for your account. "
            "Please contact your administrator."
        )

    if not getattr(settings, 'AI_ENABLE_ORG_CHATBOT', True):
        return "The organisation chatbot is currently disabled."

    ai_service = getattr(settings, 'AI_SERVICE', 'stub').lower()

    if ai_service == 'stub':
        return _stub_org_chat(messages, org_context, doc_context)
    elif ai_service == 'openai':
        return _openai_org_chat(messages, org_context, doc_context)
    elif ai_service == 'anthropic':
        return _anthropic_org_chat(messages, org_context, doc_context)
    elif ai_service == 'groq':
        return _groq_org_chat(messages, org_context, doc_context)
    elif ai_service == 'gemini':
        return _gemini_org_chat(messages, org_context, doc_context)
    else:
        return _stub_org_chat(messages, org_context, doc_context)


def _build_org_system_prompt(org_context: str, doc_context: str) -> str:
    """
    Assemble the system prompt that grounds the chatbot in org/doc knowledge.
    """
    parts = [
        "You are a helpful assistant for an organisation's document management system.",
        "Answer questions accurately and concisely based on the context provided.",
        "If the answer is not in the provided context, say so honestly — do not invent information.",
    ]
    if org_context:
        parts.append(f"\n## Organisation context\n{org_context}")
    if doc_context:
        parts.append(f"\n## Relevant document excerpts\n{doc_context}")
    return "\n".join(parts)


# ------------------------------------------------------------------
# Stub
# ------------------------------------------------------------------

def _stub_org_chat(messages: list, org_context: str, doc_context: str) -> str:
    """Stub: echoes the user's last message with a disclaimer."""
    last_user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user_msg = m.get("content", "")
            break
    return (
        f"[Stub mode] You asked: \"{last_user_msg}\". "
        "Configure a real AI_SERVICE in your settings to get proper answers."
    )


# ------------------------------------------------------------------
# OpenAI
# ------------------------------------------------------------------

def _openai_org_chat(messages: list, org_context: str, doc_context: str) -> str:
    """OpenAI implementation for the org chatbot."""
    try:
        import openai

        openai.api_key = getattr(settings, 'OPENAI_API_KEY', '')
        if not openai.api_key:
            return _stub_org_chat(messages, org_context, doc_context)

        system_prompt = _build_org_system_prompt(org_context, doc_context)
        api_messages = [{"role": "system", "content": system_prompt}] + messages

        response = openai.ChatCompletion.create(
            model=getattr(settings, 'AI_MODEL', 'gpt-4'),
            messages=api_messages,
            max_tokens=getattr(settings, 'AI_MAX_TOKENS', 512),
            temperature=getattr(settings, 'AI_TEMPERATURE', 0.5),
            timeout=getattr(settings, 'AI_REQUEST_TIMEOUT', 30),
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"OpenAI org_chat error: {e}")
        return _stub_org_chat(messages, org_context, doc_context)


# ------------------------------------------------------------------
# Anthropic
# ------------------------------------------------------------------

def _anthropic_org_chat(messages: list, org_context: str, doc_context: str) -> str:
    """Anthropic Claude implementation for the org chatbot."""
    try:
        import anthropic

        api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
        if not api_key:
            return _stub_org_chat(messages, org_context, doc_context)

        client = anthropic.Anthropic(api_key=api_key)
        system_prompt = _build_org_system_prompt(org_context, doc_context)

        message = client.messages.create(
            model=getattr(settings, 'AI_MODEL', 'claude-3-5-sonnet-20241022'),
            max_tokens=getattr(settings, 'AI_MAX_TOKENS', 512),
            system=system_prompt,
            messages=messages,
        )
        return message.content[0].text.strip()

    except Exception as e:
        print(f"Anthropic org_chat error: {e}")
        return _stub_org_chat(messages, org_context, doc_context)


# ------------------------------------------------------------------
# Groq
# ------------------------------------------------------------------

def _groq_org_chat(messages: list, org_context: str, doc_context: str) -> str:
    """Groq implementation for the org chatbot."""
    api_key = getattr(settings, 'GROQ_API_KEY', '')
    if not api_key:
        print("Groq API key missing – falling back to stub.")
        return _stub_org_chat(messages, org_context, doc_context)

    try:
        system_prompt = _build_org_system_prompt(org_context, doc_context)
        api_messages = [{"role": "system", "content": system_prompt}] + messages

        url = getattr(settings, 'GROQ_API_BASE_URL', 'https://api.groq.com/openai/v1/chat/completions')
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": getattr(settings, 'AI_MODEL', 'llama-3.1-70b-versatile'),
                "messages": api_messages,
                "max_tokens": getattr(settings, 'AI_MAX_TOKENS', 512),
                "temperature": getattr(settings, 'AI_TEMPERATURE', 0.5),
            },
            timeout=getattr(settings, 'AI_REQUEST_TIMEOUT', 30),
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print(f"Groq org_chat error: {e}")
        return _stub_org_chat(messages, org_context, doc_context)


# ------------------------------------------------------------------
# Gemini
# ------------------------------------------------------------------

def _gemini_org_chat(messages: list, org_context: str, doc_context: str) -> str:
    """Google Gemini implementation for the org chatbot."""
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        print("Gemini API key missing – falling back to stub.")
        return _stub_org_chat(messages, org_context, doc_context)

    try:
        system_prompt = _build_org_system_prompt(org_context, doc_context)

        # Gemini uses a flat "contents" list; prepend system as a user/model pair
        contents = [
            {"role": "user",   "parts": [{"text": system_prompt}]},
            {"role": "model",  "parts": [{"text": "Understood. I will answer based on the provided context."}]},
        ]
        for m in messages:
            role = "user" if m["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})

        model = getattr(settings, 'AI_MODEL', 'gemini-2.0-flash')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "contents": contents,
                "generationConfig": {
                    "maxOutputTokens": getattr(settings, 'AI_MAX_TOKENS', 512),
                    "temperature": getattr(settings, 'AI_TEMPERATURE', 0.5),
                },
            },
            timeout=getattr(settings, 'AI_REQUEST_TIMEOUT', 30),
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    except Exception as e:
        print(f"Gemini org_chat error: {e}")
        return _stub_org_chat(messages, org_context, doc_context)


# ============================================================================
# AUTO-ORGANIZATION HELPER
# ============================================================================

def choose_destination_folder(org, user, filename: str, suggested_tags_str: str):
    """
    Given a filename and AI-suggested tags, decide which FolderGroup + Folder
    the document belongs in, creating them if they don't exist yet.

    Heuristics (checked in order, first match wins):
      finance / invoice / receipt / billing / payment
          → group "Finance",  folder "Invoices"
      contract / legal / agreement / nda / compliance
          → group "Legal",    folder "Contracts"
      hr / employee / hiring / onboarding / payroll / staff
          → group "HR",       folder "Employees"
      report / quarterly / annual / audit / summary / analysis
          → group "Reports",  folder "Reports"
      project / proposal / plan / roadmap / milestone
          → group "Projects", folder "Plans"
      marketing / campaign / branding / advertising / promo
          → group "Marketing", folder "Campaigns"
      it / technical / spec / architecture / infrastructure
          → group "IT",       folder "Technical"
      default
          → group "General",  folder "Unsorted"

    Returns the Folder instance (newly created or existing).
    """
    from .models import FolderGroup, Folder

    tags = [t.strip().lower() for t in suggested_tags_str.split(',') if t.strip()]
    signals = set(tags) | {w for w in filename.lower().replace('_', ' ').replace('-', ' ').split()}

    # (keywords_set, group_name, folder_name)
    RULES = [
        ({"finance", "invoice", "receipt", "billing", "payment", "financial"}, "Finance",   "Invoices"),
        ({"contract", "legal", "agreement", "nda", "compliance", "law"},        "Legal",     "Contracts"),
        ({"hr", "employee", "hiring", "onboarding", "payroll", "staff", "recruitment"}, "HR", "Employees"),
        ({"report", "quarterly", "annual", "audit", "summary", "analysis"},     "Reports",   "Reports"),
        ({"project", "proposal", "plan", "roadmap", "milestone"},               "Projects",  "Plans"),
        ({"marketing", "campaign", "branding", "advertising", "promo"},         "Marketing", "Campaigns"),
        ({"it", "technical", "spec", "architecture", "infrastructure", "software"}, "IT",    "Technical"),
    ]

    group_name = "General"
    folder_name = "Unsorted"

    for keywords, g_name, f_name in RULES:
        if signals & keywords:  # any overlap → match
            group_name = g_name
            folder_name = f_name
            break

    group, _ = FolderGroup.objects.get_or_create(
        organization=org,
        name=group_name,
    )
    folder, _ = Folder.objects.get_or_create(
        organization=org,
        group=group,
        parent=None,
        name=folder_name,
    )
    return folder


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_ai_service_info() -> Dict[str, str]:
    """
    Get information about the current AI service configuration.
    Useful for admin dashboards.
    """
    ai_service = getattr(settings, 'AI_SERVICE', 'stub')
    
    info = {
        'service': ai_service,
        'metadata_enabled': getattr(settings, 'AI_ENABLE_METADATA_SUGGESTIONS', True),
        'summarization_enabled': getattr(settings, 'AI_ENABLE_SUMMARIZATION', True),
        'org_chatbot_enabled': getattr(settings, 'AI_ENABLE_ORG_CHATBOT', True),
        'caching_enabled': getattr(settings, 'AI_CACHE_RESULTS', False),
        'model': getattr(settings, 'AI_MODEL', 'N/A'),
    }
    
    if ai_service == 'stub':
        info['status'] = 'Using local stub implementations (no external API calls)'
    elif ai_service == 'openai':
        has_key = bool(getattr(settings, 'OPENAI_API_KEY', ''))
        info['status'] = 'OpenAI API configured' if has_key else 'OpenAI API key missing'
    elif ai_service == 'anthropic':
        has_key = bool(getattr(settings, 'ANTHROPIC_API_KEY', ''))
        info['status'] = 'Anthropic API configured' if has_key else 'Anthropic API key missing'
    elif ai_service == 'groq':                                          # NEW
        has_key = bool(getattr(settings, 'GROQ_API_KEY', ''))          # NEW
        info['status'] = 'Groq API configured' if has_key else 'Groq API key missing'  # NEW
    elif ai_service == 'gemini':
        has_key = bool(getattr(settings, 'GEMINI_API_KEY', ''))
        info['status'] = 'Gemini API configured' if has_key else 'Gemini API key missing'
    else:
        info['status'] = f'Unknown service: {ai_service}'
    
    return info