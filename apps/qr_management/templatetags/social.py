from django import template
from django.utils.safestring import mark_safe

from apps.qr_management import social

register = template.Library()


@register.simple_tag
def social_tile(platform, size="size-10", radius=7):
    return mark_safe(social.icon_tile(platform, size, int(radius)))  # noqa: S308 — static SVG


@register.simple_tag
def social_icon(platform, size="size-5"):
    return mark_safe(social.icon_svg(platform, size))  # noqa: S308 — static SVG


@register.filter
def social_name(platform):
    p = social.PLATFORMS.get(platform) or social.PLATFORMS["link"]
    return p.name


@register.simple_tag
def social_platforms():
    return list(social.PLATFORMS.values())
