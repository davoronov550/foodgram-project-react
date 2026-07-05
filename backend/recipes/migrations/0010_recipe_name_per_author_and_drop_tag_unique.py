from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0009_recipe_recipe_pub_date_idx'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='tag',
            name='unique_tags',
        ),
        migrations.AlterField(
            model_name='recipe',
            name='name',
            field=models.CharField(
                max_length=200, verbose_name='Название рецепта'
            ),
        ),
        migrations.AddConstraint(
            model_name='recipe',
            constraint=models.UniqueConstraint(
                fields=('author', 'name'),
                name='unique_recipe_per_author',
            ),
        ),
    ]
