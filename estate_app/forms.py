import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q
from django.utils import timezone
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _
from django import forms
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import Property, PropertyImage, PropertyInquiry, PropertyCategory, PropertyType, MembershipPlan

from .models import (
    CustomUser,
    UserProfile,
    
)



User = get_user_model()



# ===================================================================
#  Settings Forms
# ===================================================================

class ProfileSettingsForm(forms.ModelForm):
    """Form for profile settings"""
    
    class Meta:
        model = CustomUser
        fields = [
            'first_name', 'last_name', 'phone', 'alternate_phone',
            'seller_type', 'pan_card', 'aadhar_card'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'alternate_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'seller_type': forms.Select(attrs={'class': 'form-select'}),
            'pan_card': forms.TextInput(attrs={'class': 'form-control'}),
            'aadhar_card': forms.TextInput(attrs={'class': 'form-control'}),
        }



# ===================================================================
# User Forms
# ===================================================================

from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, UserProfile
from django.core.exceptions import ValidationError
import re

class UserRegistrationForm(UserCreationForm):
    agency_name = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your agency name'
        }),
        help_text='Required for sellers and agents'
    )
    
    phone = forms.CharField(
        max_length=17,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+91 234 567 8900'
        })
    )
    
    terms = forms.BooleanField(
        required=True,
        error_messages={'required': 'You must agree to the terms and conditions.'}
    )
    
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'phone', 'user_type', 'password1', 'password2')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your.email@example.com'}),
            'user_type': forms.RadioSelect(attrs={'class': 'user-type-radio'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove help text for password fields
        self.fields['password1'].help_text = ''
        self.fields['password2'].help_text = ''
        
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered.')
        return email
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        # Validate phone number format
        phone_regex = r'^\+?1?\d{9,15}$'
        if not re.match(phone_regex, phone):
            raise ValidationError('Please enter a valid phone number.')
        return phone
    
    def clean(self):
        cleaned_data = super().clean()
        user_type = cleaned_data.get('user_type')
        agency_name = cleaned_data.get('agency_name')
        
        # Validate agency name for sellers/agents
        if user_type in ['seller', 'agent'] and not agency_name:
            raise ValidationError({'agency_name': 'Agency name is required for sellers and agents.'})
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']  # Set username as email
        user.phone = self.cleaned_data['phone']
        
        if commit:
            user.save()
            
            # Create user profile with agency name if provided
            profile = UserProfile.objects.create(
                user=user,
                agency_name=self.cleaned_data.get('agency_name', '')
            )
            
            # Create buyer profile for buyer users
            if user.user_type == 'buyer':
                from .models import BuyerProfile
                BuyerProfile.objects.create(user=user)
        
        return user

class UserLoginForm(AuthenticationForm):
    """Custom login form"""
    
    username = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address',
            'autofocus': True
        })
    )
    
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'
        })
    )
    
    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = "Email"


class UserProfileForm(forms.ModelForm):
    """Form for user profile"""
    
    class Meta:
        model = UserProfile
        fields = [
            'avatar', 'bio', 'agency_name', 'license', 
            'whatsapp_number', 'website', 'address', 
            'city', 'state', 'country', 'pincode',
            'facebook', 'twitter', 'linkedin', 'instagram',
            'experience_years', 'specialization', 'languages'
        ]
        widgets = {
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Tell us about yourself...'
            }),
            'agency_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your agency name'
            }),
            'license': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your real estate license number'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Your address'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City'
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'State'
            }),
            'country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country'
            }),
            'pincode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'PIN Code'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com'
            }),
            'whatsapp_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1234567890'
            }),
            'experience_years': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 50
            }),
            'specialization': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Residential, Commercial, Luxury Homes'
            }),
            'languages': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'English, Hindi, Spanish'
            }),
            'facebook': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'Facebook profile URL'
            }),
            'twitter': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'Twitter profile URL'
            }),
            'linkedin': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'LinkedIn profile URL'
            }),
            'instagram': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'Instagram profile URL'
            }),
        }


class EmailVerificationForm(forms.Form):
    """Form for resending verification email"""
    
    email = forms.EmailField(
        label=_("Email Address"),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        })
    )
    
class CustomUserCreationForm(UserCreationForm):
    """Form for creating new users"""
    class Meta:
        model = CustomUser
        fields = ('email', 'first_name', 'last_name', 'user_type', 'phone')
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg',
                'placeholder': 'Enter your email'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg',
                'placeholder': 'First name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg',
                'placeholder': 'Last name'
            }),
            'user_type': forms.Select(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full p-3 border border-gray-300 rounded-lg',
                'placeholder': '+91 9876543210'
            }),
        }


class CustomUserForm(forms.ModelForm):
    """Form for updating user information"""
    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'phone', 'alternate_phone', 
                  'user_type', 'seller_type', 'agency_name', 'pan_card', 'aadhar_card')
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700',
                'placeholder': 'First name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700',
                'placeholder': 'Last name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700',
                'readonly': True
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700',
                'placeholder': '+91 9876543210'
            }),
            'alternate_phone': forms.TextInput(attrs={
                'class': 'w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700',
                'placeholder': 'Alternate phone (optional)'
            }),
            'user_type': forms.Select(attrs={
                'class': 'w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700'
            }),
            'seller_type': forms.Select(attrs={
                'class': 'w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700'
            }),
            'agency_name': forms.TextInput(attrs={
                'class': 'w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700',
                'placeholder': 'Your agency name'
            }),
            'pan_card': forms.TextInput(attrs={
                'class': 'w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700',
                'placeholder': 'PAN card number'
            }),
            'aadhar_card': forms.TextInput(attrs={
                'class': 'w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700',
                'placeholder': 'Aadhar card number'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = False
        


# ===================================================================
# Property Forms
# ===================================================================




class PropertyImageForm(forms.ModelForm):
    """Form for uploading property images"""
    class Meta:
        model = PropertyImage
        fields = ['image', 'caption', 'is_primary']
        widgets = {
            'caption': forms.TextInput(attrs={'placeholder': 'Optional caption'}),
        }


class PropertyInquiryForm(forms.ModelForm):
    """Form for submitting property inquiries"""
    class Meta:
        model = PropertyInquiry
        fields = ['name', 'email', 'phone', 'message', 'preferred_date', 'preferred_time']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Your message to the seller...'}),
            'preferred_date': forms.DateInput(attrs={'type': 'date'}),
            'preferred_time': forms.TimeInput(attrs={'type': 'time'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.property = kwargs.pop('property', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Pre-fill for logged-in users
        if self.user and self.user.is_authenticated:
            self.fields['name'].initial = self.user.get_full_name()
            self.fields['email'].initial = self.user.email
            self.fields['phone'].initial = self.user.phone
        
        # Add CSS classes
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-bhoosparsh-blue focus:border-transparent'


class LeadResponseForm(forms.ModelForm):
    """Form for responding to leads"""
    response = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Type your response here...'}),
        label='Your Response'
    )
    
    class Meta:
        model = PropertyInquiry
        fields = ['response', 'status']
        widgets = {
            'status': forms.Select(attrs={'class': 'w-full p-2 border rounded'}),
        }


class PackageSelectionForm(forms.Form):
    """Form for selecting membership packages"""
    package = forms.ModelChoiceField(
        queryset=MembershipPlan.objects.filter(is_active=True),
        widget=forms.RadioSelect,
        label="Select Package"
    )
    billing_cycle = forms.ChoiceField(
        choices=[('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('yearly', 'Yearly')],
        widget=forms.RadioSelect,
        initial='monthly',
        label="Billing Cycle"
    )
    auto_renew = forms.BooleanField(
        required=False,
        initial=True,
        label="Auto Renew Subscription"
    )        

# ===================================================================
# Account Settings Forms
# ===================================================================
    
class PrivacySettingsForm(forms.ModelForm):
    """Form for privacy settings"""
    class Meta:
        model = CustomUser
        fields = ['show_phone_to', 'show_email', 'allow_calls_from', 'allow_calls_to']
        widgets = {
            'allow_calls_from': forms.TimeInput(attrs={'type': 'time'}),
            'allow_calls_to': forms.TimeInput(attrs={'type': 'time'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-bhoosparsh-blue focus:border-transparent'


class NotificationSettingsForm(forms.ModelForm):
    """Form for notification settings"""
    # Add custom fields for notification preferences
    email_leads = forms.BooleanField(
        required=False,
        initial=True,
        label='Email me when I get new leads'
    )
    email_messages = forms.BooleanField(
        required=False,
        initial=True,
        label='Email me when I get new messages'
    )
    whatsapp_leads = forms.BooleanField(
        required=False,
        initial=True,
        label='WhatsApp notification for new leads'
    )
    sms_leads = forms.BooleanField(
        required=False,
        initial=False,
        label='SMS notification for new leads'
    )
    newsletter = forms.BooleanField(
        required=False,
        initial=True,
        label='Newsletter and updates'
    )
    
    class Meta:
        model = CustomUser
        fields = ['dashboard_theme']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Initialize notification preferences
        if self.instance.notification_preferences:
            pref = self.instance.notification_preferences
            self.fields['email_leads'].initial = pref.get('email_leads', True)
            self.fields['email_messages'].initial = pref.get('email_messages', True)
            self.fields['whatsapp_leads'].initial = pref.get('whatsapp_leads', True)
            self.fields['sms_leads'].initial = pref.get('sms_leads', False)
            self.fields['newsletter'].initial = pref.get('newsletter', True)
        
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-bhoosparsh-blue focus:border-transparent'
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        # Save notification preferences
        user.notification_preferences = {
            'email_leads': self.cleaned_data.get('email_leads', True),
            'email_messages': self.cleaned_data.get('email_messages', True),
            'whatsapp_leads': self.cleaned_data.get('whatsapp_leads', True),
            'sms_leads': self.cleaned_data.get('sms_leads', False),
            'newsletter': self.cleaned_data.get('newsletter', True),
        }
        
        if commit:
            user.save()
        return user


class PasswordChangeForm(forms.Form):
    """Form for changing password"""
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Current password'}),
        label='Current Password'
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'New password'}),
        label='New Password',
        min_length=8
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm new password'}),
        label='Confirm New Password'
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-bhoosparsh-blue focus:border-transparent'
    
    def clean(self):
        cleaned_data = super().clean()
        current_password = cleaned_data.get('current_password')
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if self.user:
            # Check current password
            if not self.user.check_password(current_password):
                self.add_error('current_password', 'Current password is incorrect')
            
            # Check if new password is same as old
            if current_password and new_password and current_password == new_password:
                self.add_error('new_password', 'New password must be different from current password')
        
        # Check if passwords match
        if new_password and confirm_password and new_password != confirm_password:
            self.add_error('confirm_password', 'Passwords do not match')
        
        return cleaned_data


class AccountDeletionForm(forms.Form):
    """Form for account deletion confirmation"""
    confirm = forms.BooleanField(
        required=True,
        label='I understand that this action cannot be undone and all my data will be permanently deleted'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter your password to confirm'}),
        label='Confirm Password'
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        for field_name, field in self.fields.items():
            if field_name == 'confirm':
                field.widget.attrs['class'] = 'w-4 h-4 text-bhoosparsh-blue rounded border-gray-300 focus:ring-bhoosparsh-blue'
            else:
                field.widget.attrs['class'] = 'w-full p-3 border rounded-lg focus:ring-2 focus:ring-bhoosparsh-blue focus:border-transparent'
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        
        if self.user and password:
            if not self.user.check_password(password):
                self.add_error('password', 'Password is incorrect')
        
        return cleaned_data   