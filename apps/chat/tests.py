import io
import json
import zipfile
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.chat.models import ChatQuizAttempt, Conversation, Message, MessageAttachment
from apps.chat.selectors import recent_conversations
from apps.chat.services import (
    generate_attachment_questions,
    generate_reply,
    normalize_question_count,
)
from apps.notes.models import Note

QUIZ_QUESTIONS = [
    {
        'question_type': 'mcq',
        'question_text': 'What molecule does cellular respiration produce?',
        'options': ['ATP', 'DNA', 'Glucose', 'Protein'],
        'correct_answer': 'ATP',
        'explanation': 'Cellular respiration produces ATP in mitochondria.',
        'order': 0,
    },
    {
        'question_type': 'mcq',
        'question_text': 'Where does cellular respiration mainly happen?',
        'options': ['Mitochondria', 'Nucleus', 'Ribosome', 'Golgi body'],
        'correct_answer': 'Mitochondria',
        'explanation': 'The mitochondria is the powerhouse of the cell.',
        'order': 1,
    },
]


def _docx_bytes(text):
    document = io.BytesIO()
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'
        f'{text}'
        '</w:t></w:r></w:p></w:body></w:document>'
    )
    with zipfile.ZipFile(document, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('word/document.xml', xml)
    return document.getvalue()


class ChatWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='student', password='secret1234',
            first_name='Ana', last_name='Cruz',
        )
        self.client.force_login(self.user)

    @patch(
        'apps.chat.views.generate_reply',
        return_value={'content': 'Here is an answer.', 'provider': 'local'},
    )
    def test_start_chat_creates_conversation_and_messages(self, mocked_reply):
        response = self.client.post(
            reverse('chat:start'),
            {'content': 'Explain database normalization'},
        )

        conversation = Conversation.objects.get()
        self.assertEqual(conversation.user, self.user)
        self.assertEqual(conversation.title, 'Explain database normalization')
        self.assertEqual(
            list(conversation.messages.values_list('role', flat=True)),
            [Message.ROLE_USER, Message.ROLE_ASSISTANT],
        )
        self.assertEqual(conversation.messages.last().content, 'Here is an answer.')
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, reverse('chat:detail', args=[conversation.pk])
        )
        mocked_reply.assert_called_once()

    @patch(
        'apps.chat.views.generate_reply',
        return_value={'content': 'Follow-up answer.', 'provider': 'local'},
    )
    def test_send_message_appends_reply_and_updates_title(self, mocked_reply):
        conversation = Conversation.objects.create(
            user=self.user, title='New chat'
        )
        Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='First question',
        )

        response = self.client.post(
            reverse('chat:send', args=[conversation.pk]),
            {'content': 'Follow-up question'},
        )

        conversation.refresh_from_db()
        self.assertEqual(conversation.title, 'Follow-up question')
        self.assertEqual(conversation.messages.count(), 3)
        self.assertEqual(
            conversation.messages.last().content, 'Follow-up answer.'
        )
        self.assertRedirects(
            response, reverse('chat:detail', args=[conversation.pk])
        )

    @patch(
        'apps.chat.views.generate_reply',
        return_value={'content': 'JSON answer.', 'provider': 'local'},
    )
    def test_start_chat_json_response(self, mocked_reply):
        response = self.client.post(
            reverse('chat:start'),
            {'content': 'Hello there'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['reply']['role'], Message.ROLE_ASSISTANT)
        self.assertEqual(data['reply']['provider'], 'local')
        self.assertIn('/chat/', data['redirect_url'])

    @patch(
        'apps.chat.views.generate_attachment_questions',
        return_value={
            'content': 'Answer the quiz below.',
            'provider': 'local',
            'questions': [{
                'question_type': 'mcq',
                'question_text': 'What molecule does cellular respiration produce?',
                'options': ['ATP', 'DNA', 'Glucose', 'Protein'],
                'correct_answer': 'ATP',
                'explanation': 'Cellular respiration produces ATP.',
                'order': 0,
            }],
        },
    )
    def test_start_chat_saves_file_and_generates_questions(self, mocked_questions):
        response = self.client.post(
            reverse('chat:start'),
            {
                'content': 'Please review this resource.',
                'question_count': '25',
                'files': SimpleUploadedFile(
                    'study-guide.docx', _docx_bytes(
                        'Cellular respiration produces ATP.'
                    ),
                    content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                ),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        user_message = Message.objects.get(role=Message.ROLE_USER)
        attachment = user_message.attachments.get()
        self.assertEqual(attachment.kind, MessageAttachment.KIND_FILE)
        self.assertEqual(attachment.original_name, 'study-guide.docx')
        self.assertEqual(
            attachment.content_type,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
        self.assertEqual(
            response.json()['reply']['content'],
            'Answer the quiz below.',
        )
        self.assertTrue(response.json()['reply']['has_quiz'])
        assistant = Message.objects.get(role=Message.ROLE_ASSISTANT)
        self.assertEqual(len(assistant.quiz_data), 1)
        self.assertEqual(assistant.quiz_data[0]['correct_answer'], 'ATP')
        mocked_questions.assert_called_once_with(
            user_message, num_questions=25
        )
        self.addCleanup(attachment.file.delete, save=False)

    def test_docx_attachment_view_shows_preview_and_can_still_be_downloaded(self):
        conversation = Conversation.objects.create(
            user=self.user, title='DOCX upload'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='Review this document.',
        )
        attachment = MessageAttachment.objects.create(
            message=message,
            original_name='study-guide.docx',
            file=SimpleUploadedFile(
                'study-guide.docx',
                _docx_bytes('Study guide content.'),
            ),
        )
        self.addCleanup(attachment.file.delete, save=False)

        response = self.client.get(
            reverse('chat:view_attachment', args=[attachment.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Study guide content.')
        self.assertContains(response, 'Download original')

        download_response = self.client.get(
            reverse('chat:download_attachment', args=[attachment.pk])
        )
        self.assertEqual(
            download_response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
        self.assertIn('attachment', download_response['Content-Disposition'])
        with zipfile.ZipFile(
            io.BytesIO(b''.join(download_response.streaming_content))
        ) as downloaded_docx:
            self.assertIn(
                'Study guide content.',
                downloaded_docx.read('word/document.xml').decode(),
            )

    @patch(
        'apps.chat.views.generate_attachment_questions',
        return_value={
            'content': 'Answer the quiz below.',
            'provider': 'local',
            'questions': [{
                'question_type': 'mcq',
                'question_text': 'What is the lesson about?',
                'options': ['Active recall', 'Cooking', 'Driving', 'Painting'],
                'correct_answer': 'Active recall',
                'explanation': 'The lesson is about active recall.',
                'order': 0,
            }],
        },
    )
    def test_start_chat_accepts_file_without_prompt(self, mocked_questions):
        response = self.client.post(
            reverse('chat:start'),
            {
                'files': SimpleUploadedFile(
                    'lesson.md', b'Lesson notes about active recall.',
                    content_type='text/markdown',
                ),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Message.objects.get(role=Message.ROLE_USER).content,
            'Generate practice questions from the attached file.',
        )
        self.assertEqual(
            Conversation.objects.get().title, 'Questions from lesson.md'
        )
        mocked_questions.assert_called_once()
        attachment = MessageAttachment.objects.get()
        self.addCleanup(attachment.file.delete, save=False)

    @patch('apps.chat.services.generate_quiz')
    def test_attachment_questions_extract_docx_text(self, mocked_generate):
        mocked_generate.return_value = {
            'questions': [{
                'question_type': 'mcq',
                'question_text': 'What does cellular respiration produce?',
                'options': ['ATP', 'DNA', 'Protein', 'Water'],
                'correct_answer': 'ATP',
                'explanation': 'ATP is produced.',
                'order': 0,
            }],
            'provider': 'local',
        }
        conversation = Conversation.objects.create(
            user=self.user, title='DOCX quiz'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='Generate questions from my document.',
        )
        attachment = MessageAttachment.objects.create(
            message=message,
            original_name='lesson.docx',
            file=SimpleUploadedFile(
                'lesson.docx',
                _docx_bytes(
                    'Cellular respiration produces ATP inside mitochondria. '
                    'Mitochondria are the powerhouse of the cell.'
                ),
            ),
        )

        result = generate_attachment_questions(message)

        source_text = mocked_generate.call_args.args[0]
        self.assertIn('Cellular respiration produces ATP', source_text)
        self.assertEqual(len(result['questions']), 1)
        self.addCleanup(attachment.file.delete, save=False)

    def test_chat_rejects_unsupported_attachment_type(self):
        response = self.client.post(
            reverse('chat:start'),
            {
                'content': 'Review this.',
                'files': SimpleUploadedFile(
                    'program.exe', b'not allowed',
                    content_type='application/octet-stream',
                ),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])
        self.assertEqual(Conversation.objects.count(), 0)

    def test_chat_attachments_can_be_viewed_and_downloaded(self):
        conversation = Conversation.objects.create(
            user=self.user, title='Uploaded notes'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='Review this file.',
        )
        attachment = MessageAttachment.objects.create(
            message=message,
            original_name='study-notes.txt',
            file=SimpleUploadedFile('study-notes.txt', b'Important study notes.'),
        )
        self.addCleanup(attachment.file.delete, save=False)

        view_response = self.client.get(
            reverse('chat:view_attachment', args=[attachment.pk])
        )
        self.assertEqual(view_response.status_code, 200)
        self.assertEqual(view_response['Content-Type'], 'text/plain; charset=utf-8')
        self.assertIn('inline', view_response['Content-Disposition'])
        self.assertIn(b'Important study notes.', b''.join(view_response.streaming_content))

        download_response = self.client.get(
            reverse('chat:download_attachment', args=[attachment.pk])
        )
        self.assertEqual(download_response.status_code, 200)
        self.assertIn('attachment', download_response['Content-Disposition'])
        self.assertIn('study-notes.txt', download_response['Content-Disposition'])
        self.assertIn(b'Important study notes.', b''.join(download_response.streaming_content))

    def test_chat_attachment_delete_is_post_only_and_private(self):
        other = get_user_model().objects.create_user(
            username='attachment-owner', password='secret1234'
        )
        conversation = Conversation.objects.create(
            user=other, title='Private uploaded notes'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='Private file.',
        )
        attachment = MessageAttachment.objects.create(
            message=message,
            original_name='private.txt',
            file=SimpleUploadedFile('private.txt', b'Private content.'),
        )
        self.addCleanup(attachment.file.delete, save=False)
        stored_name = attachment.file.name

        view_response = self.client.get(
            reverse('chat:view_attachment', args=[attachment.pk])
        )
        self.assertEqual(view_response.status_code, 404)
        delete_response = self.client.post(
            reverse('chat:delete_attachment', args=[attachment.pk])
        )
        self.assertEqual(delete_response.status_code, 404)
        self.assertTrue(MessageAttachment.objects.filter(pk=attachment.pk).exists())

        self.client.force_login(other)
        get_delete_response = self.client.get(
            reverse('chat:delete_attachment', args=[attachment.pk])
        )
        self.assertEqual(get_delete_response.status_code, 405)
        delete_response = self.client.post(
            reverse('chat:delete_attachment', args=[attachment.pk])
        )
        self.assertRedirects(delete_response, reverse('notes:note_list'))
        self.assertFalse(MessageAttachment.objects.filter(pk=attachment.pk).exists())
        self.assertFalse(attachment.file.storage.exists(stored_name))

    def test_conversation_is_private_to_owner(self):
        other = get_user_model().objects.create_user(
            username='other', password='secret1234'
        )
        conversation = Conversation.objects.create(user=other, title='Private')

        response = self.client.get(
            reverse('chat:detail', args=[conversation.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_recent_conversations_lists_pinned_chats_before_recent_chats(self):
        older = Conversation.objects.create(user=self.user, title='Older chat')
        pinned = Conversation.objects.create(
            user=self.user, title='Pinned chat', is_pinned=True
        )
        newest = Conversation.objects.create(user=self.user, title='Newest chat')
        Conversation.objects.filter(pk=older.pk).update(
            updated_at=timezone.now() - timedelta(days=2)
        )
        Conversation.objects.filter(pk=pinned.pk).update(
            updated_at=timezone.now() - timedelta(days=3)
        )

        self.assertEqual(
            list(recent_conversations(self.user)),
            [pinned, newest, older],
        )

    def test_pin_toggle_is_post_only_and_private(self):
        other = get_user_model().objects.create_user(
            username='pin-owner', password='secret1234'
        )
        conversation = Conversation.objects.create(
            user=other, title='Private conversation'
        )

        self.assertEqual(
            self.client.get(reverse('chat:toggle_pin', args=[conversation.pk])).status_code,
            405,
        )
        self.assertEqual(
            self.client.post(reverse('chat:toggle_pin', args=[conversation.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse('chat:share_conversation', args=[conversation.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse('chat:delete_conversation', args=[conversation.pk])
            ).status_code,
            404,
        )
        conversation.refresh_from_db()
        self.assertFalse(conversation.is_pinned)
        self.assertTrue(Conversation.objects.filter(pk=conversation.pk).exists())

        self.client.force_login(other)
        response = self.client.post(
            reverse('chat:toggle_pin', args=[conversation.pk])
        )
        conversation.refresh_from_db()
        self.assertRedirects(
            response, reverse('chat:detail', args=[conversation.pk])
        )
        self.assertTrue(conversation.is_pinned)

    def test_public_share_link_exposes_chat_but_not_attachments_or_answer_key(self):
        conversation = Conversation.objects.create(
            user=self.user, title='Shared study chat'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_ASSISTANT,
            content='Here is a practice question.',
            quiz_data=[{
                'question_text': 'Which is the answer?',
                'options': ['Choice A', 'Choice B'],
                'correct_answer': 'private-answer-key',
                'explanation': 'private explanation',
            }],
        )
        attachment = MessageAttachment.objects.create(
            message=message,
            original_name='private-attachment.txt',
            file=SimpleUploadedFile('private-attachment.txt', b'Private file data.'),
        )
        self.addCleanup(attachment.file.delete, save=False)

        share_response = self.client.post(
            reverse('chat:share_conversation', args=[conversation.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(share_response.status_code, 200)
        share_url = share_response.json()['share_url']
        repeated_share = self.client.post(
            reverse('chat:share_conversation', args=[conversation.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(repeated_share.json()['share_url'], share_url)
        conversation.refresh_from_db()
        self.assertIsNotNone(conversation.share_token)

        self.client.logout()
        public_response = self.client.get(share_url)
        self.assertEqual(public_response.status_code, 200)
        self.assertContains(public_response, 'Shared study chat')
        self.assertContains(public_response, 'Here is a practice question.')
        self.assertContains(public_response, 'Choice A')
        self.assertNotContains(public_response, 'private-answer-key')
        self.assertNotContains(public_response, 'private explanation')
        self.assertNotContains(public_response, 'private-attachment.txt')
        self.assertNotContains(public_response, 'Private file data.')
        self.assertEqual(public_response['Cache-Control'], 'no-store')

    def test_public_share_can_be_revoked_and_cannot_be_managed_by_another_user(self):
        other = get_user_model().objects.create_user(
            username='share-owner', password='secret1234'
        )
        conversation = Conversation.objects.create(
            user=other, title='Shared private conversation',
            share_token='3eab2ddd-8289-4bfa-97e2-7cb77f8b7187',
        )
        public_url = reverse(
            'chat:shared_conversation', args=[conversation.share_token]
        )

        self.assertEqual(self.client.get(public_url).status_code, 200)
        self.assertEqual(
            self.client.post(
                reverse('chat:revoke_share', args=[conversation.pk])
            ).status_code,
            404,
        )

        self.client.force_login(other)
        response = self.client.post(
            reverse('chat:revoke_share', args=[conversation.pk])
        )
        self.assertRedirects(
            response, reverse('chat:detail', args=[conversation.pk])
        )
        self.assertEqual(self.client.get(public_url).status_code, 404)

    def test_delete_conversation_removes_its_uploaded_files(self):
        conversation = Conversation.objects.create(
            user=self.user, title='Chat to delete'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='Remove this file.',
        )
        attachment = MessageAttachment.objects.create(
            message=message,
            original_name='delete-me.txt',
            file=SimpleUploadedFile('delete-me.txt', b'File to remove.'),
        )
        self.addCleanup(attachment.file.delete, save=False)
        stored_name = attachment.file.name

        response = self.client.post(
            reverse('chat:delete_conversation', args=[conversation.pk])
        )

        self.assertRedirects(response, reverse('dashboard'))
        self.assertFalse(Conversation.objects.filter(pk=conversation.pk).exists())
        self.assertFalse(MessageAttachment.objects.filter(pk=attachment.pk).exists())
        self.assertFalse(attachment.file.storage.exists(stored_name))

    def test_conversation_detail_renders_messages(self):
        conversation = Conversation.objects.create(
            user=self.user, title='Database review'
        )
        Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='What is normalization?',
        )
        Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_ASSISTANT,
            content='It organizes tables to reduce redundancy.',
            provider='local',
        )

        response = self.client.get(
            reverse('chat:detail', args=[conversation.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Database review')
        self.assertContains(response, 'What is normalization?')
        self.assertContains(response, 'It organizes tables to reduce redundancy.')
        self.assertContains(response, 'Ask a follow-up')

    def test_conversation_detail_renders_answerable_quiz(self):
        conversation = Conversation.objects.create(
            user=self.user, title='Cellular respiration quiz'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_ASSISTANT,
            content='Your quiz is ready.',
            provider='local',
            quiz_data=QUIZ_QUESTIONS,
        )

        response = self.client.get(
            reverse('chat:detail', args=[conversation.pk])
        )

        self.assertContains(response, 'Practice quiz')
        self.assertContains(
            response, 'What molecule does cellular respiration produce?'
        )
        self.assertContains(response, 'Submit answers')
        self.assertContains(response, 'data-ss-quiz')
        self.assertContains(response, 'name="question_count"')
        self.assertContains(response, 'max="50"')
        self.assertContains(
            response, reverse('chat:grade_quiz', args=[message.pk])
        )
        # Explanations and answer-key data stay on the server until grading.
        self.assertNotContains(
            response, 'Cellular respiration produces ATP in mitochondria.'
        )

    def test_grade_message_quiz_scores_answers_and_returns_key(self):
        conversation = Conversation.objects.create(
            user=self.user, title='Cellular respiration quiz'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_ASSISTANT,
            content='Your quiz is ready.',
            quiz_data=QUIZ_QUESTIONS,
        )

        response = self.client.post(
            reverse('chat:grade_quiz', args=[message.pk]),
            data=json.dumps({
                'answers': {'0': 'ATP', '1': 'Nucleus'},
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['score'], 1)
        self.assertEqual(data['total'], 2)
        self.assertEqual(data['percent'], 50)
        attempt = ChatQuizAttempt.objects.get(message=message, taker=self.user)
        self.assertEqual(attempt.score, 1)
        self.assertEqual(attempt.total, 2)
        self.assertEqual(attempt.percentage, 50)
        self.assertEqual(attempt.answers, {'0': 'ATP', '1': 'Nucleus'})
        self.assertTrue(data['results'][0]['correct'])
        self.assertEqual(data['results'][0]['answer'], 'ATP')
        self.assertFalse(data['results'][1]['correct'])
        self.assertEqual(data['results'][1]['answer'], 'Mitochondria')
        self.assertIn('mitochondria', data['results'][1]['explanation'].lower())

        result_page = self.client.get(
            reverse('chat:quiz_attempt_detail', args=[attempt.pk])
        )
        self.assertEqual(result_page.status_code, 200)
        self.assertContains(result_page, 'Cellular respiration quiz')
        self.assertContains(result_page, '1 / 2')
        self.assertContains(result_page, '50.00%')
        self.assertContains(result_page, 'Your answer:')
        self.assertContains(result_page, 'Nucleus')
        self.assertContains(result_page, 'Incorrect')
        self.assertContains(result_page, 'Answer key:')
        self.assertContains(result_page, 'Mitochondria')
        self.assertContains(result_page, 'Print result')
        self.assertContains(result_page, 'window.print()')

        progress = self.client.get(reverse('notes:my_progress'))
        self.assertEqual(progress.status_code, 200)
        self.assertEqual(progress.context['total_taken'], 1)
        self.assertEqual(progress.context['avg_score'], 50)
        self.assertContains(progress, 'Quiz Attempts')
        self.assertContains(progress, 'Cellular respiration quiz')
        self.assertContains(progress, '1/2 (50.0%)')

        my_quizzes = self.client.get(reverse('notes:exam_list'))
        self.assertEqual(my_quizzes.status_code, 200)
        self.assertContains(my_quizzes, 'My Quizzes')
        self.assertContains(my_quizzes, 'Chat Practice Quizzes Taken')
        self.assertNotContains(my_quizzes, 'Generated Exams')
        self.assertNotContains(my_quizzes, 'Build New Exam')
        self.assertContains(my_quizzes, 'Cellular respiration quiz')
        self.assertContains(my_quizzes, '1/2 (50.0%)')
        self.assertContains(
            my_quizzes,
            reverse('chat:quiz_attempt_detail', args=[attempt.pk]),
        )
        self.assertContains(
            my_quizzes, reverse('chat:detail', args=[conversation.pk])
        )

    def test_chat_quiz_attempt_result_is_private_to_taker(self):
        conversation = Conversation.objects.create(
            user=self.user, title='Private quiz result'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_ASSISTANT,
            content='Quiz result',
            quiz_data=QUIZ_QUESTIONS,
        )
        attempt = ChatQuizAttempt.objects.create(
            message=message,
            taker=self.user,
            score=1,
            total=2,
            percentage=50,
            answers={'0': 'ATP', '1': 'Nucleus'},
        )
        other = get_user_model().objects.create_user(
            username='quiz-result-other', password='secret1234'
        )
        self.client.force_login(other)

        response = self.client.get(
            reverse('chat:quiz_attempt_detail', args=[attempt.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_grade_message_quiz_accepts_letter_answers(self):
        conversation = Conversation.objects.create(
            user=self.user, title='Cellular respiration quiz'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_ASSISTANT,
            content='Your quiz is ready.',
            quiz_data=QUIZ_QUESTIONS,
        )

        response = self.client.post(
            reverse('chat:grade_quiz', args=[message.pk]),
            data=json.dumps({'answers': {'0': 'A', '1': 'a'}}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['score'], 2)
        self.assertEqual(response.json()['percent'], 100)

    def test_grade_message_quiz_is_private_to_owner(self):
        other = get_user_model().objects.create_user(
            username='other', password='secret1234'
        )
        conversation = Conversation.objects.create(user=other, title='Private')
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_ASSISTANT,
            content='Private quiz',
            quiz_data=QUIZ_QUESTIONS,
        )

        response = self.client.post(
            reverse('chat:grade_quiz', args=[message.pk]),
            data=json.dumps({'answers': {'0': 'ATP'}}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)

    def test_grade_message_quiz_requires_quiz_data(self):
        conversation = Conversation.objects.create(
            user=self.user, title='No quiz'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_ASSISTANT,
            content='Just an answer.',
        )

        response = self.client.post(
            reverse('chat:grade_quiz', args=[message.pk]),
            data=json.dumps({'answers': {}}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])

    def test_dashboard_lists_recent_chats(self):
        Conversation.objects.create(user=self.user, title='My recent chat')

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'My recent chat')
        self.assertContains(response, 'New Chat')
        self.assertContains(response, reverse('chat:start'))
        self.assertContains(response, 'name="question_count"')
        self.assertContains(response, 'max="50"')

    def test_empty_message_is_rejected(self):
        response = self.client.post(
            reverse('chat:start'),
            {'content': '   '},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])
        self.assertEqual(Conversation.objects.count(), 0)

    def test_start_chat_requires_login(self):
        self.client.logout()

        response = self.client.post(
            reverse('chat:start'), {'content': 'Hello'}
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/?next=', response['Location'])


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ChatServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='reader', password='secret1234'
        )

    def test_normalize_question_count_clamps_to_supported_range(self):
        self.assertEqual(normalize_question_count('12'), 12)
        self.assertEqual(normalize_question_count('50'), 50)
        self.assertEqual(normalize_question_count('0'), 1)
        self.assertEqual(normalize_question_count('500'), 50)
        self.assertEqual(normalize_question_count(None), 10)
        self.assertEqual(normalize_question_count('not-a-number'), 10)

    @override_settings(
        OPENROUTER_API_KEY='test-key',
        OPENROUTER_MODEL='test-model',
        GEMINI_API_KEY='',
        OPENAI_API_KEY='',
    )
    @patch('urllib.request.urlopen')
    def test_generate_reply_uses_configured_provider(self, mocked_urlopen):
        mocked_urlopen.return_value = _FakeResponse({
            'choices': [{'message': {'content': 'Cloud answer.'}}],
        })
        conversation = Conversation.objects.create(
            user=self.user, title='New chat'
        )
        Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='What is normalization?',
        )

        result = generate_reply(
            self.user, conversation, 'What is normalization?'
        )

        self.assertEqual(result['provider'], 'openrouter')
        self.assertEqual(result['content'], 'Cloud answer.')
        self.assertTrue(mocked_urlopen.called)

    @override_settings(
        GEMINI_API_KEY='test-gemini-key',
        GEMINI_MODEL='gemini-flash-latest',
        OPENROUTER_API_KEY='',
        OPENAI_API_KEY='',
    )
    @patch('urllib.request.urlopen')
    def test_generate_reply_prefers_gemini_with_header_auth(self, mocked_urlopen):
        mocked_urlopen.return_value = _FakeResponse({
            'candidates': [{
                'content': {'parts': [{'text': 'Gemini answer.'}]},
                'finishReason': 'STOP',
            }],
        })
        conversation = Conversation.objects.create(
            user=self.user, title='New chat'
        )
        Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='What is a primary key?',
        )

        result = generate_reply(
            self.user, conversation, 'What is a primary key?'
        )

        self.assertEqual(result['provider'], 'gemini')
        self.assertEqual(result['content'], 'Gemini answer.')
        request = mocked_urlopen.call_args[0][0]
        self.assertNotIn('key=', request.full_url)
        self.assertIn('test-gemini-key', request.headers.values())
        payload = json.loads(request.data.decode('utf-8'))
        self.assertEqual(
            payload['generationConfig']['thinkingConfig'],
            {'thinkingBudget': 0},
        )
        self.assertIn('systemInstruction', payload)

    @override_settings(
        GEMINI_API_KEY='test-gemini-key',
        GEMINI_MODEL='gemini-flash-latest',
    )
    @patch('urllib.request.urlopen')
    def test_gemini_empty_answer_reports_finish_reason(self, mocked_urlopen):
        from apps.chat.services import _gemini_chat

        mocked_urlopen.return_value = _FakeResponse({
            'candidates': [{
                'content': {'parts': []},
                'finishReason': 'MAX_TOKENS',
            }],
        })

        with self.assertRaisesMessage(ValueError, 'MAX_TOKENS'):
            _gemini_chat(
                'test-gemini-key',
                'gemini-flash-latest',
                'You are a study assistant.',
                [{'role': Message.ROLE_USER, 'content': 'Hello'}],
            )

    @patch(
        'apps.chat.services._call_provider',
        side_effect=RuntimeError('no provider configured'),
    )
    def test_offline_reply_uses_matching_notes(self, mocked_call):
        Note.objects.create(
            title='Database Normalization Basics',
            subject='IT302',
            instructor='Prof. Cruz',
            topic='Normalization',
            school_year='2025-2026',
            content=(
                'Database normalization organizes tables to reduce redundancy. '
                'First normal form requires atomic column values. '
                'Second normal form removes partial dependencies.'
            ),
            uploaded_by=self.user,
            status=Note.STATUS_APPROVED,
            is_public=True,
        )
        conversation = Conversation.objects.create(
            user=self.user, title='New chat'
        )
        Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='Explain database normalization',
        )

        result = generate_reply(
            self.user, conversation, 'Explain database normalization'
        )

        self.assertEqual(result['provider'], 'local')
        self.assertIn('offline', result['content'].lower())
        self.assertIn('Database Normalization Basics', result['content'])
        mocked_call.assert_called()

    @patch(
        'apps.chat.services._call_provider',
        side_effect=RuntimeError('no provider configured'),
    )
    def test_generic_note_request_uses_newest_notes(self, mocked_call):
        Note.objects.create(
            title='Cell Biology Review',
            subject='BIO101',
            instructor='Prof. Reyes',
            topic='Cells',
            school_year='2025-2026',
            content='Mitochondria produce ATP through cellular respiration.',
            uploaded_by=self.user,
            status=Note.STATUS_APPROVED,
            is_public=True,
        )
        conversation = Conversation.objects.create(
            user=self.user, title='New chat'
        )
        Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='Summarize my notes',
        )

        result = generate_reply(self.user, conversation, 'Summarize my notes')

        self.assertEqual(result['provider'], 'local')
        self.assertIn('Cell Biology Review', result['content'])

    @patch('apps.chat.services.generate_quiz')
    def test_attachment_questions_use_extracted_file_text(self, mocked_generate):
        mocked_generate.return_value = {
            'questions': [{
                'question_type': 'mcq',
                'question_text': 'What molecule does cellular respiration produce?',
                'options': ['ATP', 'DNA', 'Glucose', 'Protein'],
                'correct_answer': 'ATP',
                'explanation': 'Cellular respiration produces ATP in mitochondria.',
                'order': 0,
            }],
            'provider': 'local',
        }
        conversation = Conversation.objects.create(
            user=self.user, title='New chat'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='Generate practice questions from the attached file.',
        )
        attachment = MessageAttachment.objects.create(
            message=message,
            kind=MessageAttachment.KIND_FILE,
            original_name='lesson.txt',
            content_type='text/plain',
            file=SimpleUploadedFile(
                'lesson.txt',
                b'Cellular respiration produces ATP inside mitochondria. '
                b'Mitochondria are the powerhouse of the cell.',
                content_type='text/plain',
            ),
        )

        result = generate_attachment_questions(message, num_questions=75)

        source_text = mocked_generate.call_args.args[0]
        self.assertIn('Cellular respiration produces ATP', source_text)
        self.assertNotIn('=== FILE:', source_text)
        self.assertIn('lesson.txt', result['content'])
        self.assertNotIn(
            'What molecule does cellular respiration produce?',
            result['content'],
        )
        self.assertNotIn('**Answer:**', result['content'])
        self.assertEqual(result['provider'], 'local')
        self.assertEqual(len(result['questions']), 1)
        self.assertEqual(
            result['questions'][0]['correct_answer'], 'ATP'
        )
        self.assertEqual(
            mocked_generate.call_args.kwargs['question_type'], 'mcq'
        )
        self.assertEqual(
            mocked_generate.call_args.kwargs['num_questions'], 50
        )
        self.addCleanup(attachment.file.delete, save=False)

    @patch('apps.chat.services.generate_quiz')
    def test_attachment_questions_skip_unreadable_files(self, mocked_generate):
        conversation = Conversation.objects.create(
            user=self.user, title='New chat'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='Generate practice questions from the attached file.',
        )
        attachment = MessageAttachment.objects.create(
            message=message,
            kind=MessageAttachment.KIND_FILE,
            original_name='empty.txt',
            content_type='text/plain',
            file=SimpleUploadedFile(
                'empty.txt', b'   ', content_type='text/plain',
            ),
        )

        result = generate_attachment_questions(message)

        self.assertEqual(result['provider'], 'local')
        self.assertIn("couldn't read any text", result['content'])
        self.assertEqual(result['questions'], [])
        mocked_generate.assert_not_called()
        self.addCleanup(attachment.file.delete, save=False)

    @override_settings(
        GEMINI_API_KEY='',
        OPENAI_API_KEY='',
        OPENROUTER_API_KEY='',
    )
    def test_attachment_questions_fall_back_to_local_generator(self):
        conversation = Conversation.objects.create(
            user=self.user, title='New chat'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='Generate practice questions from the attached file.',
        )
        attachment = MessageAttachment.objects.create(
            message=message,
            kind=MessageAttachment.KIND_FILE,
            original_name='biology.txt',
            content_type='text/plain',
            file=SimpleUploadedFile(
                'biology.txt',
                b'Cellular respiration produces ATP inside mitochondria. '
                b'Mitochondria are known as the powerhouse of the cell. '
                b'Active recall and spaced repetition improve long-term retention.',
                content_type='text/plain',
            ),
        )

        result = generate_attachment_questions(message)

        self.assertEqual(result['provider'], 'local')
        self.assertIn('practice quiz generated from', result['content'])
        self.assertEqual(len(result['questions']), 10)
        self.assertTrue(all(
            question['question_type'] == 'mcq'
            for question in result['questions']
        ))
        self.assertNotIn('**Answer:**', result['content'])
        self.addCleanup(attachment.file.delete, save=False)

    @override_settings(
        GEMINI_API_KEY='',
        OPENAI_API_KEY='',
        OPENROUTER_API_KEY='',
    )
    def test_attachment_questions_supports_up_to_50_questions(self):
        conversation = Conversation.objects.create(
            user=self.user, title='New chat'
        )
        message = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='Generate practice questions from the attached file.',
        )
        attachment = MessageAttachment.objects.create(
            message=message,
            kind=MessageAttachment.KIND_FILE,
            original_name='biology.txt',
            content_type='text/plain',
            file=SimpleUploadedFile(
                'biology.txt',
                b'Cellular respiration produces ATP inside mitochondria. '
                b'Mitochondria are known as the powerhouse of the cell. '
                b'Active recall and spaced repetition improve long-term retention.',
                content_type='text/plain',
            ),
        )

        result = generate_attachment_questions(message, num_questions=50)
        questions = result['questions']

        self.assertEqual(len(questions), 50)
        self.assertGreater(
            len({question['question_text'] for question in questions}), 30
        )
        self.assertTrue(all(
            len(question['options']) == 4
            and question['correct_answer'] in question['options']
            for question in questions
        ))
        self.addCleanup(attachment.file.delete, save=False)

    @patch(
        'apps.chat.services._call_provider',
        side_effect=RuntimeError('no provider configured'),
    )
    def test_offline_reply_without_matching_notes(self, mocked_call):
        conversation = Conversation.objects.create(
            user=self.user, title='New chat'
        )
        Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content='Quantum chromodynamics',
        )

        result = generate_reply(
            self.user, conversation, 'Quantum chromodynamics'
        )

        self.assertEqual(result['provider'], 'local')
        self.assertIn('offline', result['content'].lower())
        self.assertIn('couldn', result['content'].lower())
