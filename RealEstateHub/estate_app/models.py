
import os
import uuid
import hashlib
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.conf import settings
from django.db.models import Q, Sum, Count, Avg
from django.core.cache import cache
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField
from builtins import property as py_property
from django.core.validators import RegexValidator
import uuid



phone_regex = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Phone number must be entered in the format: '+919876543210'. Up to 15 digits allowed."
)



class CustomUserManager(BaseUserManager):
    """Custom manager for CustomUser model"""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and return a regular user with an email and password"""
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a superuser"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_verified', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    """Enhanced Custom User Model with seller features"""
    
    USER_TYPE_CHOICES = (
        ('buyer', 'Buyer/Tenant'),
        ('seller', 'Seller/Owner'),
        ('agent', 'Agent/Broker'),
        ('builder', 'Builder/Developer'),
        ('admin', 'Administrator'),
    )
    
    SELLER_TYPE_CHOICES = (
        ('individual', 'Individual Owner'),
        ('agent', 'Real Estate Agent'),
        ('builder', 'Builder/Developer'),
        ('dealer', 'Property Dealer'),
    )
    
    # Remove username field, use email as unique identifier
    username = None
    email = models.EmailField(_('email address'), unique=True)
    
    # User type
    user_type = models.CharField(
        _('user type'),
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default='buyer'
    )
    
    # Seller specific fields
    seller_type = models.CharField(
        _('seller type'),
        max_length=20,
        choices=SELLER_TYPE_CHOICES,
        blank=True,
        null=True
    )
    
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone = models.CharField(
        _('phone number'),
        validators=[phone_regex],
        max_length=17,
        blank=True,
        null=True
    )
    
    alternate_phone = models.CharField(
        _('alternate phone'),
        validators=[phone_regex],
        max_length=17,
        blank=True,
        null=True
    )

    agency_name = models.CharField(
        _('agency name'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Real estate agency name (required for sellers and agents)')
    )
    
    # Verification documents
    pan_card = models.CharField(
        _('PAN card number'),
        max_length=20,
        blank=True,
        null=True
    )
    
    aadhar_card = models.CharField(
        _('Aadhar card number'),
        max_length=20,
        blank=True,
        null=True
    )
    
    verification_status = models.CharField(
        _('verification status'),
        max_length=20,
        choices=(
            ('basic', 'Basic'),
            ('verified', 'Verified'),
            ('premium_verified', 'Premium Verified'),
        ),
        default='basic'
    )
    
    # Privacy settings
    show_phone_to = models.CharField(
        _('show phone to'),
        max_length=20,
        choices=(
            ('everyone', 'Everyone'),
            ('premium', 'Premium Users Only'),
            ('none', 'No One'),
        ),
        default='everyone'
    )
    
    show_email = models.BooleanField(_('show email'), default=True)
    
    allow_calls_from = models.TimeField(
        _('allow calls from'),
        default=timezone.datetime.strptime('09:00', '%H:%M').time()
    )
    
    allow_calls_to = models.TimeField(
        _('allow calls to'),
        default=timezone.datetime.strptime('21:00', '%H:%M').time()
    )

    is_verified = models.BooleanField(_('verified'), default=False)
    verification_token = models.UUIDField(default=uuid.uuid4, editable=False, null=True, blank=True)
    verification_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Social login fields
    google_id = models.CharField(max_length=255, blank=True, null=True)
    facebook_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Dashboard preferences
    dashboard_theme = models.CharField(
        max_length=20,
        choices=(
            ('light', 'Light'),
            ('dark', 'Dark'),
        ),
        default='light'
    )
    
    # Notification preferences (store as JSON)
    notification_preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('User notification preferences')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Set email as the unique identifier
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    objects = CustomUserManager()
    
    class Meta:
        db_table = 'core_customuser'
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['user_type']),
            models.Index(fields=['seller_type']),
            models.Index(fields=['is_verified']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.email} ({self.get_user_type_display()})"
    
    @property
    def full_name(self):
        """Return the full name of the user"""
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('user_profile', kwargs={'pk': self.pk})
    
    def can_list_properties(self):
        """Check if user can list properties based on user type"""
        return self.user_type in ['seller', 'agent', 'builder']
    
    def is_premium_user(self):
        """Check if user has active premium membership"""
        try:
            membership = self.membership  # Changed from usermembership
            return membership.is_active and membership.plan.is_popular
        except UserMembership.DoesNotExist:
            return False
    
    def get_dashboard_stats(self):
        """Get user dashboard statistics"""
        from django.db.models import Count, Sum
        from django.utils import timezone
        from datetime import timedelta
        
        # Calculate date ranges
        today = timezone.now().date()
        last_7_days = today - timedelta(days=7)
        
        # Get user's properties
        properties = self.properties.all()
        active_properties = properties.filter(is_active=True)
        
        # Calculate total views (last 7 days)
        total_views = PropertyView.objects.filter(
            property__in=active_properties,
            viewed_at__date__gte=last_7_days
        ).count()
        
        # Calculate total leads (last 7 days)
        total_leads = PropertyInquiry.objects.filter(
            property_link__in=active_properties,
            created_at__date__gte=last_7_days
        ).count()
        
        # Calculate response rate
        responded_leads = PropertyInquiry.objects.filter(
            property_link__in=active_properties,
            response__isnull=False
        ).count()
        
        total_leads_all_time = PropertyInquiry.objects.filter(
            property_link__in=active_properties
        ).count()
        
        response_rate = (responded_leads / total_leads_all_time * 100) if total_leads_all_time > 0 else 0
        
        # Get package info
        try:
            membership = self.membership
            plan = membership.plan
            listings_used = membership.listings_used
            listings_limit = plan.max_active_listings if not plan.is_unlimited else "Unlimited"
            featured_used = membership.featured_used_this_month
            featured_limit = plan.max_featured_listings
        except UserMembership.DoesNotExist:
            plan = None
            listings_used = 0
            listings_limit = 0
            featured_used = 0
            featured_limit = 0
        
        return {
            'active_ads': active_properties.count(),
            'total_views': total_views,
            'total_leads': total_leads,
            'response_rate': round(response_rate, 1),
            'package': plan.name if plan else 'No Package',
            'listings_used': listings_used,
            'listings_limit': listings_limit,
            'featured_used': featured_used,
            'featured_limit': featured_limit,
        }


class UserProfile(models.Model):
    """Extended user profile information"""
    
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name=_('user')
    )
    
    avatar = models.ImageField(
        _('profile picture'),
        upload_to='avatars/',
        blank=True,
        null=True,
        help_text=_('Recommended size: 300x300 pixels')
    )
    
    bio = models.TextField(
        _('biography'),
        max_length=1000,
        blank=True,
        help_text=_('Tell us about yourself (max 1000 characters)')
    )
    
    agency_logo = models.ImageField(
        _('agency logo'),
        upload_to='agency_logos/',
        blank=True,
        null=True
    )
    
    license = models.CharField(
        _('real estate license'),
        max_length=100,
        blank=True,
        null=True,
        help_text=_('Your professional license number')
    )
    
    # Contact Information
    whatsapp_number = models.CharField(
        max_length=17,
        blank=True,
        null=True,
        help_text=_('WhatsApp number for quick contact')
    )
    
    website = models.URLField(
        _('website'),
        blank=True,
        null=True,
        help_text=_('Your professional website')
    )
    
    # Social Media Links
    facebook = models.URLField(blank=True, null=True)
    twitter = models.URLField(blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    
    # Address Information
    address = models.TextField(_('address'), blank=True, null=True)
    city = models.CharField(_('city'), max_length=100, blank=True, null=True)
    state = models.CharField(_('state'), max_length=100, blank=True, null=True)
    country = models.CharField(_('country'), max_length=100, blank=True, null=True)
    pincode = models.CharField(_('pincode'), max_length=10, blank=True, null=True)
    
    # Professional Details (for agents/sellers)
    experience_years = models.PositiveIntegerField(
        _('years of experience'),
        default=0,
        validators=[MaxValueValidator(50)]
    )
    
    specialization = models.CharField(
        _('specialization'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('E.g., Residential, Commercial, Luxury Homes')
    )
    
    languages = models.CharField(
        _('languages spoken'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Comma-separated list of languages')
    )
    
    # Verification
    is_verified_agent = models.BooleanField(_('verified agent'), default=False)
    verification_documents = models.FileField(
        upload_to='agent_docs/',
        blank=True,
        null=True,
        help_text=_('Upload license/document for verification')
    )
    
    # Statistics (automatically updated)
    total_listings = models.PositiveIntegerField(_('total listings'), default=0)
    total_sales = models.PositiveIntegerField(_('total sales'), default=0)
    success_rate = models.DecimalField(
        _('success rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Percentage of successful deals')
    )
    
    agency_name = models.CharField(
        _('agency name'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Real estate agency name (required for sellers and agents)')
    )
    
    # Performance metrics
    avg_response_time = models.DurationField(
        _('average response time'),
        blank=True,
        null=True
    )
    
    total_clicks = models.PositiveIntegerField(_('total clicks'), default=0)
    total_calls = models.PositiveIntegerField(_('total calls'), default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_userprofile'
        verbose_name = _('user profile')
        verbose_name_plural = _('user profiles')
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['is_verified_agent']),
            models.Index(fields=['city', 'state']),
        ]
    
    def __str__(self):
        return f"Profile of {self.user.email}"
    
    def save(self, *args, **kwargs):
        """Override save to update user type if agency details are provided"""
        if self.agency_name or self.license:
            self.user.user_type = 'agent'
            # Save user without triggering signals to avoid recursion
            super(CustomUser, self.user).save(update_fields=['user_type'])
        super().save(*args, **kwargs)
    
    @property
    def display_name(self):
        """Return display name with agency if available"""
        if self.agency_name:
            return f"{self.user.full_name} - {self.agency_name}"
        return self.user.full_name
    
    @property
    def is_complete(self):
        """Check if profile is complete for agents/sellers"""
        if self.user.user_type in ['agent', 'seller', 'builder']:
            required_fields = ['phone', 'city', 'address']
            for field in required_fields:
                if not getattr(self.user if field == 'phone' else self, field):
                    return False
        return True
    
# ====================================================================
# Membership and Subscription Models
# ====================================================================

class MembershipPlan(models.Model):
    """Membership plan for sellers/agents"""
    PLAN_TYPES = (
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    )
    
    name = models.CharField(_('plan name'), max_length=50)
    slug = models.SlugField(_('slug'), unique=True)
    description = models.TextField(_('description'), blank=True)
    plan_type = models.CharField(_('plan type'), max_length=20, choices=PLAN_TYPES, default='basic')
    
    # Pricing
    price = models.DecimalField(_('price'), max_digits=10, decimal_places=2, default=0.00)
    billing_cycle = models.CharField(
        _('billing cycle'),
        max_length=20,
        choices=(
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('yearly', 'Yearly'),
        ),
        default='monthly'
    )
    
    # Features
    max_listings = models.IntegerField(_('maximum listings'), default=1)
    max_featured = models.IntegerField(_('maximum featured listings'), default=0)
    max_active_listings = models.IntegerField(_('maximum active listings'), default=1)
    
    # Boost features
    has_spotlight_boost = models.BooleanField(_('has spotlight boost'), default=False)
    has_featured_listings = models.BooleanField(_('has featured listings'), default=False)
    has_urgent_tag = models.BooleanField(_('has urgent tag'), default=False)
    has_photo_highlight = models.BooleanField(_('has photo highlight'), default=False)
    
    # Contact features
    show_contact_details = models.BooleanField(_('show contact details'), default=False)
    whatsapp_notifications = models.BooleanField(_('whatsapp notifications'), default=False)
    sms_notifications = models.BooleanField(_('sms notifications'), default=False)
    
    # Support
    priority_support = models.BooleanField(_('priority support'), default=False)
    dedicated_manager = models.BooleanField(_('dedicated manager'), default=False)
    analytics_dashboard = models.BooleanField(_('analytics dashboard'), default=False)
    
    # Status
    is_active = models.BooleanField(_('active'), default=True)
    is_popular = models.BooleanField(_('popular'), default=False)
    is_unlimited = models.BooleanField(_('unlimited'), default=False)
    
    # Display order
    display_order = models.IntegerField(_('display order'), default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_membershipplan'
        verbose_name = _('membership plan')
        verbose_name_plural = _('membership plans')
        ordering = ['display_order', 'price']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['plan_type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['price']),
        ]
    
    def __str__(self):
        return f"{self.name} - ₹{self.price}/month"
    
    @property
    def monthly_price(self):
        """Calculate monthly price based on billing cycle"""
        if self.billing_cycle == 'monthly':
            return self.price
        elif self.billing_cycle == 'quarterly':
            return self.price / 3
        elif self.billing_cycle == 'yearly':
            return self.price / 12
        return self.price
    
    @property
    def yearly_price(self):
        """Calculate yearly price"""
        if self.billing_cycle == 'monthly':
            return self.price * 12
        elif self.billing_cycle == 'quarterly':
            return self.price * 4
        elif self.billing_cycle == 'yearly':
            return self.price
        return self.price * 12


class UserMembership(models.Model):
    """User membership subscription"""
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('pending', 'Pending'),
    )
    
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='membership',
        verbose_name=_('user')
    )
    plan = models.ForeignKey(
        MembershipPlan,
        on_delete=models.SET_NULL,
        null=True,
        related_name='users',
        verbose_name=_('membership plan')
    )
    
    # Subscription details
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    starts_at = models.DateTimeField(_('starts at'), default=timezone.now)
    expires_at = models.DateTimeField(_('expires at'), null=True, blank=True)
    
    # Payment details
    subscription_id = models.CharField(_('subscription ID'), max_length=255, blank=True, null=True)
    payment_method = models.CharField(_('payment method'), max_length=50, blank=True, null=True)
    
    # Usage tracking
    listings_used = models.IntegerField(_('listings used'), default=0)
    featured_used = models.IntegerField(_('featured listings used'), default=0)
    boosts_used = models.IntegerField(_('boosts used'), default=0)
    
    # Renewal settings
    auto_renew = models.BooleanField(_('auto renew'), default=True)
    renews_at = models.DateTimeField(_('renews at'), null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_usermembership'
        verbose_name = _('user membership')
        verbose_name_plural = _('user memberships')
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['status']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.plan.name if self.plan else 'No Plan'}"
    
    @property
    def is_active(self):
        """Check if membership is currently active"""
        if self.status != 'active':
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True
    
    @property
    def days_until_expiry(self):
        """Calculate days until expiry"""
        if not self.expires_at:
            return None
        delta = self.expires_at - timezone.now()
        return delta.days if delta.days > 0 else 0
    
    @property
    def listings_remaining(self):
        """Calculate remaining listings"""
        if not self.plan:
            return 0
        if self.plan.is_unlimited:
            return 999  # Large number for unlimited
        return max(0, self.plan.max_listings - self.listings_used)
    
    @property
    def featured_remaining(self):
        """Calculate remaining featured listings"""
        if not self.plan:
            return 0
        return max(0, self.plan.max_featured - self.featured_used)
    
    def can_create_listing(self):
        """Check if user can create a new listing"""
        if not self.plan:
            return False
        if self.plan.is_unlimited:
            return True
        return self.listings_used < self.plan.max_listings
    
    def can_feature_listing(self):
        """Check if user can feature a listing"""
        if not self.plan:
            return False
        return self.featured_used < self.plan.max_featured   




# ====================================================================
# Property Category and Type Models
# ====================================================================

class PropertyCategory(models.Model):
    """Property categories like Residential, Commercial, etc."""
    name = models.CharField(_('category name'), max_length=100)
    slug = models.SlugField(_('slug'), unique=True)
    icon = models.CharField(_('icon'), max_length=50, help_text=_('FontAwesome icon class'))
    description = models.TextField(_('description'), blank=True)
    is_active = models.BooleanField(_('active'), default=True)
    display_order = models.IntegerField(_('display order'), default=0)
    
    
    class Meta:
        db_table = 'core_propertycategory'
        verbose_name = _('property category')
        verbose_name_plural = _('property categories')
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class PropertyType(models.Model):
    """Property types like Apartment, Villa, Office, etc."""
    category = models.ForeignKey(PropertyCategory, on_delete=models.CASCADE, related_name='types')
    name = models.CharField(_('type name'), max_length=100)
    slug = models.SlugField(_('slug'), unique=True)
    description = models.TextField(_('description'), blank=True)
    is_active = models.BooleanField(_('active'), default=True)
    
    class Meta:
        db_table = 'core_propertytype'
        verbose_name = _('property type')
        verbose_name_plural = _('property types')
        ordering = ['category', 'name']
        unique_together = ['category', 'name']
    
    def __str__(self):
        return f"{self.category.name} - {self.name}"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.category.name}-{self.name}")
        super().save(*args, **kwargs)


class Property(models.Model):
    """Main Property Model"""
    PROPERTY_FOR_CHOICES = (
        ('sale', 'For Sale'),
        ('rent', 'For Rent'),
        ('pg', 'PG/Hostel'),
        ('plot', 'Plot/Land'),
    )
    
    FURNISHING_CHOICES = (
        ('furnished', 'Fully Furnished'),
        ('semi_furnished', 'Semi Furnished'),
        ('unfurnished', 'Unfurnished'),
    )
    
    LISTING_TYPE_CHOICES = (
        ('basic', 'Basic Listing'),
        ('featured', 'Featured Listing'),
        ('premium', 'Premium Listing'),
    )
    
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('sold', 'Sold/Rented'),
        ('rejected', 'Rejected'),
    )
    
    # Basic Information
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='properties')
    property_id = models.CharField(_('property ID'), max_length=20, unique=True, default=uuid.uuid4().hex[:8].upper())
    
    # Category and Type
    category = models.ForeignKey(PropertyCategory, on_delete=models.SET_NULL, null=True, related_name='properties')
    property_type = models.ForeignKey(PropertyType, on_delete=models.SET_NULL, null=True, related_name='properties')
    
    # Basic Details
    title = models.CharField(_('property title'), max_length=200)
    description = models.TextField(_('description'))
    slug = models.SlugField(_('slug'), max_length=250, unique=True, blank=True)
    
    # Property For
    property_for = models.CharField(_('property for'), max_length=20, choices=PROPERTY_FOR_CHOICES)
    listing_type = models.CharField(_('listing type'), max_length=20, choices=LISTING_TYPE_CHOICES, default='basic')
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Location Details
    address = models.TextField(_('complete address'))
    city = models.CharField(_('city'), max_length=100)
    state = models.CharField(_('state'), max_length=100)
    country = CountryField(_('country'), default='IN')
    pincode = models.CharField(_('pincode'), max_length=10)
    locality = models.CharField(_('locality/area'), max_length=200, blank=True)
    landmark = models.CharField(_('landmark'), max_length=200, blank=True)
    
    # Google Maps
    latitude = models.DecimalField(_('latitude'), max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(_('longitude'), max_digits=11, decimal_places=8, null=True, blank=True)
    google_map_url = models.URLField(_('google map URL'), blank=True)
    
    # Pricing
    price = models.DecimalField(_('price'), max_digits=15, decimal_places=2)
    price_per_sqft = models.DecimalField(_('price per sqft'), max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(_('currency'), max_length=3, default='INR')
    maintenance_charges = models.DecimalField(_('maintenance charges'), max_digits=10, decimal_places=2, null=True, blank=True)
    booking_amount = models.DecimalField(_('booking amount'), max_digits=10, decimal_places=2, null=True, blank=True)
    price_negotiable = models.BooleanField(_('price negotiable'), default=False)
    
    # Area Details
    carpet_area = models.DecimalField(_('carpet area'), max_digits=10, decimal_places=2, help_text=_('in sq.ft.'))
    builtup_area = models.DecimalField(_('builtup area'), max_digits=10, decimal_places=2, null=True, blank=True, help_text=_('in sq.ft.'))
    super_builtup_area = models.DecimalField(_('super builtup area'), max_digits=10, decimal_places=2, null=True, blank=True, help_text=_('in sq.ft.'))
    plot_area = models.DecimalField(_('plot area'), max_digits=10, decimal_places=2, null=True, blank=True, help_text=_('in sq.ft.'))
    
    # Residential Specific
    bedrooms = models.IntegerField(_('bedrooms'), null=True, blank=True)
    bathrooms = models.IntegerField(_('bathrooms'), null=True, blank=True)
    balconies = models.IntegerField(_('balconies'), default=0)
    
    # Commercial Specific
    commercial_type = models.CharField(_('commercial type'), max_length=50, blank=True, 
                                      choices=(('office', 'Office Space'), ('shop', 'Shop/Retail'), 
                                              ('warehouse', 'Warehouse/Industrial'), ('other', 'Other')))
    floor_number = models.IntegerField(_('floor number'), null=True, blank=True)
    total_floors = models.IntegerField(_('total floors'), null=True, blank=True)
    
    # Industrial Specific
    industrial_type = models.CharField(_('industrial type'), max_length=50, blank=True,
                                      choices=(('manufacturing', 'Manufacturing Unit'), ('storage', 'Storage/Warehouse'),
                                              ('factory', 'Factory'), ('other', 'Other')))
    ceiling_height = models.DecimalField(_('ceiling height'), max_digits=6, decimal_places=2, null=True, blank=True)
    loading_dock = models.BooleanField(_('loading dock'), default=False)
    power_supply = models.CharField(_('power supply'), max_length=100, blank=True)
    
    # Plot/Land Specific
    plot_type = models.CharField(_('plot type'), max_length=50, blank=True,
                                choices=(('residential', 'Residential Plot'), ('commercial', 'Commercial Plot'),
                                        ('agricultural', 'Agricultural Land'), ('industrial', 'Industrial Plot')))
    facing = models.CharField(_('facing'), max_length=50, blank=True,
                             choices=(('east', 'East'), ('west', 'West'), ('north', 'North'), ('south', 'South'),
                                     ('north-east', 'North-East'), ('north-west', 'North-West'),
                                     ('south-east', 'South-East'), ('south-west', 'South-West')))
    
    # Features
    furnishing = models.CharField(_('furnishing'), max_length=20, choices=FURNISHING_CHOICES, blank=True)
    age_of_property = models.CharField(_('age of property'), max_length=50, blank=True)
    possession_status = models.CharField(_('possession status'), max_length=100, blank=True)
    
    # Amenities (Store as JSON)
    amenities = models.JSONField(_('amenities'), default=dict, blank=True)
    
    # Images
    primary_image = models.ImageField(_('primary image'), upload_to='properties/primary/')
    
    # Contact Information
    contact_person = models.CharField(_('contact person'), max_length=100)
    contact_phone = models.CharField(_('contact phone'), max_length=17, validators=[phone_regex])
    contact_email = models.EmailField(_('contact email'), blank=True)
    show_contact = models.BooleanField(_('show contact details'), default=True)
    
    # Boost Features
    is_featured = models.BooleanField(_('featured listing'), default=False)
    is_urgent = models.BooleanField(_('urgent sale'), default=False)
    is_premium = models.BooleanField(_('premium listing'), default=False)
    is_verified = models.BooleanField(_('verified property'), default=False)
    
    # Stats
    view_count = models.PositiveIntegerField(_('view count'), default=0)
    inquiry_count = models.PositiveIntegerField(_('inquiry count'), default=0)
    favorite_count = models.PositiveIntegerField(_('favorite count'), default=0)
    
    # SEO
    meta_title = models.CharField(_('meta title'), max_length=200, blank=True)
    meta_description = models.TextField(_('meta description'), blank=True)
    meta_keywords = models.TextField(_('meta keywords'), blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'core_property'
        verbose_name = _('property')
        verbose_name_plural = _('properties')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status']),
            models.Index(fields=['property_for']),
            models.Index(fields=['city', 'state']),
            models.Index(fields=['price']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.property_id}"
    
    @property
    def is_active(self):
        """Check if property is active"""
        return self.status == 'active'
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f"{self.title}-{self.property_id}")
            self.slug = base_slug
            
            # Ensure uniqueness
            counter = 1
            while Property.objects.filter(slug=self.slug).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        
        # Auto-generate price per sqft
        if self.carpet_area and self.price and not self.price_per_sqft:
            self.price_per_sqft = self.price / self.carpet_area
        
        # Set published date when status changes to active
        if self.status == 'active' and not self.published_at:
            self.published_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    @property
    def is_active(self):
        return self.status == 'active'
    
    @property
    def location(self):
        return f"{self.city}, {self.state}"
    
    @property
    def formatted_price(self):
        if self.currency == 'INR':
            return f"₹{self.price:,.0f}"
        return f"{self.currency} {self.price:,.2f}"
    
    @property
    def price_with_unit(self):
        if self.property_for in ['rent', 'pg']:
            return f"{self.formatted_price}/month"
        return self.formatted_price
    
    @property
    def short_description(self):
        return self.description[:150] + '...' if len(self.description) > 150 else self.description
    
    def get_absolute_url(self):
        return reverse('property_detail', kwargs={'slug': self.slug})
    
    def increment_view_count(self):
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    def get_similar_properties(self, limit=4):
        """Get similar properties in same area/price range"""
        return Property.objects.filter(
            Q(city=self.city) | Q(property_type=self.property_type),
            status='active',
            property_for=self.property_for
        ).exclude(id=self.id).order_by('-created_at')[:limit]


class PropertyImage(models.Model):
    """Property images gallery"""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(_('image'), upload_to='properties/gallery/')
    caption = models.CharField(_('caption'), max_length=200, blank=True)
    is_primary = models.BooleanField(_('primary image'), default=False)
    display_order = models.IntegerField(_('display order'), default=0)
    
    class Meta:
        db_table = 'core_propertyimage'
        verbose_name = _('property image')
        verbose_name_plural = _('property images')
        ordering = ['display_order', '-is_primary']
    
    def __str__(self):
        return f"Image for {self.property.title}"
    
    def save(self, *args, **kwargs):
        # If this is set as primary, unset primary for other images
        if self.is_primary:
            PropertyImage.objects.filter(property=self.property, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)


class PropertyInquiry(models.Model):
    """Property inquiries/leads from buyers"""
    STATUS_CHOICES = (
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('interested', 'Interested'),
        ('not_interested', 'Not Interested'),
        ('converted', 'Converted'),
        ('spam', 'Spam'),
    )
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='inquiries')
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='inquiries')
    
    # Lead Information
    name = models.CharField(_('name'), max_length=100)
    email = models.EmailField(_('email'))
    phone = models.CharField(_('phone'), max_length=17, validators=[phone_regex])
    message = models.TextField(_('message'))
    
    # Additional Info
    budget = models.DecimalField(_('budget'), max_digits=15, decimal_places=2, null=True, blank=True)
    preferred_date = models.DateField(_('preferred date'), null=True, blank=True)
    preferred_time = models.TimeField(_('preferred time'), null=True, blank=True)
    
    # Status
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='new')
    priority = models.IntegerField(_('priority'), default=1, 
                                   validators=[MinValueValidator(1), MaxValueValidator(5)])
    
    # Agent/Seller Response
    response = models.TextField(_('response'), blank=True)
    responded_at = models.DateTimeField(_('responded at'), null=True, blank=True)
    responded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, 
                                     related_name='responded_inquiries')
    
    # Source
    source = models.CharField(_('source'), max_length=50, default='website',
                             choices=(('website', 'Website Form'), ('phone', 'Phone Call'),
                                     ('whatsapp', 'WhatsApp'), ('email', 'Email'),
                                     ('walkin', 'Walk-in')))
    
    # Metadata
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    user_agent = models.TextField(_('user agent'), blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_propertyinquiry'
        verbose_name = _('property inquiry')
        verbose_name_plural = _('property inquiries')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['property']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Inquiry from {self.name} for {self.property.title}"
    
    def save(self, *args, **kwargs):
        # Increment property inquiry count
        if self.pk is None:  # New inquiry
            self.property.inquiry_count += 1
            self.property.save(update_fields=['inquiry_count'])
        super().save(*args, **kwargs)
    
    def mark_as_responded(self, response_text, user):
        self.response = response_text
        self.responded_at = timezone.now()
        self.responded_by = user
        self.status = 'contacted'
        self.save()
    
    @py_property
    def is_new(self):
        return self.status == 'new'
    
    @py_property
    def time_since_created(self):
        return timezone.now() - self.created_at


class PropertyView(models.Model):
    """Track property views"""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(_('IP address'))
    user_agent = models.TextField(_('user agent'), blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'core_propertyview'
        verbose_name = _('property view')
        verbose_name_plural = _('property views')
        indexes = [
            models.Index(fields=['property', 'viewed_at']),
        ]
    
    def __str__(self):
        return f"View of {self.property.title} at {self.viewed_at}"    
    
# models.py - Add these for buyer-specific features
class BuyerProfile(models.Model):
    """Extended buyer profile information"""
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='buyer_profile',
        verbose_name=_('buyer profile')
    )
    
    # Budget preferences
    min_budget = models.DecimalField(
        _('minimum budget'),
        max_digits=15,
        decimal_places=2,
        default=0.00,
        help_text=_('Minimum property budget in INR')
    )
    
    max_budget = models.DecimalField(
        _('maximum budget'),
        max_digits=15,
        decimal_places=2,
        default=100000000.00,
        help_text=_('Maximum property budget in INR')
    )
    
    # Property preferences
    preferred_property_types = models.ManyToManyField(
        PropertyType,
        blank=True,
        verbose_name=_('preferred property types')
    )
    
    preferred_locations = models.JSONField(
        _('preferred locations'),
        default=list,
        blank=True,
        help_text=_('Preferred cities/locations for property search')
    )
    
    # Requirements
    min_bedrooms = models.IntegerField(
        _('minimum bedrooms'),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    
    min_bathrooms = models.IntegerField(
        _('minimum bathrooms'),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    
    min_area = models.DecimalField(
        _('minimum area'),
        max_digits=10,
        decimal_places=2,
        default=500.00,
        help_text=_('Minimum carpet area in sq.ft.')
    )
    
    max_area = models.DecimalField(
        _('maximum area'),
        max_digits=10,
        decimal_places=2,
        default=5000.00,
        help_text=_('Maximum carpet area in sq.ft.')
    )
    
    # Additional preferences
    furnishing_preference = models.CharField(
        _('furnishing preference'),
        max_length=20,
        choices=Property.FURNISHING_CHOICES,
        blank=True,
        null=True
    )
    
    possession_preference = models.CharField(
        _('possession preference'),
        max_length=50,
        choices=(
            ('ready', 'Ready to Move'),
            ('under_construction', 'Under Construction'),
            ('any', 'Any'),
        ),
        default='any'
    )
    
    # Property for (sale/rent)
    property_for = models.CharField(
        _('property for'),
        max_length=20,
        choices=Property.PROPERTY_FOR_CHOICES,
        default='sale'
    )
    
    # Amenities preferences (store as JSON)
    preferred_amenities = models.JSONField(
        _('preferred amenities'),
        default=list,
        blank=True
    )
    
    # Search preferences
    receive_notifications = models.BooleanField(
        _('receive notifications'),
        default=True,
        help_text=_('Receive email notifications for new properties')
    )
    
    notification_frequency = models.CharField(
        _('notification frequency'),
        max_length=20,
        choices=(
            ('immediate', 'Immediate'),
            ('daily', 'Daily Digest'),
            ('weekly', 'Weekly Digest'),
        ),
        default='daily'
    )
    
    # Statistics
    total_searches = models.PositiveIntegerField(_('total searches'), default=0)
    properties_viewed = models.PositiveIntegerField(_('properties viewed'), default=0)
    properties_saved = models.PositiveIntegerField(_('properties saved'), default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_buyerprofile'
        verbose_name = _('buyer profile')
        verbose_name_plural = _('buyer profiles')
    
    def __str__(self):
        return f"Buyer Profile: {self.user.email}"
    
    @property
    def budget_range(self):
        """Get formatted budget range"""
        return f"₹{self.min_budget:,.0f} - ₹{self.max_budget:,.0f}"
    
    @property
    def area_range(self):
        """Get formatted area range"""
        return f"{self.min_area:,.0f} - {self.max_area:,.0f} sq.ft."


class PropertyFavorite(models.Model):
    """Properties saved/favorited by buyers"""
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name=_('user')
    )
    
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='favorited_by',
        verbose_name=_('property')
    )
    
    # Additional info
    notes = models.TextField(_('notes'), blank=True)
    priority = models.IntegerField(
        _('priority'),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_('Priority level (1-5)')
    )
    
    # Status
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=(
            ('interested', 'Interested'),
            ('shortlisted', 'Shortlisted'),
            ('view_scheduled', 'View Scheduled'),
            ('offered', 'Offer Made'),
            ('not_interested', 'Not Interested'),
        ),
        default='interested'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_propertyfavorite'
        verbose_name = _('property favorite')
        verbose_name_plural = _('property favorites')
        unique_together = ['user', 'property']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} favorited {self.property.title}"


class PropertyComparison(models.Model):
    """Property comparison lists for buyers"""
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='comparisons',
        verbose_name=_('user')
    )
    
    name = models.CharField(_('comparison name'), max_length=100)
    properties = models.ManyToManyField(
        Property,
        related_name='in_comparisons',
        verbose_name=_('properties'),
        blank=True
    )
    
    # Settings
    is_shared = models.BooleanField(_('shared'), default=False)
    share_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_propertycomparison'
        verbose_name = _('property comparison')
        verbose_name_plural = _('property comparisons')
    
    def __str__(self):
        return f"{self.name} - {self.user.email}"


class SiteVisit(models.Model):
    """Site visit scheduling"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rescheduled', 'Rescheduled'),
    )
    
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='site_visits',
        verbose_name=_('property')
    )
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='site_visits',
        verbose_name=_('user')
    )
    
    # Visit details
    scheduled_date = models.DateField(_('scheduled date'))
    scheduled_time = models.TimeField(_('scheduled time'))
    duration_minutes = models.IntegerField(
        _('duration (minutes)'),
        default=60,
        validators=[MinValueValidator(15), MaxValueValidator(240)]
    )
    
    # Contact person
    contact_person = models.CharField(_('contact person'), max_length=100)
    contact_phone = models.CharField(_('contact phone'), max_length=17, validators=[phone_regex])
    
    # Status and notes
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(_('notes'), blank=True)
    feedback = models.TextField(_('feedback'), blank=True)
    
    # Agent/owner response
    response = models.TextField(_('response'), blank=True)
    responded_at = models.DateTimeField(_('responded at'), null=True, blank=True)
    
    # Reminders
    reminder_sent = models.BooleanField(_('reminder sent'), default=False)
    reminder_sent_at = models.DateTimeField(_('reminder sent at'), null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_sitevisit'
        verbose_name = _('site visit')
        verbose_name_plural = _('site visits')
        ordering = ['scheduled_date', 'scheduled_time']
    
    def __str__(self):
        return f"Site visit for {self.property.title} on {self.scheduled_date}"
    
    @py_property
    def is_upcoming(self):
        """Check if visit is upcoming"""
        visit_datetime = timezone.make_aware(
            datetime.combine(self.scheduled_date, self.scheduled_time)
        )
        return visit_datetime > timezone.now() and self.status == 'confirmed'
    
    @py_property
    def is_today(self):
        """Check if visit is today"""
        return self.scheduled_date == timezone.now().date()    