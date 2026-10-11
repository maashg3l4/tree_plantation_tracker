# Generated for the impact reaction system.

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def convert_legacy_reactions(apps, schema_editor):
    Reaction = apps.get_model('trees', 'Reaction')
    aliases = {
        'like': 'inspiring',
        'love': 'inspiring',
        'wow': 'inspiring',
        'sad': 'care',
    }
    seen = set()
    duplicate_ids = []
    reactions = Reaction.objects.using(schema_editor.connection.alias).order_by(
        'tree_id', 'user_id', '-created_at', '-pk'
    )
    for reaction in reactions.iterator():
        new_type = aliases.get(reaction.reaction, reaction.reaction)
        key = (reaction.tree_id, reaction.user_id, new_type)
        if key in seen:
            duplicate_ids.append(reaction.pk)
            continue
        seen.add(key)
        if reaction.reaction != new_type:
            reaction.reaction = new_type
            reaction.save(using=schema_editor.connection.alias, update_fields=['reaction'])
    for start in range(0, len(duplicate_ids), 500):
        Reaction.objects.using(schema_editor.connection.alias).filter(
            pk__in=duplicate_ids[start:start + 500]
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('trees', '0007_alter_reaction_type'),
    ]

    operations = [
        migrations.RenameField(
            model_name='reaction',
            old_name='type',
            new_name='reaction',
        ),
        migrations.RunPython(convert_legacy_reactions),
        migrations.AlterField(
            model_name='reaction',
            name='reaction',
            field=models.CharField(
                choices=[
                    ('planted', 'I Planted Too'),
                    ('inspiring', 'Inspiring'),
                    ('care', 'Sending Care'),
                    ('help', "I'll Help Here"),
                    ('insight', 'Data Insight'),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='reaction',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='impact_reactions',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='reaction',
            name='intensity',
            field=models.PositiveSmallIntegerField(
                choices=[(1, 'Registered'), (2, 'Committed'), (3, 'Deep')],
                default=1,
            ),
        ),
        migrations.AddField(
            model_name='reaction',
            name='note',
            field=models.CharField(blank=True, max_length=140),
        ),
        migrations.AddField(
            model_name='reaction',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name='Pledge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('species', models.CharField(blank=True, max_length=120)),
                ('status', models.CharField(
                    choices=[('pending', 'Pending'), ('planted', 'Planted'), ('abandoned', 'Abandoned')],
                    default='pending',
                    max_length=20,
                )),
                ('due_date', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('source_post', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pledges',
                    to='trees.tree',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pledges',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.CreateModel(
            name='UserImpactScore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_score', models.IntegerField(default=0)),
                ('trees_planted', models.IntegerField(default=0)),
                ('pledges_made', models.IntegerField(default=0)),
                ('help_offered', models.IntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='impact_score',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_read', models.BooleanField(default=False)),
                ('actor', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sent_tree_notifications',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('tree', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to='trees.tree',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.CreateModel(
            name='HelpOffer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('help_type', models.CharField(
                    choices=[
                        ('water', 'Watering'),
                        ('visit', 'Visit'),
                        ('donate', 'Donate'),
                        ('share', 'Share Location'),
                        ('other', 'Other'),
                    ],
                    max_length=40,
                )),
                ('message', models.TextField(blank=True)),
                ('status', models.CharField(
                    choices=[('open', 'Open'), ('completed', 'Completed'), ('cancelled', 'Cancelled')],
                    default='open',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('post', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='help_offers',
                    to='trees.tree',
                )),
                ('reaction', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='help_offer',
                    to='trees.reaction',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='help_offers',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.AddConstraint(
            model_name='reaction',
            constraint=models.UniqueConstraint(
                fields=('user', 'tree', 'reaction'),
                name='unique_user_tree_impact_reaction',
            ),
        ),
        migrations.AddIndex(
            model_name='reaction',
            index=models.Index(fields=['tree', 'reaction'], name='reaction_tree_type_idx'),
        ),
        migrations.AddIndex(
            model_name='reaction',
            index=models.Index(fields=['user', 'created_at'], name='reaction_user_created_idx'),
        ),
    ]
