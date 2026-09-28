"""Статика: CSS/JS мають іти з /app/static/, не з nginx /static/."""

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse


def _body(response):
    if getattr(response, 'streaming', False):
        return b''.join(response.streaming_content).decode('utf-8', errors='replace')
    return response.content.decode('utf-8', errors='replace')


class FrontendStaticServeTests(TestCase):
    def test_chat_css_is_served_under_app_static(self):
        response = self.client.get('/app/static/css/chat.css')
        self.assertEqual(response.status_code, 200)
        body = _body(response)
        self.assertIn('.swipe-btn__icon--heart', body)
        self.assertIn('.swipe-btn__icon--star', body)
        self.assertIn('body.page-chat[data-mode="bff"] .swipe-btn .swipe-btn__icon--heart', body)

    def test_chat_js_has_no_swipe_card_interest_chips(self):
        response = self.client.get('/app/static/js/chat.js')
        self.assertEqual(response.status_code, 200)
        body = _body(response)
        self.assertNotIn('renderCandidateTags', body)
        self.assertIn('swipe-card__matches', body)

    def test_legacy_static_prefix_still_serves_files(self):
        response = self.client.get('/static/js/chat.js')
        self.assertEqual(response.status_code, 200)

    def test_home_page_links_app_static_not_bare_static(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('/app/static/css/crush.css', content)
        self.assertNotIn('href="/static/css/crush.css"', content)


class AssetTagTests(SimpleTestCase):
    @override_settings(STATIC_URL='/app/static/')
    def test_vstatic_includes_release_token(self):
        from django.template import Context, Template

        html = Template('{% load asset_tags %}{% vstatic "js/chat.js" %}').render(Context())
        self.assertTrue(html.startswith('/app/static/js/chat.js?'))
        self.assertIn('figma-card-20260928', html)
