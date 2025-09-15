import random
import string
from datetime import timedelta
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

from .models import CustomUser, OTPVerification
from .forms import CustomUserCreationForm, CustomLoginForm, OTPVerificationForm, UserProfileForm


def generate_otp():
    return ''.join(random.choices(string.digits, k=6))


def send_otp_email(user, otp_code, purpose):
    subject = f'Your OTP for {purpose.title()}'
    message = f'''
    Hello {user.first_name},

    Your OTP code for {purpose} is: {otp_code}

    This code will expire in 10 minutes.

    If you didn't request this, please ignore this email.

    Best regards,
    Secure File Manager Team
    '''

    try:
        send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email])
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # Activate after OTP verification
            user.save()

            # Generate and send OTP
            otp_code = generate_otp()
            otp = OTPVerification.objects.create(
                user=user,
                otp_code=otp_code,
                purpose='signup',
                expires_at=timezone.now() + timedelta(minutes=10)
            )

            if send_otp_email(user, otp_code, 'account verification'):
                request.session['pending_user_id'] = user.id
                request.session['otp_purpose'] = 'signup'
                messages.success(request, 'Registration successful! Please check your email for OTP verification.')
                return redirect('accounts:verify_otp')
            else:
                user.delete()  # Clean up if email fails
                messages.error(request, 'Failed to send verification email. Please try again.')
    else:
        form = CustomUserCreationForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = CustomLoginForm(request.POST)
        if form.is_valid():
            user = form.user
            if not user.is_verified:
                messages.error(request, 'Please verify your email first.')
                return redirect('accounts:login')

            # Generate and send OTP for login
            otp_code = generate_otp()
            # Delete any existing unused OTPs
            OTPVerification.objects.filter(user=user, purpose='login', is_used=False).delete()

            otp = OTPVerification.objects.create(
                user=user,
                otp_code=otp_code,
                purpose='login',
                expires_at=timezone.now() + timedelta(minutes=10)
            )

            if send_otp_email(user, otp_code, 'login verification'):
                request.session['pending_user_id'] = user.id
                request.session['otp_purpose'] = 'login'
                messages.success(request, 'OTP sent to your email. Please verify to login.')
                return redirect('accounts:verify_otp')
            else:
                messages.error(request, 'Failed to send OTP. Please try again.')
    else:
        form = CustomLoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def verify_otp_view(request):
    user_id = request.session.get('pending_user_id')
    purpose = request.session.get('otp_purpose')

    if not user_id or not purpose:
        messages.error(request, 'Invalid verification session.')
        return redirect('accounts:login')

    try:
        user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('accounts:login')

    if request.method == 'POST':
        form = OTPVerificationForm(user=user, purpose=purpose, data=request.POST)
        if form.is_valid():
            otp_code = form.cleaned_data['otp_code']

            # Verify and use OTP
            otp = OTPVerification.objects.get(
                user=user,
                otp_code=otp_code,
                purpose=purpose,
                is_used=False
            )
            otp.is_used = True
            otp.save()

            if purpose == 'signup':
                user.is_active = True
                user.is_verified = True
                user.save()
                messages.success(request, 'Account verified successfully! You can now login.')
                # Clean up session
                del request.session['pending_user_id']
                del request.session['otp_purpose']
                return redirect('accounts:login')

            elif purpose == 'login':
                login(request, user)
                # Clean up session
                del request.session['pending_user_id']
                del request.session['otp_purpose']
                messages.success(request, f'Welcome back, {user.first_name}!')
                return redirect('dashboard:home')
    else:
        form = OTPVerificationForm(user=user, purpose=purpose)

    return render(request, 'accounts/verify_otp.html', {
        'form': form,
        'user': user,
        'purpose': purpose
    })


@require_http_methods(["POST"])
def resend_otp_view(request):
    user_id = request.session.get('pending_user_id')
    purpose = request.session.get('otp_purpose')

    if not user_id or not purpose:
        return JsonResponse({'success': False, 'message': 'Invalid session'})

    try:
        user = CustomUser.objects.get(id=user_id)

        # Delete old OTPs
        OTPVerification.objects.filter(user=user, purpose=purpose, is_used=False).delete()

        # Generate new OTP
        otp_code = generate_otp()
        otp = OTPVerification.objects.create(
            user=user,
            otp_code=otp_code,
            purpose=purpose,
            expires_at=timezone.now() + timedelta(minutes=10)
        )

        if send_otp_email(user, otp_code, purpose):
            return JsonResponse({'success': True, 'message': 'OTP resent successfully'})
        else:
            return JsonResponse({'success': False, 'message': 'Failed to send OTP'})

    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found'})


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'Logged out successfully!')
    return redirect('accounts:login')
