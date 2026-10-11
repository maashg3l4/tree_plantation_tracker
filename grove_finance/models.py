from decimal import Decimal

from django.db import models
from django.core.validators import MinValueValidator

# Create your models here.
from django.conf import settings
from django.db import models


class Transaction(models.Model):
    TYPES = [("expense", "Expense"), ("revenue", "Revenue")]

    org = models.ForeignKey(
        "grove.Organization", on_delete=models.CASCADE, related_name="transactions"
    )
    plot = models.ForeignKey(
        "grove.Plot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    trans_type = models.CharField(max_length=10, choices=TYPES)
    category = models.CharField(max_length=60)
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=3, choices=[("BDT", "Bangladeshi Taka")], default="BDT")
    description = models.CharField(max_length=200)
    date = models.DateField()
    receipt = models.FileField(upload_to="orgs/receipts/", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.trans_type}: {self.amount} {self.currency} — {self.description}"
