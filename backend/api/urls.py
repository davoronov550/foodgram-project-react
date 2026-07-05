from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    GoogleAuthView,
    IngredientViewSet,
    RecipeViewSet,
    TagViewSet,
    CustomUserViewSet
)

app_name = 'api'

router = DefaultRouter()
router.register(r'ingredients', IngredientViewSet, basename='ingredients')
router.register(r'tags', TagViewSet, basename='tags')
router.register(r'recipes', RecipeViewSet, basename='recipes')
router.register(r'users', CustomUserViewSet, basename='users')


urlpatterns = [
    path('', include(router.urls)),
    path('auth/google/', GoogleAuthView.as_view(), name='google-auth'),
    path('', include('djoser.urls')),
    path('auth/', include('djoser.urls.authtoken')),
]
