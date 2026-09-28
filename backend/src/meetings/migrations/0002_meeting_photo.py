from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('meetings', '0001_meeting_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='meeting',
            name='photo_public_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='meeting',
            name='photo_url',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
