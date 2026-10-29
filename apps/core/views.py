from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.users.guests import (
    display_identity,
    is_guest,
    merge_guest_data,
    upgrade_guest_user,
)

User = get_user_model()

MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION = timedelta(minutes=1)
INVALID_LOGIN_MESSAGE = 'Invalid username or password.'
LOCKED_MESSAGE = 'Too many failed attempts. Locked for 1 minute.'


def _reset_lock_state(request):
    request.session['failed_attempts'] = 0
    request.session['lock_time'] = None


def _get_lock_state(request):
    failed_attempts = request.session.get('failed_attempts', 0)
    lock_time = request.session.get('lock_time')

    if not lock_time:
        return failed_attempts, None

    try:
        unlock_time = timezone.datetime.fromisoformat(lock_time)
    except (TypeError, ValueError):
        _reset_lock_state(request)
        return 0, None

    if timezone.now() < unlock_time:
        remaining = int((unlock_time - timezone.now()).total_seconds())
        return failed_attempts, remaining

    _reset_lock_state(request)
    return 0, None


def _set_lock_state(request):
    lock_until = timezone.now() + LOCK_DURATION
    request.session['failed_attempts'] = MAX_FAILED_ATTEMPTS
    request.session['lock_time'] = lock_until.isoformat()
    return int(LOCK_DURATION.total_seconds())


def _validate_registration_data(data, exclude_user=None):
    errors = {}

    username = data.get('username', '').strip()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')

    username_qs = User.objects.all()
    email_qs = User.objects.all()
    if exclude_user is not None:
        username_qs = username_qs.exclude(pk=exclude_user.pk)
        email_qs = email_qs.exclude(pk=exclude_user.pk)

    if not username:
        errors['username'] = 'Username is required.'
    elif username_qs.filter(username=username).exists():
        errors['username'] = 'Username already taken.'

    if not first_name:
        errors['first_name'] = 'First name is required.'

    if not last_name:
        errors['last_name'] = 'Last name is required.'

    if not email:
        errors['email'] = 'Email is required.'
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors['email'] = 'Enter a valid email address.'
        else:
            if email_qs.filter(email=email).exists():
                errors['email'] = 'Email already registered.'

    if not password:
        errors['password'] = 'Password is required.'
    elif len(password) < 8:
        errors['password'] = 'Password must be at least 8 characters.'
    else:
        try:
            validate_password(password)
        except ValidationError as exc:
            errors['password'] = ' '.join(exc.messages)

    if password != confirm_password:
        errors['confirm_password'] = 'Passwords do not match.'

    return errors


@require_http_methods(['GET', 'POST'])
def login_view(request):
    current_is_guest = is_guest(request.user)
    if request.user.is_authenticated and not current_is_guest:
        return redirect('dashboard')

    login_context = {'current_is_guest': current_is_guest}
    failed_attempts, remaining = _get_lock_state(request)
    if remaining is not None:
        messages.error(request, f'Too many failed attempts. Try again in {remaining} seconds.')
        return render(request, 'auth/login.html', {
            **login_context, 'locked': True, 'remaining': remaining,
        })

    if request.method == 'GET':
        return render(request, 'auth/login.html', login_context)

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    user = authenticate(request, username=username, password=password)

    if user is not None:
        _reset_lock_state(request)
        if current_is_guest and user.pk != request.user.pk:
            merge_guest_data(request.user, user)
            login(request, user)
            messages.success(
                request,
                'Signed in. Your guest chats and quizzes were moved to this '
                'account.',
            )
        else:
            login(request, user)
        return redirect('dashboard')

    failed_attempts += 1
    request.session['failed_attempts'] = failed_attempts
    if failed_attempts >= MAX_FAILED_ATTEMPTS:
        remaining = _set_lock_state(request)
        messages.error(request, LOCKED_MESSAGE)
        return render(request, 'auth/login.html', {
            **login_context, 'locked': True, 'remaining': remaining,
        })

    remaining_attempts = MAX_FAILED_ATTEMPTS - failed_attempts
    messages.error(request, f'{INVALID_LOGIN_MESSAGE} {remaining_attempts} attempts remaining.')
    return render(request, 'auth/login.html', login_context)


def logout_view(request):
    logout(request)
    return redirect('login')


def home_redirect(request):
    """Keep the old /home/ address working after the dashboard moved to /."""
    return redirect('dashboard')


@login_required(login_url='login')
def home(request):
    from django.db.models import Avg

    from apps.chat.selectors import recent_conversations
    from apps.notes.models import Note, QuizAttempt, QuizSet, Subject
    from apps.users.roles import can_admin, can_moderate, ensure_profile

    ensure_profile(request.user)
    guest_session = is_guest(request.user)
    stats = {
        'my_notes': Note.objects.filter(uploaded_by=request.user).count(),
        'quizzes_total': QuizSet.objects.count(),
        'my_attempts': QuizAttempt.objects.filter(taker=request.user).count(),
        'my_avg': QuizAttempt.objects.filter(taker=request.user).aggregate(a=Avg('percentage'))['a'] or 0,
        'pending_notes': Note.objects.filter(status=Note.STATUS_PENDING).count() if can_moderate(request.user) else 0,
    }
    stats['my_avg'] = round(stats['my_avg'], 2)

    display_name, initials = display_identity(request.user)

    sidebar_subjects = Subject.objects.filter(is_active=True).order_by('name')[:3]
    sidebar_conversations = recent_conversations(request.user)

    return render(request, 'home.html', {
        'stats': stats,
        'sidebar_subjects': sidebar_subjects,
        'sidebar_conversations': sidebar_conversations,
        'active_conversation': None,
        'display_name': display_name,
        'initials': initials,
        'is_guest': guest_session,
        'can_moderate': can_moderate(request.user),
        'can_admin': can_admin(request.user),
    })


@require_http_methods(['GET', 'POST'])
def register_view(request):
    current_is_guest = is_guest(request.user)
    if request.user.is_authenticated and not current_is_guest:
        return redirect('dashboard')

    register_context = {'current_is_guest': current_is_guest}
    if request.method == 'GET':
        return render(request, 'auth/register.html', register_context)

    form_data = {
        'username': request.POST.get('username', ''),
        'first_name': request.POST.get('first_name', ''),
        'last_name': request.POST.get('last_name', ''),
        'email': request.POST.get('email', ''),
        'password': request.POST.get('password', ''),
        'confirm_password': request.POST.get('confirm_password', ''),
    }

    errors = _validate_registration_data(
        form_data,
        exclude_user=request.user if current_is_guest else None,
    )
    if errors:
        return render(request, 'auth/register.html', {
            **register_context, 'errors': errors, 'form_data': form_data,
        })

    if current_is_guest:
        user = upgrade_guest_user(
            request.user,
            username=form_data['username'].strip(),
            first_name=form_data['first_name'].strip(),
            last_name=form_data['last_name'].strip(),
            email=form_data['email'].strip(),
            password=form_data['password'],
        )
        # Password changed, so refresh the session auth hash in place.
        login(
            request,
            user,
            backend='django.contrib.auth.backends.ModelBackend',
        )
        messages.success(
            request,
            'Your account is ready. Everything you created as a guest is '
            'still here.',
        )
    else:
        user = User.objects.create_user(
            username=form_data['username'].strip(),
            first_name=form_data['first_name'].strip(),
            last_name=form_data['last_name'].strip(),
            email=form_data['email'].strip(),
            password=form_data['password'],
        )
        login(request, user)
    return redirect('dashboard')
