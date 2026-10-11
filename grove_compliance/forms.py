from django import forms

from .models import CertificationDocument


class CertificationDocumentForm(forms.ModelForm):
    class Meta:
        model = CertificationDocument
        fields = ["title", "certification_type", "document", "issued_by", "issued_on", "expires_on", "notes"]
        widgets = {
            "issued_on": forms.DateInput(attrs={"type": "date"}),
            "expires_on": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
