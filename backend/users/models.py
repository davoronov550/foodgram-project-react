from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import F, Q


class User(AbstractUser):
    """Модель пользователя."""
    email = models.EmailField(
        verbose_name='Адрес электронной почты',
        max_length=254,
        unique=True,
        help_text=('Укажите свой email'),
    )
    username = models.CharField(
        verbose_name=('Логин'),
        max_length=150,
        unique=True,
        help_text=('Укажите свой никнейм'),
    )
    first_name = models.CharField(
        verbose_name='Имя',
        max_length=150,
        help_text=('Укажите своё имя'),
    )
    last_name = models.CharField(
        verbose_name='Фамилия',
        max_length=150,
        help_text=('Укажите свою фамилию'),
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ('username',)

    class Meta:
        ordering = ('username', )
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        constraints = [
            models.UniqueConstraint(
                fields=['username', 'email'],
                name='unique_user'
            )
        ]

    def __str__(self):
        return self.username


class GoogleAccount(models.Model):
    """Привязка аккаунта пользователя к его Google-идентичности."""
    user = models.OneToOneField(
        User,
        related_name='google_account',
        verbose_name='Пользователь',
        on_delete=models.CASCADE,
    )
    google_sub = models.CharField(
        verbose_name='Google subject ID',
        max_length=255,
        unique=True,
        db_index=True,
        help_text='Стабильный идентификатор пользователя в Google '
                  '(claim "sub").',
    )
    email = models.EmailField(
        verbose_name='Email из Google',
        max_length=254,
    )
    created_at = models.DateTimeField(
        verbose_name='Дата привязки',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'Google-аккаунт'
        verbose_name_plural = 'Google-аккаунты'

    def __str__(self):
        return f'Google-аккаунт пользователя {self.user}'


class Follow(models.Model):
    """Модель подписки."""
    user = models.ForeignKey(
        User,
        related_name='follower',
        verbose_name='Подписчик',
        on_delete=models.CASCADE
    )
    author = models.ForeignKey(
        User,
        related_name='following',
        verbose_name='Автор',
        on_delete=models.CASCADE
    )

    class Meta:
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        constraints = [
            models.UniqueConstraint(
                fields=['author', 'user'],
                name='unique_follow'),
            models.CheckConstraint(
                check=~Q(user=F('author')),
                name='no_self_follow')
        ]

    def __str__(self):
        return f'Пользователь {self.user} подписан(а) на {self.author}'
