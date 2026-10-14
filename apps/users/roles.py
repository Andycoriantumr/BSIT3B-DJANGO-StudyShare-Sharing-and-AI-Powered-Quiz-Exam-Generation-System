"""Role helpers and decorators for Student / Instructor / Administrator."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect

from .models import Profile


def get_user_role(user):
    if not user or not user.is_authenticated:
        return None
    if getattr(user, 'is_superuser', False):
        # Superuser acts as Administrator everywhere.
        return Profile.ROLE_ADMIN
    try:
        profile = user.profile
    except Profile.DoesNotExist:
        profile, _ = Profile.objects.get_or_create(user=user)
        return profile.role
    return profile.role


def ensure_profile(user):
    if not user or not user.is_authenticated:
        return None
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def is_admin_user(user):
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or get_user_role(user) == Profile.ROLE_ADMIN


def is_instructor_user(user):
    if not user or not user.is_authenticated:
        return False
    return get_user_role(user) == Profile.ROLE_INSTRUCTOR


def can_moderate(user):
    """Instructor/Moderator and Administrator (and superuser)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return get_user_role(user) in (Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN)


def can_admin(user):
    """Administrator (and superuser)."""
    return is_admin_user(user)


def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required(login_url='login')
        def _wrapped(request, *args, **kwargs):
            role = get_user_role(request.user)
            if role in allowed_roles or request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            messages.error(request, 'You do not have permission to access that page.')
            return redirect('dashboard')
        return _wrapped
    return decorator


admin_required = role_required(Profile.ROLE_ADMIN)
instructor_required = role_required(Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN)
