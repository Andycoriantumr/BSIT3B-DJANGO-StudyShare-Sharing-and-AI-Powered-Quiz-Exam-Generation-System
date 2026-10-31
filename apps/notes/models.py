"""StudyShare models: notes organized by subject/instructor/topic/school year,
AI-generated quiz sets, and quiz attempts."""

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models


class Note(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected / Removed'),
    ]

    title = models.CharField(max_length=255)
    subject = models.CharField(max_length=120)
    instructor = models.CharField(max_length=120, db_index=True)
    topic = models.CharField(max_length=255, db_index=True)
    school_year = models.CharField(
        max_length=30,
        db_index=True,
        help_text='e.g. 2024-2025, 1st Year, 2nd Year',
    )
    description = models.TextField(blank=True)
    content = models.TextField(
        blank=True,
        help_text='Paste note text here. Used for search and AI quiz generation.',
    )
    file = models.FileField(
        upload_to='notes/%Y/%m/',
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    'pdf', 'docx', 'txt', 'md', 'png', 'jpg', 'jpeg',
                ]
            )
        ],
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='notes',
        on_delete=models.CASCADE,
    )
    is_public = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_APPROVED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # Composite prefix also covers subject-only lookups.
            models.Index(fields=['subject', 'school_year']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.title} ({self.subject})'

    @property
    def is_visible(self):
        return self.status == self.STATUS_APPROVED and self.is_public


class QuizSet(models.Model):
    QUESTION_TYPE_CHOICES = [
        ('mixed', 'Mixed'),
        ('mcq', 'Multiple Choice'),
        ('true_false', 'True / False'),
        ('short_answer', 'Short Answer'),
        ('essay', 'Essay / Discussion'),
    ]

    note = models.ForeignKey(Note, related_name='quiz_sets', on_delete=models.CASCADE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='quiz_sets', on_delete=models.CASCADE
    )
    title = models.CharField(max_length=255, default='Generated Quiz')
    num_questions = models.PositiveSmallIntegerField(default=5)
    question_type = models.CharField(
        max_length=20, choices=QUESTION_TYPE_CHOICES, default='mixed'
    )
    provider = models.CharField(max_length=20, default='local')
    is_exam = models.BooleanField(default=False)
    exam_subject = models.CharField(max_length=120, blank=True)
    source_note_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} for {self.note} ({self.num_questions} Qs)'

    @property
    def auto_gradable_count(self):
        return self.questions.filter(question_type__in=['mcq', 'true_false']).count()


class Question(models.Model):
    TYPE_CHOICES = [
        ('mcq', 'Multiple Choice'),
        ('true_false', 'True / False'),
        ('short_answer', 'Short Answer'),
        ('essay', 'Essay'),
    ]

    quiz = models.ForeignKey(QuizSet, related_name='questions', on_delete=models.CASCADE)
    question_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='mcq')
    question_text = models.TextField()
    options = models.JSONField(default=list, blank=True)
    correct_answer = models.TextField(blank=True)
    explanation = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'Q{self.order + 1}: {self.question_text[:60]}'

    def check_answer(self, submitted):
        """Auto-grade MCQ and True/False. Returns True/False/None (None = manual)."""
        if self.question_type not in ('mcq', 'true_false'):
            return None
        if submitted is None:
            return False
        return str(submitted).strip().lower() == str(self.correct_answer).strip().lower()


class QuizAttempt(models.Model):
    quiz = models.ForeignKey(QuizSet, related_name='attempts', on_delete=models.CASCADE)
    taker = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name='quiz_attempts', on_delete=models.CASCADE
    )
    score = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    percentage = models.FloatField(default=0)
    answers = models.JSONField(default=dict, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.taker} — {self.quiz} ({self.score}/{self.total})'

    def recalc(self):
        if self.total:
            self.percentage = round(self.score / self.total * 100, 2)
        else:
            self.percentage = 0
