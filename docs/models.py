# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
from django.conf import settings
from django.db import models
from django.core.validators import FileExtensionValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class MyModel(models.Model):
    name = models.CharField(_("Name"), max_length=100)

from accounts.models import Organization


class FolderGroup(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="folder_groups")
    name = models.CharField(max_length=120)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("organization", "name")]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.organization.org_id})"


class Folder(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="folders")
    group = models.ForeignKey(FolderGroup, on_delete=models.CASCADE, related_name="folders")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children")

    name = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("group", "parent", "name")]
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}"

    def path(self):
        parts = [self.name]
        p = self.parent
        while p:
            parts.append(p.name)
            p = p.parent
        return " / ".join(reversed(parts))


class Vault(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="vaults")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, null=True)
    
    # 6-digit PIN code
    pin_code = models.CharField(
        max_length=6,
        validators=[
            RegexValidator(
                regex=r'^\d{6}$',
                message='PIN must be exactly 6 digits',
                code='invalid_pin'
            )
        ],
        help_text='Enter a 6-digit PIN code'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("organization", "name")]
        ordering = ["name"]

    def __str__(self):
        return self.name
    
    def verify_pin(self, pin):
        """Verify if the provided PIN matches the vault's PIN"""
        return self.pin_code == pin


class Document(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="documents")
    folder = models.ForeignKey(Folder, on_delete=models.SET_NULL, null=True, blank=True, related_name="documents")
    vault = models.ForeignKey(Vault, on_delete=models.SET_NULL, null=True, blank=True, related_name="documents")

    title = models.CharField(max_length=255)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_documents")

    # Tags for access control (comma-separated list of tags)
    access_tags = models.TextField(blank=True, default="")  # e.g., "finance,hr,executive"
    
    # Per-document action permission flags (set at upload time by owner/editor)
    can_be_printed = models.BooleanField(default=True)
    can_be_moved   = models.BooleanField(default=True)
    can_be_deleted = models.BooleanField(default=True)

    is_deleted = models.BooleanField(default=False)  # simple soft-delete flag
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    
    def get_tags_list(self):
        """Return list of access tags"""
        if not self.access_tags:
            return []
        return [tag.strip() for tag in self.access_tags.split(',') if tag.strip()]
    
    def has_tag(self, tag):
        """Check if document has specific tag"""
        return tag.lower() in [t.lower() for t in self.get_tags_list()]


def doc_upload_path(instance, filename):
    org_id = instance.document.organization.org_id
    return f"org_{org_id}/docs/{instance.document_id}/{filename}"


ALLOWED_FILE_EXTENSIONS = [
    # Documents
    'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt',
    # Spreadsheets
    'xls', 'xlsx', 'csv', 'ods',
    # Presentations
    'ppt', 'pptx', 'odp',
    # Images
    'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp',
    # Archives
    'zip', 'rar', '7z', 'tar', 'gz',
    # Other
    'json', 'xml', 'html', 'css', 'js',
]


class DocumentVersion(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()

    file = models.FileField(
        upload_to=doc_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=ALLOWED_FILE_EXTENSIONS)]
    )
    file_size = models.PositiveIntegerField(default=0)

    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("document", "version")]
        ordering = ["-version"]

    def __str__(self):
        return f"{self.document.title} v{self.version}"
    
    def get_file_extension(self):
        """Get file extension"""
        import os
        return os.path.splitext(self.file.name)[1].lower().replace('.', '')


class AccessControlEntry(models.Model):
    class SubjectType(models.TextChoices):
        USER = "USER", "User"
        ROLE = "ROLE", "Role"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="aces")

    subject_type = models.CharField(max_length=10, choices=SubjectType.choices)
    subject_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    subject_role = models.CharField(max_length=20, null=True, blank=True)

    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, null=True, blank=True, related_name="aces")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True, related_name="aces")
    vault = models.ForeignKey(Vault, on_delete=models.CASCADE, null=True, blank=True, related_name="aces")

    can_view = models.BooleanField(default=False)
    can_download = models.BooleanField(default=False)
    can_print = models.BooleanField(default=False)
    can_upload = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_manage_permissions = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["organization", "subject_type"]),
        ]

    def clean(self):
        # exactly one target
        targets = [bool(self.folder_id), bool(self.document_id), bool(self.vault_id)]
        if sum(targets) != 1:
            raise ValueError("ACE must target exactly one of: folder, document, vault.")

        # subject validation
        if self.subject_type == self.SubjectType.USER and not self.subject_user_id:
            raise ValueError("subject_user required when subject_type=USER")
        if self.subject_type == self.SubjectType.ROLE and not self.subject_role:
            raise ValueError("subject_role required when subject_type=ROLE")


class ActivityLog(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="activity_logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=40, blank=True, null=True)
    target_id = models.CharField(max_length=40, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]