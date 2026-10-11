from django.db import models

# Create your models here.
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class MarketplaceListing(models.Model):
    LISTING_TYPES = [
        ("sell", "Sell products"),
        ("buy", "Buy supplies"),
        ("hire", "Hire services"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("closed", "Closed"),
    ]

    org = models.ForeignKey(
        "grove.Organization", on_delete=models.CASCADE, related_name="market_listings"
    )
    listing_type = models.CharField(max_length=10, choices=LISTING_TYPES)
    title = models.CharField(max_length=180)
    category = models.CharField(max_length=80)
    description = models.TextField()
    price_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, choices=[("BDT", "Bangladeshi Taka")], default="BDT")
    region = models.CharField(max_length=120, blank=True)
    contact_email = models.EmailField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
