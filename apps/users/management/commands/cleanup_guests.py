"""Delete abandoned guest accounts and the data they still own."""

from django.core.management.base import BaseCommand

from apps.users.guests import delete_stale_guests


class Command(BaseCommand):
    help = 'Delete guest accounts that have been inactive for N days.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Inactivity period in days (default: 30).',
        )

    def handle(self, *args, **options):
        days = max(1, options['days'])
        deleted = delete_stale_guests(days)
        self.stdout.write(
            self.style.SUCCESS(
                f'Deleted {deleted} guest account(s) inactive for {days}+ days.'
            )
        )
