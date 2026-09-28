"""Аліас: не видаляє Tyrion. Те саме, що seed_demo_profiles --reset.

    python manage.py seed_test_profiles
    python manage.py seed_test_profiles --like-target tyrion@gmail.com
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand

from profiles.management.commands.seed_demo_profiles import DEFAULT_LIKE_TARGET


class Command(BaseCommand):
    help = (
        'Безпечний аліас seed_demo_profiles --reset. '
        '20 Dating + 20 BFF зі зустрічами. Стирає лише @crushme.test.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--like-target',
            dest='like_target',
            default=DEFAULT_LIKE_TARGET,
            help='Email, якому всі демо ставлять лайк (за замовчуванням tyrion@gmail.com).',
        )

    def handle(self, *args, **options):
        call_command(
            'seed_demo_profiles',
            like_target=options['like_target'],
            reset=True,
        )
