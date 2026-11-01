from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Tree
from .forms import HealthLogForm, TaskForm

@login_required
def add_health_log(request, pk):
    tree = get_object_or_404(Tree, pk=pk, user=request.user)
    if tree.is_dead:
        return redirect('tree_detail', pk=pk)
    if request.method == 'POST':
        form = HealthLogForm(request.POST)
        if form.is_valid():
            log = form.save(commit=False)
            log.tree = tree
            log.save()
            return redirect('tree_detail', pk=pk)
    else:
        form = HealthLogForm()
    return render(request, 'trees/add_health_log.html', {'form': form, 'tree': tree})

@login_required
def add_task(request, pk):
    tree = get_object_or_404(Tree, pk=pk, user=request.user)
    if tree.is_dead:
        return redirect('tree_detail', pk=pk)
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.tree = tree
            task.save()
            return redirect('tree_detail', pk=pk)
    else:
        form = TaskForm()
    return render(request, 'trees/add_task.html', {'form': form, 'tree': tree})
