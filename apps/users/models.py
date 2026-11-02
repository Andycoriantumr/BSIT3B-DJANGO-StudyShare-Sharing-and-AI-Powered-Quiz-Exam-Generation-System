from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


def site_openrouter_api_key():
    """Return the site-wide OpenRouter key configured in the environment."""
    return (getattr(settings, 'OPENROUTER_API_KEY', '') or '').strip()


class Profile(models.Model):
    ROLE_STUDENT = 'student'
    ROLE_INSTRUCTOR = 'instructor'
    ROLE_ADMIN = 'admin'
    ROLE_CHOICES = [
        (ROLE_STUDENT, 'Student'),
        (ROLE_INSTRUCTOR, 'Instructor / Moderator'),
        (ROLE_ADMIN, 'Administrator'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name='profile', on_delete=models.CASCADE
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STUDENT)
    is_guest = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Temporary account created automatically for signed-out visitors.',
    )
    openrouter_api_key = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text=(
            'Personal OpenRouter API key for this user. '
            'Falls back to the site-wide OPENROUTER_API_KEY when blank.'
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'

    @property
    def has_openrouter_key(self):
        """True when this user has their own saved OpenRouter key."""
        return bool((self.openrouter_api_key or '').strip())

    @property
    def has_effective_openrouter_key(self):
        """True when this user can use OpenRouter (personal or site key)."""
        return bool(self.get_openrouter_api_key())

    def get_openrouter_api_key(self):
        """Return the user's key, falling back to the site-wide key."""
        return (
            (self.openrouter_api_key or '').strip()
            or site_openrouter_api_key()
        )


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def _create_profile(sender, instance, created, **kwargs):
    if created:
        # Profiles start without a personal key; AI calls fall back to the
        # site-wide OPENROUTER_API_KEY so the secret is never stored per user.
        Profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def _save_profile(sender, instance, **kwargs):
    try:
        if hasattr(instance, 'profile'):
            instance.profile.save()
    except Profile.DoesNotExist:
        Profile.objects.create(user=instance)
