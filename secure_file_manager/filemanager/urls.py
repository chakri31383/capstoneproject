from django.urls import path
from . import views

app_name = 'filemanager'

urlpatterns = [
    path('', views.file_list_view, name='file_list'),
    path('upload/', views.upload_file_view, name='upload_file'),
    path('file/<int:file_id>/', views.view_file, name='view_file'),
    path('file/<int:file_id>/edit/', views.edit_file, name='edit_file'),
    path('file/<int:file_id>/download/', views.download_file, name='download_file'),
    path('file/<int:file_id>/delete/', views.delete_file, name='delete_file'),
    path('file/<int:file_id>/toggle-favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('file/<int:file_id>/share/', views.share_file, name='share_file'),
    path('access/<int:access_id>/remove/', views.remove_access, name='remove_access'),
    path('shared/', views.shared_files, name='shared_files'),

]
