# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _


User = get_user_model()

ten_digits = RegexValidator(r"^\d{10}$", "Must be exactly 10 digits.")


class UserCreateForm(forms.ModelForm):
    """Used by org UI views: create a user inside request.user.organization."""
    
    username = forms.CharField(
        max_length=10,
        validators=[ten_digits],
        required=True,
        label="User ID (10 digits)",
        help_text="Click Generate ID button",
        widget=forms.TextInput(attrs={
            'placeholder': '10-digit ID',
            'class': 'form-input'
        })
    )
    
    password = forms.CharField(
        required=True,
        label="Password",
        help_text="Click Generate Password button",
        widget=forms.TextInput(attrs={
            'placeholder': 'Click Generate Password',
            'class': 'form-input',
            'autocomplete': 'new-password'
        })
    )

    class Meta:
        model = User
        fields = [
            "username",
            "password",
            "first_name",
            "last_name",
            "email",
            "role",
            "profession_tag",
            "can_use_ai",
            "is_active",
            "birth_date",
            "avatar",
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'profession_tag': forms.TextInput(attrs={'class': 'form-input'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'role': forms.Select(attrs={'class': 'form-input'}),
            'avatar': forms.FileInput(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.organization = kwargs.pop("organization", None)
        if self.organization is None:
            raise TypeError("UserCreateForm requires organization=...")

        super().__init__(*args, **kwargs)

        # In the APP UI, org staff creation should be ADMIN/EDITOR/VIEWER
        allowed_roles = {"ADMIN", "EDITOR", "VIEWER"}
        self.fields["role"].choices = [
            (value, label)
            for value, label in self.fields["role"].choices
            if value in allowed_roles
        ]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.organization = self.organization
        
        if self.cleaned_data.get('password'):
            user.set_password(self.cleaned_data['password'])
        
        if commit:
            user.save()
        return user


class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "role",
            "profession_tag",
            "can_use_ai",
            "is_active",
            "birth_date",
            "avatar",
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'profession_tag': forms.TextInput(attrs={'class': 'form-input'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'role': forms.Select(attrs={'class': 'form-input'}),
            'avatar': forms.FileInput(attrs={'class': 'form-input'}),
            'can_use_ai': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
        labels = {
            'can_use_ai': 'Enable AI Features',
        }
        help_texts = {
            'can_use_ai': 'Allow this user to access AI-powered features like smart document titles and summarization.',
            'profession_tag': 'Used for document access control and filtering.',
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        super().__init__(*args, **kwargs)
        
        # Prevent ADMIN from changing roles to OWNER
        if self.request_user and self.request_user.role == "ADMIN":
            allowed_roles = {"ADMIN", "EDITOR", "VIEWER"}
            self.fields["role"].choices = [
                (value, label)
                for value, label in self.fields["role"].choices
                if value in allowed_roles
            ]
        
        # Only OWNER and ADMIN can manage AI permissions
        if self.request_user and self.request_user.role not in ("OWNER", "ADMIN"):
            if 'can_use_ai' in self.fields:
                del self.fields['can_use_ai']
    
    def clean_can_use_ai(self):
        """Validate AI permission against organization plan"""
        can_use_ai = self.cleaned_data.get('can_use_ai', False)

        if not can_use_ai:
            return can_use_ai

        # Try to get the organization from the form data first (new user),
        # then fall back to the existing instance (edit user).
        org = self.cleaned_data.get('organization') or (
            self.instance.organization if self.instance and self.instance.pk else None
        )

        if org is None:
            raise forms.ValidationError(
                'AI features cannot be enabled: no organization is assigned to this user.'
            )

        if not org.plan:
            raise forms.ValidationError(
                'AI features cannot be enabled: the organization does not have a plan assigned.'
            )

        if not org.plan.ai_enabled:
            raise forms.ValidationError(
                f'AI features cannot be enabled because the "{org.plan.name}" plan '
                'does not include AI capabilities. Please upgrade the plan first.'
            )

        return can_use_ai


class AdminUserCreateForm(forms.ModelForm):
    """Admin-only: create OWNER or ADMIN for an organization."""
    raw_password = forms.CharField(
        required=False,
        label="Generated password",
        help_text="Click Generate Password, copy it somewhere safe, then Save.",
        widget=forms.TextInput(attrs={
            "class": "vTextField",
            "autocomplete": "new-password",
        }),
    )

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "birth_date",
            "organization",
            "role",
            "username",
            "is_active",
            "email",
            "avatar",
            "can_use_ai",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        is_edit = self.instance and self.instance.pk

        if 'username' in self.fields:
            if is_edit:
                self.fields['username'].disabled = True
                self.fields['username'].help_text = "Username cannot be changed."
            else:
                self.fields['username'].required = False
                self.fields['username'].help_text = "Leave blank to auto-generate, or click 'Generate User ID'."
                self.fields['username'].widget.attrs.update({
                    "class": "vTextField",
                    "placeholder": "Auto-generated if blank",
                })

        if 'organization' in self.fields:
            if is_edit:
                self.fields['organization'].disabled = True
                self.fields['organization'].help_text = "Organization cannot be changed."
            self.fields['organization'].widget.attrs.update({
                "class": "vTextField",
            })

        if 'raw_password' in self.fields:
            if is_edit:
                del self.fields['raw_password']
            else:
                self.fields['raw_password'].widget.attrs.update({
                    "class": "vTextField",
                    "placeholder": "Click 'Generate Password'",
                })

        if 'role' in self.fields:
            allowed_roles = {"OWNER", "ADMIN"}
            self.fields["role"].choices = [
                (value, label)
                for value, label in self.fields["role"].choices
                if value in allowed_roles
            ]
            
            if is_edit:
                self.fields['role'].disabled = True
                self.fields['role'].help_text = "Role cannot be changed here."

        text_fields = ['first_name', 'last_name', 'email']
        for field_name in text_fields:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.setdefault("class", "vTextField")

        if 'birth_date' in self.fields:
            self.fields['birth_date'].widget.attrs.update({
                "class": "vTextField",
            })

    def save(self, commit=True):
        user = super().save(commit=False)
        
        raw_pw = self.cleaned_data.get('raw_password')
        if raw_pw:
            user.set_password(raw_pw)
        
        if commit:
            user.save()
        return user


class OrgLoginForm(forms.Form):
    org_id = forms.CharField(
        max_length=50,
        label="Organization ID",
        required=False,  # superusers can leave this blank or type anything
    )
    user_id = forms.CharField(
        max_length=50,
        label="User ID"
    )
    password = forms.CharField(
        widget=forms.PasswordInput,
        label="Password"
    )