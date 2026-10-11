from django.contrib import admin

from .models import AIFlag, AuditLog, Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "reason", "status", "reporter", "created_at", "reviewed_by")
    list_filter = ("status", "reason", "created_at")
    search_fields = ("reporter__username", "details", "object_id")
    readonly_fields = ("reporter", "content_type", "object_id", "created_at")
    date_hierarchy = "created_at"


@admin.register(AIFlag)
class AIFlagAdmin(admin.ModelAdmin):
    list_display = ("id", "score", "suggested_action", "status", "source", "created_at")
    list_filter = ("status", "suggested_action", "source", "created_at")
    search_fields = ("reasoning", "object_id")
    readonly_fields = ("content_type", "object_id", "created_at")
    date_hierarchy = "created_at"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor_label", "action", "target_label", "target_user")
    list_filter = ("action", "created_at")
    search_fields = ("actor_label", "target_label", "target_user__username", "reason")
    readonly_fields = (
        "actor",
        "actor_label",
        "action",
        "content_type",
        "object_id",
        "target_label",
        "target_user",
        "reason",
        "before",
        "after",
        "created_at",
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.site_header = "Tree Garden Administration"
admin.site.site_title = "Tree Garden Admin"
admin.site.index_title = "Platform operations"
