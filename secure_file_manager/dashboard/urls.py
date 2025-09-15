from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('admin/users/', views.admin_users_view, name='admin_users'),
    path('admin/files/', views.admin_files_view, name='admin_files'),
    path('admin/stats/', views.system_stats_view, name='system_stats'),
    path('admin/user/<int:user_id>/toggle-status/', views.toggle_user_status, name='toggle_user_status'),
    path('admin/file/<int:file_id>/delete/', views.delete_file_admin, name='delete_file_admin'),

]
