from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.notes.models import Note, NoteRating, NoteReport, Question, QuizAttempt, QuizSet, Subject
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
        self.other = User.objects.create_user(username='student2', password='pass12345')
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

    def test_avg_rating(self):
        self.assertEqual(self.note.avg_rating, 0)
        NoteRating.objects.create(note=self.note, user=self.user, score=5)
        NoteRating.objects.create(note=self.note, user=self.other, score=3)
        self.assertEqual(self.note.avg_rating, 4.0)
        self.assertEqual(self.note.ratings_count, 2)

    def test_rating_unique_per_user(self):
        NoteRating.objects.update_or_create(
            note=self.note, user=self.user, defaults={'score': 4}
        )
        NoteRating.objects.update_or_create(
            note=self.note, user=self.user, defaults={'score': 2}
        )
        self.assertEqual(
            NoteRating.objects.filter(note=self.note, user=self.user).count(), 1
        )
        self.assertEqual(self.note.avg_rating, 2.0)

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

    def test_search_filter(self):
        self.client.force_login(self.user)
        resp = self.client.get('/notes/', {'q': 'photosynthesis'})
        self.assertContains(resp, 'Photosynthesis Notes')
        resp = self.client.get('/notes/', {'q': 'nonexistent-xyz'})
        self.assertNotContains(resp, 'Photosynthesis Notes')

    def test_rate_view(self):
        self.client.force_login(self.other)
        resp = self.client.post(f'/notes/{self.note.pk}/rate/', {'score': 5})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.note.avg_rating, 5.0)


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

    def test_subject_manage_permissions(self):
        self.client.force_login(self.student)
        resp = self.client.post('/notes/subjects/save/', {'name': 'Physics'})
        self.assertEqual(resp.status_code, 302)  # redirected to dashboard (no permission)
        self.assertFalse(Subject.objects.filter(name='Physics').exists())
        self.client.force_login(self.instructor)
        resp = self.client.post('/notes/subjects/save/', {'name': 'Physics'})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Subject.objects.filter(name='Physics').exists())

    def test_user_management_requires_admin(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get('/users/').status_code, 302)
        self.client.force_login(self.instructor)
        self.assertEqual(self.client.get('/users/').status_code, 302)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/users/').status_code, 200)


class ReportsModerationTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(username='s1', password='pass12345')
        self.reporter = User.objects.create_user(username='s2', password='pass12345')
        self.instructor = User.objects.create_user(username='ins1', password='pass12345')
        _set_role(self.instructor, Profile.ROLE_INSTRUCTOR)
        self.note = Note.objects.create(
            title='Flag me', subject='Bio', instructor='Prof', topic='T',
            school_year='2024-2025', uploaded_by=self.student, status=Note.STATUS_APPROVED,
        )

    def test_report_and_remove(self):
        self.client.force_login(self.reporter)
        resp = self.client.post(f'/notes/{self.note.pk}/report/', {'reason': 'incorrect', 'details': 'wrong'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(NoteReport.objects.filter(note=self.note).count(), 1)
        self.client.force_login(self.instructor)
        report = NoteReport.objects.get(note=self.note)
        resp = self.client.post(f'/notes/reports/{report.pk}/review/', {'action': 'remove'})
        self.assertEqual(resp.status_code, 302)
        self.note.refresh_from_db()
        self.assertEqual(self.note.status, Note.STATUS_REJECTED)
        # Rejected note hidden from other students.
        self.client.force_login(self.reporter)
        resp = self.client.get(f'/notes/{self.note.pk}/')
        self.assertEqual(resp.status_code, 302)

    def test_report_dismiss(self):
        NoteReport.objects.create(note=self.note, reporter=self.reporter, reason='spam')
        self.client.force_login(self.instructor)
        report = NoteReport.objects.get(note=self.note)
        self.client.post(f'/notes/reports/{report.pk}/review/', {'action': 'dismiss'})
        report.refresh_from_db()
        self.assertEqual(report.status, NoteReport.STATUS_DISMISSED)


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
        self.assertContains(resp, 'Q1')


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
            'provider': 'local', 'order': 'top',
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
        resp = self.client.get('/notes/exams/')
        self.assertContains(resp, 'Exam — Biology')

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
        self.assertGreaterEqual(Subject.objects.count(), 4)
        self.assertGreaterEqual(Note.objects.filter(status=Note.STATUS_APPROVED).count(), 10)
        self.assertGreaterEqual(QuizSet.objects.filter(is_exam=False).count(), 10)
        self.assertGreaterEqual(QuizSet.objects.filter(is_exam=True).count(), 2)
        n_notes = Note.objects.count()
        n_quiz = QuizSet.objects.count()
        call_command('seed_examples')
        self.assertEqual(Note.objects.count(), n_notes)
        self.assertEqual(QuizSet.objects.count(), n_quiz)


class RemovedNoteVisibilityTests(TestCase):
    """Rejected/private notes must not leak via quiz/rate/report endpoints."""

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
        self.assertEqual(
            self.client.post(f'/notes/{self.rejected.pk}/rate/', {'score': 5}).status_code, 302)

    def test_moderator_can_still_review(self):
        self.client.force_login(self.instructor)
        self.assertEqual(self.client.get(f'/notes/quiz/{self.quiz.pk}/').status_code, 200)

    def test_ensure_subject_case_variants_no_crash(self):
        from apps.notes.views import _ensure_subject
        Subject.objects.create(name='UniqSub')
        Subject.objects.create(name='uniqsub')
        _ensure_subject('UNIQSUB', self.student)  # must not raise
        self.assertTrue(Subject.objects.filter(name__iexact='uniqsub').exists())
