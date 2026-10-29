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
