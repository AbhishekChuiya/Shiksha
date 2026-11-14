from django import template
from django.utils import timezone
from django.utils.timesince import timesince
from django.utils.translation import gettext
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

# Minimal line-icon set (24x24, stroke based).
ICONS = {
    "dashboard": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/>',
    "plant": '<path d="M3 21h18M5 21V10l5 3V8l5 3V5h4v16"/>',
    "layers": '<path d="m12 3 9 5-9 5-9-5 9-5z"/><path d="m3 13 9 5 9-5"/>',
    "gauge": '<path d="M4 16a8 8 0 1 1 16 0"/><path d="m12 16 4-5"/>',
    "award": '<circle cx="12" cy="9" r="6"/><path d="m8.6 14-1.6 7 5-3 5 3-1.6-7"/>',
    "bulb": '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.5 1 2.5h6c0-1 .3-1.8 1-2.5A6 6 0 0 0 12 3z"/>',
    "book": '<path d="M4 4h10a4 4 0 0 1 4 4v12H8a4 4 0 0 1-4-4V4z"/><path d="M4 16a4 4 0 0 1 4-4h10"/>',
    "edit": '<path d="m4 20 4-1 11-11-3-3L5 16l-1 4z"/>',
    "bolt": '<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "contrast": '<circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"/>',
    "speaker": '<path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11"/>',
    "flag": '<path d="M5 21V4h11l-2 4 2 4H5"/>',
    "shield": '<path d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-3z"/><path d="m9 12 2 2 4-4"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M5 19l1.5-1.5M17.5 6.5 19 5"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "cert": '<rect x="3" y="4" width="18" height="13" rx="2"/><circle cx="12" cy="10" r="3"/><path d="m10 13-1 7 3-2 3 2-1-7"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "play": '<path d="m7 4 13 8-13 8V4z"/>',
    "file": '<path d="M14 3H6v18h12V7l-4-4z"/><path d="M14 3v4h4"/>',
    "menu": '<path d="M3 6h18M3 12h18M3 18h18"/>',
    "zap": '<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    "alert": '<path d="M12 3 2 21h20L12 3z"/><path d="M12 10v5M12 18h.01"/>',
    "video": '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10 5-3v10l-5-3"/>',
}

ICONS.update({
    "arrow-right": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "arrow-left": '<path d="M19 12H5M11 6l-6 6 6 6"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "chevron-right": '<path d="m9 6 6 6-6 6"/>',
    "chevron-left": '<path d="m15 6-6 6 6 6"/>',
    "check": '<path d="m5 12 5 5L20 7"/>',
    "check-circle": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    "x": '<path d="M6 6l12 12M18 6 6 18"/>',
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "eye-off": '<path d="M3 3l18 18M10.6 6.1A9.8 9.8 0 0 1 12 6c6.4 0 10 6 10 6a17 17 0 0 1-3.2 3.9M6.6 7.6C3.8 9.3 2 12 2 12s3.6 6 10 6c1.5 0 2.8-.3 4-.8"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9S14.5 18.4 12 21c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    "logout": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
    "repeat": '<path d="M17 2l4 4-4 4"/><path d="M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4"/><path d="M21 13v2a3 3 0 0 1-3 3H3"/>',
    "moon": '<path d="M21 13a9 9 0 1 1-10-10 7 7 0 0 0 10 10z"/>',
    "building": '<rect x="4" y="3" width="10" height="18" rx="1.5"/><path d="M14 9h4a2 2 0 0 1 2 2v10M8 7h2M8 11h2M8 15h2"/>',
    "paperclip": '<path d="m21 11-8.5 8.5a5 5 0 0 1-7-7L14 4a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L15 7"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "flame": '<path d="M12 3c1 3.5 5 5 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4 .3 1.5 1 2 2 2 0-3-1-5 1-8z"/>',
    "leaf": '<path d="M5 19c0-9 5-14 15-14 0 10-5 15-14 15"/><path d="M5 19c3-5 6-7 10-9"/>',
    "command": '<path d="M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3z"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    "home": '<path d="M3 11 12 3l9 8M5 10v10h5v-6h4v6h5V10"/>',
    "grid": '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
    "more": '<circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>',
    "star": '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9L12 3z"/>',
    "refresh": '<path d="M20 11a8 8 0 0 0-14-4M4 4v4h4M4 13a8 8 0 0 0 14 4M20 20v-4h-4"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M16 7l3 3"/>',
    "flag-alt": '<path d="M5 21V4M5 4h12l-2 4 2 4H5"/>',
    "chat": '<path d="M4 5h16v11H9l-5 4V5z"/><path d="M8 9h8M8 12h5"/>',
    "pin": '<path d="M9 3h6l-1 6 3 3H7l3-3-1-6zM12 12v9"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-8 8"/>',
    "edit2": '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2 21a7 7 0 0 1 14 0M17 4.5a3.5 3.5 0 0 1 0 7M22 21a7 7 0 0 0-4-6.3"/>',
    "upload": '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>',
    "download": '<path d="M12 4v12M7 11l5 5 5-5M4 20h16"/>',
    "up": '<path d="m6 15 6-6 6 6"/>',
    "down": '<path d="m6 9 6 6 6-6"/>',
    "sparkle": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18"/>',
})


@register.simple_tag
def icon(name, cls=""):
    body = ICONS.get(name, ICONS["file"])
    return format_html(
        '<svg class="i {}" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>',
        cls, mark_safe(body))


@register.simple_tag(takes_context=True)
def nav_active(context, *prefixes):
    path = context["request"].path
    for p in prefixes:
        if (p == "/" and path == "/") or (p != "/" and path.startswith(p)):
            return "active"
    return ""


@register.filter
def minutes_label(minutes):
    minutes = int(minutes or 0)
    if minutes < 60:
        return f"{minutes}m"
    return f"{minutes // 60}h {minutes % 60}m"


@register.filter
def ago(dt):
    """'just now' / '5 minutes ago' / '2 hours ago' — one unit only, translated."""
    if not dt:
        return ""
    if (timezone.now() - dt).total_seconds() < 60:
        return gettext("just now")
    return f"{timesince(dt).split(',')[0].replace(chr(160), ' ')} {gettext('ago')}"
