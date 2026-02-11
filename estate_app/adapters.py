from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from .models import CustomUser, UserProfile

class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom account adapter for allauth to work with CustomUser"""
    
    def save_user(self, request, user, form, commit=True):
        """Save user with additional fields"""
        data = form.cleaned_data
        
        # Set email
        user.email = data.get('email')
        
        # Set additional fields from form
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'user_type' in data:
            user.user_type = data['user_type']
        if 'phone' in data:
            user.phone = data['phone']
        
        # Set password
        if 'password1' in data:
            user.set_password(data['password1'])
        else:
            user.set_unusable_password()
        
        if commit:
            user.save()
        
        return user
    
    def get_login_redirect_url(self, request):
        """Custom login redirect based on user type"""
        if request.user.is_authenticated:
            return reverse('estate_app:dashboard')  # Change to your dashboard URL
        return super().get_login_redirect_url(request)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom social account adapter for allauth"""
    
    def pre_social_login(self, request, sociallogin):
        """Connect social account to existing user with same email"""
        email = sociallogin.account.extra_data.get('email')
        if email:
            try:
                user = CustomUser.objects.get(email=email)
                sociallogin.connect(request, user)
                messages.success(request, f"Connected your {sociallogin.account.provider} account successfully!")
            except CustomUser.DoesNotExist:
                pass
    
    def save_user(self, request, sociallogin, form=None):
        """Save user from social login and create profile"""
        user = super().save_user(request, sociallogin, form)
        
        # Update user info from social account
        extra_data = sociallogin.account.extra_data
        
        if sociallogin.account.provider == 'google':
            user.first_name = extra_data.get('given_name', '')
            user.last_name = extra_data.get('family_name', '')
            user.is_verified = True
            
        elif sociallogin.account.provider == 'facebook':
            name = extra_data.get('name', '')
            if name:
                name_parts = name.split(' ', 1)
                user.first_name = name_parts[0]
                user.last_name = name_parts[1] if len(name_parts) > 1 else ''
            user.is_verified = True
        
        # Set default user type for social login users
        user.user_type = 'buyer'
        user.save()
        
        # Create or update user profile
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Add profile picture from social account if available
        if sociallogin.account.provider == 'facebook':
            if 'picture' in extra_data:
                picture_data = extra_data['picture']
                if 'data' in picture_data and 'url' in picture_data['data']:
                    profile.avatar_url = picture_data['data']['url']
        
        profile.save()
        return user
    
    def get_connect_redirect_url(self, request, socialaccount):
        """Redirect after connecting social account"""
        messages.success(request, f"Successfully connected {socialaccount.get_provider().name} account!")
        return reverse('estate_app:profile')  # Change to your profile URL