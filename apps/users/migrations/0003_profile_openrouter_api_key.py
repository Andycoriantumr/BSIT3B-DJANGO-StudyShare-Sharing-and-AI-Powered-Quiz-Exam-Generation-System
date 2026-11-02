from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_profile_is_guest'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='openrouter_api_key',
            field=models.CharField(
                blank=True,
                default='',
                help_text=(
                    'Personal OpenRouter API key for this user. '
                    'Falls back to the site-wide OPENROUTER_API_KEY when blank.'
                ),
                max_length=255,
            ),
        ),
    ]
