# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
from django.urls import path
from . import views
from .views_chat import org_chat_page, org_chat_api

app_name = "docs"

urlpatterns = [
    # Home/Explorer
    path("", views.home, name="home"),
    path("folder/<int:folderid>/", views.folder_view, name="folder_view"),

    # Document operations
    path("upload/", views.upload, name="upload"),
    path("document/<int:docid>/", views.document_detail, name="document_detail"),
    path(
        "document/<int:docid>/upload/",
        views.document_upload_version,
        name="document_upload_version",
    ),
    path("document/<int:docid>/rename/", views.document_rename, name="document_rename"),
    path("document/<int:docid>/move/", views.document_move, name="document_move"),
    path("document/<int:docid>/copy/", views.document_copy, name="document_copy"),
    path("document/<int:docid>/delete/", views.document_delete, name="document_delete"),
    path(
        "document/<int:docid>/privacy/",
        views.document_update_privacy,
        name="document_update_privacy",
    ),

    # Vault operations
    path("vault/<int:vaultid>/access/", views.vault_access, name="vault_access"),
    path("vault/<int:vaultid>/documents/", views.vault_documents, name="vault_documents"),
    path("vault/<int:vaultid>/reset-pin/", views.vault_reset_pin, name="vault_reset_pin"),
    path("vault/<int:vaultid>/delete/", views.vault_delete, name="vault_delete"),

    # Document preview renderer (office formats)
    path("document/version/<int:version_id>/preview/", views.document_render_preview, name="document_render_preview"),

    # AI endpoints
    path("ai/suggest-title/", views.ai_suggest_title, name="ai_suggest_title"),
    path("ai/summarize/<int:docid>/", views.ai_summarize_document, name="ai_summarize_document"),

    # Structure management
    path("manage/", views.manage, name="manage"),
    path("manage/groups/create/", views.group_create, name="group_create"),
    path("manage/groups/<int:groupid>/delete/", views.group_delete, name="group_delete"),
    path("manage/folders/create/", views.folder_create, name="folder_create"),
    path("manage/folders/<int:folderid>/delete/", views.folder_delete, name="folder_delete"),
    path("manage/vaults/create/", views.vault_create, name="vault_create"),
    # AI Chatbot
    path('ai/chat/',      org_chat_page, name='org_chat_page'),
    path('ai/chat/send/', org_chat_api,  name='org_chat'),
]