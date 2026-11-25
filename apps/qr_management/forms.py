from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from PIL import Image

from .engine.style import QRStyle, StyleError
from .models import Folder, QRCode
from .types import DYNAMIC, STATIC

MAX_LOGO_BYTES = 1024 * 1024


class QRMetaForm(forms.Form):
    name = forms.CharField(label=_("Name"), max_length=120,
                           help_text=_("Only you see this name."))
    mode = forms.ChoiceField(label=_("Type of code"), widget=forms.RadioSelect)
    folder = forms.ModelChoiceField(label=_("Folder"), queryset=Folder.objects.none(),
                                    required=False, empty_label=_("No folder"))
    tags = forms.CharField(label=_("Tags"), required=False, max_length=300,
                           help_text=_("Separate with commas."))
    expires_at = forms.DateTimeField(label=_("Expires at"), required=False,
                                     widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
                                     help_text=_("Dynamic codes stop working after this time."))

    def __init__(self, *args, organization, type_def, locked_mode=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["folder"].queryset = Folder.objects.for_org(organization)
        labels = {DYNAMIC: _("Dynamic — editable later, with scan analytics"),
                  STATIC: _("Static — content stored in the code, no analytics")}
        self.fields["mode"].choices = [(m, labels[m]) for m in type_def.modes]
        self.fields["mode"].initial = type_def.default_mode
        if locked_mode or len(type_def.modes) == 1:
            self.fields["mode"].disabled = True
            self.fields["mode"].initial = locked_mode or type_def.modes[0]

    def tag_list(self) -> list[str]:
        return [t.strip() for t in self.cleaned_data.get("tags", "").split(",") if t.strip()]

    def clean(self):
        data = super().clean()
        if data.get("expires_at") and data.get("mode") == STATIC:
            self.add_error("expires_at", _("Static codes cannot expire."))
        return data


class StyleForm(forms.Form):
    fg = forms.CharField(label=_("Code color"), initial="#101B3A",
                         widget=forms.TextInput(attrs={"type": "color"}))
    bg = forms.CharField(label=_("Background"), initial="#FFFFFF",
                         widget=forms.TextInput(attrs={"type": "color"}))
    eye_color = forms.CharField(label=_("Corner color"), initial="#101B3A",
                                widget=forms.TextInput(attrs={"type": "color"}))
    module_shape = forms.ChoiceField(label=_("Pattern"), choices=[
        ("square", _("Square")), ("rounded", _("Rounded")), ("dots", _("Dots"))])
    eye_frame = forms.ChoiceField(label=_("Corner frame"), choices=[
        ("square", _("Square")), ("rounded", _("Rounded")), ("circle", _("Circle"))])
    eye_ball = forms.ChoiceField(label=_("Corner dot"), choices=[
        ("square", _("Square")), ("rounded", _("Rounded")), ("circle", _("Circle"))])
    frame = forms.ChoiceField(label=_("Frame"), choices=[
        ("none", _("None")), ("bottom", _("Label below")), ("top", _("Label above")),
        ("pill", _("Button below"))])
    frame_color = forms.CharField(label=_("Frame color"), initial="#101B3A",
                                  widget=forms.TextInput(attrs={"type": "color"}))
    cta_text = forms.CharField(label=_("Call to action"), max_length=30, required=False,
                               initial="", widget=forms.TextInput(
                                   attrs={"placeholder": _("Scan me")}))
    logo = forms.ImageField(label=_("Logo"), required=False,
                            widget=forms.ClearableFileInput(
                                attrs={"accept": "image/png,image/jpeg,image/webp"}))
    remove_logo = forms.BooleanField(label=_("Remove logo"), required=False)


    @classmethod
    def initial_from(cls, style: dict) -> dict:
        s = QRStyle.from_dict(style)
        return {**s.to_dict(), "eye_color": s.eye, "frame_color": s.frame_fill}

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if logo and hasattr(logo, "content_type"):
            if logo.size > MAX_LOGO_BYTES:
                raise ValidationError(_("The logo must be 1 MB or smaller."))
            logo.seek(0)
            with Image.open(logo) as img:
                if img.format not in ("PNG", "JPEG", "WEBP"):
                    raise ValidationError(_("Upload a PNG, JPEG or WebP image."))
            logo.seek(0)
        return logo

    def style(self) -> QRStyle:
        d = self.cleaned_data
        try:
            return QRStyle.from_dict({
                "fg": d["fg"], "bg": d["bg"], "eye_color": d["eye_color"],
                "module_shape": d["module_shape"], "eye_frame": d["eye_frame"],
                "eye_ball": d["eye_ball"], "frame": d["frame"],
                "frame_color": d["frame_color"], "cta_text": d.get("cta_text", ""),
            })
        except StyleError as exc:
            raise ValidationError(str(exc)) from exc


class BulkUploadForm(forms.Form):
    file = forms.FileField(label=_("CSV file"),
                           widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv"}))
    folder = forms.ModelChoiceField(label=_("Put codes in folder"),
                                    queryset=Folder.objects.none(), required=False,
                                    empty_label=_("No folder"))

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["folder"].queryset = Folder.objects.for_org(organization)


class FolderForm(forms.Form):
    name = forms.CharField(label=_("Folder name"), max_length=80)


STATUS_FILTERS = [("", _("All statuses")), ("active", _("Active")), ("paused", _("Paused")),
                  ("expired", _("Expired")), ("suspended", _("Suspended"))]
SORTS = [("-created_at", _("Newest")), ("name", _("Name")), ("-total_scans", _("Most scans")),
         ("-last_scan_at", _("Recently scanned"))]

__all__ = ["QRCode"]
