# Generated manually: доповнюємо довідник тегів категорії "Інтерес" новими
# назвами, які показані в макеті сторінки "Знайомства" ("Загальні інтереси").

from django.db import migrations

# Нові інтереси, яких ще немає в довіднику Tag (категорія "interest").
NEW_INTEREST_TAGS = [
    'Прогулянки',
    'Кава',
    'Їжа',
    'Психологія',
    'Настільні ігри',
    'Технології',
    'Шопінг',
    'Мода',
    'Татуювання',
    "Кар'єра та бізнес",
    'Йога',
    'Велосипед',
    'Авто / Мото',
    'Стендап',
    'Аніме',
    'Веганство',
    'Кемпінг',
]


def add_interest_tags(apps, schema_editor):
    """Створює нові теги-інтереси, якщо їх ще немає (безпечно повторно запускати)."""
    Tag = apps.get_model('profiles', 'Tag')
    for name in NEW_INTEREST_TAGS:
        Tag.objects.get_or_create(name=name, category='interest')


def remove_interest_tags(apps, schema_editor):
    """Відкат: прибирає теги, додані цією міграцією."""
    Tag = apps.get_model('profiles', 'Tag')
    Tag.objects.filter(name__in=NEW_INTEREST_TAGS, category='interest').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0005_profilemode_age_preference_and_more'),
    ]

    operations = [
        migrations.RunPython(add_interest_tags, remove_interest_tags),
    ]
