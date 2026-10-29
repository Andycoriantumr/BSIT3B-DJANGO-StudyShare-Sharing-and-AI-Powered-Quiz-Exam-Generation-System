from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.chat.models import ChatQuizAttempt, MessageAttachment
from apps.users.models import Profile
from apps.users.roles import can_admin, can_moderate

from .forms import NoteForm, ReportForm, SubjectForm
from .models import Note, NoteRating, NoteReport, Question, QuizAttempt, QuizSet, Subject
from .services import build_exam_source, generate_quiz, get_note_source_text


def _create_quiz_set(note, user, title, num, qtype, provider_name, questions,
                     is_exam=False, exam_subject='', source_ids=None):
    quiz = QuizSet.objects.create(
        note=note, created_by=user, title=title,
        num_questions=num, question_type=qtype, provider=provider_name,
        is_exam=is_exam, exam_subject=exam_subject or '',
        source_note_ids=source_ids or [],
    )
    Question.objects.bulk_create([
        Question(
            quiz=quiz,
            question_type=item.get('question_type', 'mcq'),
            question_text=item.get('question_text', ''),
            options=item.get('options', []),
            correct_answer=item.get('correct_answer', ''),
            explanation=item.get('explanation', ''),
            order=item.get('order', i),
        )
        for i, item in enumerate(questions)
    ])
    return quiz


def _visible_notes_for(user):
    qs = Note.objects.select_related('uploaded_by').annotate(
        avg_score=Avg('ratings__score'), num_ratings=Count('ratings')
    )
    if not can_moderate(user):
        qs = qs.filter(
            Q(status=Note.STATUS_APPROVED, is_public=True) | Q(uploaded_by=user)
        )
    return qs


def _pick_notes_for_exam(user, subject='', school_year='', topic='', limit=4, order='top'):
    qs = _visible_notes_for(user).filter(status=Note.STATUS_APPROVED)
    if subject:
        qs = qs.filter(subject__iexact=subject)
    if school_year:
        qs = qs.filter(school_year__iexact=school_year)
    if topic:
        qs = qs.filter(topic__icontains=topic)
    if order == 'newest':
        qs = qs.order_by('-created_at')
    else:
        qs = qs.order_by('-avg_score', '-num_ratings', '-created_at')
    return list(qs[:max(1, min(limit, 8))])


def _ensure_subject(name, user):
    name = (name or '').strip()
    if not name:
        return
    try:
        if Subject.objects.filter(name__iexact=name).exists():
            return
        Subject.objects.create(name=name, created_by=user)
    except IntegrityError:
        pass


def _can_view_note(user, note):
    """Mirror of the note_detail visibility rules (rejected/private notes)."""
    if note.status == Note.STATUS_REJECTED and not can_moderate(user) and note.uploaded_by_id != user.pk:
        return False
    if not note.is_public and note.uploaded_by_id != user.pk and not can_moderate(user):
        return False
    return True


@login_required(login_url='login')
def note_list(request):
    context = {
        'uploaded_files': MessageAttachment.objects.filter(
            message__conversation__user=request.user
        ).select_related('message__conversation').order_by('-created_at'),
    }
    return render(request, 'notes/list.html', context)


@login_required(login_url='login')
def note_detail(request, pk):
    note = get_object_or_404(
        Note.objects.select_related('uploaded_by').annotate(avg_score=Avg('ratings__score')),
        pk=pk,
    )
    if not _can_view_note(request.user, note):
        if note.status == Note.STATUS_REJECTED:
            messages.error(request, 'This note has been removed by moderators.')
        else:
            messages.error(request, 'This note is private.')
        return redirect('notes:note_list')
    ratings = note.ratings.select_related('user')[:20]
    quiz_sets = note.quiz_sets.select_related('created_by').prefetch_related('questions')
    my_attempts = QuizAttempt.objects.filter(
        quiz__in=quiz_sets, taker=request.user
    ).select_related('quiz').order_by('-submitted_at')[:10]
    report_form = ReportForm()
    return render(request, 'notes/detail.html', {
        'note': note,
        'ratings': ratings,
        'quiz_sets': quiz_sets,
        'my_rating': note.user_rating(request.user),
        'my_attempts': my_attempts,
        'report_form': report_form,
    })


@login_required(login_url='login')
def note_create(request):
    if request.method == 'GET':
        return redirect('dashboard')

    # Keep existing note POSTs compatible while uploads move to chat.
    if request.method == 'POST':
        form = NoteForm(request.POST, request.FILES)
        if form.is_valid():
            note = form.save(commit=False)
            note.uploaded_by = request.user
            # Students go through review; instructors/admins auto-approve.
            if can_moderate(request.user):
                note.status = Note.STATUS_APPROVED
            else:
                note.status = Note.STATUS_PENDING
            note.save()
            _ensure_subject(note.subject, request.user)
            if note.status == Note.STATUS_PENDING:
                messages.success(request, f'Note "{note.title}" uploaded and pending review.')
            else:
                messages.success(request, f'Note "{note.title}" uploaded.')
            return redirect('notes:note_detail', pk=note.pk)
        messages.error(request, 'The note could not be uploaded. Check the required fields and try again.')
        return redirect('dashboard')
    else:
        return redirect('dashboard')


@login_required(login_url='login')
def note_update(request, pk):
    note = get_object_or_404(Note, pk=pk)
    if note.uploaded_by != request.user and not can_moderate(request.user):
        messages.error(request, 'You can only edit your own notes.')
        return redirect('notes:note_detail', pk=pk)
    if request.method == 'POST':
        form = NoteForm(request.POST, request.FILES, instance=note)
        if form.is_valid():
            form.save()
            _ensure_subject(note.subject, request.user)
            messages.success(request, 'Note updated.')
            return redirect('notes:note_detail', pk=pk)
    else:
        form = NoteForm(instance=note)
    subjects = Subject.objects.filter(is_active=True).order_by('name')
    return render(request, 'notes/form.html', {'form': form, 'mode': 'edit', 'note': note, 'subjects': subjects})


@login_required(login_url='login')
@require_POST
def note_delete(request, pk):
    note = get_object_or_404(Note, pk=pk)
    if note.uploaded_by != request.user and not can_moderate(request.user):
        messages.error(request, 'You can only delete your own notes.')
        return redirect('notes:note_detail', pk=pk)
    title = note.title
    note.delete()
    messages.success(request, f'Note "{title}" deleted.')
    return redirect('notes:note_list')


@login_required(login_url='login')
@require_POST
def note_rate(request, pk):
    note = get_object_or_404(Note, pk=pk)
    if not _can_view_note(request.user, note):
        messages.error(request, 'You cannot rate this note.')
        return redirect('notes:note_list')
    try:
        score = int(request.POST.get('score', 0))
    except (TypeError, ValueError):
        score = 0
    if score < 1 or score > 5:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Score must be 1-5.'}, status=400)
        messages.error(request, 'Score must be between 1 and 5.')
        return redirect('notes:note_detail', pk=pk)
    comment = request.POST.get('comment', '').strip()[:1000]
    NoteRating.objects.update_or_create(
        note=note, user=request.user, defaults={'score': score, 'comment': comment}
    )
    note.refresh_from_db()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success', 'avg_rating': note.avg_rating,
            'ratings_count': note.ratings_count,
        })
    messages.success(request, 'Thanks for rating this note!')
    return redirect('notes:note_detail', pk=pk)


# ---------------------------------------------------------------------------
# Subjects (Instructor/Admin manage, everyone reads active list)
# ---------------------------------------------------------------------------

@login_required(login_url='login')
def subject_list(request):
    # Count notes by matching name since Note.subject is a CharField.
    subjects = Subject.objects.all().order_by('name')
    counts = {
        n['subject']: n['c']
        for n in Note.objects.values('subject').annotate(c=Count('id')).values('subject', 'c')
    }
    q = request.GET.get('q', '').strip()
    if q:
        subjects = subjects.filter(Q(name__icontains=q) | Q(code__icontains=q))
    paginator = Paginator(subjects, 12)
    page = paginator.get_page(request.GET.get('page', 1))
    for s in page.object_list:
        s.computed_notes = counts.get(s.name, 0)
    return render(request, 'notes/subjects.html', {
        'subjects': page, 'query': q, 'form': SubjectForm(),
    })


@login_required(login_url='login')
@user_passes_test(can_moderate, login_url='dashboard')
@require_POST
def subject_save(request):
    sid = request.POST.get('id', '').strip()
    if sid:
        subject = get_object_or_404(Subject, pk=sid)
        form = SubjectForm(request.POST, instance=subject)
    else:
        form = SubjectForm(request.POST)
    if form.is_valid():
        obj = form.save(commit=False)
        if not obj.pk:
            obj.created_by = request.user
        obj.save()
        messages.success(request, f'Subject "{obj.name}" saved.')
    else:
        messages.error(request, 'Could not save subject. Name is required and must be unique.')
    return redirect('notes:subject_list')


@login_required(login_url='login')
@user_passes_test(can_moderate, login_url='dashboard')
@require_POST
def subject_delete(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    name = subject.name
    subject.delete()
    messages.success(request, f'Subject "{name}" deleted.')
    return redirect('notes:subject_list')


# ---------------------------------------------------------------------------
# Reports + moderation queue
# ---------------------------------------------------------------------------

@login_required(login_url='login')
@require_POST
def report_create(request, pk):
    note = get_object_or_404(Note, pk=pk)
    if not _can_view_note(request.user, note):
        messages.error(request, 'You cannot report this note.')
        return redirect('notes:note_list')
    form = ReportForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Please choose a reason for the report.')
        return redirect('notes:note_detail', pk=pk)
    existing = NoteReport.objects.filter(
        note=note, reporter=request.user, status=NoteReport.STATUS_PENDING
    ).first()
    if existing:
        existing.reason = form.cleaned_data['reason']
        existing.details = form.cleaned_data['details']
        existing.save()
        messages.success(request, 'Your report was updated.')
    else:
        NoteReport.objects.create(
            note=note, reporter=request.user,
            reason=form.cleaned_data['reason'], details=form.cleaned_data['details'],
        )
        messages.success(request, 'Thanks — moderators will review this note.')
    return redirect('notes:note_detail', pk=pk)


@login_required(login_url='login')
def report_list(request):
    if can_moderate(request.user):
        qs = NoteReport.objects.select_related('note', 'reporter', 'reviewed_by').order_by('-created_at')
    else:
        qs = NoteReport.objects.filter(reporter=request.user).select_related('note').order_by('-created_at')
    status = request.GET.get('status', '').strip()
    if status in ('pending', 'dismissed', 'action_taken'):
        qs = qs.filter(status=status)
    paginator = Paginator(qs, 15)
    reports = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'notes/reports.html', {'reports': reports, 'status': status})


@login_required(login_url='login')
@user_passes_test(can_moderate, login_url='dashboard')
@require_POST
def report_review(request, pk):
    report = get_object_or_404(NoteReport, pk=pk)
    action = request.POST.get('action', 'dismiss')
    report.reviewed_by = request.user
    report.reviewed_at = timezone.now()
    if action == 'remove':
        report.status = NoteReport.STATUS_ACTION
        note = report.note
        note.status = Note.STATUS_REJECTED
        note.is_public = False
        note.save()
        NoteReport.objects.filter(note=note, status=NoteReport.STATUS_PENDING).exclude(pk=report.pk).update(
            status=NoteReport.STATUS_ACTION, reviewed_by=request.user, reviewed_at=timezone.now()
        )
        messages.success(request, f'Note "{note.title}" removed and reports closed.')
    else:
        report.status = NoteReport.STATUS_DISMISSED
        messages.success(request, 'Report dismissed.')
    report.save()
    return redirect('notes:report_list')


@login_required(login_url='login')
@user_passes_test(can_moderate, login_url='dashboard')
def moderation_queue(request):
    pending_notes = Note.objects.filter(status=Note.STATUS_PENDING).select_related('uploaded_by').annotate(
        pending_reports=Count('reports', filter=Q(reports__status=NoteReport.STATUS_PENDING))
    ).order_by('-created_at')[:50]
    flagged = Note.objects.filter(
        reports__status=NoteReport.STATUS_PENDING
    ).annotate(pending_reports=Count('reports', filter=Q(reports__status=NoteReport.STATUS_PENDING))).distinct().order_by('-created_at')[:50]
    pending_count = NoteReport.objects.filter(status=NoteReport.STATUS_PENDING).count()
    return render(request, 'notes/moderation.html', {
        'pending_notes': pending_notes,
        'flagged': flagged,
        'pending_count': pending_count,
    })


@login_required(login_url='login')
@user_passes_test(can_moderate, login_url='dashboard')
@require_POST
def moderate_note(request, pk):
    note = get_object_or_404(Note, pk=pk)
    action = request.POST.get('action', 'approve')
    if action == 'approve':
        note.status = Note.STATUS_APPROVED
        note.is_public = True
        messages.success(request, f'Note "{note.title}" approved.')
    elif action == 'reject':
        note.status = Note.STATUS_REJECTED
        note.is_public = False
        messages.success(request, f'Note "{note.title}" rejected/removed.')
    elif action == 'delete':
        title = note.title
        note.delete()
        messages.success(request, f'Note "{title}" permanently deleted.')
        return redirect('notes:moderation_queue')
    else:
        messages.error(request, 'Unknown action.')
        return redirect('notes:moderation_queue')
    note.save()
    return redirect('notes:moderation_queue')


# ---------------------------------------------------------------------------
# Quiz generation / taking / scores
# ---------------------------------------------------------------------------

@login_required(login_url='login')
@require_POST
def quiz_generate(request, pk):
    note = get_object_or_404(Note, pk=pk)
    if not _can_view_note(request.user, note):
        messages.error(request, 'You cannot generate a quiz from this note.')
        return redirect('notes:note_list')
    try:
        num = int(request.POST.get('num_questions', 5))
    except (TypeError, ValueError):
        num = 5
    num = max(1, min(num, 20))
    qtype = request.POST.get('question_type', 'mixed')
    if qtype not in ('mixed', 'mcq', 'true_false', 'short_answer', 'essay'):
        qtype = 'mixed'
    provider = request.POST.get('provider', 'auto').strip().lower()
    if provider not in ('auto', 'local', 'openai', 'gemini', 'openrouter'):
        provider = 'auto'

    source = get_note_source_text(note)
    result = generate_quiz(source, num_questions=num, question_type=qtype, provider=provider)
    quiz = _create_quiz_set(
        note, request.user,
        f'{qtype.replace("_", " ").title()} Quiz — {note.title[:60]}',
        num, qtype, result['provider'], result['questions'],
    )
    messages.success(request, f'Generated {num} questions ({result["provider"]}).')
    return redirect('notes:quiz_detail', quiz_id=quiz.pk)


@login_required(login_url='login')
def quiz_detail(request, quiz_id):
    quiz = get_object_or_404(
        QuizSet.objects.select_related('note', 'created_by').prefetch_related('questions'),
        pk=quiz_id,
    )
    if not _can_view_note(request.user, quiz.note):
        messages.error(request, 'This quiz is no longer available.')
        return redirect('notes:note_list')
    attempts = QuizAttempt.objects.filter(quiz=quiz, taker=request.user).order_by('-submitted_at')[:5]
    all_attempts = None
    if can_moderate(request.user):
        all_attempts = QuizAttempt.objects.filter(quiz=quiz).select_related('taker').order_by('-submitted_at')[:20]
    # Answers unlock only after the student submits (moderators always see them).
    has_submitted = QuizAttempt.objects.filter(quiz=quiz, taker=request.user).exists()
    show_answers = has_submitted or can_moderate(request.user)
    source_notes = []
    if quiz.is_exam and quiz.source_note_ids:
        source_notes = list(Note.objects.filter(pk__in=quiz.source_note_ids).select_related('uploaded_by'))
    return render(request, 'notes/quiz_detail.html', {
        'quiz': quiz, 'attempts': attempts, 'all_attempts': all_attempts,
        'source_notes': source_notes, 'show_answers': show_answers,
    })


@login_required(login_url='login')
@require_POST
def quiz_delete(request, quiz_id):
    quiz = get_object_or_404(QuizSet, pk=quiz_id)
    if quiz.created_by != request.user and not can_moderate(request.user):
        messages.error(request, 'You can only delete quizzes you generated.')
        return redirect('notes:quiz_detail', quiz_id=quiz_id)
    note_pk = quiz.note_id
    quiz.delete()
    messages.success(request, 'Quiz deleted.')
    return redirect('notes:note_detail', pk=note_pk)


@login_required(login_url='login')
def quiz_take(request, quiz_id):
    quiz = get_object_or_404(
        QuizSet.objects.select_related('note').prefetch_related('questions'), pk=quiz_id
    )
    if not _can_view_note(request.user, quiz.note):
        messages.error(request, 'This quiz is no longer available.')
        return redirect('notes:note_list')
    if request.method == 'POST':
        answers = {}
        score = 0
        total = 0
        for q in quiz.questions.all():
            key = f'q_{q.id}'
            submitted = (request.POST.get(key, '') or '').strip()
            answers[str(q.id)] = submitted
            verdict = q.check_answer(submitted)
            if verdict is not None:
                total += 1
                if verdict:
                    score += 1
        attempt = QuizAttempt(quiz=quiz, taker=request.user, score=score, total=total, answers=answers)
        attempt.recalc()
        attempt.save()
        messages.success(request, f'Quiz submitted: {score}/{total} ({attempt.percentage}%).')
        return redirect('notes:attempt_detail', attempt_id=attempt.pk)
    return render(request, 'notes/quiz_take.html', {'quiz': quiz})


@login_required(login_url='login')
def attempt_detail(request, attempt_id):
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related('quiz__note', 'taker').prefetch_related('quiz__questions'),
        pk=attempt_id,
    )
    if attempt.taker != request.user and not can_moderate(request.user):
        messages.error(request, 'You can only view your own attempts.')
        return redirect('dashboard')
    questions = list(attempt.quiz.questions.all())
    rows = []
    for q in questions:
        submitted = (attempt.answers or {}).get(str(q.id), '')
        verdict = q.check_answer(submitted)
        rows.append({'question': q, 'submitted': submitted, 'verdict': verdict})
    return render(request, 'notes/attempt_detail.html', {'attempt': attempt, 'rows': rows})


@login_required(login_url='login')
def my_progress(request):
    chat_attempts = ChatQuizAttempt.objects.filter(
        taker=request.user
    ).select_related('message__conversation').order_by('-submitted_at')
    chat_attempt_stats = chat_attempts.aggregate(
        avg=Avg('percentage'), count=Count('pk')
    )
    total_taken = chat_attempt_stats['count']
    avg = chat_attempt_stats['avg'] or 0
    best = chat_attempts.order_by('-percentage').first()
    notes_uploaded = Note.objects.filter(uploaded_by=request.user).count()
    ratings_given = NoteRating.objects.filter(user=request.user).count()
    quizzes_created = QuizSet.objects.filter(created_by=request.user).count()
    return render(request, 'notes/progress.html', {
        'chat_attempts': Paginator(chat_attempts, 15).get_page(
            request.GET.get('chat_page', 1)
        ),
        'total_taken': total_taken, 'avg_score': round(avg, 2),
        'best': best, 'notes_uploaded': notes_uploaded,
        'ratings_given': ratings_given, 'quizzes_created': quizzes_created,
    })


# ---------------------------------------------------------------------------
# Analytics (Administrator)
# ---------------------------------------------------------------------------

@login_required(login_url='login')
@user_passes_test(can_admin, login_url='dashboard')
def system_analytics(request):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    real_users = User.objects.exclude(profile__is_guest=True)
    users_total = real_users.count()
    by_role = {
        r['profile__role']: r['c']
        for r in real_users.values('profile__role').annotate(c=Count('id')).values('profile__role', 'c')
    }
    notes_total = Note.objects.count()
    notes_by_status = {
        r['status']: r['c'] for r in Note.objects.values('status').annotate(c=Count('id'))
    }
    notes_by_subject = list(
        Note.objects.values('subject').annotate(c=Count('id')).order_by('-c')[:8]
    )
    top_rated = list(
        Note.objects.filter(status=Note.STATUS_APPROVED).annotate(avg_score=Avg('ratings__score')).order_by('-avg_score')[:5]
    )
    ratings_total = NoteRating.objects.count()
    ratings_avg = NoteRating.objects.aggregate(a=Avg('score'))['a'] or 0
    quizzes_total = QuizSet.objects.count()
    attempts_total = QuizAttempt.objects.count()
    attempts_avg = QuizAttempt.objects.aggregate(a=Avg('percentage'))['a'] or 0
    reports_total = NoteReport.objects.count()
    reports_pending = NoteReport.objects.filter(status=NoteReport.STATUS_PENDING).count()
    recent_notes = Note.objects.select_related('uploaded_by').order_by('-created_at')[:8]
    recent_attempts = QuizAttempt.objects.select_related('quiz', 'taker').order_by('-submitted_at')[:8]
    recent_reports = NoteReport.objects.select_related('note', 'reporter').order_by('-created_at')[:8]
    # Charts: notes per subject + attempts per day (last 14 days).
    from django.db.models.functions import TruncDate
    from datetime import timedelta
    today = timezone.now().date()
    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    daily_counts = {
        r['d']: r['c'] for r in
        QuizAttempt.objects.filter(submitted_at__date__gte=days[0]).annotate(
            d=TruncDate('submitted_at')).values('d').annotate(c=Count('id'))
    }
    chart_attempts = {
        'labels': [d.strftime('%b %d') for d in days],
        'values': [daily_counts.get(d, 0) for d in days],
    }
    chart_subjects = {
        'labels': [r['subject'] for r in notes_by_subject],
        'values': [r['c'] for r in notes_by_subject],
    }
    return render(request, 'notes/analytics.html', {
        'users_total': users_total, 'by_role': by_role,
        'notes_total': notes_total, 'notes_by_status': notes_by_status,
        'notes_by_subject': notes_by_subject, 'top_rated': top_rated,
        'ratings_total': ratings_total, 'ratings_avg': round(ratings_avg, 2),
        'quizzes_total': quizzes_total, 'attempts_total': attempts_total,
        'attempts_avg': round(attempts_avg, 2),
        'reports_total': reports_total, 'reports_pending': reports_pending,
        'recent_notes': recent_notes, 'recent_attempts': recent_attempts,
        'recent_reports': recent_reports,
        'chart_subjects_json': chart_subjects,
        'chart_attempts_json': chart_attempts,
    })


# ---------------------------------------------------------------------------
# Exam generator automation (multi-note exams + bulk backfill)
# ---------------------------------------------------------------------------

EXAM_QTYPE_CHOICES = ('mixed', 'mcq', 'true_false', 'short_answer', 'essay')
EXAM_PROVIDERS = ('auto', 'local', 'openai', 'gemini', 'openrouter')


def _parse_exam_options(request):
    try:
        num = int(request.POST.get('num_questions', 20))
    except (TypeError, ValueError):
        num = 20
    num = max(1, min(num, 50))
    qtype = request.POST.get('question_type', 'mixed')
    if qtype not in EXAM_QTYPE_CHOICES:
        qtype = 'mixed'
    provider = (request.POST.get('provider', 'auto') or 'auto').strip().lower()
    if provider not in EXAM_PROVIDERS:
        provider = 'auto'
    try:
        max_notes = int(request.POST.get('max_notes', 4))
    except (TypeError, ValueError):
        max_notes = 4
    max_notes = max(1, min(max_notes, 8))
    order = request.POST.get('order', 'top')
    if order not in ('top', 'newest'):
        order = 'top'
    return num, qtype, provider, max_notes, order


@login_required(login_url='login')
def exam_builder(request):
    """One-page exam automation: pick filters -> auto-pick notes -> one exam."""
    subjects = Subject.objects.filter(is_active=True).order_by('name')
    school_years = Note.objects.values_list('school_year', flat=True).distinct().order_by('school_year')[:50]
    recent_exams = QuizSet.objects.filter(is_exam=True).select_related(
        'note', 'created_by').prefetch_related('questions').order_by('-created_at')[:10]

    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        school_year = request.POST.get('school_year', '').strip()
        topic = request.POST.get('topic', '').strip()
        num, qtype, provider, max_notes, order = _parse_exam_options(request)

        notes = _pick_notes_for_exam(request.user, subject, school_year, topic, max_notes, order)
        if not notes:
            messages.error(request, 'No approved notes match those filters. Upload notes or relax filters.')
            return redirect('notes:exam_builder')

        source = build_exam_source(notes)
        result = generate_quiz(source, num_questions=num, question_type=qtype, provider=provider)
        label = subject or 'Mixed Subjects'
        quiz = _create_quiz_set(
            notes[0], request.user,
            f'Exam — {label} ({num} Qs, {len(notes)} sources)',
            num, qtype, result['provider'], result['questions'],
            is_exam=True, exam_subject=label,
            source_ids=[n.pk for n in notes],
        )
        messages.success(
            request,
            f'Exam generated from {len(notes)} note(s) with {num} questions ({result["provider"]}).')
        return redirect('notes:quiz_detail', quiz_id=quiz.pk)

    return render(request, 'notes/exam_builder.html', {
        'subjects': subjects, 'school_years': school_years, 'recent_exams': recent_exams,
    })


@login_required(login_url='login')
def exam_list(request):
    chat_attempts = ChatQuizAttempt.objects.filter(
        taker=request.user
    ).select_related('message__conversation').order_by('-submitted_at')
    chat_attempts_page = Paginator(chat_attempts, 10).get_page(
        request.GET.get('chat_page', 1)
    )
    return render(request, 'notes/exam_list.html', {
        'chat_attempts': chat_attempts_page,
    })


@login_required(login_url='login')
@user_passes_test(can_moderate, login_url='dashboard')
@require_POST
def exam_bulk_generate(request):
    """Instructor/Admin automation: one quiz per note missing quizzes."""
    subject = request.POST.get('subject', '').strip()
    try:
        per_note = int(request.POST.get('per_note', 5))
    except (TypeError, ValueError):
        per_note = 5
    per_note = max(1, min(per_note, 20))
    qtype = request.POST.get('question_type', 'mcq')
    if qtype not in EXAM_QTYPE_CHOICES:
        qtype = 'mcq'
    provider = (request.POST.get('provider', 'auto') or 'auto').strip().lower()
    if provider not in EXAM_PROVIDERS:
        provider = 'auto'
    try:
        limit = int(request.POST.get('limit', 10))
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(limit, 50))
    only_missing = request.POST.get('only_missing', '1') == '1'

    qs = Note.objects.filter(status=Note.STATUS_APPROVED).order_by('-created_at')
    if subject:
        qs = qs.filter(subject__iexact=subject)
    if only_missing:
        qs = qs.filter(quiz_sets__isnull=True)
    notes = list(qs.distinct()[:limit])
    if not notes:
        messages.error(request, 'No matching notes to automate (all already have quizzes?).')
        return redirect('notes:exam_builder')

    created, failed = 0, 0
    for note in notes:
        try:
            result = generate_quiz(
                get_note_source_text(note), num_questions=per_note,
                question_type=qtype, provider=provider)
            _create_quiz_set(
                note, request.user,
                f'{qtype.replace("_", " ").title()} Quiz — {note.title[:60]}',
                per_note, qtype, result['provider'], result['questions'],
            )
            created += 1
        except Exception:
            failed += 1
    messages.success(request, f'Bulk automation done: {created} quiz(zes) created, {failed} failed.')
    return redirect('notes:exam_list')
