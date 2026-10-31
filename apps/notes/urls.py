from django.urls import path

from . import views

app_name = 'notes'

urlpatterns = [
    path('', views.note_list, name='note_list'),
    path('upload/', views.note_create, name='note_create'),
    path('moderation/', views.moderation_queue, name='moderation_queue'),
    path('moderation/<int:pk>/', views.moderate_note, name='moderate_note'),
    path('progress/', views.my_progress, name='my_progress'),
    path('analytics/', views.system_analytics, name='system_analytics'),
    path('exam/builder/', views.exam_builder, name='exam_builder'),
    path('exam/bulk/', views.exam_bulk_generate, name='exam_bulk_generate'),
    path('exams/', views.exam_list, name='exam_list'),
    path('<int:pk>/', views.note_detail, name='note_detail'),
    path('<int:pk>/edit/', views.note_update, name='note_update'),
    path('<int:pk>/delete/', views.note_delete, name='note_delete'),
    path('<int:pk>/quiz/generate/', views.quiz_generate, name='quiz_generate'),
    path('quiz/<int:quiz_id>/', views.quiz_detail, name='quiz_detail'),
    path('quiz/<int:quiz_id>/take/', views.quiz_take, name='quiz_take'),
    path('quiz/<int:quiz_id>/delete/', views.quiz_delete, name='quiz_delete'),
    path('attempts/<int:attempt_id>/', views.attempt_detail, name='attempt_detail'),
]
