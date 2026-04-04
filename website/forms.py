# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
# website/forms.py

from django import forms
from accounts.models import Plan
from django.utils.translation import gettext_lazy as _



# ── If you have an OrgRequest model, import it here and use ModelForm ──
# from .models import OrgRequest


ORG_TYPE_CHOICES = [
    ("", "— Select type —"),
    ("company",        "Company / Business"),
    ("ngo",            "Non-profit / NGO"),
    ("education",      "School / University"),
    ("government",     "Government body"),
    ("other",          "Other"),
]


class OrgRequestForm(forms.Form):
    # ── Organization ──────────────────────────────────────
    org_name = forms.CharField(
        label="Organization name",
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Acme Corp"}),
    )
    org_type = forms.ChoiceField(
        label="Organization type",
        choices=ORG_TYPE_CHOICES,
        required=False,
    )
    estimated_users = forms.IntegerField(
        label="Estimated number of users",
        min_value=1,
        widget=forms.NumberInput(attrs={"placeholder": "25"}),
    )
    plan = forms.ModelChoiceField(
        label="Requested plan",
        queryset=Plan.objects.filter(is_active=True).order_by("min_users"),
        required=False,
        empty_label="— Select a plan —",
    )

    # ── Applicant ─────────────────────────────────────────
    applicant_first_name = forms.CharField(
        label="First name",
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Ahmed"}),
    )
    applicant_last_name = forms.CharField(
        label="Last name",
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "Benali"}),
    )
    applicant_email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"placeholder": "ahmed@example.com"}),
    )
    applicant_date_of_birth = forms.DateField(
        label="Date of birth",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    # ── Payment ───────────────────────────────────────────
    # payment_method is fixed to "Baridi Mob" — no need to expose as a field
    baridimob_transaction_ref = forms.CharField(
        label="BaridiMob transaction reference",
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "TXN-XXXXXXXXXX"}),
    )
    baridimob_transaction_date = forms.DateField(
        label="Payment date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    receipt = forms.FileField(
        label="Payment receipt (optional)",
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "image/*,.pdf"}),
    )

    # ── Terms ─────────────────────────────────────────────
    accept_terms = forms.BooleanField(
        label="I accept the terms and conditions",
        error_messages={"required": "You must accept the terms and conditions to proceed."},
    )

    def save(self):
        """
        Save to OrgRequest model if available, otherwise return cleaned data dict.
        Replace this method body with a proper ModelForm save() when your model is ready.
        """
        # Example ModelForm usage (uncomment when OrgRequest model exists):
        # instance = OrgRequest(
        #     org_name=self.cleaned_data["org_name"],
        #     org_type=self.cleaned_data.get("org_type", ""),
        #     estimated_users=self.cleaned_data["estimated_users"],
        #     plan=self.cleaned_data.get("plan"),
        #     applicant_first_name=self.cleaned_data["applicant_first_name"],
        #     applicant_last_name=self.cleaned_data["applicant_last_name"],
        #     applicant_email=self.cleaned_data["applicant_email"],
        #     applicant_date_of_birth=self.cleaned_data["applicant_date_of_birth"],
        #     baridimob_transaction_ref=self.cleaned_data["baridimob_transaction_ref"],
        #     baridimob_transaction_date=self.cleaned_data["baridimob_transaction_date"],
        #     receipt=self.cleaned_data.get("receipt"),
        # )
        # instance.save()
        # return instance

        # Temporary: return a simple namespace so view code works uniformly
        class _FakeInstance:
            def __init__(self, cd):
                for k, v in cd.items():
                    setattr(self, k, v)
        return _FakeInstance(self.cleaned_data)


class ContactForm(forms.Form):
    name = forms.CharField(
        label="Your name",
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Ahmed Benali"}),
    )
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"placeholder": "ahmed@example.com"}),
    )
    message = forms.CharField(
        label="Message",
        widget=forms.Textarea(attrs={"placeholder": "How can we help you?", "rows": 5}),
    )