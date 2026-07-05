from django.db.models import F, QuerySet, Sum

from recipes.models import RecipeIngredient
from users.models import User


def get_ingredients(user: User) -> QuerySet:
    """
    Cуммирование одинаковых ингредиентов
    из разных рецептов для списка покупок.
    """
    ingredients = RecipeIngredient.objects.filter(
        recipe__shopping__user=user
    ).values(
        name=F('ingredient__name'),
        unit=F('ingredient__unit')
    ).annotate(total=Sum('amount')).values_list(
        'name', 'unit', 'total')
    return ingredients
