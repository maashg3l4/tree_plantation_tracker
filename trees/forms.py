from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Tree, HealthLog, Task
from .location_data import COUNTRIES


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        return [super().clean(upload, initial) for upload in files]


class TreeForm(forms.ModelForm):
    latitude = forms.FloatField(widget=forms.HiddenInput(), required=False)
    longitude = forms.FloatField(widget=forms.HiddenInput(), required=False)
    species = forms.CharField(required=False, widget=forms.TextInput(attrs={'id': 'id_species'}))
    extra_images = MultipleFileField(required=False)
    video = forms.FileField(required=False)
    save_as_draft = forms.BooleanField(required=False)
    scheduled_publish_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
        ),
    )
    country = forms.ChoiceField(choices=COUNTRIES, required=False)
    division = forms.CharField(required=False)
    district = forms.CharField(required=False)
    other_location = forms.CharField(required=False)

    class Meta:
        model = Tree
        fields = [
            'name', 'species', 'caption', 'country', 'division', 'district', 'other_location',
            'location', 'latitude', 'longitude', 'date_planted', 'image',
        ]
        widgets = {
            'date_planted': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_extra_images(self):
        images = self.cleaned_data.get("extra_images", [])
        if len(images) > 9:
            raise ValidationError("Add up to 9 extra photos; the cover photo counts as one.")
        for image in images:
            if image.size > 10 * 1024 * 1024 or image.content_type not in {
                "image/jpeg", "image/png", "image/webp"
            }:
                raise ValidationError("Extra photos must be JPEG, PNG, or WebP and 10 MB or smaller.")
        return images

    def clean_video(self):
        video = self.cleaned_data.get("video")
        if video and (
            video.size > 50 * 1024 * 1024
            or video.content_type not in {"video/mp4", "video/webm"}
        ):
            raise ValidationError("Videos must be MP4 or WebM and 50 MB or smaller.")
        return video

    def clean(self):
        cleaned = super().clean()
        publish_at = cleaned.get("scheduled_publish_at")
        if publish_at and cleaned.get("save_as_draft"):
            self.add_error("scheduled_publish_at", "Choose a draft or a scheduled post, not both.")
        elif publish_at and timezone.is_naive(publish_at):
            publish_at = timezone.make_aware(publish_at, timezone.get_current_timezone())
            cleaned["scheduled_publish_at"] = publish_at
        if publish_at and publish_at <= timezone.now():
            self.add_error("scheduled_publish_at", "Choose a future publication time.")
        return cleaned

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
