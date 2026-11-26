"""Digital Menu: interactive QR menus for cafés, restaurants, hotels and shops."""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.images import public_path, validate_image
from apps.core.models import TenantModel
from apps.core.utils import generate_token

CURRENCIES = [("AZN", "₼ AZN"), ("USD", "$ USD"), ("EUR", "€ EUR"), ("TRY", "₺ TRY"),
              ("RUB", "₽ RUB"), ("GBP", "£ GBP"), ("GEL", "₾ GEL"), ("AED", "AED")]
SYMBOLS = {"AZN": "₼", "USD": "$", "EUR": "€", "TRY": "₺", "RUB": "₽", "GBP": "£",
           "GEL": "₾", "AED": "AED"}
MONEY = {"max_digits": 10, "decimal_places": 2, "validators": [MinValueValidator(Decimal("0"))]}


def menu_upload_to(instance, filename: str) -> str:
    return public_path("menus", filename)


def _new_token() -> str:
    return generate_token(8)


class Menu(TenantModel):
    class Layout(models.TextChoices):
        LIST = "list", _("List with photos")
        GRID = "grid", _("Photo grid")
        COMPACT = "compact", _("Compact (no photos)")

    public_token = models.CharField(max_length=24, unique=True, default=_new_token,
                                    editable=False)
    name = models.CharField(_("menu name"), max_length=120)
    description = models.CharField(_("short description"), max_length=300, blank=True)
    language = models.CharField(_("menu language"), max_length=8, choices=settings.LANGUAGES,
                                default="az", help_text=_("Language of buttons on the menu."))
    currency = models.CharField(_("currency"), max_length=3, choices=CURRENCIES, default="AZN")
    accent_color = models.CharField(_("colour"), max_length=7, default="#101B3A")
    layout = models.CharField(_("layout"), max_length=8, choices=Layout.choices,
                              default=Layout.LIST)
    logo = models.ImageField(_("logo"), upload_to=menu_upload_to, blank=True,
                             validators=[validate_image])
    cover = models.ImageField(_("cover image"), upload_to=menu_upload_to, blank=True,
                              validators=[validate_image])
    address = models.CharField(_("address"), max_length=240, blank=True)
    phone = models.CharField(_("phone"), max_length=32, blank=True)
    hours = models.CharField(_("opening hours"), max_length=160, blank=True,
                             help_text=_("e.g. Every day 09:00–23:00"))
    wifi_name = models.CharField(_("Wi-Fi name"), max_length=64, blank=True)
    wifi_password = models.CharField(_("Wi-Fi password"), max_length=64, blank=True)
    footer_note = models.CharField(_("note at the bottom"), max_length=300, blank=True,
                                   help_text=_("e.g. Service charge 10% · Prices include VAT"))
    is_published = models.BooleanField(_("published"), default=False)
    qr_code = models.ForeignKey("qr_management.QRCode", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="+")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = _("digital menu")
        verbose_name_plural = _("digital menus")

    def __str__(self) -> str:
        return self.name

    @property
    def public_path(self) -> str:
        return f"/m/{self.public_token}"

    @property
    def public_url(self) -> str:
        return f"{settings.SITE_URL}{self.public_path}"

    @property
    def symbol(self) -> str:
        return SYMBOLS.get(self.currency, self.currency)


class MenuCategory(TenantModel):
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(_("category name"), max_length=80)
    description = models.CharField(_("description"), max_length=200, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(_("visible"), default=True)

    class Meta:
        ordering = ["position", "pk"]
        verbose_name = _("menu category")
        verbose_name_plural = _("menu categories")

    def __str__(self) -> str:
        return self.name


class MenuItem(TenantModel):
    class Availability(models.TextChoices):
        AVAILABLE = "available", _("Available")
        SOLD_OUT = "sold_out", _("Sold out today")
        HIDDEN = "hidden", _("Hidden")

    TAGS = [("popular", _("Popular")), ("new", _("New")), ("spicy", _("Spicy")),
            ("vegetarian", _("Vegetarian")), ("vegan", _("Vegan")),
            ("gluten_free", _("Gluten-free")), ("chef", _("Chef's choice"))]

    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="items")
    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(_("name"), max_length=120)
    description = models.TextField(_("description"), max_length=600, blank=True)
    image = models.ImageField(_("photo"), upload_to=menu_upload_to, blank=True,
                              validators=[validate_image])
    price = models.DecimalField(_("price"), **MONEY)
    discount_price = models.DecimalField(_("discounted price"), null=True, blank=True,
                                         help_text=_("Optional. Shown instead of the price, "
                                                     "with the old price crossed out."),
                                         **MONEY)
    unit = models.CharField(_("portion"), max_length=40, blank=True,
                            help_text=_("e.g. 250 g, 0.5 L, 1 piece"))
    availability = models.CharField(_("availability"), max_length=10,
                                    choices=Availability.choices, default=Availability.AVAILABLE)
    tags = models.JSONField(_("labels"), default=list, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]
        verbose_name = _("menu item")
        verbose_name_plural = _("menu items")

    def __str__(self) -> str:
        return self.name

    @property
    def has_discount(self) -> bool:
        return self.discount_price is not None and self.discount_price < self.price

    @property
    def current_price(self) -> Decimal:
        return self.discount_price if self.has_discount else self.price

    @property
    def discount_percent(self) -> int:
        if not self.has_discount or not self.price:
            return 0
        return round((1 - self.discount_price / self.price) * 100)

    @property
    def tag_labels(self) -> list[tuple[str, str]]:
        names = dict(self.TAGS)
        return [(t, names[t]) for t in self.tags if t in names]


class MenuItemOption(TenantModel):
    """A size/variant (replaces the price) or an add-on (added to the price)."""

    class Kind(models.TextChoices):
        VARIANT = "variant", _("Size / variant")
        ADDON = "addon", _("Extra / add-on")

    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name="options")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    name = models.CharField(_("name"), max_length=80)
    price = models.DecimalField(_("price"), **MONEY)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-kind", "position", "pk"]  # sizes ("variant") before extras ("addon")
        verbose_name = _("menu item option")
        verbose_name_plural = _("menu item options")

    def __str__(self) -> str:
        return f"{self.item} · {self.name}"


class MenuStat(models.Model):
    """Daily counters: menu views, category taps and item opens."""

    class Kind(models.TextChoices):
        VIEW = "view", _("Menu view")
        CATEGORY = "category", _("Category")
        ITEM = "item", _("Item")

    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="stats")
    day = models.DateField()
    kind = models.CharField(max_length=8, choices=Kind.choices)
    object_id = models.PositiveIntegerField(default=0)  # category/item id, 0 for views
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["menu", "day", "kind", "object_id"],
                                               name="menus_stat_unique")]
        indexes = [models.Index(fields=["menu", "kind", "day"])]

    def __str__(self) -> str:
        return f"{self.menu_id} {self.day} {self.kind}:{self.object_id} = {self.count}"
