from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0008_alter_recipe_cooking_time_and_more'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='recipe',
            index=models.Index(
                fields=['-pub_date'], name='recipe_pub_date_idx'
            ),
        ),
    ]
