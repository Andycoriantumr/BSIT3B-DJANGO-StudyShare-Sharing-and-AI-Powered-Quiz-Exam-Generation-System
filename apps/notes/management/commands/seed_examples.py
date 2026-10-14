"""Seed example subjects, notes, quizzes, and exams for demos.

Idempotent: safe to run multiple times (uses get_or_create, skips notes that
already have quizzes).

Example:
  python manage.py seed_examples
  python manage.py seed_examples --user instructor --no-exams
  python manage.py seed_examples --reset   # wipes StudyShare demo data first
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.notes.models import Note, NoteRating, QuizSet, Subject
from apps.notes.services import build_exam_source, generate_quiz
from apps.notes.views import _create_quiz_set

EXAMPLE_SUBJECTS = [
    {'name': 'Biology', 'code': 'BIO101', 'description': 'Life science fundamentals.'},
    {'name': 'Mathematics', 'code': 'MATH101', 'description': 'Algebra and probability basics.'},
    {'name': 'Philippine History', 'code': 'HIST101', 'description': 'Key eras in Philippine history.'},
    {'name': 'IT Capstone', 'code': 'IT401', 'description': 'Software projects and databases.'},
]

EXAMPLE_NOTES = [
    {
        'title': 'Photosynthesis Fundamentals',
        'subject': 'Biology', 'instructor': 'Prof. Santos', 'topic': 'Photosynthesis',
        'school_year': '2024-2025',
        'description': 'How plants convert light into chemical energy.',
        'content': (
            'Photosynthesis converts light energy into chemical energy stored in glucose. '
            'Chlorophyll absorbs sunlight inside the chloroplasts of plant cells. '
            'Carbon dioxide enters through the stomata while water is absorbed by the roots. '
            'The light-dependent reactions produce ATP and NADPH in the thylakoid membranes. '
            'The Calvin cycle fixes carbon dioxide into sugar in the stroma of the chloroplast. '
            'Oxygen is released as a byproduct that most living organisms depend on for respiration.'
        ),
    },
    {
        'title': 'Mitosis and Cell Division',
        'subject': 'Biology', 'instructor': 'Prof. Santos', 'topic': 'Mitosis',
        'school_year': '2024-2025',
        'description': 'Stages of mitosis and why they matter.',
        'content': (
            'Mitosis produces two genetically identical daughter cells from one parent cell. '
            'During prophase, chromatin condenses into visible chromosomes and the spindle forms. '
            'In metaphase, chromosomes line up along the equatorial plate of the cell. '
            'Sister chromatids separate and move to opposite poles during anaphase. '
            'Telophase reforms the nuclear envelope around each set of chromosomes. '
            'Cytokinesis then divides the cytoplasm to complete the process of cell division.'
        ),
    },
    {
        'title': 'Human Digestive System Overview',
        'subject': 'Biology', 'instructor': 'Prof. Santos', 'topic': 'Digestion',
        'school_year': '2024-2025',
        'description': 'Organs and enzymes of digestion.',
        'content': (
            'Digestion mechanically and chemically breaks food into absorbable nutrients. '
            'Salivary amylase in the mouth begins the chemical digestion of starch. '
            'Hydrochloric acid and pepsin in the stomach digest proteins into peptides. '
            'The small intestine absorbs most nutrients through villi into the bloodstream. '
            'Bile from the liver emulsifies fats to increase the surface area for enzymes. '
            'Undigested material passes into the large intestine where water is reabsorbed.'
        ),
    },
    {
        'title': 'Solving Quadratic Equations',
        'subject': 'Mathematics', 'instructor': 'Prof. Reyes', 'topic': 'Quadratics',
        'school_year': '2024-2025',
        'description': 'Factoring, completing the square, and the formula.',
        'content': (
            'A quadratic equation has the standard form ax squared plus bx plus c equals zero. '
            'Factoring rewrites the quadratic as a product of two linear binomial expressions. '
            'Completing the square converts the equation into a perfect square trinomial form. '
            'The quadratic formula gives solutions using negative b plus or minus the discriminant. '
            'The discriminant b squared minus 4ac determines the number of real solutions. '
            'A positive discriminant means two real roots while zero means exactly one repeated root.'
        ),
    },
    {
        'title': 'Basic Probability Rules',
        'subject': 'Mathematics', 'instructor': 'Prof. Reyes', 'topic': 'Probability',
        'school_year': '2024-2025',
        'description': 'Sample spaces, independent events, expected value.',
        'content': (
            'Probability measures the likelihood of an event on a scale from zero to one. '
            'The sample space is the set of all possible outcomes of a random experiment. '
            'Two events are independent when the occurrence of one does not affect the other. '
            'The addition rule finds the probability that at least one of two events occurs. '
            'Conditional probability measures the chance of an event given that another occurred. '
            'Expected value is the long-run average outcome of a repeated random process.'
        ),
    },
    {
        'title': 'The Philippine Revolution',
        'subject': 'Philippine History', 'instructor': 'Prof. Aquino', 'topic': 'Revolution',
        'school_year': '2024-2025',
        'description': 'Causes and key events of the 1896 revolution.',
        'content': (
            'The Philippine Revolution began in 1896 against more than three centuries of Spanish rule. '
            'The Katipunan was a secret society founded by Andres Bonifacio to organize the uprising. '
            'The Cry of Pugad Lawin symbolized the start of open revolt in August 1896. '
            'Jose Rizal advocated reforms through education before his execution in December 1896. '
            'Emilio Aguinaldo later led revolutionary forces and declared independence in June 1898. '
            'The revolution shifted into resistance against the United States after the Treaty of Paris.'
        ),
    },
    {
        'title': 'The Post-War Philippine Republic',
        'subject': 'Philippine History', 'instructor': 'Prof. Aquino', 'topic': 'Post-War Republic',
        'school_year': '2024-2025',
        'description': 'Rebuilding the republic after World War II.',
        'content': (
            'The Third Philippine Republic was inaugurated on July 4, 1946 after independence. '
            'Manuel Roxas became the first president of the newly independent republic. '
            'War rehabilitation funds helped rebuild infrastructure destroyed during the occupation. '
            'The Bell Trade Act shaped early economic relations between the Philippines and America. '
            'Land reform debates grew as tenant farmers demanded fair ownership of farmland. '
            'Democratic institutions expanded even as regional inequalities remained a challenge.'
        ),
    },
    {
        'title': 'SDLC Overview for Capstone',
        'subject': 'IT Capstone', 'instructor': 'Prof. Cruz', 'topic': 'SDLC',
        'school_year': '2024-2025',
        'description': 'Planning through maintenance in software projects.',
        'content': (
            'The software development life cycle organizes work from planning through maintenance. '
            'Requirements gathering captures what stakeholders need the system to accomplish. '
            'System design translates requirements into architecture, modules, and data models. '
            'Implementation writes and reviews code according to the approved technical design. '
            'Testing verifies that each feature meets its acceptance criteria before release. '
            'Deployment and maintenance deliver the system and fix issues discovered in production.'
        ),
    },
    {
        'title': 'Database Normalization Basics',
        'subject': 'IT Capstone', 'instructor': 'Prof. Cruz', 'topic': 'Normalization',
        'school_year': '2024-2025',
        'description': 'First through third normal forms with examples.',
        'content': (
            'Normalization organizes relational tables to reduce redundancy and anomalies. '
            'First normal form requires atomic values with no repeating groups in any row. '
            'Second normal form removes partial dependencies on only part of a composite key. '
            'Third normal form eliminates transitive dependencies between non-key attributes. '
            'A primary key uniquely identifies each row while foreign keys link related tables. '
            'Denormalization is sometimes used to improve read performance for reporting queries.'
        ),
    },
    {
        'title': 'Agile Scrum in Student Teams',
        'subject': 'IT Capstone', 'instructor': 'Prof. Cruz', 'topic': 'Scrum',
        'school_year': '2024-2025',
        'description': 'Sprints, roles, and ceremonies that work for class projects.',
        'content': (
            'Scrum divides capstone work into short sprints that each deliver a usable increment. '
            'The product owner prioritizes the backlog by value to the users of the system. '
            'The scrum master removes blockers so the team can sustain steady progress. '
            'Daily standups keep every member aware of yesterday, today, and impediments. '
            'Sprint reviews demonstrate completed features to stakeholders for fast feedback. '
            'Retrospectives help student teams improve collaboration before the next sprint begins.'
        ),
    },
]


class Command(BaseCommand):
    help = 'Seed example subjects, notes, quizzes, and exams (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument('--user', default='', help='Owner username for seeded items.')
        parser.add_argument('--no-quizzes', action='store_true', help='Skip per-note quiz generation.')
        parser.add_argument('--no-exams', action='store_true', help='Skip automated exam generation.')
        parser.add_argument('--reset', action='store_true',
                            help='Delete existing StudyShare demo data (notes, subjects, quizzes) first.')

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        username = options['user'].strip()
        if username:
            owner, _ = User.objects.get_or_create(username=username, defaults={'is_staff': True})
        else:
            owner = (User.objects.filter(username='instructor').first()
                     or User.objects.filter(is_superuser=True).order_by('id').first()
                     or User.objects.order_by('id').first())
            if owner is None:
                owner = User.objects.create_user(username='demo_teacher', password='demo12345', is_staff=True)

        if options['reset']:
            QuizSet.objects.all().delete()
            Note.objects.all().delete()
            Subject.objects.all().delete()
            self.stdout.write('Reset: cleared notes, subjects, and quizzes.')

        sub_created = 0
        for s in EXAMPLE_SUBJECTS:
            _, created = Subject.objects.get_or_create(
                name=s['name'],
                defaults={'code': s['code'], 'description': s['description'], 'created_by': owner},
            )
            sub_created += int(created)

        note_created = 0
        notes = []
        for n in EXAMPLE_NOTES:
            note, created = Note.objects.get_or_create(
                title=n['title'],
                defaults={
                    'subject': n['subject'], 'instructor': n['instructor'], 'topic': n['topic'],
                    'school_year': n['school_year'], 'description': n['description'],
                    'content': n['content'], 'uploaded_by': owner,
                    'status': Note.STATUS_APPROVED, 'is_public': True,
                },
            )
            note_created += int(created)
            notes.append(note)

        # A few ratings so top-rated ordering has something to show.
        raters = list(User.objects.exclude(pk=owner.pk)[:3])
        for i, note in enumerate(notes[:6]):
            for j, rater in enumerate(raters):
                NoteRating.objects.update_or_create(
                    note=note, user=rater,
                    defaults={'score': 5 - ((i + j) % 3), 'comment': ''},
                )

        quiz_created = 0
        if not options['no_quizzes']:
            for note in notes:
                if note.quiz_sets.exists():
                    continue
                result = generate_quiz(
                    note.content, num_questions=5, question_type='mixed', provider='local')
                _create_quiz_set(
                    note, owner, f'Mixed Quiz — {note.title[:60]}',
                    5, 'mixed', result['provider'], result['questions'],
                )
                quiz_created += 1

        exam_created = 0
        if not options['no_exams']:
            bundles = [
                ('Biology', [n for n in notes if n.subject == 'Biology']),
                ('IT Capstone', [n for n in notes if n.subject == 'IT Capstone']),
            ]
            for label, bundle in bundles:
                if len(bundle) < 2:
                    continue
                if QuizSet.objects.filter(is_exam=True, exam_subject=label).exists():
                    continue
                result = generate_quiz(
                    build_exam_source(bundle), num_questions=20,
                    question_type='mixed', provider='local')
                _create_quiz_set(
                    bundle[0], owner, f'Exam — {label} (20 Qs, {len(bundle)} sources)',
                    20, 'mixed', result['provider'], result['questions'],
                    is_exam=True, exam_subject=label,
                    source_ids=[n.pk for n in bundle],
                )
                exam_created += 1

        self.stdout.write(
            f'Seeded: {sub_created} new subjects, {note_created} new notes, '
            f'{quiz_created} new quizzes, {exam_created} new exams '
            f'(totals: {Subject.objects.count()} subjects, {Note.objects.count()} notes, '
            f'{QuizSet.objects.filter(is_exam=False).count()} quizzes, '
            f'{QuizSet.objects.filter(is_exam=True).count()} exams).'
        )
