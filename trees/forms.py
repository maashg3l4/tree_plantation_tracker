from django import forms
from .models import Tree, HealthLog, Task
from .location_data import COUNTRIES

class TreeForm(forms.ModelForm):
    latitude = forms.FloatField(widget=forms.HiddenInput(), required=False)
    longitude = forms.FloatField(widget=forms.HiddenInput(), required=False)
    species = forms.CharField(required=False, widget=forms.TextInput(attrs={'id': 'id_species'}))
    country = forms.ChoiceField(choices=COUNTRIES, required=False)
    division = forms.CharField(required=False)
    district = forms.CharField(required=False)
    other_location = forms.CharField(required=False)

    class Meta:
        model = Tree
        fields = [
            'name', 'species', 'country', 'division', 'district', 'other_location',
            'location', 'latitude', 'longitude', 'date_planted', 'image',
        ]
        widgets = {
            'date_planted': forms.DateInput(attrs={'type': 'date'}),
        }

class HealthLogForm(forms.ModelForm):
    class Meta:
        model = HealthLog
        fields = ['date', 'health_status', 'notes', 'is_dead', 'death_reason']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'death_reason': forms.Textarea(attrs={'rows': 2}),
        }

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['task_type', 'scheduled_date', 'completed']
        widgets = {
            'scheduled_date': forms.DateInput(attrs={'type': 'date'})
        }
