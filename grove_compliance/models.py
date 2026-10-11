from django.db import models

# Create your models here.
from django.conf import settings
from django.db import models


class CertificationDocument(models.Model):
    org = models.ForeignKey(
        "grove.Organization", on_delete=models.CASCADE, related_name="documents"
    )
    title = models.CharField(max_length=180)
    certification_type = models.CharField(max_length=80)
    document = models.FileField(upload_to="orgs/compliance/")
    issued_by = models.CharField(max_length=160, blank=True)
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["expires_on", "-uploaded_at"]

    def __str__(self):
        return f"{self.title} — {self.org.name}"
