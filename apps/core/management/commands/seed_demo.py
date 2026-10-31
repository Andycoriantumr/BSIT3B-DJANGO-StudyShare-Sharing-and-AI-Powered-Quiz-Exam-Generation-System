"""Create the demo student account and seed example StudyShare content."""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.users.models import Profile

STUDENT_ACCOUNT = {
    'username': 'andy',
    'password': 'Andy123456',
    'first_name': 'Andy',
    'last_name': 'Peduhan',
    'role': Profile.ROLE_STUDENT,
    'is_staff': False,
    'is_superuser': False,
}

OPTIONAL_STAFF_ACCOUNTS = [
    {
        'username': 'instructor',
        'password': 'Instructor123456',
        'first_name': 'Rino',
        'last_name': 'Montalvo',
        'role': Profile.ROLE_INSTRUCTOR,
        'is_staff': True,
        'is_superuser': False,
    },
    {
        'username': 'admin',
        'password': 'Admin123456',
        'first_name': 'Jerald',
        'last_name': 'Macasling',
        'role': Profile.ROLE_ADMIN,
        'is_staff': True,
        'is_superuser': True,
    },
]


class Command(BaseCommand):
    help = 'Create the demo student account and seed example subjects, notes, quizzes, and exams.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-staff',
            action='store_true',
            help='Also create the demo instructor and admin accounts.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        accounts = [STUDENT_ACCOUNT]
        if options['with_staff']:
            accounts.extend(OPTIONAL_STAFF_ACCOUNTS)

        created_count = 0
        for account in accounts:
            user, created = User.objects.get_or_create(
                username=account['username'],
                defaults={
                    'first_name': account['first_name'],
                    'last_name': account['last_name'],
                    'is_staff': account['is_staff'],
                    'is_superuser': account['is_superuser'],
                },
            )
            if created:
                user.set_password(account['password'])
                created_count += 1

            # Keep demo roles and staff flags predictable on repeat runs,
            # but never reset a password that already exists.
            user.first_name = account['first_name']
            user.last_name = account['last_name']
            user.is_staff = account['is_staff']
            user.is_superuser = account['is_superuser']
            user.save()

            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role = account['role']
            profile.is_guest = False
            profile.save(update_fields=['role', 'is_guest', 'updated_at'])

        call_command('seed_examples', user=STUDENT_ACCOUNT['username'])

        self.stdout.write(
            self.style.SUCCESS(
                f'Demo account ready ({created_count} created). '
                f'Sign in as {STUDENT_ACCOUNT["username"]}.'
            )
        )
