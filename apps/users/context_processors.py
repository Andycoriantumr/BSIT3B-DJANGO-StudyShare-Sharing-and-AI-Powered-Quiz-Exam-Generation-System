from .guests import is_guest
from .roles import get_user_role, can_moderate, can_admin


def user_role(request):
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {}
    role = get_user_role(request.user)
    return {
        'user_role': role,
        'is_guest': is_guest(request.user),
        'is_student': role == 'student',
        'is_instructor': role == 'instructor',
        'is_admin_role': role == 'admin',
        'can_moderate': can_moderate(request.user),
        'can_admin': can_admin(request.user),
    }
