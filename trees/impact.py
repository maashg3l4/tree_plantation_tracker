from django.db import transaction
from django.db.models import Case, F, IntegerField, Sum, Value, When

from .models import HelpOffer, Pledge, Reaction, UserImpactScore


REACTION_WEIGHTS = {
    'planted': 10,
    'help': 8,
    'inspiring': 3,
    'care': 2,
    'insight': 1,
}


def refresh_user_impact_score(user):
    with transaction.atomic():
        user.__class__._default_manager.select_for_update().get(pk=user.pk)
        weighted_score = user.impact_reactions.aggregate(
            total=Sum(
                F('intensity')
                * Case(
                    *[
                        When(reaction=reaction_type, then=Value(weight))
                        for reaction_type, weight in REACTION_WEIGHTS.items()
                    ],
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )
        )['total'] or 0
        pledges = Pledge.objects.filter(user=user)
        score, _ = UserImpactScore.objects.update_or_create(
            user=user,
            defaults={
                'total_score': weighted_score,
                'trees_planted': pledges.filter(status='planted').count(),
                'pledges_made': pledges.count(),
                'help_offered': HelpOffer.objects.filter(user=user).count(),
            },
        )
    return score
