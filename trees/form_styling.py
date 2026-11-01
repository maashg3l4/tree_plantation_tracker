from django import forms


class StyledFormMixin:
    """Apply the shared Canopy control styles to every project-owned form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.HiddenInput):
                continue
            if isinstance(widget, (forms.CheckboxSelectMultiple, forms.RadioSelect)):
                class_name = "canopy-choice-list"
            elif isinstance(widget, forms.CheckboxInput):
                class_name = "canopy-check"
            elif isinstance(widget, (forms.ClearableFileInput, forms.FileInput)):
                class_name = "canopy-file"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                class_name = "canopy-select"
            elif isinstance(widget, forms.Textarea):
                class_name = "canopy-textarea"
            else:
                class_name = "canopy-input"

            existing_classes = widget.attrs.get("class", "").split()
            if class_name not in existing_classes:
                existing_classes.append(class_name)
            widget.attrs["class"] = " ".join(existing_classes)
