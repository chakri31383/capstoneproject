import os
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator

User = get_user_model()


def user_directory_path(instance, filename):
    return f'uploads/user_{instance.owner.id}/{filename}'


class FileCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='fa-folder')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "File Categories"


class UserFile(models.Model):
    VISIBILITY_CHOICES = [
        ('private', 'Private'),
        ('public', 'Public'),
        ('restricted', 'Restricted'),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to=user_directory_path,
                            validators=[FileExtensionValidator(
                                allowed_extensions=['pdf', 'doc', 'docx', 'txt', 'jpg',
                                                    'jpeg', 'png', 'gif', 'mp4', 'avi', 'mov',
                                                    'zip', 'rar', 'xlsx', 'pptx'])])
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_files')
    category = models.ForeignKey(FileCategory, on_delete=models.SET_NULL,
                                 null=True, blank=True)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES,
                                  default='private')
    file_size = models.BigIntegerField()
    file_type = models.CharField(max_length=100)
    is_favorite = models.BooleanField(default=False)
    download_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = self.file.size
            self.file_type = os.path.splitext(self.file.name)[1].lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def formatted_size(self):
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    class Meta:
        ordering = ['-created_at']


class FileAccess(models.Model):
    PERMISSION_CHOICES = [
        ('view', 'View Only'),
        ('download', 'View & Download'),
        ('edit', 'View, Download & Edit'),
    ]

    file = models.ForeignKey(UserFile, on_delete=models.CASCADE, related_name='access_permissions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='file_permissions')
    permission = models.CharField(max_length=10, choices=PERMISSION_CHOICES, default='view')
    granted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='granted_permissions')
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.email} - {self.file.name} ({self.permission})"

    class Meta:
        unique_together = ['file', 'user']


class FileActivity(models.Model):
    ACTION_CHOICES = [
        ('upload', 'Uploaded'),
        ('view', 'Viewed'),
        ('download', 'Downloaded'),
        ('update', 'Updated'),
        ('delete', 'Deleted'),
        ('share', 'Shared'),
    ]

    file = models.ForeignKey(UserFile, on_delete=models.CASCADE, related_name='activities')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.email} {self.action} {self.file.name}"

    class Meta:
        ordering = ['-timestamp']
