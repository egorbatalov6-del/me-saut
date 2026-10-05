from django.urls import path
import views

urlpatterns = [
    path('', views.index, name='home'),
    path('register/', views.register_view, name='register'),
    path('profile/', views.profile_view, name='profile'),
    path('logout/', views.logout_view, name='logout'),
    path('buy/', views.buy_game, name='buy_game'),
    path('success/', views.success_buy, name='success_buy'),
    path('admin-login/', views.admin_login_action, name='admin_login_action'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-edit/<str:game_id>/', views.admin_edit_game, name='admin_edit_game'),
    path('admin-delete/<str:game_id>/', views.admin_delete_game, name='admin_delete_game'),
    path('call-admin/', views.call_admin_view, name='call_admin_view'),
    
    # 🤖 Добавленные пути для работы ИИ-бота и живого чата с админом:
    path('ai-chat/', views.ai_chat_view, name='ai_chat'),
    path('get-chat/', views.get_chat_messages, name='get_chat_messages'),
]