from django.urls import path

from . import views

app_name = "integrations"

urlpatterns = [
    path("line/webhook/<slug:tenant_slug>/", views.line_webhook, name="line_webhook"),
    # Unified inbox
    path("inbox/", views.inbox, name="inbox"),
    path("inbox/<int:pk>/", views.inbox, name="conversation"),
    path("inbox/<int:pk>/reply/", views.conversation_reply, name="conversation_reply"),
    path("inbox/<int:pk>/assign/", views.conversation_assign, name="conversation_assign"),
    path("inbox/<int:pk>/status/", views.conversation_status, name="conversation_status"),
    path("inbox/<int:pk>/ai-reply/", views.conversation_ai_reply, name="conversation_ai_reply"),
    path(
        "inbox/<int:pk>/ai-summary/",
        views.conversation_ai_summary,
        name="conversation_ai_summary",
    ),
    path(
        "inbox/<int:pk>/make-quote/", views.conversation_make_quote, name="conversation_make_quote"
    ),
]
