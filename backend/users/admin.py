from django.contrib import admin
from django.contrib.auth import get_user_model

from .models import Follow, GoogleAccount

User = get_user_model()


class UserAdmin(admin.ModelAdmin):
    """Отображение модели пользователя в админке."""
    list_display = ('pk', 'username', 'email', 'first_name', 'last_name')
    list_filter = ('email', 'first_name')
    search_fields = ('email', 'first_name')
    ordering = ('username',)
    empty_value_display = '-пусто-'


class FollowAdmin(admin.ModelAdmin):
    """Отображение модели подписок в админке."""
    list_display = ('pk', 'user', 'author')
    list_filter = ('user', 'author')
    empty_value_display = '-пусто-'


class GoogleAccountAdmin(admin.ModelAdmin):
    """Отображение привязок Google-аккаунтов в админке."""
    list_display = ('pk', 'user', 'google_sub', 'email', 'created_at')
    search_fields = ('email', 'google_sub', 'user__username')
    empty_value_display = '-пусто-'


admin.site.register(User, UserAdmin)
admin.site.register(Follow, FollowAdmin)
admin.site.register(GoogleAccount, GoogleAccountAdmin)
