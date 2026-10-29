from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def _create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def _save_profile(sender, instance, **kwargs):
    try:
        if hasattr(instance, 'profile'):
            instance.profile.save()
    except Profile.DoesNotExist:
        Profile.objects.create(user=instance)
