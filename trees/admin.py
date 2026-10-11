from django.contrib import admin
from .models import NewsletterSubscription, Tree, HealthLog, Task

@admin.register(Tree)
class TreeAdmin(admin.ModelAdmin):
    list_display = ('name', 'species', 'location', 'date_planted')

@admin.register(HealthLog)
class HealthLogAdmin(admin.ModelAdmin):
    list_display = ('tree', 'date', 'health_status')

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('tree', 'task_type', 'scheduled_date', 'completed')
    list_filter = ('task_type', 'completed')


@admin.register(NewsletterSubscription)
class NewsletterSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("email", "is_active", "subscribed_at", "unsubscribed_at")
    list_filter = ("is_active",)
    search_fields = ("email",)
    readonly_fields = ("email", "unsubscribe_token", "subscribed_at", "unsubscribed_at")
