from django.contrib import admin

from .models import Note, NoteRating, NoteReport, Question, QuizAttempt, QuizSet, Subject


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'instructor', 'topic', 'school_year', 'uploaded_by', 'status', 'is_public', 'created_at')
    list_filter = ('subject', 'school_year', 'status', 'is_public')
    search_fields = ('title', 'subject', 'instructor', 'topic', 'description')


@admin.register(NoteRating)
class NoteRatingAdmin(admin.ModelAdmin):
    list_display = ('note', 'user', 'score', 'created_at')
    list_filter = ('score',)


@admin.register(NoteReport)
class NoteReportAdmin(admin.ModelAdmin):
    list_display = ('note', 'reporter', 'reason', 'status', 'created_at')
    list_filter = ('reason', 'status')


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0


@admin.register(QuizSet)
class QuizSetAdmin(admin.ModelAdmin):
    list_display = ('title', 'note', 'created_by', 'num_questions', 'question_type', 'provider', 'is_exam', 'created_at')
    list_filter = ('question_type', 'provider', 'is_exam')
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'question_type', 'order')
    list_filter = ('question_type',)


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'taker', 'score', 'total', 'percentage', 'submitted_at')
    list_filter = ('submitted_at',)
