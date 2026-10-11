from django.contrib import admin

from .models import (
    Organization,
    OrganizationMember,
    Plot,
    PlotHealthAnalysis,
    PlotHealthSnapshot,
    Task,
    TreeBatch,
)

admin.site.register(Organization)
admin.site.register(OrganizationMember)
admin.site.register(Plot)
admin.site.register(TreeBatch)
admin.site.register(Task)
admin.site.register(PlotHealthSnapshot)
admin.site.register(PlotHealthAnalysis)
