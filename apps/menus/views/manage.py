from csp.decorators import csp_replace
from django.contrib import messages
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from apps.organizations.permissions import can, require_capability, require_module

from .. import services
from ..forms import CategoryForm, ItemForm, SettingsForm, StartForm
from ..models import Menu, MenuCategory, MenuItem


def _menus(request):
    return Menu.objects.for_org(request.organization)


def _menu(request, pk):
    return get_object_or_404(_menus(request).select_related("qr_code"), pk=pk)


def _category(request, menu, cat_id):
    return get_object_or_404(MenuCategory.objects.for_org(request.organization), pk=cat_id,
                             menu=menu)


def _item(request, menu, item_id):
    return get_object_or_404(MenuItem.objects.for_org(request.organization), pk=item_id,
                             menu=menu)


def _builder(org_slug, pk, anchor=""):
    resp = redirect("menu_builder", org_slug=org_slug, pk=pk)
    if anchor:
        resp["Location"] += f"#{anchor}"
    return resp


@require_module("menus")
@require_capability("content.view")
def menu_list(request, org_slug):
    menus = _menus(request).annotate(n_items=Count("items", distinct=True),
                                     n_categories=Count("categories", distinct=True))
    return render(request, "menus/list.html", {"menus": menus})


@require_module("menus")
@require_capability("content.create")
def menu_create(request, org_slug):
    form = StartForm(request.POST or None, initial={
        "currency": "AZN", "language": getattr(request, "LANGUAGE_CODE", "az")})
    if request.method == "POST" and form.is_valid():
        try:
            menu = services.create_menu(organization=request.organization, actor=request.user,
                                        data=form.cleaned_data, request=request)
        except services.MenuError as exc:
            messages.error(request, str(exc))
        else:
            if request.POST.get("starter") == "1":
                from django.utils import translation

                with translation.override(menu.language):  # in the guests' language
                    for name in (_("Hot drinks"), _("Main dishes"), _("Desserts")):
                        services.add_category(menu=menu, name=name)
            messages.success(request, _("Menu created. Add categories and items."))
            return redirect("menu_builder", org_slug=org_slug, pk=menu.pk)
    return render(request, "menus/create.html", {"form": form})


def _tabs(menu, active):
    return {"menu": menu, "tab": active}


@require_module("menus")
@require_capability("content.view")
def menu_builder(request, org_slug, pk):
    menu = _menu(request, pk)
    categories = list(menu.categories.prefetch_related(
        Prefetch("items", queryset=MenuItem.objects.order_by("position", "pk")
                 .prefetch_related("options"))))
    return render(request, "menus/builder.html", {
        **_tabs(menu, "builder"), "categories": categories,
        "category_form": CategoryForm(prefix="new")})


@require_module("menus")
@require_capability("content.edit")
@require_POST
def category_save(request, org_slug, pk, cat_id=None):
    menu = _menu(request, pk)
    category = _category(request, menu, cat_id) if cat_id else None
    prefix = f"cat{cat_id}" if cat_id else "new"
    form = CategoryForm(request.POST, instance=category, prefix=prefix)
    if not form.is_valid():
        messages.error(request, _("Enter a category name."))
        return _builder(org_slug, pk)
    if category is None:
        try:
            category = services.add_category(menu=menu, name=form.cleaned_data["name"],
                                             description=form.cleaned_data["description"])
        except services.MenuError as exc:
            messages.error(request, str(exc))
            return _builder(org_slug, pk)
        messages.success(request, _("Category added."))
    else:
        form.save()
        messages.success(request, _("Category saved."))
    return _builder(org_slug, pk, f"cat-{category.pk}")


@require_module("menus")
@require_capability("content.edit")
@require_POST
def category_move(request, org_slug, pk, cat_id):
    menu = _menu(request, pk)
    category = _category(request, menu, cat_id)
    services.move(category, menu.categories, request.POST.get("direction", "up"))
    return _builder(org_slug, pk, f"cat-{category.pk}")


@require_module("menus")
@require_capability("content.delete")
@require_POST
def category_delete(request, org_slug, pk, cat_id):
    menu = _menu(request, pk)
    category = _category(request, menu, cat_id)
    for item in category.items.all():
        services.delete_item(item=item)
    category.delete()
    messages.success(request, _("Category and its items deleted."))
    return _builder(org_slug, pk)


@require_module("menus")
@require_capability("content.edit")
def item_edit(request, org_slug, pk, item_id=None):
    menu = _menu(request, pk)
    item = _item(request, menu, item_id) if item_id else None
    if item is None and not menu.categories.exists():
        messages.error(request, _("Add a category first."))
        return _builder(org_slug, pk)
    initial = {}
    if item is None and (cat := request.GET.get("category")):
        initial["category"] = cat
    form = ItemForm(request.POST or None, request.FILES or None, instance=item, menu=menu,
                    initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            saved = services.save_item(menu=menu, form=form, options=form.options)
        except services.MenuError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, _("Item saved."))
            if request.POST.get("another") == "1":
                return redirect(f"{request.path.rsplit('/items/', 1)[0]}/items/new/"
                                f"?category={saved.category_id}")
            return _builder(org_slug, pk, f"item-{saved.pk}")
    return render(request, "menus/item_form.html", {**_tabs(menu, "builder"), "form": form,
                                                    "item": item})


@require_module("menus")
@require_capability("content.edit")
@require_POST
def item_action(request, org_slug, pk, item_id):
    menu = _menu(request, pk)
    item = _item(request, menu, item_id)
    action = request.POST.get("action")
    if action in ("up", "down"):
        services.move(item, menu.items.filter(category=item.category), action)
    elif action in MenuItem.Availability.values:
        item.availability = action
        item.save(update_fields=["availability", "updated_at"])
    elif action == "delete" and can(request, "content.delete"):
        services.delete_item(item=item)
        messages.success(request, _("Item deleted."))
        return _builder(org_slug, pk)
    return _builder(org_slug, pk, f"item-{item.pk}")


@require_module("menus")
@require_capability("content.view")
def menu_settings(request, org_slug, pk):
    menu = _menu(request, pk)
    form = SettingsForm(request.POST or None, request.FILES or None, instance=menu)
    if request.method == "POST":
        if not can(request, "content.edit"):
            messages.error(request, _("You don't have permission to do that."))
        elif form.is_valid():
            form.save()
            messages.success(request, _("Menu settings saved."))
            return redirect("menu_settings", org_slug=org_slug, pk=pk)
    return render(request, "menus/settings.html", {**_tabs(menu, "settings"), "form": form})


@require_module("menus")
@require_capability("content.view")
def menu_share(request, org_slug, pk):
    menu = _menu(request, pk)
    return render(request, "menus/share.html", {**_tabs(menu, "share"),
                                                "report": services.report(menu)})


@require_module("menus")
@require_capability("content.edit")
@require_POST
def menu_publish(request, org_slug, pk):
    menu = _menu(request, pk)
    publish = request.POST.get("publish") == "1"
    try:
        services.set_published(menu=menu, actor=request.user, published=publish,
                               request=request)
    except services.MenuError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, _("Your menu is live. Print the QR code for tables.")
                         if publish else _("The menu is hidden. Its QR code shows nothing now."))
    return redirect("menu_share", org_slug=org_slug, pk=pk)


@require_module("menus")
@require_capability("content.delete")
@require_POST
def menu_delete(request, org_slug, pk):
    menu = _menu(request, pk)
    if request.POST.get("confirm", "").strip() != menu.name.strip():
        messages.error(request, _("Type the menu name exactly to confirm deletion."))
        return redirect("menu_settings", org_slug=org_slug, pk=pk)
    services.delete_menu(menu=menu, actor=request.user, request=request)
    messages.success(request, _("Menu deleted."))
    return redirect("menu_list", org_slug=org_slug)


@require_module("menus")
@require_capability("content.view")
@xframe_options_sameorigin
@csp_replace({"frame-ancestors": ["'self'"]})
def menu_preview(request, org_slug, pk):
    from .public import render_menu

    return render_menu(request, _menu(request, pk), preview=True)
