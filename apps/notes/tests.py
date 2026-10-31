from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.chat.models import Conversation, Message, MessageAttachment
from apps.notes.models import Note, Question, QuizAttempt, QuizSet
from apps.notes.services import build_exam_source, generate_quiz
from apps.users.models import Profile
from apps.users.roles import can_admin, can_moderate, get_user_role

User = get_user_model()


def _set_role(user, role):
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.role = role
    profile.save()
    # Refresh superuser flags for admin consistency in tests.
    user.refresh_from_db()
    return profile


@override_settings(GEMINI_API_KEY='', OPENAI_API_KEY='', OPENROUTER_API_KEY='')
class NotesModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='student1', password='pass12345')
        self.note = Note.objects.create(
            title='Photosynthesis Notes',
            subject='Biology',
            instructor='Prof. Santos',
            topic='Photosynthesis',
            school_year='2024-2025',
            description='Intro to photosynthesis',
            content=(
                'Photosynthesis converts light energy into chemical energy. '
                'Chlorophyll absorbs sunlight in the chloroplasts. '
                'Carbon dioxide and water produce glucose and oxygen. '
                'The Calvin cycle fixes carbon in the stroma.'
            ),
            uploaded_by=self.user,
        )

    def test_local_quiz_fallback(self):
        result = generate_quiz(self.note.content, num_questions=4, question_type='mixed')
        self.assertEqual(result['provider'], 'local')
        self.assertEqual(len(result['questions']), 4)
        types = {q['question_type'] for q in result['questions']}
        self.assertTrue(len(types) >= 2)

    def test_quiz_generate_view(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            f'/notes/{self.note.pk}/quiz/generate/',
            {'num_questions': 3, 'question_type': 'mcq'},
        )
        self.assertEqual(resp.status_code, 302)
        quiz = QuizSet.objects.get(note=self.note)
        self.assertEqual(quiz.questions.count(), 3)
        self.assertEqual(quiz.provider, 'local')

    def test_uploaded_notes_page_lists_only_my_chat_attachments(self):
        conversation = Conversation.objects.create(
            user=self.user, title='My uploaded file'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='Use this file.',
        )
        attachment = MessageAttachment.objects.create(
            message=message,
            original_name='my-study-guide.txt',
            file=SimpleUploadedFile('my-study-guide.txt', b'My study guide.'),
        )
        self.addCleanup(attachment.file.delete, save=False)

        other = get_user_model().objects.create_user(
            username='file-owner', password='pass12345'
        )
        other_conversation = Conversation.objects.create(
            user=other, title='Someone elses file'
        )
        other_message = Message.objects.create(
            conversation=other_conversation,
            role=Message.ROLE_USER,
            content='Private upload.',
        )
        other_attachment = MessageAttachment.objects.create(
            message=other_message,
            original_name='private-study-guide.txt',
            file=SimpleUploadedFile(
                'private-study-guide.txt', b'Someone elses study guide.'
            ),
        )
        self.addCleanup(other_attachment.file.delete, save=False)

        self.client.force_login(self.user)
        response = self.client.get(reverse('notes:note_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Uploaded Notes')
        self.assertContains(response, 'My Uploaded Files')
        self.assertNotContains(response, 'Shared Study Notes')
        self.assertNotContains(response, 'Photosynthesis Notes')
        self.assertContains(response, 'my-study-guide.txt')
        self.assertContains(
            response, reverse('chat:view_attachment', args=[attachment.pk])
        )
        self.assertContains(
            response, reverse('chat:download_attachment', args=[attachment.pk])
        )
        self.assertContains(
            response, reverse('chat:delete_attachment', args=[attachment.pk])
        )
        self.assertNotContains(response, 'private-study-guide.txt')

    def test_progress_page_syncs_uploaded_chat_files(self):
        conversation = Conversation.objects.create(
            user=self.user, title='My uploaded file'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='Use this file.',
        )
        attachment = MessageAttachment.objects.create(
            message=message,
            original_name='progress-study-guide.txt',
            file=SimpleUploadedFile('progress-study-guide.txt', b'My study guide.'),
        )
        self.addCleanup(attachment.file.delete, save=False)

        other = get_user_model().objects.create_user(
            username='other-file-owner', password='pass12345'
        )
        other_conversation = Conversation.objects.create(
            user=other, title='Someone elses file'
        )
        other_message = Message.objects.create(
            conversation=other_conversation,
            role=Message.ROLE_USER,
            content='Private upload.',
        )
        other_attachment = MessageAttachment.objects.create(
            message=other_message,
            original_name='private-progress-guide.txt',
            file=SimpleUploadedFile(
                'private-progress-guide.txt', b'Someone elses study guide.'
            ),
        )
        self.addCleanup(other_attachment.file.delete, save=False)

        self.client.force_login(self.user)
        response = self.client.get(reverse('notes:my_progress'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['notes_uploaded'], 1)
        self.assertContains(response, 'Uploaded Notes')
        self.assertNotContains(response, 'Ratings given')
        self.assertNotIn('ratings_given', response.context)
        self.assertContains(response, 'progress-study-guide.txt')
        self.assertContains(response, 'My uploaded file')
        self.assertContains(
            response, reverse('chat:view_attachment', args=[attachment.pk])
        )
        self.assertContains(
            response, reverse('chat:download_attachment', args=[attachment.pk])
        )
        self.assertNotContains(response, 'private-progress-guide.txt')
        self.assertNotContains(response, 'Someone elses file')


class RolesTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username='stu', password='pass12345')
        self.instructor = User.objects.create_user(username='ins', password='pass12345')
        self.admin = User.objects.create_user(username='adm', password='pass12345')
        _set_role(self.student, Profile.ROLE_STUDENT)
        _set_role(self.instructor, Profile.ROLE_INSTRUCTOR)
        _set_role(self.admin, Profile.ROLE_ADMIN)

    def test_default_role_is_student(self):
        u = User.objects.create_user(username='newbie', password='pass12345')
        self.assertEqual(get_user_role(u), Profile.ROLE_STUDENT)

    def test_role_helpers(self):
        self.assertFalse(can_moderate(self.student))
        self.assertTrue(can_moderate(self.instructor))
        self.assertTrue(can_moderate(self.admin))
        self.assertFalse(can_admin(self.student))
        self.assertFalse(can_admin(self.instructor))
        self.assertTrue(can_admin(self.admin))

    def test_student_upload_goes_pending(self):
        self.client.force_login(self.student)
        resp = self.client.post('/notes/upload/', {
            'title': 'Student Note', 'subject': 'Math', 'instructor': 'Prof X',
            'topic': 'Algebra', 'school_year': '2024-2025',
            'description': 'd', 'content': 'x' * 50, 'is_public': 'on',
        })
        self.assertEqual(resp.status_code, 302)
        note = Note.objects.get(title='Student Note')
        self.assertEqual(note.status, Note.STATUS_PENDING)

    def test_instructor_upload_auto_approved(self):
        self.client.force_login(self.instructor)
        resp = self.client.post('/notes/upload/', {
            'title': 'Ins Note', 'subject': 'Math', 'instructor': 'Prof X',
            'topic': 'Algebra', 'school_year': '2024-2025',
            'description': 'd', 'content': 'x' * 50, 'is_public': 'on',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Note.objects.get(title='Ins Note').status, Note.STATUS_APPROVED)

    def test_moderation_permissions(self):
        # Student blocked, instructor/admin allowed.
        self.client.force_login(self.student)
        self.assertEqual(self.client.get('/notes/moderation/').status_code, 302)
        self.client.force_login(self.instructor)
        self.assertEqual(self.client.get('/notes/moderation/').status_code, 200)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/notes/analytics/').status_code, 200)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get('/notes/analytics/').status_code, 302)

    def test_user_management_requires_admin(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get('/users/').status_code, 302)
        self.client.force_login(self.instructor)
        self.assertEqual(self.client.get('/users/').status_code, 302)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/users/').status_code, 200)


class QuizTakeTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username='taker', password='pass12345')
        self.note = Note.objects.create(
            title='Quiz Note', subject='Sci', instructor='Prof', topic='T',
            school_year='2024-2025', uploaded_by=self.student,
        )
        self.quiz = QuizSet.objects.create(note=self.note, created_by=self.student, title='Q1')
        self.q1 = Question.objects.create(
            quiz=self.quiz, question_type='mcq', question_text='2+2?', options=['3', '4'],
            correct_answer='4', order=0,
        )
        self.q2 = Question.objects.create(
            quiz=self.quiz, question_type='true_false', question_text='Sky blue?',
            options=['True', 'False'], correct_answer='True', order=1,
        )
        Question.objects.create(
            quiz=self.quiz, question_type='essay', question_text='Discuss.', order=2,
        )

    def test_take_and_score(self):
        self.client.force_login(self.student)
        resp = self.client.get(f'/notes/quiz/{self.quiz.pk}/take/')
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(f'/notes/quiz/{self.quiz.pk}/take/', {
            f'q_{self.q1.id}': '4', f'q_{self.q2.id}': 'False', f'q_{Question.objects.get(order=2).id}': 'my essay',
        })
        self.assertEqual(resp.status_code, 302)
        attempt = QuizAttempt.objects.get(quiz=self.quiz, taker=self.student)
        self.assertEqual(attempt.score, 1)
        self.assertEqual(attempt.total, 2)
        self.assertEqual(attempt.percentage, 50.0)
        # Detail + progress pages.
        self.assertEqual(self.client.get(f'/notes/attempts/{attempt.pk}/').status_code, 200)
        resp = self.client.get('/notes/progress/')
        self.assertContains(resp, 'Quiz Attempts')
        self.assertNotContains(resp, 'Quiz Note')
        self.assertEqual(resp.context['total_taken'], 0)


@override_settings(GEMINI_API_KEY='', OPENAI_API_KEY='', OPENROUTER_API_KEY='')
class AIProviderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='aiuser', password='pass12345')
        self.note = Note.objects.create(
            title='AI Note', subject='Sci', instructor='Prof', topic='T',
            school_year='2024-2025', uploaded_by=self.user,
            content='Photosynthesis converts light energy into chemical energy. ' * 5,
        )

    def test_explicit_local(self):
        from apps.notes.services import generate_quiz
        result = generate_quiz('Some long enough source text. ' * 10, provider='local')
        self.assertEqual(result['provider'], 'local')
        self.assertTrue(len(result['questions']) >= 1)

    def test_auto_without_keys_falls_back_local(self):
        from apps.notes.services import generate_quiz
        result = generate_quiz('Some long enough source text. ' * 10, provider='auto')
        # No keys in test env -> local.
        self.assertEqual(result['provider'], 'local')

    @override_settings(
        AI_PROVIDER='local',
        OPENAI_API_KEY='configured-openai-key',
        GEMINI_API_KEY='configured-gemini-key',
        OPENROUTER_API_KEY='configured-openrouter-key',
    )
    def test_auto_with_local_provider_setting_skips_cloud_providers(self):
        from unittest.mock import patch
        from apps.notes.services import generate_quiz

        with patch(
            'apps.notes.services._try_provider',
            side_effect=AssertionError('Offline generation must not call a provider.'),
        ) as try_provider:
            result = generate_quiz(
                'Photosynthesis converts light energy into chemical energy. ' * 5,
                provider='auto',
            )

        self.assertEqual(result['provider'], 'local')
        self.assertTrue(result['questions'])
        try_provider.assert_not_called()

    def test_local_mcq_choices_are_uppercase_and_unique(self):
        from apps.notes.services import generate_quiz
        source = (
            'Photosynthesis converts light energy into chemical energy. '
            'Chlorophyll absorbs sunlight in the chloroplasts. '
            'Carbon dioxide and water produce glucose and oxygen. '
            'Cellular respiration produces ATP in mitochondria. '
            'Enzymes speed up chemical reactions in cells. '
            'DNA stores genetic information in the nucleus. '
            'Proteins are built from amino acids. '
            'Mitosis produces two identical cells. '
            'Osmosis moves water across membranes. '
            'Diffusion spreads particles from high to low concentration.'
        )
        result = generate_quiz(
            source, num_questions=10, question_type='mcq', provider='local'
        )
        self.assertEqual(len(result['questions']), 10)
        option_sets = set()
        for question in result['questions']:
            options = question['options']
            self.assertEqual(len(options), 4)
            self.assertTrue(all(option == option.upper() for option in options))
            self.assertEqual(len({option.casefold() for option in options}), 4)
            self.assertIn(question['correct_answer'], options)
            option_sets.add(tuple(sorted(options)))
        # Do not repeat the exact same choice list across the quiz.
        self.assertEqual(len(option_sets), 10)

    def test_local_true_false_choices_are_uppercase(self):
        from apps.notes.services import generate_quiz
        result = generate_quiz(
            'Active recall and spaced repetition improve long-term retention. ' * 8,
            num_questions=5,
            question_type='true_false',
            provider='local',
        )
        self.assertTrue(result['questions'])
        for question in result['questions']:
            self.assertEqual(question['options'], ['TRUE', 'FALSE'])
            self.assertIn(question['correct_answer'], ('TRUE', 'FALSE'))

    def test_provider_choices_are_uppercased_and_deduplicated(self):
        import json
        from unittest.mock import patch
        from apps.notes import services as svc

        fake_questions = [
            {
                'question_type': 'mcq',
                'question_text': 'Q1?',
                'options': ['alpha', 'Alpha', 'beta', 'gamma', 'delta'],
                'correct_answer': 'alpha',
                'explanation': '',
            },
            {
                'question_type': 'mcq',
                'question_text': 'Q2?',
                'options': ['ALL OF THE ABOVE', 'NONE OF THE ABOVE', 'beta', 'gamma'],
                'correct_answer': 'beta',
                'explanation': '',
            },
            {
                'question_type': 'true_false',
                'question_text': 'Q3?',
                'options': ['True', 'False'],
                'correct_answer': 'false',
                'explanation': '',
            },
        ]

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({
                    'choices': [
                        {'message': {'content': json.dumps(fake_questions)}}
                    ]
                }).encode()

        with patch.object(
            svc, 'get_openrouter_config', return_value=('test-key', 'test-model')
        ), patch('urllib.request.urlopen', return_value=FakeResp()):
            result = svc.generate_quiz(
                'Some long enough source text. ' * 10,
                num_questions=3,
                provider='openrouter',
            )

        first, second, third = result['questions']
        self.assertEqual(first['options'], ['ALPHA', 'BETA', 'GAMMA', 'DELTA'])
        self.assertEqual(first['correct_answer'], 'ALPHA')
        self.assertTrue(
            all(option == option.upper() for option in second['options'])
        )
        self.assertEqual(
            len({option.casefold() for option in second['options']}),
            len(second['options']),
        )
        self.assertFalse(
            'ALL OF THE ABOVE' in second['options']
            and 'NONE OF THE ABOVE' in second['options']
        )
        self.assertIn(second['correct_answer'], second['options'])
        self.assertEqual(second['correct_answer'], 'BETA')
        self.assertEqual(third['options'], ['TRUE', 'FALSE'])
        self.assertEqual(third['correct_answer'], 'FALSE')

    def test_explicit_missing_key_falls_back_local(self):
        from apps.notes.services import generate_quiz
        result = generate_quiz('Some long enough source text. ' * 10, provider='gemini')
        self.assertEqual(result['provider'], 'local')

    def test_openrouter_mocked_success(self):
        import io
        import json
        from unittest.mock import patch
        from apps.notes import services as svc

        fake_questions = [
            {'question_type': 'mcq', 'question_text': 'Q1?', 'options': ['A', 'B', 'C', 'D'],
             'correct_answer': 'A', 'explanation': 'exp'},
            {'question_type': 'true_false', 'question_text': 'Q2?', 'options': [],
             'correct_answer': 'True', 'explanation': ''},
        ]

        class FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self):
                return json.dumps({'choices': [{'message': {'content': json.dumps(fake_questions)}}]}).encode()

        with patch.object(svc, 'get_openrouter_config', return_value=('test-key', 'test-model')), \
             patch('urllib.request.urlopen', return_value=FakeResp()):
            result = svc.generate_quiz('Some long enough source text. ' * 10, num_questions=2, provider='openrouter')
        self.assertEqual(result['provider'], 'openrouter')
        self.assertEqual(len(result['questions']), 2)

    def test_gemini_mocked_success(self):
        import json
        from unittest.mock import patch
        from apps.notes import services as svc

        fake_questions = [
            {'question_type': 'mcq', 'question_text': 'Q1?', 'options': ['A', 'B', 'C', 'D'],
             'correct_answer': 'B', 'explanation': ''},
        ]

        class FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self):
                return json.dumps({'candidates': [{'content': {'parts': [{'text': json.dumps(fake_questions)}]}}]}).encode()

        with patch.object(svc, 'get_gemini_config', return_value=('test-key', 'gemini-1.5-flash')), \
             patch('urllib.request.urlopen', return_value=FakeResp()):
            result = svc.generate_quiz('Some long enough source text. ' * 10, num_questions=1, provider='gemini')
        self.assertEqual(result['provider'], 'gemini')
        self.assertEqual(result['questions'][0]['correct_answer'], 'B')

    def test_quiz_generate_view_with_provider_param(self):
        self.client.force_login(self.user)
        resp = self.client.post(f'/notes/{self.note.pk}/quiz/generate/', {
            'num_questions': 2, 'question_type': 'mcq', 'provider': 'local',
        })
        self.assertEqual(resp.status_code, 302)
        quiz = QuizSet.objects.filter(note=self.note).latest('id')
        self.assertEqual(quiz.provider, 'local')
        self.assertEqual(quiz.questions.count(), 2)


class ExamAutomationTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username='examstu', password='pass12345')
        self.instructor = User.objects.create_user(username='examins', password='pass12345')
        _set_role(self.instructor, Profile.ROLE_INSTRUCTOR)
        self.notes = [
            Note.objects.create(
                title=f'Bio Note {i}', subject='Biology', instructor='Prof', topic=f'Topic {i}',
                school_year='2024-2025', uploaded_by=self.student,
                content='Photosynthesis converts light energy into chemical energy. Chlorophyll absorbs sunlight. ' * 4,
                status=Note.STATUS_APPROVED,
            )
            for i in range(3)
        ]

    def test_build_exam_source_combines_notes(self):
        src = build_exam_source(self.notes)
        for n in self.notes:
            self.assertIn(n.title, src)

    def test_exam_builder_creates_exam(self):
        self.client.force_login(self.student)
        resp = self.client.get('/notes/exam/builder/')
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post('/notes/exam/builder/', {
            'subject': 'Biology', 'school_year': '', 'topic': '',
            'max_notes': 3, 'num_questions': 6, 'question_type': 'mcq',
            'provider': 'local', 'order': 'newest',
        })
        self.assertEqual(resp.status_code, 302)
        exam = QuizSet.objects.filter(is_exam=True).latest('id')
        self.assertEqual(exam.questions.count(), 6)
        self.assertEqual(len(exam.source_note_ids), 3)
        self.assertEqual(exam.exam_subject, 'Biology')
        # Answers locked until submitted: no key/answers yet, then visible after take.
        resp = self.client.get(f'/notes/quiz/{exam.pk}/')
        self.assertNotContains(resp, 'Answer Key')
        self.assertContains(resp, 'Bio Note 0')
        q = exam.questions.first()
        self.client.post(f'/notes/quiz/{exam.pk}/take/', {f'q_{q.id}': q.correct_answer})
        resp = self.client.get(f'/notes/quiz/{exam.pk}/')
        self.assertContains(resp, 'Answer Key')

    def test_exam_builder_no_match(self):
        self.client.force_login(self.student)
        resp = self.client.post('/notes/exam/builder/', {
            'subject': 'NonexistentSubjectXYZ', 'max_notes': 4,
            'num_questions': 5, 'question_type': 'mixed', 'provider': 'local',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(QuizSet.objects.filter(is_exam=True).count(), 0)

    def test_bulk_skips_notes_with_quizzes(self):
        existing = QuizSet.objects.create(note=self.notes[0], created_by=self.student, title='Q')
        Question.objects.create(quiz=existing, question_text='q', correct_answer='a')
        self.client.force_login(self.instructor)
        resp = self.client.post('/notes/exam/bulk/', {
            'subject': 'Biology', 'per_note': 2, 'question_type': 'mcq',
            'provider': 'local', 'limit': 10, 'only_missing': '1',
        })
        self.assertEqual(resp.status_code, 302)
        # 2 new quizzes (notes 1,2); note 0 skipped.
        self.assertEqual(QuizSet.objects.filter(is_exam=False).count(), 3)

    def test_bulk_requires_moderator(self):
        self.client.force_login(self.student)
        resp = self.client.post('/notes/exam/bulk/', {'subject': 'Biology'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(QuizSet.objects.count(), 0)

    def test_management_command(self):
        call_command('auto_generate_quizzes', subject='Biology', limit=2,
                     per_note=2, provider='local', question_type='mcq')
        self.assertEqual(QuizSet.objects.count(), 2)

    def test_exam_list_page(self):
        self.client.force_login(self.student)
        self.client.post('/notes/exam/builder/', {
            'subject': 'Biology', 'max_notes': 2, 'num_questions': 3,
            'question_type': 'mcq', 'provider': 'local',
        })
        self.assertTrue(QuizSet.objects.filter(is_exam=True).exists())
        resp = self.client.get('/notes/exams/')
        self.assertContains(resp, 'My Quizzes')
        self.assertNotContains(resp, 'Generated Exams')
        self.assertNotContains(resp, 'Exam — Biology')

    def test_answers_locked_until_submitted(self):
        taker = User.objects.create_user(username='locktaker', password='pass12345')
        note = Note.objects.create(
            title='Lock Note', subject='Sci', instructor='Prof', topic='T',
            school_year='2024-2025', uploaded_by=taker,
        )
        quiz = QuizSet.objects.create(note=note, created_by=taker, title='LockQ')
        Question.objects.create(
            quiz=quiz, question_type='mcq', question_text='2+2?',
            options=['3', '4'], correct_answer='4', order=0,
        )
        self.client.force_login(taker)
        resp = self.client.get(f'/notes/quiz/{quiz.pk}/')
        self.assertNotContains(resp, 'Show answer')
        self.assertContains(resp, 'Answers unlock after you submit')
        q = quiz.questions.get()
        self.client.post(f'/notes/quiz/{quiz.pk}/take/', {f'q_{q.id}': '4'})
        resp = self.client.get(f'/notes/quiz/{quiz.pk}/')
        self.assertContains(resp, 'Show answer')


class SeedExamplesTests(TestCase):
    def test_seed_creates_examples_and_is_idempotent(self):
        call_command('seed_examples')
        self.assertGreaterEqual(Note.objects.filter(status=Note.STATUS_APPROVED).count(), 10)
        self.assertGreaterEqual(QuizSet.objects.filter(is_exam=False).count(), 10)
        self.assertGreaterEqual(QuizSet.objects.filter(is_exam=True).count(), 2)
        n_notes = Note.objects.count()
        n_quiz = QuizSet.objects.count()
        call_command('seed_examples')
        self.assertEqual(Note.objects.count(), n_notes)
        self.assertEqual(QuizSet.objects.count(), n_quiz)


class RemovedNoteVisibilityTests(TestCase):
    """Rejected/private notes must not leak via quiz endpoints."""

    def setUp(self):
        self.owner = User.objects.create_user(username='visowner', password='pass12345')
        self.student = User.objects.create_user(username='visstu', password='pass12345')
        self.instructor = User.objects.create_user(username='visins', password='pass12345')
        _set_role(self.instructor, Profile.ROLE_INSTRUCTOR)
        self.rejected = Note.objects.create(
            title='Rejected Note', subject='Sci', instructor='Prof', topic='T',
            school_year='2024-2025', uploaded_by=self.owner,
            status=Note.STATUS_REJECTED, is_public=False,
            content='Hidden content. ' * 20,
        )
        self.quiz = QuizSet.objects.create(note=self.rejected, created_by=self.owner, title='RQ')
        Question.objects.create(
            quiz=self.quiz, question_type='mcq', question_text='1+1?',
            options=['1', '2'], correct_answer='2', order=0,
        )

    def test_student_blocked_from_removed_content(self):
        self.client.force_login(self.student)
        self.assertEqual(
            self.client.post(f'/notes/{self.rejected.pk}/quiz/generate/',
                             {'num_questions': 2, 'provider': 'local'}).status_code, 302)
        self.assertEqual(QuizSet.objects.filter(note=self.rejected).count(), 1)  # no new quiz
        self.assertEqual(self.client.get(f'/notes/quiz/{self.quiz.pk}/').status_code, 302)
        self.assertEqual(self.client.get(f'/notes/quiz/{self.quiz.pk}/take/').status_code, 302)

    def test_moderator_can_still_review(self):
        self.client.force_login(self.instructor)
        self.assertEqual(self.client.get(f'/notes/quiz/{self.quiz.pk}/').status_code, 200)
