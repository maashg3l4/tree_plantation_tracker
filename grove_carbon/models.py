from django.db import models

# Create your models here.
from django.conf import settings
from django.db import models


class CarbonCalculation(models.Model):
    org = models.ForeignKey(
        "grove.Organization", on_delete=models.CASCADE, related_name="carbon_calculations"
    )
    plot = models.ForeignKey(
        "grove.Plot", on_delete=models.CASCADE, related_name="carbon_calculations"
    )
    co2_tonnes = models.DecimalField(max_digits=12, decimal_places=2)
    methodology = models.CharField(max_length=60, default="Grove estimate v1")
    eligible_credits = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.CharField(max_length=240, blank=True)
    calculated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-calculated_at"]

    def __str__(self):
        return f"{self.co2_tonnes} tCO2e — {self.plot.name}"
