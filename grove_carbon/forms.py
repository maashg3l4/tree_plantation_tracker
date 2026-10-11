from django import forms

from grove.models import Plot


class CarbonEstimateForm(forms.Form):
    plot = forms.ModelChoiceField(queryset=Plot.objects.none())
    horizon_years = forms.IntegerField(min_value=1, max_value=100, initial=1)

    def __init__(self, *args, org, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plot"].queryset = Plot.objects.filter(org=org)
