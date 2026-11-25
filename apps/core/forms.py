from django.forms.renderers import TemplatesSetting


class QrumyFormRenderer(TemplatesSetting):
    """Render every Django form field with the Qrumy design-system template."""

    form_template_name = "components/forms/form.html"
    field_template_name = "components/forms/field.html"
