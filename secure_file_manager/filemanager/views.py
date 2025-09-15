import os
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404, FileResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from itertools import chain

from .models import UserFile, FileCategory, FileAccess, FileActivity
from .forms import FileUploadForm, FileEditForm, FileAccessForm, FileSearchForm
from dashboard.models import SystemSettings

User = get_user_model()


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@login_required
def file_list_view(request):
    # Get search parameters
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    file_type = request.GET.get('type', '')
    favorites_only = request.GET.get('favorites', '')

    # Base queryset
    files = UserFile.objects.filter(owner=request.user)

    # Apply filters
    if query:
        files = files.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )

    if category_id:
        files = files.filter(category_id=category_id)

    if file_type:
        if file_type == 'image':
            files = files.filter(file_type__in=['.jpg', '.jpeg', '.png', '.gif'])
        elif file_type == 'document':
            files = files.filter(file_type__in=['.pdf', '.doc', '.docx', '.txt'])
        elif file_type == 'video':
            files = files.filter(file_type__in=['.mp4', '.avi', '.mov'])
        elif file_type == 'archive':
            files = files.filter(file_type__in=['.zip', '.rar'])

    if favorites_only:
        files = files.filter(is_favorite=True)

    # Order by favorites first, then by creation date
    files = files.order_by('-is_favorite', '-created_at')

    # Pagination
    paginator = Paginator(files, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get statistics
    user_files = UserFile.objects.filter(owner=request.user)
    stats = {
        'total_files': user_files.count(),
        'favorite_files': user_files.filter(is_favorite=True).count(),
        'shared_files': user_files.filter(visibility__in=['public', 'restricted']).count(),
        'total_size': user_files.aggregate(total=Sum('file_size'))['total'] or 0,
    }

    # Format total size
    size = stats['total_size']
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            stats['total_size'] = f"{size:.1f} {unit}"
            break
        size /= 1024.0
    else:
        stats['total_size'] = f"{size:.1f} TB"

    context = {
        'files': page_obj,
        'categories': FileCategory.objects.all(),
        'stats': stats,
        'search_form': FileSearchForm(request.GET),
    }

    return render(request, 'filemanager/file_list.html', context)


@login_required
def upload_file_view(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file_obj = form.save(commit=False)
            file_obj.owner = request.user

            # Set name from filename if not provided
            if not file_obj.name:
                filename = file_obj.file.name
                file_obj.name = os.path.splitext(filename)[0]

            file_obj.save()

            # Log activity
            FileActivity.objects.create(
                file=file_obj,
                user=request.user,
                action='upload',
                ip_address=get_client_ip(request)
            )

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'File uploaded successfully!',
                    'file_id': file_obj.id
                })

            messages.success(request, 'File uploaded successfully!')
            return redirect('filemanager:file_list')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Upload failed. Please check your file and try again.'
                })
    else:
        form = FileUploadForm()

    return render(request, 'filemanager/upload_file.html', {'form': form})


@login_required
def view_file(request, file_id):
    file_obj = get_object_or_404(UserFile, id=file_id)

    # Check permissions
    if not can_access_file(request.user, file_obj, 'view'):
        messages.error(request, 'You do not have permission to view this file.')
        return redirect('filemanager:file_list')

    # Log activity
    FileActivity.objects.create(
        file=file_obj,
        user=request.user,
        action='view',
        ip_address=get_client_ip(request)
    )

    return render(request, 'filemanager/file_detail.html', {'file': file_obj})


@login_required
def download_file(request, file_id):
    file_obj = get_object_or_404(UserFile, id=file_id)

    # Check permissions
    if not can_access_file(request.user, file_obj, 'download'):
        messages.error(request, 'You do not have permission to download this file.')
        return redirect('filemanager:file_list')

    # Increment download count
    file_obj.download_count += 1
    file_obj.save()

    # Log activity
    FileActivity.objects.create(
        file=file_obj,
        user=request.user,
        action='download',
        ip_address=get_client_ip(request)
    )

    # Serve file
    try:
        response = FileResponse(
            file_obj.file.open('rb'),
            as_attachment=True,
            filename=file_obj.name + file_obj.file_type
        )
        return response
    except Exception as e:
        messages.error(request, 'Error downloading file.')
        return redirect('filemanager:view_file', file_id=file_id)


@login_required
def edit_file(request, file_id):
    file_obj = get_object_or_404(UserFile, id=file_id, owner=request.user)

    if request.method == 'POST':
        form = FileEditForm(request.POST, instance=file_obj)
        if form.is_valid():
            form.save()

            # Log activity
            FileActivity.objects.create(
                file=file_obj,
                user=request.user,
                action='update',
                ip_address=get_client_ip(request)
            )

            messages.success(request, 'File updated successfully!')
            return redirect('filemanager:view_file', file_id=file_id)
    else:
        form = FileEditForm(instance=file_obj)

    return render(request, 'filemanager/edit_file.html', {
        'form': form,
        'file': file_obj
    })


@login_required
@require_http_methods(["POST"])
def delete_file(request, file_id):
    file_obj = get_object_or_404(UserFile, id=file_id, owner=request.user)

    try:
        # Delete physical file
        if file_obj.file and os.path.exists(file_obj.file.path):
            os.remove(file_obj.file.path)

        # Log activity before deletion
        FileActivity.objects.create(
            file=file_obj,
            user=request.user,
            action='delete',
            ip_address=get_client_ip(request)
        )

        file_name = file_obj.name
        file_obj.delete()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'"{file_name}" has been deleted successfully.'
            })

        messages.success(request, f'"{file_name}" has been deleted successfully.')
        return redirect('filemanager:file_list')

    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'Error deleting file.'
            })

        messages.error(request, 'Error deleting file.')
        return redirect('filemanager:file_list')


@login_required
@require_http_methods(["POST"])
def toggle_favorite(request, file_id):
    file_obj = get_object_or_404(UserFile, id=file_id, owner=request.user)

    file_obj.is_favorite = not file_obj.is_favorite
    file_obj.save()

    return JsonResponse({
        'success': True,
        'is_favorite': file_obj.is_favorite,
        'message': 'Favorite status updated.'
    })


@login_required
def share_file(request, file_id):
    file_obj = get_object_or_404(UserFile, id=file_id, owner=request.user)

    if file_obj.visibility != 'restricted':
        return JsonResponse({
            'success': False,
            'message': 'Only restricted files can be shared with specific users.'
        })

    if request.method == 'POST':
        user_email = request.POST.get('user_email')
        permission = request.POST.get('permission', 'view')
        expires_at = request.POST.get('expires_at')

        try:
            target_user = User.objects.get(email=user_email, is_verified=True)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'User not found or not verified.'
            })

        # Check if access already exists
        access, created = FileAccess.objects.get_or_create(
            file=file_obj,
            user=target_user,
            defaults={
                'permission': permission,
                'granted_by': request.user,
                'expires_at': expires_at if expires_at else None
            }
        )

        if not created:
            access.permission = permission
            access.expires_at = expires_at if expires_at else None
            access.save()

        # Log activity
        FileActivity.objects.create(
            file=file_obj,
            user=request.user,
            action='share',
            ip_address=get_client_ip(request)
        )

        return JsonResponse({
            'success': True,
            'message': f'File shared with {target_user.get_full_name()}.'
        })

    return JsonResponse({'success': False, 'message': 'Invalid request method.'})


@login_required
@require_http_methods(["POST"])
def remove_access(request, access_id):
    access = get_object_or_404(FileAccess, id=access_id, file__owner=request.user)

    user_name = access.user.get_full_name()
    access.delete()

    return JsonResponse({
        'success': True,
        'message': f'Access removed for {user_name}.'
    })


@login_required
def shared_files(request):
    """Files specifically shared with the current user"""
    # Only files explicitly shared with the current user
    accessible_files = UserFile.objects.filter(
        access_permissions__user=request.user
    ).filter(
        Q(access_permissions__expires_at__isnull=True) |
        Q(access_permissions__expires_at__gt=timezone.now())
    ).distinct().order_by('-created_at')

    # Search functionality
    query = request.GET.get('q', '')
    if query:
        accessible_files = accessible_files.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )

    # Pagination
    paginator = Paginator(accessible_files, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'filemanager/shared_files.html', {
        'files': page_obj,
        'query': query
    })


@login_required
def public_files(request):
    """Browse all public files from other users"""
    # Check if public file browsing is enabled
    public_browsing_enabled = SystemSettings.get_setting('enable_public_file_browsing', 'true').lower() == 'true'

    if not public_browsing_enabled:
        messages.warning(request, 'Public file browsing is currently disabled.')
        return redirect('filemanager:file_list')

    # Get all public files except user's own
    public_files = UserFile.objects.filter(
        visibility='public'
    ).exclude(owner=request.user).select_related('owner', 'category').order_by('-created_at')

    # Search functionality
    query = request.GET.get('q', '')
    category_id = request.GET.get('category', '')
    file_type = request.GET.get('type', '')

    if query:
        public_files = public_files.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        )

    if category_id:
        public_files = public_files.filter(category_id=category_id)

    if file_type:
        if file_type == 'image':
            public_files = public_files.filter(file_type__in=['.jpg', '.jpeg', '.png', '.gif'])
        elif file_type == 'document':
            public_files = public_files.filter(file_type__in=['.pdf', '.doc', '.docx', '.txt'])
        elif file_type == 'video':
            public_files = public_files.filter(file_type__in=['.mp4', '.avi', '.mov'])
        elif file_type == 'archive':
            public_files = public_files.filter(file_type__in=['.zip', '.rar'])

    # Pagination
    paginator = Paginator(public_files, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistics
    stats = {
        'total_public_files': UserFile.objects.filter(visibility='public').exclude(owner=request.user).count(),
        'categories': FileCategory.objects.all(),
    }

    return render(request, 'filemanager/public_files.html', {
        'files': page_obj,
        'query': query,
        'category_id': category_id,
        'file_type': file_type,
        'stats': stats,
        'categories': FileCategory.objects.all(),
    })


def can_access_file(user, file_obj, permission_type='view'):
    """
    Check if user can access file based on permission type
    permission_type: 'view', 'download', 'edit'
    """
    # Owner has all permissions
    if file_obj.owner == user:
        return True

    # Public files - anyone can view and download
    if file_obj.visibility == 'public':
        return permission_type in ['view', 'download']

    # Private files - only owner
    if file_obj.visibility == 'private':
        return False

    # Restricted files - check specific permissions
    if file_obj.visibility == 'restricted':
        try:
            access = FileAccess.objects.get(
                file=file_obj,
                user=user
            )

            # Check if access has expired
            if access.expires_at and access.expires_at < timezone.now():
                return False

            # Check permission level
            if permission_type == 'view':
                return True
            elif permission_type == 'download':
                return access.permission in ['download', 'edit']
            elif permission_type == 'edit':
                return access.permission == 'edit'

        except FileAccess.DoesNotExist:
            return False

    return False
