import json

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.db import transaction
from django.db.models import Case, Count, F, IntegerField, Prefetch, Sum, Value, When
from django.views.decorators.http import require_POST
from .models import (
    Comment,
    HealthLog,
    HelpOffer,
    Notification,
    Pledge,
    Profile,
    Reaction,
    Tree,
    TreeHealthAnalysis,
    UserImpactScore,
)
from .forms import TreeForm, HealthLogForm, TaskForm
from .forms_profile import ProfileForm, UserForm, PasswordChangeForm
from .impact import refresh_user_impact_score
from .ai_services import AIServiceError, analyze_tree_health, identify_species, image_digest

# Registration view
def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('tree_list')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

# Login view
def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('tree_list')
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})

# Logout view
def user_logout(request):
    logout(request)
    return redirect('tree_list')

def tree_list(request):
    trees = Tree.objects.select_related('user', 'user__profile').prefetch_related(
        Prefetch('reactions', queryset=Reaction.objects.select_related('user').order_by('-created_at')),
        Prefetch('comments', queryset=Comment.objects.select_related('user').order_by('created_at')),
        Prefetch('health_logs', queryset=HealthLog.objects.order_by('-date', '-pk')),
        Prefetch(
            'health_analyses',
            queryset=TreeHealthAnalysis.objects.order_by('-created_at'),
            to_attr='prefetched_health_analyses',
        ),
    ).annotate(
        inspiration_boost=Sum(
            Case(
                When(reactions__reaction='inspiring', then=F('reactions__intensity')),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
    ).order_by('-inspiration_boost', '-updated_at')
    for tree in trees:
        profile = getattr(tree.user, 'profile', None)
        tree.profile_picture = profile.profile_picture if profile else None
        tree.reaction_counts = {reaction_type: 0 for reaction_type, _ in Reaction.REACTION_TYPES}
        tree.user_reaction_state = {}
        for reaction in tree.reactions.all():
            tree.reaction_counts[reaction.reaction] += 1
            if request.user.is_authenticated and reaction.user_id == request.user.id:
                tree.user_reaction_state[reaction.reaction] = reaction.intensity
        tree.reaction_state = ','.join(
            f'{reaction_type}:{intensity}'
            for reaction_type, intensity in tree.user_reaction_state.items()
        )
        tree.latest_reactions = list(tree.reactions.all())[:5]
        tree.latest_health_analysis = next(iter(tree.prefetched_health_analyses), None)
        tree.health_issues_json = json.dumps(tree.latest_health_analysis.issues) if tree.latest_health_analysis else '[]'
        tree.health_recommendations_json = json.dumps(
            tree.latest_health_analysis.recommendations
        ) if tree.latest_health_analysis else '[]'
        latest_health = next(iter(tree.health_logs.all()), None)
        tree.has_health_data = bool(latest_health)
        if tree.is_dead or (latest_health and latest_health.is_dead):
            tree.feed_status = 'struggling'
        elif latest_health and any(
            marker in latest_health.health_status.lower()
            for marker in ('struggl', 'poor', 'critical', 'declin', 'dead')
        ):
            tree.feed_status = 'struggling'
        elif latest_health and any(
            marker in latest_health.health_status.lower()
            for marker in ('thriv', 'healthy', 'excellent', 'good')
        ):
            tree.feed_status = 'thriving'
        else:
            tree.feed_status = 'unknown'
    return render(request, 'trees/tree_list.html', {
        'trees': trees,
        'impact_reaction_types': Reaction.REACTION_TYPES,
    })


@login_required
@require_POST
def identify_tree_species(request):
    image = request.FILES.get('image')
    if not image:
        return JsonResponse({'success': False, 'error': 'Choose a tree image first.'}, status=400)
    try:
        result = identify_species(image)
    except AIServiceError as error:
        return JsonResponse({'success': False, 'error': str(error)}, status=error.status_code)
    if result['predictions']:
        predictions = request.session.get('species_identifications', {})
        predictions[result['image_hash']] = result
        request.session['species_identifications'] = predictions
    return JsonResponse({'success': True, **result})


@login_required
@require_POST
def analyze_tree(request, pk):
    tree = get_object_or_404(Tree, pk=pk)
    if tree.user_id != request.user.id:
        return JsonResponse(
            {'success': False, 'error': 'Only the tree owner can request a health analysis.'},
            status=403,
        )
    if not tree.image:
        return JsonResponse({'success': False, 'error': 'This tree has no image to analyze.'}, status=400)
    try:
        with tree.image.open('rb') as image:
            image_hash = image_digest(image)
        analysis = None
        if request.POST.get('force') != '1':
            analysis = tree.health_analyses.filter(image_hash=image_hash).first()
        if analysis is None:
            with tree.image.open('rb') as image:
                result = analyze_tree_health(image)
            analysis = TreeHealthAnalysis.objects.create(post=tree, **result)
    except AIServiceError as error:
        return JsonResponse({'success': False, 'error': str(error)}, status=error.status_code)
    return JsonResponse({
        'success': True,
        'analysis': {
            'score': analysis.score,
            'issues': analysis.issues,
            'recommendations': analysis.recommendations,
            'confidence': analysis.confidence,
            'model_used': analysis.model_used,
            'created_at': analysis.created_at.isoformat(),
        },
    })

@login_required
def add_tree(request):
    if request.method == 'POST':
        form = TreeForm(request.POST, request.FILES)
        if form.is_valid():
            tree = form.save(commit=False)
            tree.user = request.user
            image = form.cleaned_data.get('image')
            predictions = request.session.get('species_identifications', {})
            prediction = predictions.pop(image_digest(image), None) if image else None
            if prediction:
                guess = prediction['predictions'][0]
                tree.ai_species_guess = guess['name'][:120]
                tree.ai_confidence = guess.get('confidence')
                tree.ai_species_corrected = (
                    tree.species.strip().casefold() != guess['name'].strip().casefold()
                )
                request.session['species_identifications'] = predictions
            tree.save()
            return redirect('tree_list')
    else:
        form = TreeForm()
    return render(request, 'trees/add_tree.html', {'form': form})

@login_required
def tree_detail(request, pk):
    tree = get_object_or_404(Tree, pk=pk)
    health_logs = tree.health_logs.all().order_by('-date')
    tasks = tree.tasks.all().order_by('scheduled_date')
    comments = tree.comments.select_related('user').order_by('created_at')
    reactions = tree.reactions.select_related('user').order_by('-created_at')
    tree.latest_health_analysis = tree.health_analyses.first()
    tree.health_issues_json = json.dumps(tree.latest_health_analysis.issues) if tree.latest_health_analysis else '[]'
    tree.health_recommendations_json = json.dumps(
        tree.latest_health_analysis.recommendations
    ) if tree.latest_health_analysis else '[]'
    tree.reaction_counts = {reaction_type: 0 for reaction_type, _ in Reaction.REACTION_TYPES}
    tree.user_reaction_state = {}
    for reaction in reactions:
        tree.reaction_counts[reaction.reaction] += 1
        if reaction.user_id == request.user.id:
            tree.user_reaction_state[reaction.reaction] = reaction.intensity
    tree.reaction_state = ','.join(
        f'{reaction_type}:{intensity}'
        for reaction_type, intensity in tree.user_reaction_state.items()
    )
    tree.latest_reactions = list(reactions[:5])
    latest_health = health_logs.first()
    tree.has_health_data = bool(latest_health)
    if tree.is_dead or (latest_health and latest_health.is_dead):
        tree.feed_status = 'struggling'
    elif latest_health and any(
        marker in latest_health.health_status.lower()
        for marker in ('struggl', 'poor', 'critical', 'declin', 'dead')
    ):
        tree.feed_status = 'struggling'
    elif latest_health and any(
        marker in latest_health.health_status.lower()
        for marker in ('thriv', 'healthy', 'excellent', 'good')
    ):
        tree.feed_status = 'thriving'
    else:
        tree.feed_status = 'unknown'
    health_form = HealthLogForm()
    task_form = TaskForm()
    # Handle comments
    if request.method == 'POST' and request.POST.get('form_type') == 'comment':
        text = request.POST.get('comment_text')
        if text:
            Comment.objects.create(tree=tree, user=request.user, text=text)
            return redirect('tree_detail', pk=tree.pk)
    if request.method == 'POST':
        if request.POST.get('form_type') == 'health':
            health_form = HealthLogForm(request.POST)
            if health_form.is_valid():
                log = health_form.save(commit=False)
                log.tree = tree
                # If tree is dead, propagate to health log
                if tree.is_dead:
                    log.is_dead = True
                    log.death_reason = tree.death_reason
                log.save()
                return redirect('tree_detail', pk=tree.pk)
        elif request.POST.get('form_type') == 'task':
            task_form = TaskForm(request.POST)
            if task_form.is_valid():
                task = task_form.save(commit=False)
                task.tree = tree
                task.save()
                return redirect('tree_detail', pk=tree.pk)
        elif request.POST.get('form_type') == 'mark_dead':
            reason = request.POST.get('death_reason')
            tree.is_dead = True
            tree.death_reason = reason
            tree.save()
            # Propagate to health log
            from .models import HealthLog
            HealthLog.objects.create(
                tree=tree,
                date=tree.updated_at.date(),
                health_status='Dead',
                is_dead=True,
                death_reason=reason
            )
            return redirect('tree_detail', pk=tree.pk)
    return render(request, 'trees/tree_detail.html', {
        'tree': tree,
        'health_logs': health_logs,
        'tasks': tasks,
        'health_form': health_form,
        'task_form': task_form,
        'comments': comments,
        'reactions': reactions,
        'impact_reaction_types': Reaction.REACTION_TYPES,
    })

@login_required
def mark_task_completed(request, task_id):
    if request.method == 'POST':
        from .models import Task
        task = Task.objects.get(id=task_id)
        task.completed = True
        task.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

def profile_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    profile, created = Profile.objects.get_or_create(user=request.user)
    impact_score, _ = UserImpactScore.objects.get_or_create(user=request.user)
    user_form = UserForm(instance=request.user)
    profile_form = ProfileForm(instance=profile)
    password_form = PasswordChangeForm()
    message = None
    if request.method == 'POST':
        if 'update_profile' in request.POST:
            user_form = UserForm(request.POST, instance=request.user)
            profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                message = 'Profile updated successfully.'
        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(request.POST)
            if password_form.is_valid():
                old = password_form.cleaned_data['old_password']
                new1 = password_form.cleaned_data['new_password1']
                new2 = password_form.cleaned_data['new_password2']
                if not request.user.check_password(old):
                    password_form.add_error('old_password', 'Old password is incorrect.')
                elif new1 != new2:
                    password_form.add_error('new_password2', 'Passwords do not match.')
                else:
                    request.user.set_password(new1)
                    request.user.save()
                    login(request, request.user)
                    message = 'Password changed successfully.'
    return render(request, 'registration/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
        'profile': profile,
        'message': message,
        'impact_score': impact_score,
        'pledges': Pledge.objects.filter(user=request.user).select_related('source_post').order_by('-created_at'),
        'notifications': Notification.objects.filter(user=request.user).select_related('actor', 'tree').order_by('-created_at')[:10],
    })


@login_required
@require_POST
def update_pledge_status(request, pledge_id):
    pledge = get_object_or_404(Pledge, pk=pledge_id, user=request.user)
    status = request.POST.get('status')
    if status not in ('planted', 'abandoned'):
        return JsonResponse({'success': False, 'error': 'Invalid pledge status.'}, status=400)
    with transaction.atomic():
        pledge.status = status
        pledge.save(update_fields=['status'])
        refresh_user_impact_score(request.user)
    return redirect('profile')


@require_POST
def react_or_comment(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'You must be logged in to react or comment.'}, status=403)
    tree_id = request.POST.get('tree_id')
    form_type = request.POST.get('form_type')
    if not tree_id or not form_type:
        return JsonResponse({'success': False, 'error': 'Missing tree_id or form_type.'}, status=400)
    tree = get_object_or_404(Tree, pk=tree_id)
    if form_type == 'react':
        reaction_type = request.POST.get('reaction_type')
        if reaction_type not in dict(Reaction.REACTION_TYPES):
            return JsonResponse({'success': False, 'error': 'Invalid reaction_type.'}, status=400)
        try:
            intensity = int(request.POST.get('intensity', '1'))
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'error': 'Intensity must be 1, 2, or 3.'}, status=400)
        if intensity not in dict(Reaction.INTENSITY_LEVELS):
            return JsonResponse({'success': False, 'error': 'Intensity must be 1, 2, or 3.'}, status=400)
        note = request.POST.get('note', '')
        if len(note) > 140:
            return JsonResponse({'success': False, 'error': 'Reaction notes must be 140 characters or fewer.'}, status=400)

        help_type = request.POST.get('help_type', 'water')
        help_message = request.POST.get('help_message', '')
        if reaction_type == 'help' and help_type not in dict(HelpOffer.HELP_TYPES):
            return JsonResponse({'success': False, 'error': 'Invalid help type.'}, status=400)
        if len(help_message) > 1000:
            return JsonResponse({'success': False, 'error': 'Help messages must be 1000 characters or fewer.'}, status=400)

        with transaction.atomic():
            reaction, _ = Reaction.objects.update_or_create(
                tree=tree,
                user=request.user,
                reaction=reaction_type,
                defaults={'intensity': intensity, 'note': note},
            )
            if reaction_type == 'planted':
                pledge, pledge_created = Pledge.objects.get_or_create(
                    user=request.user,
                    source_post=tree,
                    defaults={'species': tree.species},
                )
                if pledge_created and tree.user_id != request.user.id:
                    Notification.objects.create(
                        user=tree.user,
                        actor=request.user,
                        tree=tree,
                        message=f'{request.user.username} pledged to plant a tree like yours.',
                    )
            elif reaction_type == 'help':
                HelpOffer.objects.update_or_create(
                    reaction=reaction,
                    defaults={
                        'user': request.user,
                        'post': tree,
                        'help_type': help_type,
                        'message': help_message,
                    },
                )
            refresh_user_impact_score(request.user)

        counts = {reaction_type: 0 for reaction_type, _ in Reaction.REACTION_TYPES}
        for item in tree.reactions.values('reaction').annotate(count=Count('pk')):
            counts[item['reaction']] = item['count']
        timeline = [
            {
                'username': item.user.username,
                'reaction': item.get_reaction_display(),
                'reaction_type': item.reaction,
                'note': item.note,
                'created_at': item.created_at.isoformat(),
            }
            for item in tree.reactions.select_related('user').order_by('-created_at')[:5]
        ]
        return JsonResponse({'success': True, 'counts': counts, 'timeline': timeline})
    if form_type == 'comment':
        text = request.POST.get('comment_text', '').strip()
        if not text:
            return JsonResponse({'success': False, 'error': 'Missing comment_text.'}, status=400)
        Comment.objects.create(tree=tree, user=request.user, text=text)
        comments = tree.comments.select_related('user').order_by('created_at')
        if request.headers.get('HX-Request') == 'true':
            return render(request, 'trees/partials/comment_list.html', {'comments': comments})
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request.'}, status=400)

@login_required
def delete_tree(request, pk):
    tree = get_object_or_404(Tree, pk=pk)
    if tree.user != request.user:
        return JsonResponse({'success': False, 'error': 'You do not have permission to delete this tree.'}, status=403)
    if request.method == 'POST':
        affected_user_ids = set(tree.reactions.values_list('user_id', flat=True))
        affected_user_ids.update(tree.help_offers.values_list('user_id', flat=True))
        with transaction.atomic():
            tree.delete()
            for affected_user in get_user_model().objects.filter(pk__in=affected_user_ids):
                refresh_user_impact_score(affected_user)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request.'}, status=400)
