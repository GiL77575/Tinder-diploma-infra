# Generated manually: доповнюємо довідники тегів "Хобі" та "Мова" новими
# назвами з макету сторінки "Друзі" ("Хобі та рівень" / "Мови"), а також
# перейменовуємо "Велоспорт" на "Велосипед" — так само, як підпис у макеті.

from django.db import migrations

# Нові хобі, яких ще немає в довіднику Tag (категорія "hobby").
NEW_HOBBY_TAGS = [
    'Фотографія',
    'Відео',
    'Танці',
    'IT',
]

# Нові мови, яких ще немає в довіднику Tag (категорія "language").
NEW_LANGUAGE_TAGS = [
    'Італійська',
    'Китайська',
    'Японська',
    'Корейська',
    'Чеська',
]

OLD_HOBBY_NAME = 'Велоспорт'
NEW_HOBBY_NAME = 'Велосипед'


def seed_tags(apps, schema_editor):
    """Перейменовує «Велоспорт» і додає нові теги хобі/мов (безпечно повторно запускати)."""
    Tag = apps.get_model('profiles', 'Tag')

    old_bike = Tag.objects.filter(name=OLD_HOBBY_NAME, category='hobby').first()
    if old_bike and not Tag.objects.filter(name=NEW_HOBBY_NAME, category='hobby').exists():
        old_bike.name = NEW_HOBBY_NAME
        old_bike.save(update_fields=['name'])

    for name in NEW_HOBBY_TAGS:
        Tag.objects.get_or_create(name=name, category='hobby')
    for name in NEW_LANGUAGE_TAGS:
        Tag.objects.get_or_create(name=name, category='language')


def unseed_tags(apps, schema_editor):
    """Відкат: повертає стару назву хобі й прибирає теги, додані цією міграцією."""
    Tag = apps.get_model('profiles', 'Tag')

    new_bike = Tag.objects.filter(name=NEW_HOBBY_NAME, category='hobby').first()
    if new_bike:
        new_bike.name = OLD_HOBBY_NAME
        new_bike.save(update_fields=['name'])

    Tag.objects.filter(name__in=NEW_HOBBY_TAGS, category='hobby').delete()
    Tag.objects.filter(name__in=NEW_LANGUAGE_TAGS, category='language').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0006_seed_extra_interest_tags'),
    ]

    operations = [
        migrations.RunPython(seed_tags, unseed_tags),
    ]
