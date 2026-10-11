from django import forms

from .models import Report


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason", "details"]
        widgets = {
            "reason": forms.Select(attrs={"class": "ops-form-control"}),
            "details": forms.Textarea(
                attrs={
                    "class": "ops-form-control",
                    "rows": 3,
                    "maxlength": 1000,
                    "placeholder": "Add context that will help the moderators review this.",
                }
            ),
        }


class ModerationActionForm(forms.Form):
    action = forms.ChoiceField(
        widget=forms.Select(attrs={"class": "ops-form-control"}),
        choices=[
            ("dismiss", "Dismiss report"),
            ("keep", "Keep content"),
            ("warn", "Warn content owner"),
            ("hide", "Hide content"),
            ("remove", "Remove content"),
        ]
    )
    reason = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(
            attrs={"rows": 3, "class": "ops-form-control", "required": True}
        ),
    )


class AIFlagActionForm(forms.Form):
    action = forms.ChoiceField(
        widget=forms.Select(attrs={"class": "ops-form-control"}),
        choices=[
            ("keep", "Keep content"),
            ("warn", "Warn content owner"),
            ("hide", "Hide content"),
            ("remove", "Remove content"),
        ]
    )
    reason = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(
            attrs={"rows": 3, "class": "ops-form-control", "required": True}
        ),
    )
