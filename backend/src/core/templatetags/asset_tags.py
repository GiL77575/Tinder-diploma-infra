"""{% vstatic %} — як {% static %}, плюс ?v=<mtime> щоб браузер не тримав старий CSS/JS."""
import os

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()

# Якщо mtime на сервері не змінився після pull — цей суфікс усе одно скидає кеш.
ASSET_RELEASE = 'edit-chip-click-fix-20260930'


@register.simple_tag
def vstatic(path):
    url = static(path)
    version_parts = [ASSET_RELEASE]

    absolute_path = finders.find(path)
    if absolute_path:
        try:
            version_parts.append(str(int(os.path.getmtime(absolute_path))))
        except OSError:
            pass
    elif getattr(settings, 'DEBUG', False):
        version_parts.append('dev')

    separator = '&' if '?' in url else '?'
    return f'{url}{separator}v={"-".join(version_parts)}'
