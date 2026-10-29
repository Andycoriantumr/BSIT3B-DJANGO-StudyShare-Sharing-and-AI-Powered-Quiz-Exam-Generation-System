from django.urls import path

from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.chat_home, name='chat_home'),
    path('start/', views.start_chat, name='start'),
    path('shared/<uuid:token>/', views.shared_conversation, name='shared_conversation'),
    path('messages/<int:pk>/grade/', views.grade_message_quiz, name='grade_quiz'),
    path('quiz-attempts/<int:pk>/', views.quiz_attempt_detail, name='quiz_attempt_detail'),
    path('conversations/<int:pk>/pin/', views.toggle_pin_conversation, name='toggle_pin'),
    path('conversations/<int:pk>/share/', views.share_conversation, name='share_conversation'),
    path('conversations/<int:pk>/unshare/', views.revoke_conversation_share, name='revoke_share'),
    path('conversations/<int:pk>/delete/', views.delete_conversation, name='delete_conversation'),
    path('attachments/<int:pk>/', views.view_attachment, name='view_attachment'),
    path('attachments/<int:pk>/download/', views.download_attachment, name='download_attachment'),
    path('attachments/<int:pk>/delete/', views.delete_attachment, name='delete_attachment'),
    path('<int:pk>/', views.conversation_detail, name='detail'),
    path('<int:pk>/send/', views.send_message, name='send'),
]
