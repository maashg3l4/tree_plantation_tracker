from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models.functions import Lower
import re

from .models import Profile


User = get_user_model()


class SignupForm(forms.Form):
    email = forms.EmailField(max_length=254)
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    accept_terms = forms.BooleanField(
        label="I agree to the Terms of Service and Privacy Policy."
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The passwords do not match.")
        if password1:
            candidate = User(email=cleaned.get("email", ""))
            try:
                validate_password(password1, user=candidate)
            except ValidationError as error:
                self.add_error("password1", error)
        return cleaned


class EmailLoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    remember_me = forms.BooleanField(required=False, initial=True)

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get("email")
        password = cleaned.get("password")
        if email and password:
            user = User.objects.filter(email__iexact=email).first()
            if user:
                self.user = authenticate(
                    self.request, username=user.get_username(), password=password
                )
            if self.user is None:
                raise forms.ValidationError("That email and password combination was not recognized.")
        return cleaned

    def get_user(self):
        return self.user


class OnboardingForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    username = forms.CharField(max_length=30)
    profile_picture = forms.ImageField(required=False)
    bio = forms.CharField(max_length=160, required=False, widget=forms.Textarea(attrs={"rows": 3}))
    location = forms.CharField(max_length=120, required=False)
    interests = forms.MultipleChoiceField(
        choices=Profile.GARDEN_INTERESTS,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data["username"].strip().lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,30}", username):
            raise forms.ValidationError(
                "Use 3–30 letters, numbers, hyphens, or underscores for your handle."
            )
        if User.objects.annotate(lower_username=Lower("username")).filter(
            lower_username=username.lower()
        ).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("That username is already taken.")
        return username

    def clean_profile_picture(self):
        image = self.cleaned_data.get("profile_picture")
        if image and image.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Profile photos must be 5 MB or smaller.")
        return image
