# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
# website/views.py

from django.conf import settings
from django.core.mail import send_mail, EmailMessage
from django.shortcuts import render, redirect
from django.views import View

from accounts.models import Plan
from .forms import OrgRequestForm, ContactForm
from django.utils.translation import gettext_lazy as _


class HomeView(View):
    template_name = "website/home.html"

    def get(self, request):
        return render(request, self.template_name)


class PlanListView(View):
    template_name = "website/plans.html"

    def get(self, request):
        plans = Plan.objects.filter(is_active=True).order_by("min_users")
        return render(request, self.template_name, {"plans": plans})


class OrgRequestCreateView(View):
    template_name = "website/create_organization.html"

    def _get_selected_plan(self, request):
        plan_id = request.GET.get("plan_id") or request.POST.get("plan_id")
        if plan_id:
            try:
                return Plan.objects.get(pk=plan_id, is_active=True)
            except Plan.DoesNotExist:
                pass
        return None

    def get(self, request):
        selected_plan = self._get_selected_plan(request)
        initial = {}
        if selected_plan:
            initial["plan"] = selected_plan.pk
        form = OrgRequestForm(initial=initial)
        return render(request, self.template_name, {
            "form": form,
            "selected_plan": selected_plan,
            "contact_email": settings.DEFAULT_FROM_EMAIL,
        })

    def post(self, request):
        selected_plan = self._get_selected_plan(request)
        form = OrgRequestForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {
                "form": form,
                "selected_plan": selected_plan,
                "contact_email": settings.DEFAULT_FROM_EMAIL,
            })

        org_request = form.save()
        cd = form.cleaned_data

        # ── Build email body ───────────────────────────────────────────────
        plan_name = "-"
        if hasattr(org_request, "plan") and org_request.plan:
            plan_name = org_request.plan.name

        receipt_info = "No"
        if org_request.receipt:
            receipt_name = getattr(org_request.receipt, "name", "") or ""
            receipt_info = f"Yes — {receipt_name}" if receipt_name else "Yes"

        lines = [
            "New JoeDocs organization request",
            "=" * 42,
            "",
            f"Selected plan      : {plan_name}",
            "",
            "── Organization ──────────────────────────",
            f"Name               : {cd['org_name']}",
            f"Type               : {cd.get('org_type') or '-'}",
            f"Estimated users    : {cd['estimated_users']}",
            "",
            "── Applicant ─────────────────────────────",
            f"Name               : {cd.get('applicant_first_name', '')} {cd.get('applicant_last_name', '')}".strip(),
            f"Email              : {cd['applicant_email']}",
            f"Date of birth      : {cd['applicant_date_of_birth']}",
            "",
            "── Payment (Baridi Mob) ──────────────────",
            f"Transaction ref    : {cd['baridimob_transaction_ref']}",
            f"Transaction date   : {cd['baridimob_transaction_date']}",
            f"Receipt attached   : {receipt_info}",
            "",
            f"Terms accepted     : {cd['accept_terms']}",
        ]
        body = "\n".join(lines)

        subject = f"New JoeDocs org request — {cd['org_name']} / {plan_name}"
        from_email = settings.DEFAULT_FROM_EMAIL
        recipients = getattr(settings, "ORG_REQUEST_RECIPIENTS", [settings.DEFAULT_FROM_EMAIL])

        # Use EmailMessage so we can attach the receipt file if present
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email,
            to=recipients,
        )

        # Attach receipt file if uploaded
        receipt_file = request.FILES.get("receipt")
        if receipt_file:
            receipt_file.seek(0)
            email.attach(
                receipt_file.name,
                receipt_file.read(),
                receipt_file.content_type,
            )

        email.send(fail_silently=False)

        return redirect("website:thank_you")


class ThankYouView(View):
    template_name = "website/thank_you.html"

    def get(self, request):
        return render(request, self.template_name)


class DownloadView(View):
    template_name = "website/download.html"

    def get(self, request):
        return render(request, self.template_name)


class ContactView(View):
    template_name = "website/contact.html"

    def get(self, request):
        form = ContactForm()
        return render(request, self.template_name, {
            "form": form,
            "success": False,
            "contact_email": settings.DEFAULT_FROM_EMAIL,
        })

    def post(self, request):
        form = ContactForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                "form": form,
                "success": False,
                "contact_email": settings.DEFAULT_FROM_EMAIL,
            })

        cd = form.cleaned_data
        body = (
            f"Contact form submission — JoeLinkAI\n"
            f"=====================================\n\n"
            f"Name    : {cd['name']}\n"
            f"Email   : {cd['email']}\n\n"
            f"Message :\n{cd['message']}"
        )

        recipients = getattr(
            settings,
            "CONTACT_RECIPIENTS",
            getattr(settings, "ORG_REQUEST_RECIPIENTS", [settings.DEFAULT_FROM_EMAIL]),
        )

        send_mail(
            subject=f"JoeLinkAI contact: {cd['name']}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )

        return render(request, self.template_name, {
            "form": form,
            "success": True,
            "contact_email": settings.DEFAULT_FROM_EMAIL,
        })