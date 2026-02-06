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

from .models import CustomUser, UserProfile
from .forms import UserRegistrationForm, UserLoginForm, UserProfileForm, EmailVerificationForm
from .tokens import account_activation_token

# ==============================================
#  Authentication Views
# ==============================================

def register_view(request):
    """Handle user registration"""
    # if request.user.is_authenticated:
    #     return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()

                # Get or create user profile directly (avoid signal recursion)
                profile, created = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={}
                )

                # Update profile based on user type
                if user.user_type in ['seller', 'agent']:
                    profile.agency_name = form.cleaned_data.get('agency_name', '')
                    profile.save()

                # Send verification email
                if settings.EMAIL_VERIFICATION_REQUIRED:
                    send_verification_email(request, user)
                    messages.success(
                        request,
                        'Registration successful! Please check your email to verify your account.'
                    )
                    return redirect('verification_sent')
                else:
                    user.is_verified = True
                    user.save()
                    login(request, user)
                    messages.success(request, 'Registration successful! Welcome to our platform.')
                    return redirect('dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserRegistrationForm()

    context = {
        'form': form,
        'title': 'Register',
        'user_types': CustomUser.USER_TYPE_CHOICES,
    }
    return render(request, 'auth/register.html', context)


def login_view(request):
    """Handle user login"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            remember_me = form.cleaned_data.get('remember_me')
            
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
                
                messages.success(request, f'Welcome back, {user.first_name}!')
                
                # Redirect based on user type
                next_url = request.GET.get('next', None)
                if next_url:
                    return redirect(next_url)
                return redirect('dashboard')
            else:
                messages.error(request, 'Invalid email or password.')
        else:
            messages.error(request, 'Invalid email or password.')
    else:
        form = UserLoginForm()
    
    context = {
        'form': form,
        'title': 'Login',
    }
    return render(request, 'auth/login.html', context)


def logout_view(request):
    """Handle user logout"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('home')

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
                # Use the appropriate backend
                # First, try to find which backend to use
                from django.contrib.auth import authenticate
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)
                print(f"DEBUG: Auto-logged in user: {user.email}")
            
            messages.success(request, f'Email verified successfully! Welcome to {settings.SITE_NAME}.')
            print("DEBUG: Verification successful!")
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

@login_required
def profile_view(request):
    """Display user profile"""
    user = request.user
    profile = user.profile
    
    context = {
        'user': user,
        'profile': profile,
        'title': 'My Profile',
    }
    return render(request, 'dashboard/profile/profile.html', context)


@login_required
def edit_profile_view(request):
    """Edit user profile"""
    user = request.user
    profile = user.profile

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()

            # Update user phone if changed
            if 'phone' in request.POST:
                user.phone = request.POST.get('phone')
                user.save()

            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserProfileForm(instance=profile)

    context = {
        'form': form,
        'user': user,
        'title': 'Edit Profile',
    }
    return render(request, 'dashboard/profile/edit_profile.html', context)


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


# ==============================================
#  Seller/Agent Settings Views
# ==============================================

# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import JsonResponse
import json
from .forms import UserProfileForm, ProfileSettingsForm, PrivacySettingsForm, NotificationSettingsForm
from .models import UserProfile

@login_required
def seller_settings(request):
    """Main settings page with tabs"""
    user = request.user
    profile = user.profile
    
    # Initialize forms
    profile_form = UserProfileForm(instance=profile)
    user_form = ProfileSettingsForm(instance=user)
    privacy_form = PrivacySettingsForm(instance=user)
    
    # Get active tab from query params
    active_tab = request.GET.get('tab', 'profile')
    
    # Initialize notification form with user preferences
    notification_prefs = user.notification_preferences or {}
    
    context = {
        'user': user,
        'profile': profile,
        'profile_form': profile_form,
        'user_form': user_form,
        'privacy_form': privacy_form,
        'active_tab': active_tab,
        'notification_prefs': notification_prefs,
        'title': 'Settings',
    }
    return render(request, 'dashboard/seller/settings.html', context)

@login_required
@require_POST
def update_profile(request):
    """Update profile settings"""
    user = request.user
    profile = user.profile
    
    profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)
    user_form = ProfileSettingsForm(request.POST, instance=user)
    
    if profile_form.is_valid() and user_form.is_valid():
        profile_form.save()
        user_form.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Profile updated successfully!'
            })
        else:
            messages.success(request, 'Profile updated successfully!')
            return redirect('seller_settings')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'errors': profile_form.errors,
            'user_errors': user_form.errors
        })
    else:
        messages.error(request, 'Please correct the errors below.')
        return redirect('seller_settings')

@login_required
@require_POST
def update_privacy(request):
    """Update privacy settings"""
    user = request.user
    form = PrivacySettingsForm(request.POST, instance=user)
    
    if form.is_valid():
        form.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Privacy settings updated successfully!'
            })
        else:
            messages.success(request, 'Privacy settings updated successfully!')
            return redirect('seller_settings?tab=privacy')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'errors': form.errors
        })
    else:
        messages.error(request, 'Please correct the errors below.')
        return redirect('seller_settings?tab=privacy')

@login_required
@require_POST
def update_notifications(request):
    """Update notification preferences"""
    user = request.user
    form = NotificationSettingsForm(request.POST)
    
    if form.is_valid():
        form.save_to_user(user)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Notification preferences updated successfully!'
            })
        else:
            messages.success(request, 'Notification preferences updated successfully!')
            return redirect('seller_settings?tab=notifications')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'errors': form.errors
        })
    else:
        messages.error(request, 'Please correct the errors below.')
        return redirect('seller_settings?tab=notifications')

@login_required
@require_POST
def update_password(request):
    """Change password"""
    from django.contrib.auth import update_session_auth_hash
    
    current_password = request.POST.get('current_password')
    new_password = request.POST.get('new_password')
    confirm_password = request.POST.get('confirm_password')
    
    # Validate current password
    if not request.user.check_password(current_password):
        return JsonResponse({
            'success': False,
            'error': 'Current password is incorrect.'
        })
    
    # Validate new password
    if len(new_password) < 8:
        return JsonResponse({
            'success': False,
            'error': 'New password must be at least 8 characters long.'
        })
    
    # Check if passwords match
    if new_password != confirm_password:
        return JsonResponse({
            'success': False,
            'error': 'New passwords do not match.'
        })
    
    # Change password
    request.user.set_password(new_password)
    request.user.save()
    
    # Update session to prevent logout
    update_session_auth_hash(request, request.user)
    
    return JsonResponse({
        'success': True,
        'message': 'Password changed successfully!'
    })

@login_required
@require_POST
def update_account(request):
    """Update account settings including theme and notifications"""
    user = request.user
    
    # Update dashboard theme
    theme = request.POST.get('dashboard_theme')
    if theme in ['light', 'dark']:
        user.dashboard_theme = theme
        user.save(update_fields=['dashboard_theme'])
    
    # Update notification preferences
    notification_data = request.POST.get('notification_preferences')
    if notification_data:
        try:
            user.notification_preferences = json.loads(notification_data)
            user.save(update_fields=['notification_preferences'])
        except json.JSONDecodeError:
            pass
    
    return JsonResponse({
        'success': True,
        'message': 'Account settings updated successfully!'
    })
    
    
    
    
    


@login_required
def dashboard_view(request):
    """User dashboard based on role"""
    user = request.user
    
    # Prepare context based on user type
    context = {
        'user': user,
        'title': 'Dashboard',
    }
    
    if user.user_type == 'admin':
        template = 'dashboard/admin_dashboard.html'
        # Add admin-specific context
    elif user.user_type in ['seller', 'agent']:
        template = 'dashboard/seller_dashboard.html'
        # Add seller/agent specific context
        try:
            context['membership'] = user.usermembership
            context['active_listings'] = user.property_set.filter(is_active=True).count()
        except:
            pass
    else:  # buyer/tenant
        template = 'core/dashboard/buyer_dashboard.html'
        # Add buyer-specific context
        # context['favorites'] = user.propertyfavorite_set.all()[:5]
        context['recent_searches'] = []  # Implement search history if needed
    
    return render(request, template, context)


"""
Home page view with featured properties, statistics, and sections
"""
from django.shortcuts import render
from django.db.models import Count, Q
from django.utils import timezone
from django.core.cache import cache
from django.db.models.functions import TruncMonth
from django.db.models import Avg, Max, Min, Sum
from django.contrib.gis.geoip2 import GeoIP2
# from django.contrib.gis.geos import Point
# from django.contrib.gis.db.models.functions import Distance
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
import json
from datetime import datetime, timedelta

from .models import (
    Property, PropertyCategory, PropertyImage, 
    CustomUser, MembershipPlan, PropertyAmenity
)


# @cache_page(6
# 0 * 15)  # Cache for 15 minutes
def home_view(request):
    """Home page view with dynamic content"""
    
    # Get user's location for personalized content
    user_location = get_user_location(request)
    
    # Featured properties (cached for performance)
    cache_key = f'home_featured_properties_{user_location}'
    featured_properties = cache.get(cache_key)
    
    if featured_properties is None:
        featured_properties = get_featured_properties(user_location)
        cache.set(cache_key, featured_properties, 60 * 30)  # 30 minutes cache
    
    # Recently added properties
    recent_properties = get_recent_properties(user_location)
    
    # Popular categories
    popular_categories = get_popular_categories()
    
    # Statistics
    stats = get_home_statistics()
    
    # Testimonials
    testimonials = get_testimonials()
    
    # City statistics for location selector
    city_stats = get_city_statistics()
    
    # For logged in users, show personalized recommendations
    personalized_recommendations = []
    if request.user.is_authenticated:
        personalized_recommendations = get_personalized_recommendations(request.user)
    
    context = {
        'title': 'RealEstatePro - Find Your Dream Property',
        'featured_properties': featured_properties,
        'recent_properties': recent_properties,
        'popular_categories': popular_categories,
        'stats': stats,
        'testimonials': testimonials,
        'city_stats': city_stats,
        'personalized_recommendations': personalized_recommendations,
        'user_location': user_location,
        'current_year': timezone.now().year,
    }
    
    return render(request, 'home.html', context)


def get_user_location(request):
    """Get user's location based on IP or session"""
    location = None
    
    # Check session first
    if 'user_location' in request.session:
        location = request.session['user_location']
    else:
        # Try to get location from IP
        try:
            g = GeoIP2()
            ip = get_client_ip(request)
            if ip:
                location_data = g.city(ip)
                if location_data:
                    location = {
                        'city': location_data['city'],
                        'country': location_data['country_name'],
                        'lat': location_data['latitude'],
                        'lng': location_data['longitude']
                    }
                    request.session['user_location'] = location
        except Exception as e:
            # Fallback to default location
            location = {'city': 'Mumbai', 'country': 'India', 'lat': 19.0760, 'lng': 72.8777}
    
    return location


def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_featured_properties(location=None, limit=8):
    """Get featured properties with optimization"""
    queryset = Property.objects.filter(
        is_active=True,
        is_featured=True,
        featured_until__gte=timezone.now()  # Only active featured listings
    ).select_related(
        'owner'
    ).prefetch_related(
        'images'
    ).only(
        'id', 'title', 'slug', 'price', 'city', 'locality',
        'bedrooms', 'bathrooms', 'super_area', 'status', 'created_at',
        'is_featured', 'is_verified', 'owner__id'
    ).order_by('-created_at')[:limit]
    
    # If location is available, prioritize nearby properties
    if location and location.get('lat') and location.get('lng'):
        # This is a simplified version - in production, use PostGIS
        queryset = list(queryset)
        queryset.sort(key=lambda x: (
            0 if x.city == location['city'] else 1,
            -x.created_at.timestamp()
        ))
    
    return queryset


def get_recent_properties(location=None, limit=6):
    """Get recently added properties"""
    queryset = Property.objects.filter(
        is_active=True,
        created_at__gte=timezone.now() - timedelta(days=30)
    ).select_related(
        'owner'
    ).prefetch_related(
        'images'
    ).only(
        'id', 'title', 'slug', 'price', 'city', 'locality',
        'bedrooms', 'bathrooms', 'super_area', 'status', 'created_at',
        'is_featured', 'owner__id'
    ).order_by('-created_at')[:limit]
    
    return queryset


def get_popular_categories(limit=6):
    """Get popular property categories"""
    cache_key = 'popular_categories'
    categories = cache.get(cache_key)
    
    if categories is None:
        categories = PropertyCategory.objects.filter(
            is_active=True
        ).annotate(
            property_count=Count('properties', filter=Q(properties__is_active=True))
        ).filter(
            property_count__gt=0
        ).order_by('-property_count')[:limit]
        
        cache.set(cache_key, categories, 60 * 60)  # 1 hour cache
    
    return categories


def get_home_statistics():
    """Get home page statistics"""
    cache_key = 'home_statistics'
    stats = cache.get(cache_key)
    
    if stats is None:
        total_properties = Property.objects.filter(is_active=True).count()
        total_users = CustomUser.objects.filter(is_active=True).count()
        
        # Properties added this month
        this_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_this_month = Property.objects.filter(
            is_active=True,
            created_at__gte=this_month_start
        ).count()
        
        # Success stories (properties marked as sold/rented)
        success_stories = Property.objects.filter(
            is_active=True,
            status__in=['sold', 'rented']
        ).count()
        
        # Average time to sell (simplified)
        sold_properties = Property.objects.filter(
            status='sold',
            is_active=True,
            created_at__isnull=False,
            updated_at__isnull=False
        )
        
        avg_time_to_sell = None
        if sold_properties.exists():
            # This is a simplified calculation
            avg_time_to_sell = 45  # days
        
        stats = {
            'total_properties': f"{total_properties:,}",
            'total_users': f"{total_users:,}",
            'new_this_month': f"{new_this_month:,}",
            'success_stories': f"{success_stories:,}",
            'avg_time_to_sell': avg_time_to_sell,
        }
        
        cache.set(cache_key, stats, 60 * 30)  # 30 minutes cache
    
    return stats


def get_testimonials():
    """Get testimonials for home page"""
    testimonials = [
        {
            'name': 'Rajesh Kumar',
            'role': 'Property Buyer',
            'city': 'Mumbai',
            'avatar_color': 'bg-blue-500',
            'content': 'Found my dream home in just 2 weeks! The platform made it so easy to compare properties and connect with sellers.',
            'rating': 5,
            'property_type': '3BHK Apartment',
        },
        {
            'name': 'Priya Sharma',
            'role': 'Real Estate Agent',
            'city': 'Delhi',
            'avatar_color': 'bg-purple-500',
            'content': 'As an agent, this platform has helped me reach more clients. The analytics and tools are incredibly useful.',
            'rating': 5,
            'property_type': 'Commercial Space',
        },
        {
            'name': 'Michael Chen',
            'role': 'NRI Investor',
            'city': 'Bangalore',
            'avatar_color': 'bg-green-500',
            'content': 'Investing from abroad was challenging until I found RealEstatePro. The virtual tours and detailed documentation made it seamless.',
            'rating': 5,
            'property_type': 'Luxury Villa',
        },
    ]
    
    return testimonials


def get_city_statistics():
    """Get statistics for popular cities"""
    cache_key = 'city_statistics'
    city_stats = cache.get(cache_key)
    
    if city_stats is None:
        # Get top 6 cities with most properties
        cities = Property.objects.filter(
            is_active=True
        ).values('city').annotate(
            property_count=Count('id'),
            avg_price=Avg('price'),
            min_price=Min('price'),
            max_price=Max('price')
        ).order_by('-property_count')[:6]
        
        city_stats = list(cities)
        cache.set(cache_key, city_stats, 60 * 60)  # 1 hour cache
    
    return city_stats


def get_personalized_recommendations(user, limit=4):
    """Get personalized property recommendations based on user behavior"""
    if not user.is_authenticated:
        return []
    
    recommendations = []
    
    # Get user's saved searches or favorite properties
    try:
        # If user has favorites, recommend similar properties
        favorites = user.favorites.select_related('property').all()[:3]
        if favorites.exists():
            favorite_categories = set([fav.property.category_id for fav in favorites])
            favorite_cities = set([fav.property.city for fav in favorites])
            
            recommendations = Property.objects.filter(
                is_active=True,
                category_id__in=list(favorite_categories)[:2],
                city__in=list(favorite_cities)[:2]
            ).exclude(
                id__in=[fav.property_id for fav in favorites]
            ).select_related(
                'owner'
            ).prefetch_related(
                'images'
            ).order_by('-created_at')[:limit]
    
    except Exception as e:
        # Log error and return empty
        pass
    
    return recommendations


def search_suggestions_view(request):
    """AJAX endpoint for search suggestions"""
    query = request.GET.get('q', '').strip().lower()
    
    if len(query) < 2:
        return JsonResponse({'suggestions': []})
    
    cache_key = f'search_suggestions_{query}'
    suggestions = cache.get(cache_key)
    
    if suggestions is None:
        # Search in properties
        properties = Property.objects.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(city__icontains=query) |
            Q(locality__icontains=query)
        ).filter(is_active=True).values('title', 'slug', 'city', 'price')[:5]
        
        # Search in cities
        cities = Property.objects.filter(
            city__icontains=query
        ).values_list('city', flat=True).distinct()[:5]
        
        # Search in categories
        categories = PropertyCategory.objects.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query)
        ).filter(is_active=True).values('name', 'slug')[:5]
        
        suggestions = {
            'properties': list(properties),
            'cities': list(cities),
            'categories': list(categories),
        }
        
        cache.set(cache_key, suggestions, 60 * 5)  # 5 minutes cache
    
    return JsonResponse(suggestions)


def city_properties_view(request, city):
    """Get properties for a specific city"""
    properties = Property.objects.filter(
        city=city,
        is_active=True
    ).select_related('owner').prefetch_related('images')[:8]
    
    city_stats = Property.objects.filter(
        city=city,
        is_active=True
    ).aggregate(
        total=Count('id'),
        avg_price=Avg('price'),
        for_sale=Count('id', filter=Q(status='for_sale')),
        for_rent=Count('id', filter=Q(status='for_rent'))
    )
    
    return JsonResponse({
        'properties': [
            {
                'title': p.title,
                'slug': p.slug,
                'price': p.price,
                'city': p.city,
                'locality': p.locality,
                'bedrooms': p.bedrooms,
                'bathrooms': p.bathrooms,
                'image': p.primary_image.url if p.primary_image else None
            }
            for p in properties
        ],
        'stats': city_stats
    })

