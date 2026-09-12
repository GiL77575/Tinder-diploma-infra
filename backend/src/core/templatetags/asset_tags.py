"""{% vstatic %} — як {% static %}, плюс ?v=<mtime> щоб браузер не тримав старий CSS/JS."""
import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def vstatic(path):
    """{% vstatic 'css/home.css' %} — {% static %} + ?v=<mtime> для кешбастингу."""
    url = static(path)

    absolute_path = finders.find(path)
    if not absolute_path:
        return url

    try:
        version = int(os.path.getmtime(absolute_path))
    except OSError:
        return url

    separator = '&' if '?' in url else '?'
    return f'{url}{separator}v={version}'
