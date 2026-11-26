from csp.decorators import csp_replace
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from apps.organizations.permissions import can, require_capability, require_module

from .. import services
from ..forms import (
    PRESET_COLORS,
    ContactForm,
    DesignForm,
    PhotoForm,
    ProfileForm,
    SocialForm,
    StartForm,
)
from ..models import MAX_GALLERY, Card, CardPhoto

STEPS = [
    ("design", gettext_lazy("Template"), DesignForm),
    ("profile", gettext_lazy("Profile"), ProfileForm),
    ("contact", gettext_lazy("Contact"), ContactForm),
    ("social", gettext_lazy("Social media"), SocialForm),
    ("gallery", gettext_lazy("Gallery"), None),
    ("share", gettext_lazy("Publish & share"), None),
]
STEP_KEYS = [s[0] for s in STEPS]


def _cards(request):
    return Card.objects.for_org(request.organization)


def _card(request, pk):
    return get_object_or_404(_cards(request).select_related("qr_code"), pk=pk)


@require_module("cards")
@require_capability("content.view")
def card_list(request, org_slug):
    cards = list(_cards(request))
    return render(request, "cards/list.html", {"cards": cards})


@require_module("cards")
@require_capability("content.create")
def card_create(request, org_slug):
    form = StartForm(request.POST or None, initial={"kind": "person", "template": "classic"})
    if request.method == "POST" and form.is_valid():
        try:
            card = services.create_card(organization=request.organization, actor=request.user,
                                        data=form.cleaned_data, request=request)
        except services.CardError as exc:
            messages.error(request, str(exc))
        else:
            return redirect("card_step", org_slug=org_slug, pk=card.pk, step="profile")
    return render(request, "cards/create.html", {"form": form})


def _step_context(request, card, step, **extra):
    index = STEP_KEYS.index(step)
    return {"card": card, "step": step, "steps": STEPS, "step_index": index,
            "prev_step": STEP_KEYS[index - 1] if index else None,
            "next_step": STEP_KEYS[index + 1] if index + 1 < len(STEP_KEYS) else None,
            "preset_colors": PRESET_COLORS, **extra}


@require_module("cards")
@require_capability("content.view")
def card_step(request, org_slug, pk, step):
    card = _card(request, pk)
    if step not in STEP_KEYS:
        return redirect("card_step", org_slug=org_slug, pk=pk, step="design")
    form_class = {k: f for k, _label, f in STEPS}[step]
    form = None
    if form_class is not None:
        if form_class is SocialForm:
            form = SocialForm(request.POST or None, instance=card)
        else:
            form = form_class(request.POST or None, request.FILES or None, instance=card)
        if request.method == "POST":
            if not can(request, "content.edit"):
                messages.error(request, _("You don't have permission to do that."))
                return redirect("card_step", org_slug=org_slug, pk=pk, step=step)
            if form.is_valid():
                services.save_step(card=card, actor=request.user, form=form, request=request)
                messages.success(request, _("Saved."))
                nxt = request.POST.get("next") or step
                if nxt not in STEP_KEYS:
                    nxt = step
                return redirect("card_step", org_slug=org_slug, pk=pk, step=nxt)
    extra = {}
    if step == "gallery":
        extra = {"photo_form": PhotoForm(), "photos": card.photos.all(),
                 "max_gallery": MAX_GALLERY}
    if step == "share":
        extra = {"stats": services.stats(card)}
    return render(request, f"cards/steps/{step}.html",
                  _step_context(request, card, step, form=form, **extra))


@require_module("cards")
@require_capability("content.edit")
@require_POST
def card_photo_add(request, org_slug, pk):
    card = _card(request, pk)
    form = PhotoForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            services.add_photo(card=card, upload=form.cleaned_data["image"],
                               caption=form.cleaned_data.get("caption", ""))
            messages.success(request, _("Photo added."))
        except services.CardError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
    return redirect("card_step", org_slug=org_slug, pk=pk, step="gallery")


@require_module("cards")
@require_capability("content.edit")
@require_POST
def card_photo_delete(request, org_slug, pk, photo_id):
    card = _card(request, pk)
    photo = get_object_or_404(CardPhoto.objects.for_org(request.organization), pk=photo_id,
                              card=card)
    services.delete_photo(photo=photo)
    messages.success(request, _("Photo deleted."))
    return redirect("card_step", org_slug=org_slug, pk=pk, step="gallery")


@require_module("cards")
@require_capability("content.edit")
@require_POST
def card_publish(request, org_slug, pk):
    card = _card(request, pk)
    publish = request.POST.get("publish") == "1"
    try:
        services.set_published(card=card, actor=request.user, published=publish,
                               request=request)
    except services.CardError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, _("Your card is live. Share the link or print the QR code.")
                         if publish else _("The card is hidden. Its link shows nothing now."))
    return redirect("card_step", org_slug=org_slug, pk=pk, step="share")


@require_module("cards")
@require_capability("content.delete")
@require_POST
def card_delete(request, org_slug, pk):
    card = _card(request, pk)
    if request.POST.get("confirm", "").strip() != card.name.strip():
        messages.error(request, _("Type the card name exactly to confirm deletion."))
        return redirect("card_step", org_slug=org_slug, pk=pk, step="share")
    services.delete_card(card=card, actor=request.user, request=request)
    messages.success(request, _("Card deleted."))
    return redirect("card_list", org_slug=org_slug)


@require_module("cards")
@require_capability("content.view")
@xframe_options_sameorigin
@csp_replace({"frame-ancestors": ["'self'"]})
def card_preview(request, org_slug, pk):
    """Live preview inside the editor (iframe). Not counted as a view."""
    from .public import render_card

    return render_card(request, _card(request, pk), preview=True)
