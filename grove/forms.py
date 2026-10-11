from django import forms
from django.contrib.auth import get_user_model

from .models import Organization, OrganizationMember, Plot, Task


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = [
            "name",
            "org_type",
            "description",
            "country",
            "region",
            "total_area_hectares",
            "is_public",
            "logo",
            "cover_image",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class PlotForm(forms.ModelForm):
    boundary = forms.JSONField(widget=forms.HiddenInput)

    class Meta:
        model = Plot
        fields = ["name", "area_hectares", "soil_type", "irrigation", "boundary"]

    def clean_boundary(self):
        boundary = self.cleaned_data["boundary"]
        if not isinstance(boundary, dict) or boundary.get("type") != "Polygon":
            raise forms.ValidationError("Draw one closed plot boundary on the map.")
        rings = boundary.get("coordinates")
        if not isinstance(rings, list) or not rings or not isinstance(rings[0], list):
            raise forms.ValidationError("The plot boundary is not a valid polygon.")
        points = rings[0]
        if len(points) < 4 or points[0] != points[-1]:
            raise forms.ValidationError("Close the plot boundary by joining its first and last points.")
        for point in points:
            if (
                not isinstance(point, (list, tuple))
                or len(point) < 2
                or not all(
                    isinstance(value, (int, float)) and not isinstance(value, bool)
                    for value in point[:2]
                )
            ):
                raise forms.ValidationError("The plot boundary contains an invalid coordinate.")
            longitude, latitude = point[:2]
            if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
                raise forms.ValidationError("Plot coordinates must be valid longitude and latitude.")
        return boundary


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            "plot",
            "assigned_to",
            "task_type",
            "title",
            "notes",
            "priority",
            "due_date",
        ]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class OrganizationMemberForm(forms.ModelForm):
    class Meta:
        model = OrganizationMember
        fields = ["user", "role"]

    def __init__(self, *args, org, actor_role, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = get_user_model().objects.exclude(
            organizationmember__org=org
        ).order_by("username")
        roles = [("worker", "Worker"), ("viewer", "Viewer")]
        if actor_role == "owner":
            roles.insert(0, ("manager", "Manager"))
        self.fields["role"].choices = roles


class TaskCompletionForm(forms.Form):
    proof_image = forms.ImageField(required=False)

    def clean_proof_image(self):
        image = self.cleaned_data.get("proof_image")
        if image and image.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Task proof images must be 10 MB or smaller.")
        return image
