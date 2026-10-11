from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.functions import Lower
from django.utils import timezone
from datetime import timedelta

from .models import Profile

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'profile_picture',
            'cover_image',
            'bio',
            'location',
            'website',
            'account_type',
            'language',
        ]

class UserForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.profile = kwargs.pop('profile', None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = User
        fields = ['username', 'email']

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if username == self.instance.username:
            return username
        if User.objects.annotate(lower_username=Lower('username')).filter(
            lower_username=username.lower()
        ).exclude(pk=self.instance.pk).exists():
            raise ValidationError('That username is already taken.')
        if self.profile and self.profile.username_changed_at:
            next_change = self.profile.username_changed_at + timedelta(days=30)
            if timezone.now() < next_change:
                raise ValidationError(
                    f'You can change your username again on {next_change:%B %d, %Y}.'
                )
        return username

class PasswordChangeForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput, required=True, label='Old password')
    new_password1 = forms.CharField(widget=forms.PasswordInput, required=True, label='New password')
    new_password2 = forms.CharField(widget=forms.PasswordInput, required=True, label='Confirm password')
