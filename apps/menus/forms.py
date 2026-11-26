import re
from decimal import Decimal, InvalidOperation

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.qr_management.types import PhoneField

from .models import Menu, MenuCategory, MenuItem

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_OPTIONS = 8
IMG = {"accept": "image/png,image/jpeg,image/webp"}


class StartForm(forms.ModelForm):
    class Meta:
        model = Menu
        fields = ["name", "currency", "language"]
        widgets = {"name": forms.TextInput(attrs={"placeholder": _("e.g. Main menu")})}


class SettingsForm(forms.ModelForm):
    phone = PhoneField(label=_("Phone"), max_length=32, required=False)
    remove_logo = forms.BooleanField(label=_("Remove logo"), required=False)
    remove_cover = forms.BooleanField(label=_("Remove cover"), required=False)

    class Meta:
        model = Menu
        fields = ["name", "description", "currency", "language", "layout", "accent_color",
                  "logo", "cover", "address", "phone", "hours", "wifi_name", "wifi_password",
                  "footer_note"]
        widgets = {"accent_color": forms.TextInput(attrs={"type": "color"}),
                   "layout": forms.RadioSelect,
                   "logo": forms.ClearableFileInput(attrs=IMG),
                   "cover": forms.ClearableFileInput(attrs=IMG)}

    def clean_accent_color(self):
        color = (self.cleaned_data.get("accent_color") or "").strip()
        if not HEX.match(color):
            raise forms.ValidationError(_("Choose a valid color."))
        return color.upper()

    def save(self, commit=True):
        menu = super().save(commit=False)
        for field in ("logo", "cover"):
            if self.cleaned_data.get(f"remove_{field}") and getattr(menu, field):
                getattr(menu, field).delete(save=False)
                setattr(menu, field, "")
        if commit:
            menu.save()
        return menu


class CategoryForm(forms.ModelForm):
    class Meta:
        model = MenuCategory
        fields = ["name", "description", "is_visible"]
        widgets = {"name": forms.TextInput(attrs={"placeholder": _("e.g. Breakfast")})}


class ItemForm(forms.ModelForm):
    tags = forms.MultipleChoiceField(label=_("Labels"), choices=MenuItem.TAGS, required=False,
                                     widget=forms.CheckboxSelectMultiple)
    remove_image = forms.BooleanField(label=_("Remove photo"), required=False)

    class Meta:
        model = MenuItem
        fields = ["category", "name", "description", "image", "price", "discount_price",
                  "unit", "availability", "tags"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3}),
                   "image": forms.ClearableFileInput(attrs=IMG),
                   "price": forms.NumberInput(attrs={"step": "0.01", "min": "0",
                                                     "inputmode": "decimal"}),
                   "discount_price": forms.NumberInput(attrs={"step": "0.01", "min": "0",
                                                              "inputmode": "decimal"}),
                   "name": forms.TextInput(attrs={"placeholder": _("e.g. Cappuccino")})}

    def __init__(self, *args, menu, **kwargs):
        super().__init__(*args, **kwargs)
        self.menu = menu
        self.fields["category"].queryset = MenuCategory.objects.for_org(
            menu.organization).filter(menu=menu)
        self.fields["category"].empty_label = None
        for kind in ("variant", "addon"):
            for i in range(1, MAX_OPTIONS + 1):
                self.fields[f"{kind}_{i}_name"] = forms.CharField(max_length=80, required=False)
                self.fields[f"{kind}_{i}_price"] = forms.CharField(max_length=12, required=False)
        if self.instance.pk and not self.is_bound:
            for kind in ("variant", "addon"):
                for i, opt in enumerate(self.instance.options.filter(kind=kind)[:MAX_OPTIONS],
                                        start=1):
                    self.initial[f"{kind}_{i}_name"] = opt.name
                    self.initial[f"{kind}_{i}_price"] = opt.price

    def option_rows(self, kind: str):
        rows = [{"n": i, "name": self[f"{kind}_{i}_name"], "price": self[f"{kind}_{i}_price"]}
                for i in range(1, MAX_OPTIONS + 1)]
        filled = [r["n"] for r in rows if (r["name"].value() or "")]
        visible = max(filled[-1] if filled else 0, 1)
        return rows, visible

    def variant_rows(self):
        return self.option_rows("variant")

    def addon_rows(self):
        return self.option_rows("addon")

    def clean(self):
        data = super().clean()
        price, discount = data.get("price"), data.get("discount_price")
        if price is not None and discount is not None and discount >= price:
            self.add_error("discount_price", _("The discounted price must be lower than the "
                                               "price."))
        options = []
        for kind in ("variant", "addon"):
            for i in range(1, MAX_OPTIONS + 1):
                name = (data.pop(f"{kind}_{i}_name", "") or "").strip()
                raw = (data.pop(f"{kind}_{i}_price", "") or "").strip().replace(",", ".")
                if not name and not raw:
                    continue
                if not name:
                    self.add_error(None, _("Every option needs a name."))
                    continue
                try:
                    value = Decimal(raw or "0")
                    if value < 0:
                        raise InvalidOperation
                except InvalidOperation:
                    self.add_error(None, _("“%(name)s”: enter a valid price.") % {"name": name})
                    continue
                options.append({"kind": kind, "name": name[:80],
                                "price": value.quantize(Decimal("0.01"))})
        self.options = options
        return data

    def save(self, commit=True):
        item = super().save(commit=False)
        item.tags = self.cleaned_data.get("tags") or []
        if self.cleaned_data.get("remove_image") and item.image:
            item.image.delete(save=False)
            item.image = ""
        if commit:
            item.save()
        return item
