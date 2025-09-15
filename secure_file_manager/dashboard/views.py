from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from django.utils import timezone

from filemanager.models import UserFile, FileActivity, FileCategory
from accounts.models import CustomUser
from .models import SystemSettings, UserActivity

User = get_user_model()


@login_required
def home_view(request):
    # User's file statistics
    user_files = UserFile.objects.filter(owner=request.user)
    stats = {
        'total_files': user_files.count(),
        'total_size': format_file_size(user_files.aggregate(Sum('file_size'))['file_size__sum'] or 0),
        'shared_files': user_files.filter(visibility__in=['public', 'restricted']).count(),
        'total_downloads': user_files.aggregate(Sum('download_count'))['download_count__sum'] or 0,
    }

    # Recent files (last 10)
    recent_files = user_files.order_by('-created_at')[:10]

    # Recent activities (last 10)
    recent_activities = FileActivity.objects.filter(
        user=request.user
    ).select_related('file').order_by('-timestamp')[:10]

    context = {
        'stats': stats,
        'recent_files': recent_files,
        'recent_activities': recent_activities,
    }

    # Admin statistics (if user is admin)
    if request.user.is_admin:
        admin_stats = {
            'total_users': User.objects.count(),
            'total_files': UserFile.objects.count(),
            'total_storage': format_file_size(UserFile.objects.aggregate(Sum('file_size'))['file_size__sum'] or 0),
            'total_downloads': UserFile.objects.aggregate(Sum('download_count'))['download_count__sum'] or 0,
        }
        context['admin_stats'] = admin_stats

    return render(request, 'dashboard/home.html', context)


@login_required
@staff_member_required
def admin_users_view(request):
    search_query = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')

    users = User.objects.all()

    # Apply filters
    if search_query:
        users = users.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(username__icontains=search_query)
        )

    if role_filter:
        users = users.filter(role=role_filter)

    if status_filter == 'active':
        users = users.filter(is_active=True, is_verified=True)
    elif status_filter == 'inactive':
        users = users.filter(Q(is_active=False) | Q(is_verified=False))

    # Add file counts to users
    users = users.annotate(
        file_count=Count('owned_files'),
        total_size=Sum('owned_files__file_size')
    ).order_by('-date_joined')

    # Pagination
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'users': page_obj,
        'search_query': search_query,
        'role_filter': role_filter,
        'status_filter': status_filter,
    }

    return render(request, 'dashboard/admin_users.html', context)


@login_required
@staff_member_required
def admin_files_view(request):
    search_query = request.GET.get('search', '')
    owner_filter = request.GET.get('owner', '')
    category_filter = request.GET.get('category', '')
    visibility_filter = request.GET.get('visibility', '')

    files = UserFile.objects.select_related('owner', 'category')

    # Apply filters
    if search_query:
        files = files.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if owner_filter:
        files = files.filter(owner__email__icontains=owner_filter)

    if category_filter:
        files = files.filter(category_id=category_filter)

    if visibility_filter:
        files = files.filter(visibility=visibility_filter)

    files = files.order_by('-created_at')

    # Pagination
    paginator = Paginator(files, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get filter options
    categories = FileCategory.objects.all()

    context = {
        'files': page_obj,
        'categories': categories,
        'search_query': search_query,
        'owner_filter': owner_filter,
        'category_filter': category_filter,
        'visibility_filter': visibility_filter,
    }

    return render(request, 'dashboard/admin_files.html', context)


@login_required
@staff_member_required
def system_stats_view(request):
    # Time ranges
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # File statistics
    total_files = UserFile.objects.count()
    files_this_week = UserFile.objects.filter(created_at__date__gte=week_ago).count()
    files_this_month = UserFile.objects.filter(created_at__date__gte=month_ago).count()

    # Storage statistics
    total_storage = UserFile.objects.aggregate(Sum('file_size'))['file_size__sum'] or 0

    # User statistics
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True, is_verified=True).count()
    new_users_this_week = User.objects.filter(date_joined__date__gte=week_ago).count()

    # Activity statistics
    total_downloads = UserFile.objects.aggregate(Sum('download_count'))['download_count__sum'] or 0
    activities_this_week = FileActivity.objects.filter(timestamp__date__gte=week_ago).count()

    # File type distribution
    file_types = {}
    for file_obj in UserFile.objects.values('file_type'):
        file_type = file_obj['file_type']
        if file_type in file_types:
            file_types[file_type] += 1
        else:
            file_types[file_type] = 1

    # Top users by file count
    top_users = User.objects.annotate(
        file_count=Count('owned_files')
    ).filter(file_count__gt=0).order_by('-file_count')[:10]

    # Recent activities
    recent_activities = FileActivity.objects.select_related(
        'user', 'file'
    ).order_by('-timestamp')[:20]

    context = {
        'total_files': total_files,
        'files_this_week': files_this_week,
        'files_this_month': files_this_month,
        'total_storage': format_file_size(total_storage),
        'total_users': total_users,
        'active_users': active_users,
        'new_users_this_week': new_users_this_week,
        'total_downloads': total_downloads,
        'activities_this_week': activities_this_week,
        'file_types': file_types,
        'top_users': top_users,
        'recent_activities': recent_activities,
    }

    return render(request, 'dashboard/system_stats.html', context)


@login_required
@staff_member_required
def toggle_user_status(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)

        # Don't allow deactivating the current admin user
        if user == request.user:
            return JsonResponse({
                'success': False,
                'message': 'You cannot deactivate your own account.'
            })

        user.is_active = not user.is_active
        user.save()

        # Log admin activity
        UserActivity.objects.create(
            user=request.user,
            action='toggle_user_status',
            description=f'{"Activated" if user.is_active else "Deactivated"} user: {user.email}',
            ip_address=get_client_ip(request)
        )

        return JsonResponse({
            'success': True,
            'is_active': user.is_active,
            'message': f'User {"activated" if user.is_active else "deactivated"} successfully.'
        })

    return JsonResponse({'success': False, 'message': 'Invalid request method.'})


@login_required
@staff_member_required
def delete_file_admin(request, file_id):
    if request.method == 'POST':
        file_obj = get_object_or_404(UserFile, id=file_id)

        # Log admin activity
        UserActivity.objects.create(
            user=request.user,
            action='delete_file_admin',
            description=f'Deleted file: {file_obj.name} (Owner: {file_obj.owner.email})',
            ip_address=get_client_ip(request)
        )

        file_name = file_obj.name
        file_obj.delete()

        return JsonResponse({
            'success': True,
            'message': f'File "{file_name}" deleted successfully.'
        })

    return JsonResponse({'success': False, 'message': 'Invalid request method.'})


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def format_file_size(size_bytes):
    if size_bytes == 0:
        return "0 B"

    size = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"
