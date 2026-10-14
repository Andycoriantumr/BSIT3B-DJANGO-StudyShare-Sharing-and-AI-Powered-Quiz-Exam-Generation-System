"""Bulk quiz automation for cron/schedulers.

Example:
  python manage.py auto_generate_quizzes --subject Biology --limit 10 --per-note 5 --provider auto
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.notes.models import Note
from apps.notes.services import generate_quiz, get_note_source_text
from apps.notes.views import _create_quiz_set


class Command(BaseCommand):
    help = 'Auto-generate quizzes for approved notes missing them.'

    def add_arguments(self, parser):
        parser.add_argument('--subject', default='', help='Only this subject (exact, case-insensitive).')
        parser.add_argument('--school-year', default='', help='Only this school year.')
        parser.add_argument('--limit', type=int, default=10, help='Max notes to process (1-50).')
        parser.add_argument('--per-note', type=int, default=5, help='Questions per quiz (1-20).')
        parser.add_argument('--question-type', default='mcq',
                            choices=['mixed', 'mcq', 'true_false', 'short_answer', 'essay'])
        parser.add_argument('--provider', default='auto',
                            choices=['auto', 'local', 'openai', 'gemini', 'openrouter'])
        parser.add_argument('--user', default='', help='Username to own generated quizzes (default: first superuser).')
        parser.add_argument('--include-existing', action='store_true',
                            help='Also generate for notes that already have quizzes.')

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['user'].strip()
        if username:
            try:
                owner = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stderr.write(f'User "{username}" not found.')
                return
        else:
            owner = User.objects.filter(is_superuser=True).order_by('id').first() or User.objects.order_by('id').first()
        if owner is None:
            self.stderr.write('No users exist; cannot own generated quizzes.')
            return

        limit = max(1, min(options['limit'], 50))
        per_note = max(1, min(options['per_note'], 20))
        qs = Note.objects.filter(status=Note.STATUS_APPROVED).order_by('-created_at')
        if options['subject'].strip():
            qs = qs.filter(subject__iexact=options['subject'].strip())
        if options['school_year'].strip():
            qs = qs.filter(school_year__iexact=options['school_year'].strip())
        if not options['include_existing']:
            qs = qs.filter(quiz_sets__isnull=True)
        notes = list(qs.distinct()[:limit])

        created, failed = 0, 0
        for note in notes:
            try:
                result = generate_quiz(
                    get_note_source_text(note), num_questions=per_note,
                    question_type=options['question_type'], provider=options['provider'])
                _create_quiz_set(
                    note, owner,
                    f"{options['question_type'].replace('_', ' ').title()} Quiz — {note.title[:60]}",
                    per_note, options['question_type'], result['provider'], result['questions'],
                )
                created += 1
            except Exception as exc:
                failed += 1
                self.stderr.write(f'Failed for note {note.pk}: {exc}')
        self.stdout.write(f'Automation done: {created} created, {failed} failed, {len(notes)} processed.')
