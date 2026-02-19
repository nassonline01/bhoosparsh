from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.urls import reverse
import uuid
from django.core.paginator import Paginator
from django.db.models import Q, Count
from .models import Property, PropertyType, PropertyInquiry

from .models import CustomUser, UserProfile, Property, PropertyCategory, PropertyInquiry, PropertyView, PropertyFavorite, PropertyType, PropertyImage
from .forms import UserRegistrationForm, UserLoginForm, UserProfileForm, EmailVerificationForm
from .tokens import account_activation_token

# ==============================================
#  Authentication Views
# ==============================================

def register_view(request):
    """Handle user registration"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.username = form.cleaned_data['email']  # Set username to email
                    
                    # Save user first
                    user.save()
                    
                    # Create user profile with agency name if provided
                    profile, created = UserProfile.objects.get_or_create(
                        user=user,
                        defaults={}
                    )
                    
                    # Update profile based on user type
                    user_type = form.cleaned_data.get('user_type')
                    if user_type in ['seller', 'agent']:
                        agency_name = form.cleaned_data.get('agency_name', '')
                        if agency_name:
                            profile.agency_name = agency_name
                            profile.save()
                    
                    # Create buyer profile for buyer users
                    if user.user_type == 'buyer':
                        from .models import BuyerProfile
                        BuyerProfile.objects.get_or_create(user=user)
                    
                    # Log the user in if email verification is not required
                    if not settings.EMAIL_VERIFICATION_REQUIRED:
                        user.is_verified = True
                        user.save()
                        login(request, user)
                        messages.success(request, 'Registration successful! Welcome to our platform.')
                        return redirect('dashboard')
                    
                    # Send verification email
                    if settings.EMAIL_VERIFICATION_REQUIRED:
                        if send_verification_email(request, user):
                            messages.success(
                                request,
                                'Registration successful! Please check your email to verify your account.'
                            )
                            return redirect('verification_sent')
                        else:
                            messages.error(
                                request,
                                'Registration successful but we could not send verification email. '
                                'Please contact support or try logging in.'
                            )
                            return redirect('login')
                            
            except Exception as e:
                messages.error(request, f'An error occurred during registration: {str(e)}')
        else:
            # Show form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = UserRegistrationForm()

    context = {
        'form': form,
        'title': 'Register',
    }
    return render(request, 'auth/register.html', context)


def login_view(request):
    """Handle user login with role-based redirection"""
    if request.user.is_authenticated:
        # Redirect already logged-in users to appropriate dashboard
        return redirect_to_dashboard(request.user)
    
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            remember_me = form.cleaned_data.get('remember_me')
            
            # Try to authenticate with email
            user = authenticate(request, email=email, password=password)
            
            if user is not None:
                # Check if account is active
                if not user.is_active:
                    messages.error(request, 'Your account is inactive. Please contact support.')
                    return redirect('login')
                
                # Check if email verification is required
                if settings.EMAIL_VERIFICATION_REQUIRED and not user.is_verified:
                    messages.warning(
                        request, 
                        'Please verify your email address before logging in. '
                        'Check your email for the verification link.'
                    )
                    return redirect('resend_verification')
                
                # Log the user in
                login(request, user)
                
                # Handle "remember me" functionality
                if not remember_me:
                    request.session.set_expiry(0)  # Session expires when browser closes
                else:
                    # Remember for 30 days
                    request.session.set_expiry(60 * 60 * 24 * 30)
                
                messages.success(request, f'Welcome back, {user.first_name}!')
                
                # Redirect based on user type
                return redirect_to_dashboard(user, next_url=request.GET.get('next'))
                
            else:
                messages.error(request, 'Invalid email or password.')
        else:
            messages.error(request, 'Invalid email or password.')
    else:
        form = UserLoginForm()
    
    context = {
        'form': form,
        'title': 'Login',
        'show_forgot_password': True,
        'show_register': True,
    }
    return render(request, 'auth/login.html', context)


def redirect_to_dashboard(user, next_url=None):
    """Redirect user to appropriate dashboard based on user type"""
    
    # If there's a next URL and it's safe, use it
    if next_url and is_safe_url(next_url, allowed_hosts=None):
        return redirect(next_url)
    
    # Check if user is superuser - SUPERUSER GETS HIGHEST PRIORITY
    if user.is_superuser:
        return redirect('admin_dashboard')
    
    # Define redirect URLs for each user type
    user_type_redirects = {
        'buyer': 'buyer_dashboard',
        'seller': 'seller_dashboard',
        'agent': 'seller_dashboard',
        'builder': 'seller_dashboard',
        'admin': 'admin_dashboard',
        'dealer': 'seller_dashboard',
    }
    
    # Get user type, default to buyer if not set
    user_type = user.user_type.lower() if hasattr(user, 'user_type') else 'buyer'
    
    # Get redirect URL name
    redirect_url_name = user_type_redirects.get(user_type, 'buyer_dashboard')
    
    # Check if user needs to complete profile
    try:
        if user.is_superuser:
            # Superusers go directly to admin dashboard
            pass
            
        elif user_type in ['seller', 'agent', 'builder', 'dealer']:
            # For sellers/agents/builders, check if profile is complete
            if not hasattr(user, 'profile') or not user.profile.is_complete:
                messages.info(
                    request,
                    'Please complete your profile to access all seller features.'
                )
                return redirect('seller_profile')
        
        elif user_type == 'buyer':
            # For buyers, ensure buyer profile exists
            if not hasattr(user, 'buyer_profile'):
                from .models import BuyerProfile
                BuyerProfile.objects.create(user=user)
            
            # Check if buyer has set preferences
            buyer_profile = user.buyer_profile
            if not buyer_profile.min_budget or not buyer_profile.max_budget:
                messages.info(
                    request,
                    'Please set your property preferences for better recommendations.'
                )
                return redirect('buyer_profile')
    
    except Exception as e:
        print(f"Error checking user profile: {e}")
        # Continue with normal redirect if there's an error
    
    # Perform the redirect
    try:
        return redirect(redirect_url_name)
    except:
        # Fallback to buyer dashboard
        return redirect('buyer_dashboard')


def is_safe_url(url, allowed_hosts=None):
    """Check if the URL is safe for redirection"""
    from django.utils.http import url_has_allowed_host_and_scheme
    return url_has_allowed_host_and_scheme(url, allowed_hosts=allowed_hosts)


def logout_view(request):
    """Handle user logout"""
    from django.contrib.auth import logout
    
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, 'You have been logged out successfully.')
    
    return redirect('login')



# ==============================================
#  Email Verification Views
# ==============================================

def send_verification_email(request, user):
    """Send email verification link with proper HTML formatting"""
    print("\n" + "="*50)
    print("DEBUG: Sending verification email")
    print(f"DEBUG: User: {user.email}")
    print(f"DEBUG: User ID: {user.id}")
    
    # Get SITE_URL from settings
    site_url = settings.SITE_URL
    print(f"DEBUG: SITE_URL from settings: {site_url}")
    
    # Make sure SITE_URL doesn't end with /
    if site_url.endswith('/'):
        site_url = site_url.rstrip('/')
    
    # Generate token and uid
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = account_activation_token.make_token(user)
    
    # Build the verification URL - use the correct URL pattern
    verification_url = f"{site_url}/verify-email/{uid}/{token}/"
    print(f"DEBUG: Generated verification URL: {verification_url}")
    
    # Decode the uid to verify it's correct
    try:
        decoded_uid = force_str(urlsafe_base64_decode(uid))
        print(f"DEBUG: Decoded UID: {decoded_uid} (should match user ID: {user.id})")
    except Exception as e:
        print(f"DEBUG: Could not decode UID: {e}")
    
    print("="*50 + "\n")
    
    # Prepare email context
    mail_subject = f'Verify Your Email - {settings.SITE_NAME}'
    
    context = {
        'user': user,
        'site_name': settings.SITE_NAME,
        'site_url': site_url,
        'verification_url': verification_url,
        'current_year': timezone.now().year,
        'uid': uid,
        'token': token,
        'protocol': 'https' if request.is_secure() else 'http',
        'domain': request.get_host(),
    }
    
    # Render HTML email template
    message = render_to_string('auth/email/verification_email.html', context)
    
    # Create plain text alternative for email clients that don't support HTML
    plain_message = f"""
    Verify Your Email - {settings.SITE_NAME}
    
    Hello {user.first_name or user.username},
    
    Thank you for registering with {settings.SITE_NAME}! Please verify your email address by clicking the link below:
    
    {verification_url}
    
    This verification link will expire in 24 hours.
    
    If you didn't create an account, please ignore this email.
    
    Best regards,
    The {settings.SITE_NAME} Team
    
    {site_url}
    """
    
    # Create EmailMessage object
    email = EmailMessage(
        subject=mail_subject,
        body=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    
    # Set content type to HTML
    email.content_subtype = "html"
    
    # Add alternative plain text version
    email.alternatives = [(plain_message, 'text/plain')]
    
    try:
        # Send email
        email.send(fail_silently=False)
        
        # Update user's verification sent timestamp
        user.verification_sent_at = timezone.now()
        user.save(update_fields=['verification_sent_at'])
        
        print(f"DEBUG: Email sent successfully to {user.email}")
        return True
        
    except Exception as e:
        print(f"DEBUG: Error sending email: {str(e)}")
        print(f"DEBUG: Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

def verify_email_view(request, uidb64, token):
    """Handle email verification with debugging"""
    print("\n" + "="*50)
    print("DEBUG: Email verification attempt")
    print(f"DEBUG: Received uidb64: {uidb64}")
    print(f"DEBUG: Received token: {token}")
    
    try:
        # Decode the user ID
        uid = force_str(urlsafe_base64_decode(uidb64))
        print(f"DEBUG: Decoded UID: {uid}")
        
        # Get the user
        user = CustomUser.objects.get(pk=uid)
        print(f"DEBUG: Found user: {user.email} (ID: {user.id})")
        print(f"DEBUG: User is_verified before: {user.is_verified}")
        print(f"DEBUG: User type: {user.user_type}")
        
    except (TypeError, ValueError, OverflowError):
        print("DEBUG: Error decoding UID (TypeError/ValueError/OverflowError)")
        user = None
    except CustomUser.DoesNotExist:
        print("DEBUG: User does not exist with that ID")
        user = None
    
    if user is not None:
        # Check the token
        token_valid = account_activation_token.check_token(user, token)
        print(f"DEBUG: Token valid? {token_valid}")
        
        if token_valid:
            user.is_verified = True
            user.verification_token = None
            user.save()
            print(f"DEBUG: User verified! is_verified after: {user.is_verified}")
            
            # Auto-login user if they're not already logged in
            if not request.user.is_authenticated:
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)
                print(f"DEBUG: Auto-logged in user: {user.email}")
            
            messages.success(request, f'Email verified successfully! Welcome to {settings.SITE_NAME}.')
            print("DEBUG: Verification successful!")
            
            # ============================================
            # REDIRECT BASED ON USER TYPE
            # ============================================
            
            # Define redirect URLs for each user type
            user_type_redirects = {
                'buyer': 'buyer_dashboard',
                'seller': 'seller_dashboard',
                'agent': 'seller_dashboard',  # Agents use seller dashboard
                'builder': 'seller_dashboard',  # Builders use seller dashboard
                'admin': 'admin_dashboard',  # Admin users
                'dealer': 'seller_dashboard',  # Dealers use seller dashboard
            }
            
            # Get the redirect URL based on user type
            default_redirect = 'dashboard'  # Fallback
            redirect_url_name = user_type_redirects.get(user.user_type, default_redirect)
            
            print(f"DEBUG: User type: {user.user_type}, Redirecting to: {redirect_url_name}")
            
            # Check if the user needs to complete their profile
            try:
                if user.user_type in ['seller', 'agent', 'builder', 'dealer']:
                    # For sellers/agents/builders, check if profile is complete
                    if not hasattr(user, 'profile') or not user.profile.is_complete:
                        print(f"DEBUG: Seller/Agent profile incomplete, redirecting to profile setup")
                        messages.info(
                            request,
                            'Please complete your profile to access all features.'
                        )
                        return redirect('seller_profile')
                
                elif user.user_type == 'buyer':
                    # For buyers, check if buyer profile exists and has basic preferences
                    if not hasattr(user, 'buyer_profile'):
                        from .models import BuyerProfile
                        BuyerProfile.objects.create(user=user)
                        print(f"DEBUG: Created buyer profile for user")
                    
                    # Check if buyer has set preferences
                    buyer_profile = user.buyer_profile
                    if not buyer_profile.min_budget or not buyer_profile.max_budget:
                        print(f"DEBUG: Buyer preferences not set, redirecting to buyer profile")
                        messages.info(
                            request,
                            'Please set your property preferences for better recommendations.'
                        )
                        return redirect('buyer_profile')
            
            except Exception as e:
                print(f"DEBUG: Error checking user profile: {e}")
                # Continue with normal redirect if there's an error
            
            # Perform the redirect
            try:
                return redirect(redirect_url_name)
            except:
                # Fallback to generic dashboard if named URL doesn't exist
                print(f"DEBUG: Redirect URL {redirect_url_name} not found, using fallback")
                return redirect('dashboard')
            
        else:
            print("DEBUG: Token is invalid or expired")
            messages.error(request, 'Verification link is invalid or has expired.')
    else:
        print("DEBUG: User is None")
        messages.error(request, 'Verification link is invalid.')
    
    print("="*50 + "\n")
    return redirect('resend_verification')


def verification_sent_view(request):
    """Show verification sent confirmation"""
    return render(request, 'auth/email/verification_sent.html', {'title': 'Verification Sent'})


def resend_verification_view(request):
    """Resend verification email"""
    if request.method == 'POST':
        form = EmailVerificationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            try:
                user = CustomUser.objects.get(email=email)
                
                # Check if already verified
                if user.is_verified:
                    messages.info(request, 'This email is already verified.')
                    return redirect('login')
                
                # Check if email was sent recently (prevent spam)
                if user.verification_sent_at:
                    time_diff = timezone.now() - user.verification_sent_at
                    if time_diff.total_seconds() < 300:  # 5 minutes
                        messages.warning(
                            request, 
                            'Verification email was recently sent. Please check your inbox.'
                        )
                        return redirect('resend_verification')
                
                # Resend verification email
                send_verification_email(request, user)
                messages.success(request, 'Verification email has been resent. Please check your inbox.')
                return redirect('verification_sent')
                
            except CustomUser.DoesNotExist:
                messages.error(request, 'No account found with this email address.')
    else:
        form = EmailVerificationForm()
    
    context = {
        'form': form,
        'title': 'Resend Verification Email',
    }
    return render(request, 'auth/email/resend_verification.html', context)

# ==============================================
#  User Profile Views
# ==============================================

# @login_required
# def profile_view(request):
#     """Display user profile"""
#     user = request.user
#     profile = user.profile
    
#     context = {
#         'user': user,
#         'profile': profile,
#         'title': 'My Profile',
#     }
#     return render(request, 'dashboard/profile/profile.html', context)


# @login_required
# def edit_profile_view(request):
#     """Edit user profile"""
#     user = request.user
#     profile = user.profile

#     if request.method == 'POST':
#         form = UserProfileForm(request.POST, request.FILES, instance=profile)
#         if form.is_valid():
#             form.save()

#             # Update user phone if changed
#             if 'phone' in request.POST:
#                 user.phone = request.POST.get('phone')
#                 user.save()

#             messages.success(request, 'Profile updated successfully!')
#             return redirect('profile')
#         else:
#             messages.error(request, 'Please correct the errors below.')
#     else:
#         form = UserProfileForm(instance=profile)

#     context = {
#         'form': form,
#         'user': user,
#         'title': 'Edit Profile',
#     }
#     return render(request, 'dashboard/profile/edit_profile.html', context)


@login_required
def change_password_view(request):
    """Change user password"""
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        # Validate current password
        if not request.user.check_password(current_password):
            return JsonResponse({'success': False, 'error': 'Current password is incorrect.'})

        # Validate new password
        if len(new_password) < 8:
            return JsonResponse({'success': False, 'error': 'New password must be at least 8 characters long.'})

        # Check if passwords match
        if new_password != confirm_password:
            return JsonResponse({'success': False, 'error': 'New passwords do not match.'})

        # Change password
        request.user.set_password(new_password)
        request.user.save()

        # Update session to prevent logout
        update_session_auth_hash(request, request.user)

        return JsonResponse({'success': True, 'message': 'Password changed successfully!'})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


# # ==============================================
# #  Seller/Agent Settings Views
# # ==============================================

# # views.py
# from django.shortcuts import render, redirect, get_object_or_404
# from django.contrib.auth.decorators import login_required
# from django.contrib import messages
# from django.views.decorators.http import require_POST
# from django.http import JsonResponse
# import json
# from .forms import UserProfileForm, ProfileSettingsForm
# from .models import UserProfile

# @login_required
# def seller_settings(request):
#     """Main settings page with tabs"""
#     user = request.user
#     profile = user.profile
    
#     # Initialize forms
#     profile_form = UserProfileForm(instance=profile)
#     user_form = ProfileSettingsForm(instance=user)
#     privacy_form = PrivacySettingsForm(instance=user)
    
#     # Get active tab from query params
#     active_tab = request.GET.get('tab', 'profile')
    
#     # Initialize notification form with user preferences
#     notification_prefs = user.notification_preferences or {}
    
#     context = {
#         'user': user,
#         'profile': profile,
#         'profile_form': profile_form,
#         'user_form': user_form,
#         'privacy_form': privacy_form,
#         'active_tab': active_tab,
#         'notification_prefs': notification_prefs,
#         'title': 'Settings',
#     }
#     return render(request, 'dashboard/seller/settings.html', context)

# @login_required
# @require_POST
# def update_profile(request):
#     """Update profile settings"""
#     user = request.user
#     profile = user.profile
    
#     profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)
#     user_form = ProfileSettingsForm(request.POST, instance=user)
    
#     if profile_form.is_valid() and user_form.is_valid():
#         profile_form.save()
#         user_form.save()
        
#         if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#             return JsonResponse({
#                 'success': True,
#                 'message': 'Profile updated successfully!'
#             })
#         else:
#             messages.success(request, 'Profile updated successfully!')
#             return redirect('seller_settings')
    
#     if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#         return JsonResponse({
#             'success': False,
#             'errors': profile_form.errors,
#             'user_errors': user_form.errors
#         })
#     else:
#         messages.error(request, 'Please correct the errors below.')
#         return redirect('seller_settings')

# @login_required
# @require_POST
# def update_privacy(request):
#     """Update privacy settings"""
#     user = request.user
#     form = PrivacySettingsForm(request.POST, instance=user)
    
#     if form.is_valid():
#         form.save()
        
#         if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#             return JsonResponse({
#                 'success': True,
#                 'message': 'Privacy settings updated successfully!'
#             })
#         else:
#             messages.success(request, 'Privacy settings updated successfully!')
#             return redirect('seller_settings?tab=privacy')
    
#     if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#         return JsonResponse({
#             'success': False,
#             'errors': form.errors
#         })
#     else:
#         messages.error(request, 'Please correct the errors below.')
#         return redirect('seller_settings?tab=privacy')

# @login_required
# @require_POST
# def update_notifications(request):
#     """Update notification preferences"""
#     user = request.user
#     form = NotificationSettingsForm(request.POST)
    
#     if form.is_valid():
#         form.save_to_user(user)
        
#         if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#             return JsonResponse({
#                 'success': True,
#                 'message': 'Notification preferences updated successfully!'
#             })
#         else:
#             messages.success(request, 'Notification preferences updated successfully!')
#             return redirect('seller_settings?tab=notifications')
    
#     if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#         return JsonResponse({
#             'success': False,
#             'errors': form.errors
#         })
#     else:
#         messages.error(request, 'Please correct the errors below.')
#         return redirect('seller_settings?tab=notifications')

# @login_required
# @require_POST
# def update_password(request):
#     """Change password"""
#     from django.contrib.auth import update_session_auth_hash
    
#     current_password = request.POST.get('current_password')
#     new_password = request.POST.get('new_password')
#     confirm_password = request.POST.get('confirm_password')
    
#     # Validate current password
#     if not request.user.check_password(current_password):
#         return JsonResponse({
#             'success': False,
#             'error': 'Current password is incorrect.'
#         })
    
#     # Validate new password
#     if len(new_password) < 8:
#         return JsonResponse({
#             'success': False,
#             'error': 'New password must be at least 8 characters long.'
#         })
    
#     # Check if passwords match
#     if new_password != confirm_password:
#         return JsonResponse({
#             'success': False,
#             'error': 'New passwords do not match.'
#         })
    
#     # Change password
#     request.user.set_password(new_password)
#     request.user.save()
    
#     # Update session to prevent logout
#     update_session_auth_hash(request, request.user)
    
#     return JsonResponse({
#         'success': True,
#         'message': 'Password changed successfully!'
#     })

# @login_required
# @require_POST
# def update_account(request):
#     """Update account settings including theme and notifications"""
#     user = request.user
    
#     # Update dashboard theme
#     theme = request.POST.get('dashboard_theme')
#     if theme in ['light', 'dark']:
#         user.dashboard_theme = theme
#         user.save(update_fields=['dashboard_theme'])
    
#     # Update notification preferences
#     notification_data = request.POST.get('notification_preferences')
#     if notification_data:
#         try:
#             user.notification_preferences = json.loads(notification_data)
#             user.save(update_fields=['notification_preferences'])
#         except json.JSONDecodeError:
#             pass
    
#     return JsonResponse({
#         'success': True,
#         'message': 'Account settings updated successfully!'
#     })

# @login_required
# def dashboard_view(request):
#     """User dashboard based on role"""
#     user = request.user
    
#     # Prepare context based on user type
#     context = {
#         'user': user,
#         'title': 'Dashboard',
#     }
    
#     if user.user_type == 'admin':
#         template = 'dashboard/admin_dashboard.html'
#         # Add admin-specific context
#     elif user.user_type in ['seller', 'agent']:
#         template = 'dashboard/seller_dashboard.html'
#         # Add seller/agent specific context
#         try:
#             context['membership'] = user.usermembership
#             context['active_listings'] = user.property_set.filter(is_active=True).count()
#         except:
#             pass
#     else:  # buyer/tenant
#         template = 'core/dashboard/buyer_dashboard.html'
#         # Add buyer-specific context
#         # context['favorites'] = user.propertyfavorite_set.all()[:5]
#         context['recent_searches'] = []  # Implement search history if needed
    
#     return render(request, template, context)


# ==============================================
#  Home Page View
# ==============================================

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
import json

from .models import Property, PropertyType

def home_view(request):
    """Home page with featured properties and premier houses"""
    
    # Get featured properties (no login required)
    featured_properties = Property.objects.filter(
        status='active',
        is_featured=True
    ).select_related('owner').prefetch_related('images')[:3]  # Limit to 3
    
    # Get all active properties for premier section (will be filtered by JS)
    premier_properties = Property.objects.filter(
        status='active'
    ).select_related('owner').prefetch_related('images')
    
    # Order by urgent first, then by upload date
    premier_properties = premier_properties.order_by(
        '-is_urgent', '-created_at'
    )[:8]  # Limit to 8
    
    context = {
        'featured_properties': featured_properties,
        'premier_properties': premier_properties,
        'property_types': PropertyType.objects.filter(is_active=True)[:8],
    }
    
    return render(request, 'core/home.html', context)


def api_filter_properties(request):
    """API endpoint for filtering properties (no login required)"""
    
    # Get filter parameters
    property_type = request.GET.get('property_type', '')
    price_range = request.GET.get('price_range', '')
    location = request.GET.get('location', '')
    bedrooms = request.GET.get('bedrooms', '')
    
    # Base queryset - only active properties
    properties = Property.objects.filter(status='active')
    
    # Apply filters
    if property_type:
        properties = properties.filter(
            Q(title__icontains=property_type) |
            Q(property_type__name__icontains=property_type)
        )
    
    if price_range:
        try:
            if price_range == '1000000+':
                properties = properties.filter(price__gte=1000000)
            else:
                min_price, max_price = map(int, price_range.split('-'))
                properties = properties.filter(price__gte=min_price, price__lte=max_price)
        except (ValueError, TypeError):
            pass
    
    if location:
        properties = properties.filter(
            Q(city__icontains=location) |
            Q(locality__icontains=location) |
            Q(address__icontains=location)
        )
    
    if bedrooms and bedrooms != '0':
        if bedrooms == '4':
            properties = properties.filter(bedrooms__gte=4)
        else:
            try:
                properties = properties.filter(bedrooms=int(bedrooms))
            except ValueError:
                pass
    
    # Limit to 20 results for performance
    properties = properties[:20]
    
    # Format properties for JSON
    properties_data = []
    for prop in properties:
        properties_data.append({
            'id': prop.id,
            'title': prop.title,
            'description': prop.description[:150] + '...' if len(prop.description) > 150 else prop.description,
            'price': float(prop.price),
            'price_formatted': f"₹{prop.price:,.0f}" if prop.property_for != 'rent' else f"₹{prop.price:,.0f}/mo",
            'bedrooms': prop.bedrooms,
            'bathrooms': prop.bathrooms,
            'address': f"{prop.locality or ''} {prop.city}",
            'city': prop.city,
            'property_for': prop.get_property_for_display(),
            'image': prop.primary_image.url if prop.primary_image else '/static/images/property-placeholder.jpg',
            'is_urgent': prop.is_urgent,
            'is_featured': prop.is_featured,
        })
    
    return JsonResponse({
        'success': True,
        'properties': properties_data,
        'count': len(properties_data),
    })


def api_property_details(request, property_id):
    """API endpoint for property details"""
    try:
        property = Property.objects.get(id=property_id, status='active')
        
        # Increment view count
        property.view_count += 1
        property.save(update_fields=['view_count'])
        
        data = {
            'success': True,
            'property': {
                'id': property.id,
                'title': property.title,
                'description': property.description,
                'price': float(property.price),
                'price_formatted': f"₹{property.price:,.0f}" if property.property_for != 'rent' else f"₹{property.price:,.0f}/mo",
                'price_per_sqft': float(property.price_per_sqft) if property.price_per_sqft else None,
                'carpet_area': float(property.carpet_area) if property.carpet_area else None,
                'bedrooms': property.bedrooms,
                'bathrooms': property.bathrooms,
                'balconies': property.balconies,
                'city': property.city,
                'locality': property.locality,
                'address': property.address,
                'property_for': property.get_property_for_display(),
                'furnishing': property.get_furnishing_display() if property.furnishing else None,
                'amenities': property.amenities,
                'possession_status': property.possession_status,
                'age_of_property': property.age_of_property,
                'contact_person': property.contact_person,
                'contact_phone': property.contact_phone,
                'contact_email': property.contact_email,
                'image': property.primary_image.url if property.primary_image else '/static/images/property-placeholder.jpg',
                'is_urgent': property.is_urgent,
                'is_featured': property.is_featured,
            }
        }
        
        return JsonResponse(data)
    except Property.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Property not found'}, status=404)


def api_send_contact(request):
    """API endpoint for contact form (no login required)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Extract form data
            first_name = data.get('first_name', '')
            last_name = data.get('last_name', '')
            email = data.get('email', '')
            phone = data.get('phone', '')
            inquiry_type = data.get('inquiry_type', '')
            message = data.get('message', '')
            property_id = data.get('property_id')
            
            # Get property info if provided
            property_info = ""
            if property_id:
                try:
                    property = Property.objects.get(id=property_id)
                    property_info = f"\n\nRegarding Property: {property.title} (ID: {property.property_id})"
                except Property.DoesNotExist:
                    pass
            
            # Prepare email content
            subject = f"New Contact Form Inquiry: {inquiry_type}"
            email_message = f"""
            New contact form submission:
            
            Name: {first_name} {last_name}
            Email: {email}
            Phone: {phone}
            Inquiry Type: {inquiry_type}
            Message: {message}
            {property_info}
            """
            
            # Send email
            send_mail(
                subject,
                email_message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.CONTACT_EMAIL],
                fail_silently=False,
            )
            
            # Also save to database if you have a Contact model
            # Contact.objects.create(...)
            
            return JsonResponse({
                'success': True,
                'message': 'Your message has been sent successfully! We will contact you within 24 hours.'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


@login_required
def premier_properties_view(request):
    """View for premier properties (login required)"""
    # Get all urgent properties first, then others
    properties = Property.objects.filter(
        status='active'
    ).order_by('-is_urgent', '-created_at')
    
    # Paginate
    paginator = Paginator(properties, 12)
    page = request.GET.get('page', 1)
    properties_page = paginator.get_page(page)
    
    context = {
        'properties': properties_page,
        'is_premier': True,
    }
    
    return render(request, 'core/premier_properties.html', context)

# ==============================================
#  Properties List View with Filters
# ==============================================

def properties_list_view(request):
    """Display featured properties with filters"""
    
    # Base queryset - only active and featured properties
    properties = Property.objects.filter(
        status='active',
        is_featured=True
    ).select_related('owner', 'owner__profile').prefetch_related('images')
    
    # Apply search filters
    search_query = request.GET.get('q', '')
    if search_query:
        properties = properties.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(address__icontains=search_query) |
            Q(city__icontains=search_query) |
            Q(locality__icontains=search_query)
        )
    
    # City filter
    city = request.GET.get('city', '')
    if city:
        properties = properties.filter(city__icontains=city)
    
    # Property for filter (sale/rent)
    property_for = request.GET.get('property_for', '')
    if property_for:
        properties = properties.filter(property_for=property_for)
    
    # Price range filter
    price_range = request.GET.get('price_range', '')
    if price_range:
        if price_range == 'under_50l':
            properties = properties.filter(price__lt=5000000)
        elif price_range == '50l_1cr':
            properties = properties.filter(price__gte=5000000, price__lt=10000000)
        elif price_range == '1cr_2cr':
            properties = properties.filter(price__gte=10000000, price__lt=20000000)
        elif price_range == 'above_2cr':
            properties = properties.filter(price__gte=20000000)
    
    # Min/Max price
    min_price = request.GET.get('min_price')
    if min_price:
        try:
            properties = properties.filter(price__gte=float(min_price))
        except ValueError:
            pass
    
    max_price = request.GET.get('max_price')
    if max_price:
        try:
            properties = properties.filter(price__lte=float(max_price))
        except ValueError:
            pass
    
    # Property type filter
    property_type_ids = request.GET.getlist('property_type')
    if property_type_ids:
        properties = properties.filter(property_type_id__in=property_type_ids)
    
    # BHK filter
    bhk = request.GET.get('bhk')
    if bhk:
        if bhk == '4plus':
            properties = properties.filter(bedrooms__gte=4)
        else:
            try:
                properties = properties.filter(bedrooms=int(bhk))
            except ValueError:
                pass
    
    # Amenities filter
    amenities = request.GET.getlist('amenities')
    if amenities:
        for amenity in amenities:
            properties = properties.filter(amenities__selected__contains=[amenity])
    
    # Possession filter
    possession = request.GET.get('possession')
    if possession == 'ready':
        properties = properties.filter(possession_status__icontains='ready')
    elif possession == 'under_construction':
        properties = properties.filter(possession_status__icontains='construction')
    
    # Sorting
    sort_by = request.GET.get('sort', '-created_at')
    valid_sort_fields = ['price', '-price', 'created_at', '-created_at', 'view_count', '-view_count', 'inquiry_count', '-inquiry_count']
    if sort_by in valid_sort_fields:
        properties = properties.order_by(sort_by)
    else:
        properties = properties.order_by('-created_at')
    
    # Get user favorites if logged in
    user_favorites = []
    if request.user.is_authenticated:
        user_favorites = request.user.favorites.values_list('property_id', flat=True)
    
    # Pagination
    paginator = Paginator(properties, 10)  # Show 10 properties per page
    page_number = request.GET.get('page')
    featured_properties = paginator.get_page(page_number)
    
    # Get all property types for filter
    property_types = PropertyType.objects.filter(is_active=True)
    
    context = {
        'featured_properties': featured_properties,
        'property_types': property_types,
        'user_favorites': list(user_favorites),
    }
    
    return render(request, 'core/properties_list.html', context)

from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Property, PropertyType

def api_featured_properties(request):
    """API endpoint for featured properties with filters - returns JSON"""
    
    # Base queryset - only active and featured properties
    properties = Property.objects.filter(
        status='active',
        is_featured=True
    ).select_related('owner').prefetch_related('images')
    
    # Apply filters
    search_query = request.GET.get('q', '')
    if search_query:
        properties = properties.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(address__icontains=search_query) |
            Q(city__icontains=search_query) |
            Q(locality__icontains=search_query)
        )
    
    city = request.GET.get('city', '')
    if city:
        properties = properties.filter(city__icontains=city)
    
    property_for = request.GET.get('property_for', '')
    if property_for:
        properties = properties.filter(property_for=property_for)
    
    # Price range
    price_range = request.GET.get('price_range', '')
    if price_range:
        if price_range == 'under_50l':
            properties = properties.filter(price__lt=5000000)
        elif price_range == '50l_1cr':
            properties = properties.filter(price__gte=5000000, price__lt=10000000)
        elif price_range == '1cr_2cr':
            properties = properties.filter(price__gte=10000000, price__lt=20000000)
        elif price_range == 'above_2cr':
            properties = properties.filter(price__gte=20000000)
    
    # Min/Max price
    min_price = request.GET.get('min_price')
    if min_price:
        try:
            properties = properties.filter(price__gte=float(min_price))
        except ValueError:
            pass
    
    max_price = request.GET.get('max_price')
    if max_price:
        try:
            properties = properties.filter(price__lte=float(max_price))
        except ValueError:
            pass
    
    # Property types
    property_type_ids = request.GET.getlist('property_type')
    if property_type_ids:
        properties = properties.filter(property_type_id__in=property_type_ids)
    
    # BHK
    bhk = request.GET.get('bhk')
    if bhk:
        if bhk == '4plus':
            properties = properties.filter(bedrooms__gte=4)
        else:
            try:
                properties = properties.filter(bedrooms=int(bhk))
            except ValueError:
                pass
    
    # Amenities
    amenities = request.GET.getlist('amenities')
    if amenities:
        for amenity in amenities:
            properties = properties.filter(amenities__selected__contains=[amenity])
    
    # Possession
    possession = request.GET.get('possession')
    if possession == 'ready':
        properties = properties.filter(possession_status__icontains='ready')
    elif possession == 'under_construction':
        properties = properties.filter(possession_status__icontains='construction')
    
    # Sorting
    sort_by = request.GET.get('sort', '-created_at')
    valid_sort_fields = ['price', '-price', 'created_at', '-created_at', 'view_count', '-view_count']
    if sort_by in valid_sort_fields:
        properties = properties.order_by(sort_by)
    else:
        properties = properties.order_by('-created_at')
    
    # Pagination
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 8))
    
    paginator = Paginator(properties, page_size)
    total_pages = paginator.num_pages
    total_count = paginator.count
    
    if page > total_pages:
        page = total_pages
    
    page_obj = paginator.get_page(page)
    
    # Format properties for JSON
    properties_data = []
    for prop in page_obj:
        prop_data = {
            'id': prop.id,
            'title': prop.title,
            'description': prop.description,
            'price': float(prop.price),
            'price_per_sqft': float(prop.price_per_sqft) if prop.price_per_sqft else None,
            'carpet_area': float(prop.carpet_area) if prop.carpet_area else None,
            'bedrooms': prop.bedrooms,
            'bathrooms': prop.bathrooms,
            'city': prop.city,
            'locality': prop.locality,
            'address': prop.address,
            'property_for': prop.property_for,
            'furnishing': prop.furnishing,
            'furnishing_display': prop.get_furnishing_display() if prop.furnishing else None,
            'amenities': prop.amenities,
            'is_featured': prop.is_featured,
            'is_premium': prop.is_premium,
            'is_verified': prop.is_verified,
            'is_urgent': prop.is_urgent,
            'contact_person': prop.contact_person,
            'contact_phone': prop.contact_phone,
            'contact_email': prop.contact_email,
            'primary_image': prop.primary_image.url if prop.primary_image else None,
            'images_count': prop.images.count(),
            'owner_initials': prop.owner.first_name[0] + prop.owner.last_name[0] if prop.owner.first_name and prop.owner.last_name else 'U',
            'owner_type': prop.owner.get_user_type_display() if prop.owner else 'Individual Owner',
            'status_display': prop.get_status_display(),
        }
        
        # Add images if needed
        if prop.images.exists():
            prop_data['images'] = [{'image': img.image.url} for img in prop.images.all()[:5]]
        
        properties_data.append(prop_data)
    
    return JsonResponse({
        'properties': properties_data,
        'total_pages': total_pages,
        'total_count': total_count,
        'current_page': page,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
    })

def api_property_types(request):
    """API endpoint to get all property types"""
    types = PropertyType.objects.filter(is_active=True).values('id', 'name')
    return JsonResponse(list(types), safe=False)

def api_property_details(request, id):
    """API endpoint to get single property details"""
    try:
        property = Property.objects.get(id=id, status='active')
        
        data = {
            'success': True,
            'property': {
                'id': property.id,
                'title': property.title,
                'description': property.description,
                'price': float(property.price),
                'price_per_sqft': float(property.price_per_sqft) if property.price_per_sqft else None,
                'carpet_area': float(property.carpet_area) if property.carpet_area else None,
                'builtup_area': float(property.builtup_area) if property.builtup_area else None,
                'bedrooms': property.bedrooms,
                'bathrooms': property.bathrooms,
                'balconies': property.balconies,
                'city': property.city,
                'locality': property.locality,
                'address': property.address,
                'property_for': property.property_for,
                'furnishing': property.furnishing,
                'furnishing_display': property.get_furnishing_display() if property.furnishing else None,
                'amenities': property.amenities,
                'possession_status': property.possession_status,
                'age_of_property': property.age_of_property,
                'contact_person': property.contact_person,
                'contact_phone': property.contact_phone,
                'contact_email': property.contact_email,
                'status_display': property.get_status_display(),
                'primary_image': property.primary_image.url if property.primary_image else None,
            }
        }
        
        # Increment view count
        property.view_count += 1
        property.save(update_fields=['view_count'])
        
        return JsonResponse(data)
    except Property.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Property not found'}, status=404)