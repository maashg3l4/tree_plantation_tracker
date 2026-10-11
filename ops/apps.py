from django.apps import AppConfig
from django.db.models.signals import post_migrate


OPS_GROUPS = ("Ops Admin", "Moderator", "Support", "Analyst")


def ensure_ops_groups(sender, **kwargs):
    from django.contrib.auth.models import Group

    for name in OPS_GROUPS:
        Group.objects.get_or_create(name=name)


class OpsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ops'

    def ready(self):
        post_migrate.connect(
            ensure_ops_groups,
            sender=self,
            dispatch_uid="ops.ensure_role_groups",
        )
