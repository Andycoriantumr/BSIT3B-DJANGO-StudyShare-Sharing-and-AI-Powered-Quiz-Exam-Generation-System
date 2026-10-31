from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.chat.models import Conversation, Message
from apps.notes.models import Note, QuizAttempt, QuizSet
from apps.users.guests import create_guest_user, delete_stale_guests
from apps.users.models import Profile

User = get_user_model()

DASHBOARD = reverse('dashboard')


def _current_user(client):
    return User.objects.get(pk=client.session['_auth_user_id'])


def _browse(client, url, **extra):
    """GET a URL the way a browser navigation would."""
    return client.get(url, **{'HTTP_ACCEPT': 'text/html', **extra})


def _make_note(owner, title='Biology Review'):
    return Note.objects.create(
        title=title,
        subject='Biology',
        instructor='Prof. Cruz',
        topic='Cells',
        school_year='2026-2027',
        uploaded_by=owner,
    )


class GuestSessionTests(TestCase):
    def test_dashboard_creates_and_reuses_a_guest(self):
        response = _browse(self.client, DASHBOARD)

        self.assertEqual(response.status_code, 200)
        guest = _current_user(self.client)
        self.assertTrue(guest.profile.is_guest)
        self.assertEqual(guest.profile.role, Profile.ROLE_STUDENT)
        self.assertFalse(guest.has_usable_password())

        _browse(self.client, DASHBOARD)
        self.assertEqual(_current_user(self.client).pk, guest.pk)
        self.assertEqual(
            User.objects.filter(profile__is_guest=True).count(), 1
        )

    def test_auth_pages_do_not_create_guest_accounts(self):
        self.client.get(reverse('login'), HTTP_ACCEPT='text/html')
        self.client.get(reverse('register'), HTTP_ACCEPT='text/html')

        self.assertFalse(User.objects.exists())

    def test_non_browser_requests_do_not_create_guests(self):
        response = self.client.get(DASHBOARD)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/?next=', response['Location'])
        self.assertFalse(User.objects.exists())

    def test_registered_session_is_not_replaced(self):
        user = User.objects.create_user(
            username='student', password='secret1234'
        )
        self.client.force_login(user)

        _browse(self.client, DASHBOARD)

        self.assertEqual(_current_user(self.client).pk, user.pk)
        self.assertFalse(User.objects.filter(profile__is_guest=True).exists())

    @patch(
        'apps.chat.views.generate_reply',
        return_value={'content': 'Guest answer.', 'provider': 'local'},
    )
    def test_guest_can_start_a_chat(self, mocked_reply):
        _browse(self.client, DASHBOARD)

        response = self.client.post(
            reverse('chat:start'), {'content': 'Explain mitosis'}
        )

        self.assertEqual(response.status_code, 302)
        conversation = Conversation.objects.get()
        self.assertTrue(conversation.user.profile.is_guest)
        self.assertEqual(
            list(conversation.messages.values_list('role', flat=True)),
            [Message.ROLE_USER, Message.ROLE_ASSISTANT],
        )
        mocked_reply.assert_called_once()

    def test_guest_cannot_reach_moderation_or_admin_pages(self):
        _browse(self.client, DASHBOARD)

        for url in (
            reverse('users:user_list'),
            reverse('notes:moderation_queue'),
            reverse('notes:system_analytics'),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(
                    response['Location'].startswith(f'{DASHBOARD}?next=')
                )


class GuestRegistrationTests(TestCase):
    def setUp(self):
        _browse(self.client, DASHBOARD)
        self.guest = _current_user(self.client)
        self.conversation = Conversation.objects.create(
            user=self.guest, title='Saved guest chat'
        )

    def test_registration_upgrades_the_guest_in_place(self):
        response = self.client.post(reverse('register'), {
            'username': 'newstudent',
            'first_name': 'Nina',
            'last_name': 'Santos',
            'email': 'nina@example.com',
            'password': 'StudyPass123!',
            'confirm_password': 'StudyPass123!',
        })

        self.assertRedirects(response, DASHBOARD)
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(User.objects.filter(profile__is_guest=True).exists())

        account = User.objects.get()
        self.assertEqual(account.pk, self.guest.pk)
        self.assertEqual(account.username, 'newstudent')
        self.assertEqual(account.get_full_name(), 'Nina Santos')
        self.assertFalse(account.profile.is_guest)
        self.assertTrue(account.has_usable_password())
        self.assertIsNotNone(
            authenticate(username='newstudent', password='StudyPass123!')
        )

        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.user_id, account.pk)
        self.assertEqual(self.client.session['_auth_user_id'], str(account.pk))

        dashboard = _browse(self.client, DASHBOARD)
        self.assertFalse(dashboard.context['is_guest'])

    def test_registration_validation_ignores_the_guest_username(self):
        response = self.client.post(reverse('register'), {
            'username': self.guest.username,
            'first_name': 'Nina',
            'last_name': 'Santos',
            'email': 'nina@example.com',
            'password': 'StudyPass123!',
            'confirm_password': 'StudyPass123!',
        })

        self.assertRedirects(response, DASHBOARD)
        self.assertFalse(User.objects.filter(profile__is_guest=True).exists())


class GuestLoginMergeTests(TestCase):
    def setUp(self):
        self.target = User.objects.create_user(
            username='realuser',
            password='targetpass123',
            email='real@example.com',
            first_name='Real',
            last_name='User',
        )
        _browse(self.client, DASHBOARD)
        self.guest = _current_user(self.client)

        self.conversation = Conversation.objects.create(
            user=self.guest, title='Guest conversation'
        )
        self.guest_note = _make_note(self.guest, title='Guest note')
        self.target_note = _make_note(self.target, title='Target note')

        self.quiz = QuizSet.objects.create(
            note=self.target_note, created_by=self.guest, title='Guest quiz'
        )
        self.attempt = QuizAttempt.objects.create(
            quiz=self.quiz, taker=self.guest, score=1, total=1, percentage=100
        )

    def test_signing_in_moves_guest_data_to_the_account(self):
        response = self.client.post(reverse('login'), {
            'username': 'realuser',
            'password': 'targetpass123',
        })

        self.assertRedirects(response, DASHBOARD)
        self.assertEqual(self.client.session['_auth_user_id'], str(self.target.pk))
        self.assertFalse(User.objects.filter(pk=self.guest.pk).exists())

        self.conversation.refresh_from_db()
        self.guest_note.refresh_from_db()
        self.quiz.refresh_from_db()
        self.attempt.refresh_from_db()

        self.assertEqual(self.conversation.user_id, self.target.pk)
        self.assertEqual(self.guest_note.uploaded_by_id, self.target.pk)
        self.assertEqual(self.quiz.created_by_id, self.target.pk)
        self.assertEqual(self.attempt.taker_id, self.target.pk)


class GuestCleanupTests(TestCase):
    def test_stale_guests_are_deleted(self):
        guest = create_guest_user()
        User.objects.filter(pk=guest.pk).update(
            last_login=timezone.now() - timedelta(days=45)
        )

        deleted = delete_stale_guests(days=30)

        self.assertEqual(deleted, 1)
        self.assertFalse(User.objects.filter(pk=guest.pk).exists())


class GuestAdminVisibilityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin', password='adminpass123'
        )
        profile, _ = Profile.objects.get_or_create(user=self.admin)
        profile.role = Profile.ROLE_ADMIN
        profile.save()
        self.admin.refresh_from_db()
        self.client.force_login(self.admin)
        self.guest = create_guest_user()

    def test_user_management_hides_guests(self):
        response = self.client.get(reverse('users:user_list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.guest.username, response.content.decode())
        self.assertEqual(
            list(response.context['users'].object_list), [self.admin]
        )

        ajax = self.client.get(reverse('users:user_list_ajax'))
        self.assertEqual(ajax.json()['total'], 1)

    def test_guest_cannot_be_opened_or_edited(self):
        response = self.client.get(
            reverse('users:user_get_ajax', args=[self.guest.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_analytics_user_count_excludes_guests(self):
        response = self.client.get(reverse('notes:system_analytics'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['users_total'], 1)
        self.assertEqual(response.context['by_role'], {'admin': 1})
