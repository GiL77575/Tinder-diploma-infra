from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Спільні дрібні речі для всіх застосунків (template tags, Site sync)."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        self._sync_site_domain()

    @staticmethod
    def _sync_site_domain():
        """Keep django.contrib.sites in sync with PUBLIC_HOST for allauth OAuth."""
        from django.conf import settings

        public_host = getattr(settings, 'PUBLIC_HOST', '').strip()
        if not public_host:
            return

        try:
            from django.contrib.sites.models import Site
        except Exception:
            return

        try:
            site = Site.objects.filter(pk=settings.SITE_ID).first()
            if site is None:
                return
            if site.domain != public_host:
                site.domain = public_host
                site.name = public_host
                site.save(update_fields=['domain', 'name'])
        except Exception:
            # DB may be unavailable during migrate / first boot
            pass
