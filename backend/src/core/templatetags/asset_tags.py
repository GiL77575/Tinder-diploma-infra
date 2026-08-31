"""Template tag для "версіонованих" static-посилань.

Проблема: {% static %} завжди повертає той самий URL для файлу (напр.
/static/css/home.css), тож браузер може роками показувати закешовану стару
версію CSS/JS навіть після реального редагування файлу на диску — це і
спричиняло ситуації "зробив правку, а в браузері старий вигляд".

{% vstatic %} робить те саме, що і {% static %}, але додає ?v=<mtime файлу>
в кінець URL. Значення змінюється щоразу, коли файл реально редагується,
тож браузер бачить "новий" URL і завжди підвантажує свіжу версію,
не показуючи застарілий кеш.
"""
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
