"""Маршрути акаунта: головна, вхід, вихід, реєстрація, інфосторінки."""

from django.urls import path

from .views import (
    home_view,
    info_page_view,
    login_view,
    logout_view,
    register_view,
)

urlpatterns = [
    path('', home_view, name='home'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', register_view, name='register'),
    path('about/', info_page_view, {'slug': 'about'}, name='about'),
    path('safety/', info_page_view, {'slug': 'safety'}, name='safety'),
    path('support/', info_page_view, {'slug': 'support'}, name='support'),
    path('demo/anna/', info_page_view, {'slug': 'demo-anna'}, name='demo_anna'),
    path('demo/maryna/', info_page_view, {'slug': 'demo-maryna'}, name='demo_maryna'),
]
