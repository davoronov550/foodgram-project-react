import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('users', '0003_alter_user_password'),
    ]

    operations = [
        migrations.CreateModel(
            name='GoogleAccount',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID')),
                ('google_sub', models.CharField(
                    db_index=True,
                    help_text='Стабильный идентификатор пользователя в '
                              'Google (claim "sub").',
                    max_length=255, unique=True,
                    verbose_name='Google subject ID')),
                ('email', models.EmailField(
                    max_length=254, verbose_name='Email из Google')),
                ('created_at', models.DateTimeField(
                    auto_now_add=True, verbose_name='Дата привязки')),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='google_account',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Google-аккаунт',
                'verbose_name_plural': 'Google-аккаунты',
            },
        ),
    ]
