from django import forms

from .models import Transaction


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["plot", "trans_type", "category", "amount", "currency", "description", "date", "receipt"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def clean_receipt(self):
        receipt = self.cleaned_data.get("receipt")
        if receipt:
            if receipt.size > 15 * 1024 * 1024:
                raise forms.ValidationError("Receipts must be 15 MB or smaller.")
            if receipt.name.rsplit(".", 1)[-1].lower() not in {"pdf", "png", "jpg", "jpeg"}:
                raise forms.ValidationError("Upload a PDF, PNG, or JPEG receipt.")
        return receipt
