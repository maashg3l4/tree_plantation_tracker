from django import forms

from .models import MarketplaceListing
from trees.form_styling import StyledFormMixin


class MarketplaceListingForm(StyledFormMixin, forms.ModelForm):
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
