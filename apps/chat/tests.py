import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.chat.models import Conversation, Message
from apps.chat.services import generate_reply
from apps.notes.models import Note


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

    def test_conversation_is_private_to_owner(self):
        other = get_user_model().objects.create_user(
            username='other', password='secret1234'
        )
        conversation = Conversation.objects.create(user=other, title='Private')

        response = self.client.get(
            reverse('chat:detail', args=[conversation.pk])
        )

        self.assertEqual(response.status_code, 404)

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

    def test_dashboard_lists_recent_chats(self):
        Conversation.objects.create(user=self.user, title='My recent chat')

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'My recent chat')
        self.assertContains(response, 'New Chat')
        self.assertContains(response, reverse('chat:start'))

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
        self.assertIn('/?next=', response['Location'])


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
