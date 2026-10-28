from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


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

    def test_home_requires_login(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 302)
