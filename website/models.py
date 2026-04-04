# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
# website/models.py

from django.db import models
from django.utils.translation import gettext_lazy as _

class MyModel(models.Model):
    name = models.CharField(_("Name"), max_length=100)

class OrgRequest(models.Model):
    org_name = models.CharField(max_length=255)
    org_type = models.CharField(max_length=100, blank=True)

    estimated_users = models.PositiveIntegerField()

    applicant_name = models.CharField(max_length=255)
    applicant_email = models.EmailField()
    applicant_date_of_birth = models.DateField()

    baridimob_transaction_ref = models.CharField(max_length=100)
    baridimob_transaction_date = models.DateField()

    receipt = models.FileField(
        upload_to="org_requests/receipts/",
        blank=True,
        null=True,
    )

    accept_terms = models.BooleanField()

    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.org_name} / {self.applicant_email} @ {self.submitted_at:%Y-%m-%d}"
