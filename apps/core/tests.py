from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.notes.models import Note, QuizSet
from apps.users.models import Profile


class HomeViewTests(TestCase):
    def test_home_renders_for_authenticated_user(self):
        user = get_user_model().objects.create_user(
            username='admin', password='secret1234',
            first_name='Andy', last_name='Peduhan',
        )

        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')
        self.assertContains(response, "What's on the agenda today?")
        self.assertContains(response, 'Ask StudyShare')
        self.assertContains(response, 'New Chat')
        self.assertEqual(response.context['display_name'], 'Andy Peduhan')
        self.assertEqual(response.context['initials'], 'AP')

    def test_home_removes_quiz_suggestion_and_starts_at_zero(self):
        user = get_user_model().objects.create_user(
            username='freshstudent', password='secret1234'
        )
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Create a quiz from your notes')
        stats = response.context['stats']
        self.assertEqual(stats['my_notes'], 0)
        self.assertEqual(stats['my_attempts'], 0)
        self.assertEqual(stats['my_avg'], 0)
        self.assertContains(response, 'quizzes taken')
        self.assertContains(response, 'average score')

    def test_home_activity_matches_my_progress(self):
        from apps.chat.models import (
            ChatQuizAttempt,
            Conversation,
            Message,
            MessageAttachment,
        )
        from apps.notes.models import Note, QuizAttempt, QuizSet

        user = get_user_model().objects.create_user(
            username='progressstudent', password='secret1234'
        )
        conversation = Conversation.objects.create(
            user=user, title='Biology chat'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_ASSISTANT,
            content='Practice quiz',
            quiz_data=[],
        )
        attachment = MessageAttachment.objects.create(
            message=message,
            original_name='biology-chat.txt',
            file=SimpleUploadedFile(
                'biology-chat.txt', b'Cellular respiration produces ATP.'
            ),
        )
        self.addCleanup(attachment.file.delete, save=False)
        ChatQuizAttempt.objects.create(
            message=message,
            taker=user,
            score=8,
            total=10,
            percentage=80,
        )

        # Note-based uploads/attempts belong to the notes library and must not
        # change the new-chat counters, which mirror My Progress.
        note = Note.objects.create(
            title='Note-only upload',
            subject='Biology',
            instructor='Prof. Santos',
            topic='Respiration',
            school_year='2024-2025',
            uploaded_by=user,
            content='Cellular respiration produces ATP.',
        )
        quiz = QuizSet.objects.create(
            note=note, created_by=user, title='Note-only quiz'
        )
        QuizAttempt.objects.create(
            quiz=quiz, taker=user, score=1, total=5, percentage=20
        )

        self.client.force_login(user)
        home = self.client.get(reverse('dashboard'))
        progress = self.client.get(reverse('notes:my_progress'))
        stats = home.context['stats']

        self.assertEqual(stats['my_notes'], 1)
        self.assertEqual(stats['my_notes'], progress.context['notes_uploaded'])
        self.assertEqual(stats['my_attempts'], 1)
        self.assertEqual(stats['my_attempts'], progress.context['total_taken'])
        self.assertEqual(stats['my_avg'], 80.0)
        self.assertEqual(stats['my_avg'], progress.context['avg_score'])

    def test_home_is_available_to_guests(self):
        response = self.client.get(
            reverse('dashboard'), HTTP_ACCEPT='text/html'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')
        self.assertContains(response, "What's on the agenda today?")
        self.assertContains(response, 'Ask StudyShare')
        self.assertContains(response, 'New Chat')
        self.assertTrue(response.context['is_guest'])
        self.assertEqual(response.context['display_name'], 'Guest')
        self.assertEqual(response.context['initials'], 'G')

        guest_id = self.client.session['_auth_user_id']
        guest = get_user_model().objects.get(pk=guest_id)
        self.assertTrue(guest.profile.is_guest)
        self.assertFalse(guest.has_usable_password())

    def test_login_page_removes_classmates_and_centers_aside_content(self):
        response = self.client.get(reverse('login'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "classmates'")
        self.assertContains(response, 'Study smarter with your notes.')

    def test_home_redirects_to_dashboard(self):
        self.client.get(reverse('dashboard'), HTTP_ACCEPT='text/html')
        response = self.client.get('/home/')

        self.assertRedirects(response, reverse('dashboard'))

    def test_non_browser_requests_do_not_create_guest_accounts(self):
        cases = (
            {},
            {'HTTP_ACCEPT': '*/*'},
            {'HTTP_ACCEPT': 'application/json'},
            {
                'HTTP_ACCEPT': 'text/html',
                'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest',
            },
            {'HTTP_ACCEPT': 'text/html', 'HTTP_SEC_PURPOSE': 'prefetch'},
        )
        for headers in cases:
            with self.subTest(headers=headers):
                response = self.client.get(reverse('dashboard'), **headers)
                self.assertRedirects(
                    response,
                    f"{reverse('login')}?next={reverse('dashboard')}",
                )

        self.client.head(reverse('dashboard'), HTTP_ACCEPT='text/html')
        self.assertFalse(get_user_model().objects.exists())


class SeedDemoTests(TestCase):
    def test_seed_demo_creates_student_account_and_example_content(self):
        call_command('seed_demo', verbosity=0)

        User = get_user_model()
        self.assertEqual(User.objects.count(), 1)

        andy = User.objects.get(username='andy')
        self.assertTrue(andy.check_password('Andy123456'))
        self.assertEqual(andy.profile.role, Profile.ROLE_STUDENT)
        self.assertFalse(andy.is_staff)
        self.assertFalse(andy.is_superuser)

        self.assertEqual(Note.objects.count(), 10)
        self.assertFalse(Note.objects.exclude(uploaded_by=andy).exists())
        self.assertEqual(QuizSet.objects.filter(is_exam=False).count(), 10)
        self.assertEqual(QuizSet.objects.filter(is_exam=True).count(), 2)

        # Repeat runs must not duplicate accounts or content.
        call_command('seed_demo', verbosity=0)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Note.objects.count(), 10)
        self.assertEqual(QuizSet.objects.count(), 12)

    def test_seed_demo_with_staff_adds_role_accounts(self):
        call_command('seed_demo', with_staff=True, verbosity=0)

        User = get_user_model()
        self.assertEqual(User.objects.count(), 3)

        instructor = User.objects.get(username='instructor')
        admin = User.objects.get(username='admin')
        self.assertEqual(instructor.profile.role, Profile.ROLE_INSTRUCTOR)
        self.assertTrue(instructor.is_staff)
        self.assertEqual(admin.profile.role, Profile.ROLE_ADMIN)
        self.assertTrue(admin.is_superuser)
