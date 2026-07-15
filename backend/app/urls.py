# pyrefly: ignore [missing-import]
from django.contrib import admin
# pyrefly: ignore [missing-import]
from django.urls import path
from app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.root),
    path('api/health', views.health_check),
    path('api/kb', views.list_or_create_kb),
    path('api/kb/<str:kb_id>', views.get_or_delete_kb),
    path('api/kb/<str:kb_id>/documents', views.list_or_create_doc),
    path('api/kb/<str:kb_id>/documents/<str:doc_id>', views.delete_doc),
    path('api/kb/<str:kb_id>/chat', views.chat_view),
    path('api/kb/<str:kb_id>/conversations', views.list_conversations),
    path('api/conversations/<str:conv_id>/messages', views.get_messages),
    path('api/transcribe', views.transcribe_audio),
    path('api/tts', views.synthesize_speech),
]
