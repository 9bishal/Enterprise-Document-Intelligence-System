"""
URL configuration for django_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.contrib import admin
from django.urls import path
from django.http import HttpResponse, HttpResponseRedirect

# Import views
from django_backend import views
from django_backend.monitoring import health as health_views

# Root home landing view
def home_view(request):
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Intradoc AI Backend Service</title>
        <style>
            body {
                background-color: #FAF9F5;
                color: #141413;
                font-family: system-ui, -apple-system, sans-serif;
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
                text-align: center;
            }
            .container {
                max-width: 460px;
                padding: 40px;
                background: #FFFFFF;
                border: 1px solid rgba(20, 20, 19, 0.08);
                border-radius: 24px;
                box-shadow: 0 10px 30px rgba(20, 20, 19, 0.03);
            }
            .logo {
                font-size: 32px;
                margin-bottom: 20px;
            }
            h1 {
                font-size: 24px;
                font-weight: 700;
                margin: 0 0 10px;
                letter-spacing: -0.5px;
            }
            p {
                font-size: 14.5px;
                color: #5C5A55;
                line-height: 1.6;
                margin: 0 0 24px;
            }
            .btn {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                font-family: inherit;
                font-weight: 500;
                border-radius: 18px;
                padding: 12px 24px;
                border: 1px solid rgba(20, 20, 19, 0.08);
                background: #141413;
                color: #FAF9F5;
                text-decoration: none;
                cursor: pointer;
                transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                box-shadow: 0 2px 4px rgba(20, 20, 19, 0.02);
            }
            .btn:hover {
                transform: translateY(-2px);
                background: #E05E3F;
                border-color: #E05E3F;
                color: #FFFFFF;
                box-shadow: 0 10px 30px rgba(20, 20, 19, 0.12);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">✦</div>
            <h1>Intradoc AI Backend Service</h1>
            <p>The Django REST API backend is running. Open the workspace client to start using the application.</p>
            <a href="{frontend_url}" class="btn">Go to Workspace Client</a>
        </div>
    </body>
    </html>
    """
    return HttpResponse(html.replace("{frontend_url}", settings.FRONTEND_URL))

from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("", home_view),
    path("admin/", admin.site.urls),
    path("favicon.ico", lambda request: HttpResponseRedirect("/static/favicon.ico")),
    
    # Auth Endpoints
    path("api/auth/signup", views.auth_signup),
    path("api/auth/login", views.auth_login),
    path("api/auth/logout", views.auth_logout),
    path("api/auth/me", views.auth_me),
    path("api/auth/forgot-password", views.auth_forgot_password),
    path("api/auth/reset-password", views.auth_reset_password),
    path("api/auth/token/refresh", TokenRefreshView.as_view(), name="token_refresh"),
    
    # Document Endpoints
    path("api/documents", views.get_documents_list),
    path("api/documents/upload", views.upload_document),
    path("api/documents/upload/batch", views.upload_documents_batch),
    path("api/documents/<str:doc_id>", views.delete_document),
    path("api/documents/<str:doc_id>/file", views.preview_document),
    
    # Session Endpoints
    path("api/chat/sessions", views.chat_sessions_api),
    path("api/chat/sessions/<str:session_id>", views.delete_chat_session),
    path("api/chat/sessions/<str:session_id>/messages", views.get_messages),
    
    # Core RAG Endpoint
    path("api/chat/query", views.query_rag),
    path("api/chat/query/stream", views.query_rag_stream),
    
    # Admin Monitoring Endpoint
    path("api/admin/metrics", views.admin_metrics),

    # Admin Invite & User Management Endpoints
    path("api/admin/invite", views.admin_invite),
    path("api/admin/users", views.admin_users_list),
    path("api/admin/users/<int:user_id>", views.admin_update_user),
    path("api/admin/knowledge-graph", views.admin_knowledge_graph_data),
    path("api/admin/documents/<str:doc_id>/delete", views.admin_delete_document),
    
    # Health & Monitoring Endpoints
    path("api/health/live", health_views.health_live),
    path("api/health/ready", health_views.health_ready),
    path("api/cache/stats", health_views.cache_stats),
    path("api/departments", views.get_departments),

    # Global LLM Settings Endpoints
    path("api/llm-config", views.get_public_llm_config),
    path("api/admin/llm-config", views.get_admin_llm_config),
    path("api/admin/llm-config/update", views.update_admin_llm_config),
]
