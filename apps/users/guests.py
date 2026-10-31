"""Transparent guest accounts for visitors who have not signed in.

StudyShare stores ownership on conversations, notes, quizzes, attempts, and
reports with a required user foreign key, so guests are represented by a real
Django user with an unusable password. The account is created and logged in
automatically by ``apps.core.middleware.GuestSessionMiddleware``.
"""

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Profile
from .roles import ensure_profile

GUEST_USERNAME_PREFIX = 'guest_'
GUEST_DISPLAY_NAME = 'Guest'
GUEST_INITIALS = 'G'


def is_guest(user):
    """Return True when ``user`` is an authenticated temporary guest."""
    if not user or not user.is_authenticated:
        return False
    try:
        return bool(user.profile.is_guest)
    except Profile.DoesNotExist:
        return False


def display_identity(user):
    """Return the name and initials shown in the StudyShare shell."""
    if is_guest(user):
        return GUEST_DISPLAY_NAME, GUEST_INITIALS
    display_name = user.get_full_name().strip() or user.username
    initials = (
        ''.join(part[0] for part in display_name.split()[:2]).upper()
        or display_name[:1].upper()
    )
    return display_name, initials


def create_guest_user():
    """Create and return a fresh guest user with a student profile."""
    User = get_user_model()
    for _ in range(10):
        username = f'{GUEST_USERNAME_PREFIX}{uuid.uuid4().hex[:12]}'
        if not User.objects.filter(username=username).exists():
            break
    else:  # pragma: no cover - collisions are practically impossible
        username = f'{GUEST_USERNAME_PREFIX}{uuid.uuid4().hex}'

    guest = User.objects.create_user(username=username, password=None)
    profile = ensure_profile(guest)
    profile.role = Profile.ROLE_STUDENT
    profile.is_guest = True
    profile.save(update_fields=['role', 'is_guest'])
    # Clear the reverse OneToOne cache populated by profile creation so
    # callers immediately see is_guest=True.
    guest.refresh_from_db()
    return guest


def upgrade_guest_user(user, *, username, first_name, last_name, email,
                       password):
    """Turn the current guest into a registered account in place.

    Using the same user row keeps every conversation, note, quiz, and
    attempt created before registration.
    """
    with transaction.atomic():
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.set_password(password)
        user.save()
        profile = ensure_profile(user)
        profile.is_guest = False
        profile.role = Profile.ROLE_STUDENT
        profile.save(update_fields=['is_guest', 'role'])
        # Drop the old guest profile from the reverse OneToOne cache.
        user.refresh_from_db()
    return user


def merge_guest_data(guest, target):
    """Move everything owned by ``guest`` to ``target``, then delete the guest."""
    if not guest or not target or guest.pk == target.pk:
        return
    if not is_guest(guest):
        return

    # Imported lazily so app loading never depends on this helper.
    from apps.chat.models import Conversation
    from apps.notes.models import Note, QuizAttempt, QuizSet

    with transaction.atomic():
        Conversation.objects.filter(user=guest).update(user=target)
        Note.objects.filter(uploaded_by=guest).update(uploaded_by=target)
        QuizSet.objects.filter(created_by=guest).update(created_by=target)
        QuizAttempt.objects.filter(taker=guest).update(taker=target)

        guest.delete()


def delete_stale_guests(days=30):
    """Delete abandoned guest accounts and everything still owned by them."""
    cutoff = timezone.now() - timedelta(days=max(1, int(days)))
    User = get_user_model()
    stale_ids = list(
        User.objects.filter(profile__is_guest=True)
        .filter(
            Q(last_login__lt=cutoff)
            | Q(last_login__isnull=True, date_joined__lt=cutoff)
        )
        .values_list('pk', flat=True)
    )
    if stale_ids:
        User.objects.filter(pk__in=stale_ids).delete()
    return len(stale_ids)
