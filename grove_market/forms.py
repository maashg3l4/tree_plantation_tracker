from django import forms

from .models import MarketplaceListing


class MarketplaceListingForm(forms.ModelForm):
    class Meta:
        model = MarketplaceListing
        fields = [
            "listing_type",
            "title",
            "category",
            "description",
            "price_amount",
            "currency",
            "region",
            "contact_email",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}
