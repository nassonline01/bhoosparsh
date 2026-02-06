
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
    
    def update_performance_metrics(self):
        """Update performance metrics"""
        from django.db.models import Avg
        from django.utils import timezone
        from datetime import timedelta
        
        # Calculate average response time
        last_30_days = timezone.now() - timedelta(days=30)
        inquiries = PropertyInquiry.objects.filter(
            property_link__owner=self.user,
            created_at__gte=last_30_days,
            responded_at__isnull=False
        )
        
        if inquiries.exists():
            avg_response = inquiries.aggregate(
                avg_response=Avg(models.F('responded_at') - models.F('created_at'))
            )['avg_response']
            self.avg_response_time = avg_response
        
        # Calculate total calls (simplified)
        self.total_calls = PropertyInquiry.objects.filter(
            property_link__owner=self.user,
            contact_method='phone'
        ).count()
        
        self.save()

# =======================================================================
#  Property Models
# =======================================================================


# =======================================================================
#  Enhanced Property Models (Updated)
# =======================================================================
class PropertyCategory(models.Model):
    """Main property categories like 99acres"""
    
    PROPERTY_TYPES = (
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('industrial', 'Industrial'),
        ('land', 'Plots/Land'),
        ('agricultural', 'Agricultural'),
        ('pg_co-living', 'PG/Co-Living'),
    )
    
    name = models.CharField(_('Category Name'), max_length=100, unique=True)
    slug = models.SlugField(_('Slug'), max_length=100, unique=True)
    property_type = models.CharField(_('Property Type'), max_length=20, choices=PROPERTY_TYPES)
    icon = models.CharField(_('Icon'), max_length=50, blank=True)
    description = models.TextField(_('Description'), blank=True)
    display_order = models.IntegerField(_('Display Order'), default=0)
    is_active = models.BooleanField(_('Active'), default=True)
    
    # Field configuration for dynamic forms
    has_bedrooms = models.BooleanField(_('Has Bedrooms'), default=False)
    has_bathrooms = models.BooleanField(_('Has Bathrooms'), default=False)
    has_balconies = models.BooleanField(_('Has Balconies'), default=False)
    has_area = models.BooleanField(_('Has Area'), default=True)
    has_floor = models.BooleanField(_('Has Floor Number'), default=False)
    has_furnishing = models.BooleanField(_('Has Furnishing'), default=False)
    has_parking = models.BooleanField(_('Has Parking'), default=True)
    has_age = models.BooleanField(_('Has Age'), default=False)
    has_facing = models.BooleanField(_('Has Facing'), default=False)
    has_dimensions = models.BooleanField(_('Has Dimensions'), default=False)
    has_pantry = models.BooleanField(_('Has Pantry'), default=False)
    has_conference_room = models.BooleanField(_('Has Conference Room'), default=False)
    has_washrooms = models.BooleanField(_('Has Washrooms'), default=False)
    has_power_backup = models.BooleanField(_('Has Power Backup'), default=False)
    has_clear_height = models.BooleanField(_('Has Clear Height'), default=False)
    has_floor_loading = models.BooleanField(_('Has Floor Loading'), default=False)
    has_soil_type = models.BooleanField(_('Has Soil Type'), default=False)
    has_irrigation = models.BooleanField(_('Has Irrigation'), default=False)
    has_crops = models.BooleanField(_('Has Crops'), default=False)
    
    class Meta:
        verbose_name = _('Property Category')
        verbose_name_plural = _('Property Categories')
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_property_type_display()})"
    
    def get_subcategories(self):
        return self.subcategories.filter(is_active=True)


class PropertySubCategory(models.Model):
    """Property subcategories like Apartment, Villa, Office, Shop, etc."""
    
    category = models.ForeignKey(PropertyCategory, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(_('Subcategory Name'), max_length=100)
    slug = models.SlugField(_('Slug'), max_length=100, unique=True)
    icon = models.CharField(_('Icon'), max_length=50, blank=True)
    description = models.TextField(_('Description'), blank=True)
    display_order = models.IntegerField(_('Display Order'), default=0)
    is_active = models.BooleanField(_('Active'), default=True)
    
    class Meta:
        verbose_name = _('Property Subcategory')
        verbose_name_plural = _('Property Subcategories')
        ordering = ['display_order', 'name']
        unique_together = ['category', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.category.name})"


class Property(models.Model):
    """Main Property Model - Enhanced for 99acres style"""
    
    # Listing Types
    LISTING_TYPES = (
        ('sale', 'For Sale'),
        ('rent', 'For Rent'),
        ('lease', 'For Lease'),
        ('pg', 'PG/Co-Living'),
    )
    
    # Property Status
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('pending', 'Pending Review'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('sold', 'Sold'),
        ('rented', 'Rented'),
        ('expired', 'Expired'),
        ('archived', 'Archived'),
    )
    
    # Furnishing Options
    FURNISHING_CHOICES = (
        ('furnished', 'Fully Furnished'),
        ('semi_furnished', 'Semi Furnished'),
        ('unfurnished', 'Unfurnished'),
    )
    
    # Facing Directions
    FACING_CHOICES = (
        ('north', 'North'),
        ('south', 'South'),
        ('east', 'East'),
        ('west', 'West'),
        ('north_east', 'North-East'),
        ('north_west', 'North-West'),
        ('south_east', 'South-East'),
        ('south_west', 'South-West'),
    )
    
    # Age of Property
    AGE_CHOICES = (
        ('new', 'New Construction'),
        ('under_construction', 'Under Construction'),
        ('0-1', 'Less than 1 year'),
        ('1-5', '1-5 years'),
        ('5-10', '5-10 years'),
        ('10+', 'More than 10 years'),
    )
    
    # Possession Status
    POSSESSION_CHOICES = (
        ('ready_to_move', 'Ready to Move'),
        ('under_construction', 'Under Construction'),
        ('resale', 'Resale'),
        ('new_booking', 'New Booking'),
    )
    
    # Ownership Types
    OWNERSHIP_CHOICES = (
        ('freehold', 'Freehold'),
        ('leasehold', 'Leasehold'),
        ('cooperative', 'Cooperative Society'),
        ('power_of_attorney', 'Power of Attorney'),
    )
    
    # Power Backup Types
    POWER_BACKUP_CHOICES = (
        ('inverter', 'Inverter'),
        ('dg_set', 'DG Set'),
        ('both', 'Both'),
        ('none', 'None'),
    )
    
    # Soil Types (for agricultural)
    SOIL_TYPE_CHOICES = (
        ('black', 'Black Soil'),
        ('red', 'Red Soil'),
        ('laterite', 'Laterite Soil'),
        ('alluvial', 'Alluvial Soil'),
        ('mountain', 'Mountain Soil'),
        ('desert', 'Desert Soil'),
    )
    
    # Basic Information
    ref_id = models.CharField(_('Reference ID'), max_length=20, unique=True, editable=False)
    title = models.CharField(_('Property Title'), max_length=255)
    slug = models.SlugField(_('Slug'), max_length=300, unique=True)
    description = models.TextField(_('Description'))
    listing_type = models.CharField(_('Listing Type'), max_length=10, choices=LISTING_TYPES, default='sale')
    
    # Category Information
    category = models.ForeignKey(PropertyCategory, on_delete=models.PROTECT, related_name='properties')
    subcategory = models.ForeignKey(PropertySubCategory, on_delete=models.PROTECT, related_name='properties')
    
    # Price Information
    price = models.DecimalField(_('Price'), max_digits=15, decimal_places=2, validators=[MinValueValidator(0)])
    price_negotiable = models.BooleanField(_('Price Negotiable'), default=False)
    security_deposit = models.DecimalField(_('Security Deposit'), max_digits=15, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    maintenance_charges = models.DecimalField(_('Maintenance Charges'), max_digits=10, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    booking_amount = models.DecimalField(_('Booking Amount'), max_digits=10, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    
    # Area Information
    super_area = models.DecimalField(_('Super/Built-up Area'), max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    carpet_area = models.DecimalField(_('Carpet Area'), max_digits=10, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    plot_area = models.DecimalField(_('Plot Area'), max_digits=10, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    area_unit = models.CharField(_('Area Unit'), max_length=10, default='sqft', choices=(
        ('sqft', 'Square Feet'),
        ('sqm', 'Square Meters'),
        ('sqyd', 'Square Yards'),
        ('acre', 'Acres'),
        ('hectare', 'Hectares'),
        ('gunta', 'Guntas'),
        ('marla', 'Marla'),
        ('bigha', 'Bigha'),
    ))
    
    # Property Specifications (Residential/Commercial)
    bedrooms = models.PositiveIntegerField(_('Bedrooms'), blank=True, null=True, validators=[MaxValueValidator(20)])
    bathrooms = models.PositiveIntegerField(_('Bathrooms'), blank=True, null=True, validators=[MaxValueValidator(20)])
    balconies = models.PositiveIntegerField(_('Balconies'), default=0, validators=[MaxValueValidator(10)])
    parking = models.PositiveIntegerField(_('Parking Spaces'), default=0, validators=[MaxValueValidator(20)])
    floor_number = models.IntegerField(_('Floor Number'), blank=True, null=True)
    total_floors = models.IntegerField(_('Total Floors'), blank=True, null=True)
    furnishing = models.CharField(_('Furnishing'), max_length=20, choices=FURNISHING_CHOICES, blank=True, null=True)
    age_of_property = models.CharField(_('Age of Property'), max_length=20, choices=AGE_CHOICES, blank=True, null=True)
    possession_status = models.CharField(_('Possession Status'), max_length=20, choices=POSSESSION_CHOICES, blank=True, null=True)
    ownership_type = models.CharField(_('Ownership Type'), max_length=20, choices=OWNERSHIP_CHOICES, blank=True, null=True)
    facing = models.CharField(_('Facing Direction'), max_length=20, choices=FACING_CHOICES, blank=True, null=True)
    
    # Commercial Specific Fields
    pantry = models.BooleanField(_('Pantry Available'), default=False)
    conference_room = models.BooleanField(_('Conference Room Available'), default=False)
    washrooms = models.PositiveIntegerField(_('Washrooms'), blank=True, null=True, validators=[MaxValueValidator(20)])
    power_backup = models.CharField(_('Power Backup'), max_length=10, choices=POWER_BACKUP_CHOICES, blank=True, null=True)
    clear_height = models.DecimalField(_('Clear Height (ft)'), max_digits=5, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    floor_loading = models.DecimalField(_('Floor Loading (kg/sqft)'), max_digits=8, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)])
    
    # Plot/Land Specific Fields
    plot_length = models.DecimalField(_('Plot Length'), max_digits=8, decimal_places=2, blank=True, null=True)
    plot_breadth = models.DecimalField(_('Plot Breadth'), max_digits=8, decimal_places=2, blank=True, null=True)
    plot_type = models.CharField(_('Plot Type'), max_length=20, choices=(
        ('corner', 'Corner Plot'),
        ('inside', 'Inside Plot'),
        ('park_facing', 'Park Facing'),
        ('road_facing', 'Main Road Facing'),
    ), blank=True, null=True)
    approved_by = models.CharField(_('Approved By'), max_length=100, blank=True, null=True)
    facing_road_width = models.DecimalField(_('Facing Road Width (ft)'), max_digits=5, decimal_places=2, blank=True, null=True)
    
    # Agricultural Specific Fields
    soil_type = models.CharField(_('Soil Type'), max_length=20, choices=SOIL_TYPE_CHOICES, blank=True, null=True)
    irrigation_facilities = models.TextField(_('Irrigation Facilities'), blank=True, null=True)
    crops_grown = models.TextField(_('Crops Grown'), blank=True, null=True)
    water_source = models.CharField(_('Water Source'), max_length=100, blank=True, null=True)
    electricity_connection = models.BooleanField(_('Electricity Connection'), default=False)
    farm_house = models.BooleanField(_('Farm House Available'), default=False)
    
    # PG/Co-Living Specific Fields
    food_included = models.BooleanField(_('Food Included'), default=False)
    shared_rooms = models.BooleanField(_('Shared Rooms Available'), default=False)
    separate_washrooms = models.BooleanField(_('Separate Washrooms'), default=False)
    laundry_service = models.BooleanField(_('Laundry Service'), default=False)
    
    # Location Information
    address = models.TextField(_('Address'))
    city = models.CharField(_('City'), max_length=100, db_index=True)
    locality = models.CharField(_('Locality/Area'), max_length=100, db_index=True)
    landmark = models.CharField(_('Landmark'), max_length=255, blank=True, null=True)
    pincode = models.CharField(_('Pincode'), max_length=10, db_index=True)
    state = models.CharField(_('State'), max_length=100)
    country = models.CharField(_('Country'), max_length=100, default='India')
    latitude = models.DecimalField(_('Latitude'), max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(_('Longitude'), max_digits=9, decimal_places=6, blank=True, null=True)
    
    # Contact Information
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='properties')
    contact_person = models.CharField(_('Contact Person'), max_length=100)
    contact_email = models.EmailField(_('Contact Email'))
    contact_phone = models.CharField(_('Contact Phone'), max_length=15)
    alternate_phone = models.CharField(_('Alternate Phone'), max_length=15, blank=True, null=True)
    whatsapp_enabled = models.BooleanField(_('WhatsApp Enabled'), default=True)
    preferred_contact_time = models.CharField(_('Preferred Contact Time'), max_length=100, blank=True, null=True)
    
    # Listing Preferences
    preferred_tenants = models.CharField(_('Preferred Tenants'), max_length=20, choices=(
        ('family', 'Family Only'),
        ('bachelors', 'Bachelors Allowed'),
        ('company', 'Company Lease'),
        ('anyone', 'Anyone'),
    ), blank=True, null=True)
    available_from = models.DateField(_('Available From'), blank=True, null=True)
    
    # Verification & Legal
    rera_registered = models.BooleanField(_('RERA Registered'), default=False)
    rera_number = models.CharField(_('RERA Number'), max_length=100, blank=True, null=True)
    legal_documents = models.TextField(_('Legal Documents'), blank=True, null=True)
    is_verified = models.BooleanField(_('Verified'), default=False)
    
    # Status & Flags
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='draft')
    is_active = models.BooleanField(_('Active'), default=False)
    is_featured = models.BooleanField(_('Featured'), default=False)
    is_premium = models.BooleanField(_('Premium'), default=False)
    is_urgent = models.BooleanField(_('Urgent'), default=False)
    
    # Amenities (M2M relationship)
    amenities = models.ManyToManyField('Amenity', blank=True, related_name='properties')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(_('Published At'), blank=True, null=True)
    expires_at = models.DateTimeField(_('Expires At'), blank=True, null=True)
    featured_until = models.DateTimeField(_('Featured Until'), blank=True, null=True)
    
    # Statistics
    view_count = models.PositiveIntegerField(_('View Count'), default=0)
    inquiry_count = models.PositiveIntegerField(_('Inquiry Count'), default=0)
    click_count = models.PositiveIntegerField(_('Click Count'), default=0)
    
    # SEO Fields
    meta_title = models.CharField(_('Meta Title'), max_length=200, blank=True, null=True)
    meta_description = models.TextField(_('Meta Description'), blank=True, null=True)
    meta_keywords = models.TextField(_('Meta Keywords'), blank=True, null=True)
    
    # Audit
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='properties_created')
    last_modified_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='properties_modified')

    class Meta:
        verbose_name = _('Property')
        verbose_name_plural = _('Properties')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['city', 'locality']),
            models.Index(fields=['price']),
            models.Index(fields=['bedrooms']),
            models.Index(fields=['category', 'subcategory']),
            models.Index(fields=['is_active', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['listing_type']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.city}"
    
    def save(self, *args, **kwargs):
        """Override save method to generate ref_id and slug"""
        if not self.ref_id:
            # Generate unique reference ID
            import random
            import string
            prefix = "BHOOSPARSH" if self.listing_type == 'sale' else "RENT"
            timestamp = timezone.now().strftime('%y%m%d')
            random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            self.ref_id = f"{prefix}{timestamp}{random_str}"
        
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Property.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        # Auto-generate title if empty
        if not self.title:
            self.title = self.generate_title()
        
        # Auto-fill contact information from owner
        if not self.contact_email and self.owner:
            self.contact_email = self.owner.email
        if not self.contact_phone and self.owner.phone:
            self.contact_phone = self.owner.phone
        if not self.contact_person and self.owner:
            self.contact_person = self.owner.get_full_name() or self.owner.email
        
        # Set published date if becoming active
        if self.is_active and not self.published_at:
            self.published_at = timezone.now()
        
        # Set expiry date (90 days from publish)
        if self.published_at and not self.expires_at:
            self.expires_at = self.published_at + timezone.timedelta(days=90)
        
        super().save(*args, **kwargs)
    
    def generate_title(self):
        """Auto-generate property title based on details"""
        title_parts = []
        
        # Add bedrooms if available
        if self.bedrooms:
            title_parts.append(f"{self.bedrooms} BHK")
        
        # Add subcategory name
        if self.subcategory:
            title_parts.append(self.subcategory.name)
        
        # Add listing type
        listing_type_display = dict(self.LISTING_TYPES).get(self.listing_type, 'Property')
        title_parts.append(listing_type_display)
        
        # Add location
        if self.locality and self.city:
            title_parts.append(f"in {self.locality}, {self.city}")
        
        return " ".join(title_parts)
    
    @property
    def price_per_unit(self):
        """Calculate price per sqft/sqm"""
        if self.super_area and self.super_area > 0:
            return self.price / self.super_area
        return Decimal('0')
    
    @property
    def days_remaining(self):
        """Days remaining until expiry"""
        if self.expires_at:
            delta = self.expires_at - timezone.now()
            return max(0, delta.days)
        return 0
    
    @property
    def primary_image(self):
        """Get primary image"""
        try:
            return self.images.filter(is_primary=True).first().image
        except (PropertyImage.DoesNotExist, AttributeError):
            first_image = self.images.first()
            return first_image.image if first_image else None
    
    def get_fields_to_display(self):
        """Get which fields should be displayed based on category"""
        fields = {}
        
        # Always show basic fields
        fields['basic'] = ['title', 'description', 'listing_type', 'price']
        
        # Add category-specific fields
        if self.category:
            if self.category.has_bedrooms and self.bedrooms:
                fields['residential'] = ['bedrooms', 'bathrooms', 'balconies', 'furnishing']
            if self.category.has_pantry and self.pantry is not None:
                fields['commercial'] = ['pantry', 'conference_room', 'washrooms', 'power_backup']
            if self.category.has_dimensions and (self.plot_length or self.plot_breadth):
                fields['plot'] = ['plot_length', 'plot_breadth', 'plot_type', 'facing_road_width']
            if self.category.has_soil_type and self.soil_type:
                fields['agricultural'] = ['soil_type', 'irrigation_facilities', 'crops_grown']
        
        return fields
    
    def get_required_fields(self):
        """Get required fields based on category"""
        required = [
            'title', 'description', 'listing_type', 'price', 
            'category', 'subcategory', 'city', 'locality', 'address'
        ]
        
        if self.category:
            if self.category.has_area:
                required.append('super_area')
            if self.listing_type == 'rent':
                required.append('security_deposit')
        
        return required


class PropertyImage(models.Model):
    """Property Images with ordering"""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(_('Image'), upload_to='properties/images/')
    thumbnail = models.ImageField(_('Thumbnail'), upload_to='properties/thumbnails/', blank=True, null=True)
    caption = models.CharField(_('Caption'), max_length=255, blank=True, null=True)
    is_primary = models.BooleanField(_('Primary Image'), default=False)
    order = models.PositiveIntegerField(_('Order'), default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Property Image')
        verbose_name_plural = _('Property Images')
        ordering = ['order', 'uploaded_at']
    
    def __str__(self):
        return f"Image for {self.property.title}"
    
    def save(self, *args, **kwargs):
        # Ensure only one primary image per property
        if self.is_primary:
            PropertyImage.objects.filter(property=self.property, is_primary=True).update(is_primary=False)
        
        # Generate thumbnail
        if self.image and not self.thumbnail:
            from PIL import Image
            from io import BytesIO
            from django.core.files.base import ContentFile
            import os
            
            try:
                img = Image.open(self.image)
                img.thumbnail((300, 200))
                
                thumb_io = BytesIO()
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    rgb_img.save(thumb_io, format='JPEG', quality=85)
                else:
                    img.save(thumb_io, format='JPEG', quality=85)
                
                thumb_name = f"thumb_{os.path.basename(self.image.name)}"
                self.thumbnail.save(thumb_name, ContentFile(thumb_io.getvalue()), save=False)
            except Exception as e:
                print(f"Error generating thumbnail: {e}")
        
        super().save(*args, **kwargs)

class Amenity(models.Model):
    """Amenities and Features"""
    
    AMENITY_CATEGORIES = (
        ('basic', 'Basic Amenities'),
        ('security', 'Security'),
        ('parking', 'Parking'),
        ('community', 'Community'),
        ('green', 'Green Features'),
        ('luxury', 'Luxury Amenities'),
        ('commercial', 'Commercial'),
        ('agricultural', 'Agricultural'),
    )
    
    name = models.CharField(_('Amenity Name'), max_length=100, unique=True)
    slug = models.SlugField(_('Slug'), max_length=100, unique=True)
    icon = models.CharField(_('Icon'), max_length=50, blank=True)
    category = models.CharField(_('Category'), max_length=20, choices=AMENITY_CATEGORIES, default='basic')
    description = models.TextField(_('Description'), blank=True)
    applicable_to = models.CharField(_('Applicable To'), max_length=20, choices=PropertyCategory.PROPERTY_TYPES, default='residential')
    display_order = models.IntegerField(_('Display Order'), default=0)
    is_active = models.BooleanField(_('Active'), default=True)
    
    class Meta:
        verbose_name = _('Amenity')
        verbose_name_plural = _('Amenities')
        ordering = ['category', 'display_order', 'name']
    
    def __str__(self):
        return self.name

class PropertyVideo(models.Model):
    """Property Videos and Virtual Tours"""
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='videos')
    title = models.CharField(_('Title'), max_length=255)
    video_url = models.URLField(_('Video URL'))
    video_type = models.CharField(_('Video Type'), max_length=20, choices=(
        ('youtube', 'YouTube'),
        ('vimeo', 'Vimeo'),
        ('facebook', 'Facebook'),
        ('virtual_tour', 'Virtual Tour'),
        ('property_video', 'Property Video'),
    ))
    thumbnail = models.ImageField(_('Thumbnail'), upload_to='properties/videos/thumbnails/', blank=True, null=True)
    description = models.TextField(_('Description'), blank=True)
    order = models.PositiveIntegerField(_('Order'), default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Property Video')
        verbose_name_plural = _('Property Videos')
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return f"{self.title} - {self.property.title}"



# =======================================================================
#  Lead Management Models
# =======================================================================

class PropertyInquiry(models.Model):
    """Property inquiry/lead model"""
    
    INQUIRY_STATUS = (
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('interested', 'Interested'),
        ('scheduled', 'Site Visit Scheduled'),
        ('negotiation', 'Under Negotiation'),
        ('closed_won', 'Closed - Won'),
        ('closed_lost', 'Closed - Lost'),
        ('spam', 'Spam'),
    )
    
    CONTACT_METHOD = (
        ('phone', 'Phone Call'),
        ('whatsapp', 'WhatsApp'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('form', 'Contact Form'),
    )
    
    LEAD_SOURCE = (
        ('website', 'Website'),
        ('mobile_app', 'Mobile App'),
        ('partner', 'Partner Site'),
        ('referral', 'Referral'),
        ('organic', 'Organic Search'),
    )
    
    property_link = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='inquiries',
        verbose_name=_('property')
    )
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inquiries_made',
        verbose_name=_('inquirer')
    )
    
    # Lead information
    name = models.CharField(_('name'), max_length=100)
    email = models.EmailField(_('email'), blank=True, null=True)
    phone = models.CharField(_('phone'), max_length=17)
    whatsapp_enabled = models.BooleanField(_('whatsapp enabled'), default=True)
    
    # Lead details
    message = models.TextField(_('message'), blank=True, null=True)
    budget = models.DecimalField(
        _('budget'),
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )
    
    timeline = models.CharField(
        _('timeline'),
        max_length=50,
        blank=True,
        null=True,
        help_text=_('When do they plan to buy/rent?')
    )
    
    # Status tracking
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=INQUIRY_STATUS,
        default='new'
    )
    
    contact_method = models.CharField(
        _('contact method'),
        max_length=20,
        choices=CONTACT_METHOD,
        default='form'
    )
    
    lead_source = models.CharField(
        _('lead source'),
        max_length=20,
        choices=LEAD_SOURCE,
        default='website'
    )
    
    priority = models.CharField(
        _('priority'),
        max_length=20,
        choices=(
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('hot', 'Hot'),
        ),
        default='medium'
    )
    
    # Interaction tracking
    response = models.TextField(_('response'), blank=True, null=True)
    responded_at = models.DateTimeField(_('responded at'), blank=True, null=True)
    responded_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inquiries_responded',
        verbose_name=_('responded by')
    )
    
    # Notes
    notes = models.TextField(_('notes'), blank=True, null=True)
    
    # Privacy
    consent_given = models.BooleanField(_('consent given'), default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_contacted = models.DateTimeField(_('last contacted'), blank=True, null=True)
    
    class Meta:
        db_table = 'core_propertyinquiry'
        verbose_name = _('property inquiry')
        verbose_name_plural = _('property inquiries')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['property_link', 'status']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['created_at']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"Inquiry for {self.property_link.title} by {self.name}"
    
    def save(self, *args, **kwargs):
        """Update property inquiry count"""
        is_new = self.pk is None
        
        super().save(*args, **kwargs)
        
        if is_new:
            # Increment property inquiry count
            self.property_link.increment_inquiry_count()
            
            # Send notification to property owner
            self.send_notification()
    
    def send_notification(self):
        """Send notification about new inquiry"""
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        
        try:
            # Email notification
            subject = f"New Inquiry for {self.property_link.title}"
            
            context = {
                'inquiry': self,
                'property': self.property_link,
                'user': self.property_link.owner,
            }
            
            html_message = render_to_string('properties/email/new_inquiry.html', context)
            text_message = f"New inquiry from {self.name} for {self.property_link.title}"
            
            send_mail(
                subject=subject,
                message=text_message,
                html_message=html_message,
                from_email=None,
                recipient_list=[self.property_link.owner.email],
                fail_silently=True,
            )
            
            # TODO: Send WhatsApp notification if enabled
            # TODO: Send push notification
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error sending inquiry notification: {e}")
    
    def mark_as_contacted(self, user, method='phone', notes=None):
        """Mark inquiry as contacted"""
        self.status = 'contacted'
        self.last_contacted = timezone.now()
        self.contact_method = method
        
        if notes:
            if self.notes:
                self.notes += f"\n\n{timezone.now().strftime('%Y-%m-%d %H:%M')}: {notes}"
            else:
                self.notes = f"{timezone.now().strftime('%Y-%m-%d %H:%M')}: {notes}"
        
        self.save()


class LeadInteraction(models.Model):
    """Track all interactions with a lead"""
    
    INTERACTION_TYPE = (
        ('call', 'Phone Call'),
        ('whatsapp', 'WhatsApp Message'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('visit', 'Site Visit'),
        ('meeting', 'Meeting'),
        ('note', 'Note'),
    )
    
    lead = models.ForeignKey(
        'PropertyInquiry',
        on_delete=models.CASCADE,
        related_name='interactions',
        verbose_name=_('lead')
    )
    
    interaction_type = models.CharField(
        _('interaction type'),
        max_length=20,
        choices=INTERACTION_TYPE
    )
    
    # Interaction details
    subject = models.CharField(_('subject'), max_length=255, blank=True, null=True)
    message = models.TextField(_('message'), blank=True, null=True)
    duration = models.DurationField(_('duration'), blank=True, null=True)
    
    # Who performed the interaction
    performed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='lead_interactions',
        verbose_name=_('performed by')
    )
    
    # Follow-up
    follow_up_date = models.DateTimeField(_('follow up date'), blank=True, null=True)
    follow_up_notes = models.TextField(_('follow up notes'), blank=True, null=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(_('IP address'), blank=True, null=True)
    user_agent = models.TextField(_('user agent'), blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'core_leadinteraction'
        verbose_name = _('lead interaction')
        verbose_name_plural = _('lead interactions')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_interaction_type_display()} for {self.lead}"


# =======================================================================
#  Analytics Models
# =======================================================================

class PropertyView(models.Model):
    """Track property views with detailed analytics"""
    
    DEVICE_TYPE = (
        ('desktop', 'Desktop'),
        ('mobile', 'Mobile'),
        ('tablet', 'Tablet'),
    )
    
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='property_views',
        verbose_name=_('property')
    )
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='property_views',
        verbose_name=_('user')
    )
    
    session_key = models.CharField(
        _('session key'),
        max_length=255,
        blank=True,
        null=True
    )
    
    # View details
    viewed_at = models.DateTimeField(_('viewed at'), auto_now_add=True)
    duration_seconds = models.PositiveIntegerField(
        _('duration seconds'),
        default=0,
        help_text=_('Time spent viewing property in seconds')
    )
    
    # Device and browser info
    device_type = models.CharField(
        _('device type'),
        max_length=20,
        choices=DEVICE_TYPE,
        default='desktop'
    )
    
    browser = models.CharField(
        _('browser'),
        max_length=100,
        blank=True,
        null=True
    )
    
    os = models.CharField(
        _('operating system'),
        max_length=100,
        blank=True,
        null=True
    )
    
    screen_resolution = models.CharField(
        _('screen resolution'),
        max_length=20,
        blank=True,
        null=True
    )
    
    # Traffic source
    referrer = models.URLField(_('referrer'), blank=True, null=True)
    source = models.CharField(
        _('source'),
        max_length=50,
        choices=(
            ('direct', 'Direct'),
            ('organic', 'Organic Search'),
            ('social', 'Social Media'),
            ('email', 'Email'),
            ('referral', 'Referral'),
        ),
        default='direct'
    )
    
    campaign = models.CharField(
        _('campaign'),
        max_length=100,
        blank=True,
        null=True
    )
    
    # Engagement metrics
    images_viewed = models.PositiveIntegerField(
        _('images viewed'),
        default=0
    )
    
    description_read = models.BooleanField(
        _('description read'),
        default=False
    )
    
    contact_viewed = models.BooleanField(
        _('contact viewed'),
        default=False
    )
    
    # Location data
    ip_address = models.GenericIPAddressField(_('IP address'), blank=True, null=True)
    city = models.CharField(_('city'), max_length=100, blank=True, null=True)
    country = models.CharField(_('country'), max_length=100, blank=True, null=True)
    
    class Meta:
        db_table = 'core_propertyview'
        verbose_name = _('property view')
        verbose_name_plural = _('property views')
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['property', 'viewed_at']),
            models.Index(fields=['user', 'viewed_at']),
            models.Index(fields=['device_type']),
            models.Index(fields=['source']),
        ]
    
    def __str__(self):
        return f"View of {self.property.title} at {self.viewed_at}"
    
    @classmethod
    def track_view(cls, property_obj, request, duration=0, images_viewed=0, description_read=False):
        """Track a property view"""
        try:
            user = request.user if request.user.is_authenticated else None
            
            # Get device info
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            device_type = cls._get_device_type(user_agent)
            
            # Get referrer
            referrer = request.META.get('HTTP_REFERER', '')
            
            # Create view record
            view = cls.objects.create(
                property=property_obj,
                user=user,
                session_key=request.session.session_key,
                duration_seconds=duration,
                device_type=device_type,
                browser=cls._get_browser(user_agent),
                os=cls._get_os(user_agent),
                referrer=referrer,
                images_viewed=images_viewed,
                description_read=description_read,
                ip_address=cls._get_client_ip(request),
            )
            
            return view
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error tracking property view: {e}")
            return None
    
    @staticmethod
    def _get_device_type(user_agent):
        """Determine device type from user agent"""
        user_agent = user_agent.lower()
        
        if 'mobile' in user_agent:
            return 'mobile'
        elif 'tablet' in user_agent or 'ipad' in user_agent:
            return 'tablet'
        else:
            return 'desktop'
    
    @staticmethod
    def _get_browser(user_agent):
        """Extract browser from user agent"""
        # Simplified browser detection
        user_agent = user_agent.lower()
        
        if 'chrome' in user_agent:
            return 'Chrome'
        elif 'firefox' in user_agent:
            return 'Firefox'
        elif 'safari' in user_agent:
            return 'Safari'
        elif 'edge' in user_agent:
            return 'Edge'
        else:
            return 'Other'
    
    @staticmethod
    def _get_os(user_agent):
        """Extract OS from user agent"""
        user_agent = user_agent.lower()
        
        if 'windows' in user_agent:
            return 'Windows'
        elif 'mac' in user_agent:
            return 'macOS'
        elif 'linux' in user_agent:
            return 'Linux'
        elif 'android' in user_agent:
            return 'Android'
        elif 'ios' in user_agent or 'iphone' in user_agent:
            return 'iOS'
        else:
            return 'Other'
    
    @staticmethod
    def _get_client_ip(request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class DailyPropertyStats(models.Model):
    """Daily aggregated property statistics"""
    
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='daily_stats',
        verbose_name=_('property')
    )
    
    date = models.DateField(_('date'), db_index=True)
    
    # View statistics
    total_views = models.PositiveIntegerField(_('total views'), default=0)
    unique_visitors = models.PositiveIntegerField(_('unique visitors'), default=0)
    avg_duration = models.PositiveIntegerField(_('average duration'), default=0)
    
    # Lead statistics
    total_inquiries = models.PositiveIntegerField(_('total inquiries'), default=0)
    phone_inquiries = models.PositiveIntegerField(_('phone inquiries'), default=0)
    whatsapp_inquiries = models.PositiveIntegerField(_('whatsapp inquiries'), default=0)
    email_inquiries = models.PositiveIntegerField(_('email inquiries'), default=0)
    
    # Engagement metrics
    contact_clicks = models.PositiveIntegerField(_('contact clicks'), default=0)
    whatsapp_clicks = models.PositiveIntegerField(_('whatsapp clicks'), default=0)
    call_clicks = models.PositiveIntegerField(_('call clicks'), default=0)
    
    # Device breakdown
    desktop_views = models.PositiveIntegerField(_('desktop views'), default=0)
    mobile_views = models.PositiveIntegerField(_('mobile views'), default=0)
    tablet_views = models.PositiveIntegerField(_('tablet views'), default=0)
    
    # Source breakdown
    direct_views = models.PositiveIntegerField(_('direct views'), default=0)
    organic_views = models.PositiveIntegerField(_('organic views'), default=0)
    social_views = models.PositiveIntegerField(_('social views'), default=0)
    referral_views = models.PositiveIntegerField(_('referral views'), default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_dailypropertystats'
        verbose_name = _('daily property stats')
        verbose_name_plural = _('daily property stats')
        unique_together = ['property', 'date']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['property', 'date']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"Stats for {self.property.title} on {self.date}"
    
    @classmethod
    def update_daily_stats(cls, property_obj):
        """Update daily statistics for a property"""
        from django.utils import timezone
        from django.db.models import Count, Avg, Q
        
        today = timezone.now().date()
        
        # Get today's views
        today_views = PropertyView.objects.filter(
            property=property_obj,
            viewed_at__date=today
        )
        
        # Get today's inquiries
        today_inquiries = PropertyInquiry.objects.filter(
            property_link=property_obj,
            created_at__date=today
        )
        
        # Calculate statistics
        stats = {
            'total_views': today_views.count(),
            'unique_visitors': today_views.values('session_key').distinct().count(),
            'avg_duration': today_views.aggregate(avg=Avg('duration_seconds'))['avg'] or 0,
            
            'total_inquiries': today_inquiries.count(),
            'phone_inquiries': today_inquiries.filter(contact_method='phone').count(),
            'whatsapp_inquiries': today_inquiries.filter(contact_method='whatsapp').count(),
            'email_inquiries': today_inquiries.filter(contact_method='email').count(),
            
            'desktop_views': today_views.filter(device_type='desktop').count(),
            'mobile_views': today_views.filter(device_type='mobile').count(),
            'tablet_views': today_views.filter(device_type='tablet').count(),
            
            'direct_views': today_views.filter(source='direct').count(),
            'organic_views': today_views.filter(source='organic').count(),
            'social_views': today_views.filter(source='social').count(),
            'referral_views': today_views.filter(source='referral').count(),
        }
        
        # Update or create daily stats
        daily_stats, created = cls.objects.update_or_create(
            property=property_obj,
            date=today,
            defaults=stats
        )
        
        return daily_stats



def property_image_path(instance, filename):
    """Generate path for property images"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"properties/property_{instance.property.id}/{filename}"





class PropertyAmenity(models.Model):
    """Through model for property amenities with additional data"""
    
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='property_amenities'
    )
    
    amenity = models.ForeignKey(
        Amenity,
        on_delete=models.CASCADE,
        related_name='property_amenities'
    )
    
    description = models.TextField(blank=True, null=True)
    is_available = models.BooleanField(default=True)
    
    # Additional metadata
    distance = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text=_('Distance from property (e.g., 500m, 1km)')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'core_propertyamenity'
        verbose_name = _('property amenity')
        verbose_name_plural = _('property amenities')
        unique_together = [['property', 'amenity']]
        ordering = ['amenity__category', 'amenity__name']
    
    def __str__(self):
        return f"{self.property.title} - {self.amenity.name}"    
    
  

# =======================================================================
#  Membership Plan Model
# =======================================================================


class MembershipPlan(models.Model):
    """Enhanced Membership Plan model with advanced features"""
    
    DURATION_CHOICES = (
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi_annual', 'Semi-Annual'),
        ('annual', 'Annual'),
        ('lifetime', 'Lifetime'),
    )
    
    TIER_CHOICES = (
        ('basic', 'Basic'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    )
    
    # Core Information
    name = models.CharField(_('plan name'), max_length=100, unique=True)
    slug = models.SlugField(_('slug'), max_length=100, unique=True)
    tier = models.CharField(_('tier'), max_length=20, choices=TIER_CHOICES, default='basic')
    description = models.TextField(_('description'))
    
    # Pricing
    monthly_price = models.DecimalField(
        _('monthly price'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    
    annual_price = models.DecimalField(
        _('annual price'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        blank=True,
        null=True,
        help_text=_('Annual price (if different from monthly × 12)')
    )
    
    # Features & Limits
    max_active_listings = models.PositiveIntegerField(
        _('max active listings'),
        default=1,
        help_text=_('0 for unlimited')
    )
    
    max_featured_listings = models.PositiveIntegerField(
        _('featured listings per month'),
        default=0
    )
    
    max_images_per_listing = models.PositiveIntegerField(
        _('images per listing'),
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(50)]
    )
    
    # Feature Flags
    has_priority_ranking = models.BooleanField(_('priority ranking'), default=False)
    has_advanced_analytics = models.BooleanField(_('advanced analytics'), default=False)
    has_dedicated_support = models.BooleanField(_('dedicated support'), default=False)
    can_use_virtual_tour = models.BooleanField(_('virtual tour'), default=False)
    can_use_video = models.BooleanField(_('property videos'), default=False)
    has_agency_profile = models.BooleanField(_('agency profile'), default=False)
    has_bulk_upload = models.BooleanField(_('bulk upload'), default=False)
    
    # Badges & Recognition
    badge_text = models.CharField(_('badge text'), max_length=50, blank=True, null=True)
    badge_color = models.CharField(
        _('badge color'),
        max_length=20,
        default='primary',
        choices=(
            ('primary', 'Primary'),
            ('success', 'Success'),
            ('warning', 'Warning'),
            ('danger', 'Danger'),
            ('info', 'Info'),
            ('dark', 'Dark'),
        )
    )
    
    display_order = models.PositiveIntegerField(_('display order'), default=0)
    is_popular = models.BooleanField(_('popular plan'), default=False)
    is_active = models.BooleanField(_('active'), default=True)
    is_featured = models.BooleanField(_('featured plan'), default=False)
    
    # Trial Settings
    has_trial = models.BooleanField(_('free trial'), default=False)
    trial_days = models.PositiveIntegerField(_('trial days'), default=0)
    
    # Razorpay Integration
    razorpay_plan_id = models.CharField(
        _('Razorpay plan ID'),
        max_length=100,
        blank=True,
        null=True,
        help_text=_('Razorpay Plan ID for subscriptions')
    )
    
    razorpay_plan_id_monthly = models.CharField(
        _('Monthly Razorpay plan ID'),
        max_length=100,
        blank=True,
        null=True
    )
    
    razorpay_plan_id_annual = models.CharField(
        _('Annual Razorpay plan ID'),
        max_length=100,
        blank=True,
        null=True
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    meta_title = models.CharField(_('meta title'), max_length=200, blank=True, null=True)
    meta_description = models.TextField(_('meta description'), blank=True, null=True)
    
    class Meta:
        db_table = 'membership_plan'
        verbose_name = _('membership plan')
        verbose_name_plural = _('membership plans')
        ordering = ['display_order', 'monthly_price']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['tier']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_popular']),
            models.Index(fields=['monthly_price']),
        ]
    
    def __str__(self):
        return f"{self.name} (${self.monthly_price}/month)"
    
    def save(self, *args, **kwargs):
        """Override save to generate slug and sync with Razorpay"""
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        
        # Auto-set annual price if not provided
        if not self.annual_price:
            self.annual_price = self.monthly_price * 12
        
        super().save(*args, **kwargs)
        
        # Sync with Razorpay (async in production)
        if settings.RAZORPAY_LIVE_MODE:
            from membership.services import RazorpayService
            try:
                RazorpayService.sync_plan_to_razorpay(self)
            except Exception as e:
                # Log error but don't break save
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error syncing plan to Razorpay: {e}")
    
    @property
    def is_unlimited(self):
        """Check if plan has unlimited listings"""
        return self.max_active_listings == 0
    
    @property
    def yearly_savings(self):
        """Calculate yearly savings percentage"""
        if not self.annual_price:
            return 0
        
        monthly_total = self.monthly_price * 12
        if monthly_total <= 0:
            return 0
        
        savings = ((monthly_total - self.annual_price) / monthly_total) * 100
        return round(savings, 2)
    
    @property
    def daily_price(self):
        """Calculate daily price"""
        return self.monthly_price / 30
    
    @property
    def features_list(self):
        """Get features as list"""
        features = []
        
        # Listing features
        if self.is_unlimited:
            features.append("Unlimited active listings")
        else:
            features.append(f"Up to {self.max_active_listings} active listings")
        
        if self.max_featured_listings > 0:
            features.append(f"{self.max_featured_listings} featured listings per month")
        
        features.append(f"Up to {self.max_images_per_listing} images per listing")
        
        # Advanced features
        if self.has_priority_ranking:
            features.append("Priority ranking in search results")
        
        if self.has_advanced_analytics:
            features.append("Advanced analytics dashboard")
        
        if self.has_dedicated_support:
            features.append("Dedicated customer support")
        
        if self.can_use_virtual_tour:
            features.append("Virtual tour integration")
        
        if self.can_use_video:
            features.append("Property video uploads")
        
        if self.has_agency_profile:
            features.append("Professional agency profile")
        
        if self.has_bulk_upload:
            features.append("Bulk property upload")
        
        if self.badge_text:
            features.append(f"'{self.badge_text}' verification badge")
        
        if self.has_trial and self.trial_days > 0:
            features.append(f"{self.trial_days}-day free trial")
        
        return features
    
    @property
    def popular_features(self):
        """Get top 3 features for display"""
        return self.features_list[:3]
    
    def get_price_for_duration(self, duration='monthly'):
        """Get price for specific duration"""
        if duration == 'annual':
            return self.annual_price or self.monthly_price * 12
        return self.monthly_price
    
    def get_razorpay_plan_id(self, duration='monthly'):
        """Get Razorpay plan ID for duration"""
        if duration == 'annual' and self.razorpay_plan_id_annual:
            return self.razorpay_plan_id_annual
        return self.razorpay_plan_id_monthly or self.razorpay_plan_id


class UserSubscription(models.Model):
    """Advanced User Subscription model with Razorpay integration"""
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('expired', 'Expired'),
        ('pending', 'Pending'),
        ('trialing', 'Trialing'),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('razorpay', 'Razorpay'),
        ('stripe', 'Stripe'),
        ('manual', 'Manual'),
        ('free', 'Free'),
    )
    
    # Core Relations
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='subscription',
        verbose_name=_('user')
    )
    
    plan = models.ForeignKey(
        MembershipPlan,
        on_delete=models.PROTECT,
        related_name='user_subscriptions',
        verbose_name=_('membership plan')
    )
    
    # Subscription Details
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    duration = models.CharField(
        _('billing duration'),
        max_length=20,
        choices=MembershipPlan.DURATION_CHOICES,
        default='monthly'
    )
    
    # Razorpay Integration
    razorpay_subscription_id = models.CharField(
        _('Razorpay subscription ID'),
        max_length=255,
        blank=True,
        null=True,
        db_index=True
    )
    
    razorpay_customer_id = models.CharField(
        _('Razorpay customer ID'),
        max_length=255,
        blank=True,
        null=True,
        db_index=True
    )
    
    razorpay_plan_id = models.CharField(
        _('Razorpay plan ID'),
        max_length=100,
        blank=True,
        null=True
    )
    
    razorpay_payment_id = models.CharField(
        _('Razorpay payment ID'),
        max_length=255,
        blank=True,
        null=True
    )
    
    razorpay_signature = models.CharField(
        _('Razorpay signature'),
        max_length=500,
        blank=True,
        null=True
    )
    
    # Payment Details
    payment_method = models.CharField(
        _('payment method'),
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='razorpay'
    )
    
    amount_paid = models.DecimalField(
        _('amount paid'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    currency = models.CharField(
        _('currency'),
        max_length=3,
        default='INR'
    )
    
    # Dates
    start_date = models.DateTimeField(
        _('start date'),
        default=timezone.now
    )
    
    end_date = models.DateTimeField(
        _('end date'),
        blank=True,
        null=True
    )
    
    trial_start = models.DateTimeField(
        _('trial start'),
        blank=True,
        null=True
    )
    
    trial_end = models.DateTimeField(
        _('trial end'),
        blank=True,
        null=True
    )
    
    current_period_start = models.DateTimeField(
        _('current period start'),
        blank=True,
        null=True
    )
    
    current_period_end = models.DateTimeField(
        _('current period end'),
        blank=True,
        null=True
    )
    
    canceled_at = models.DateTimeField(
        _('canceled at'),
        blank=True,
        null=True
    )
    
    # Settings
    auto_renew = models.BooleanField(
        _('auto renew'),
        default=True
    )
    
    is_trial = models.BooleanField(
        _('trial period'),
        default=False
    )
    
    # Usage Tracking
    listings_used = models.PositiveIntegerField(
        _('listings used'),
        default=0
    )
    
    featured_used_this_month = models.PositiveIntegerField(
        _('featured listings used this month'),
        default=0
    )
    
    total_listings_created = models.PositiveIntegerField(
        _('total listings created'),
        default=0
    )
    
    # Analytics
    last_payment_date = models.DateTimeField(
        _('last payment date'),
        blank=True,
        null=True
    )
    
    next_payment_date = models.DateTimeField(
        _('next payment date'),
        blank=True,
        null=True
    )
    
    payment_failed_count = models.PositiveIntegerField(
        _('payment failed count'),
        default=0
    )
    
    # Metadata
    metadata = models.JSONField(
        _('metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional subscription data')
    )
    
    notes = models.TextField(
        _('notes'),
        blank=True,
        null=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_subscription'
        verbose_name = _('user subscription')
        verbose_name_plural = _('user subscriptions')
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['razorpay_subscription_id']),
            models.Index(fields=['status', 'end_date']),
            models.Index(fields=['start_date']),
            models.Index(fields=['end_date']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.plan.name} ({self.status})"
    
    def save(self, *args, **kwargs):
        """Override save to handle date calculations"""
        # Calculate end date for new subscriptions
        if not self.end_date and self.start_date and self.plan and not self.is_trial:
            self.end_date = self.calculate_end_date()
        
        # Set trial dates if applicable
        if self.is_trial and self.plan.has_trial and not self.trial_end:
            self.trial_start = self.start_date
            self.trial_end = self.start_date + timedelta(days=self.plan.trial_days)
        
        # Set current period dates
        if not self.current_period_start:
            self.current_period_start = self.start_date
        
        if not self.current_period_end and self.current_period_start:
            self.current_period_end = self.current_period_start + timedelta(days=30)
        
        super().save(*args, **kwargs)
    
    def calculate_end_date(self):
        """Calculate subscription end date based on duration"""
        duration_days = {
            'monthly': 30,
            'quarterly': 90,
            'semi_annual': 180,
            'annual': 365,
            'lifetime': 36500,  # 100 years
        }.get(self.duration, 30)
        
        return self.start_date + timedelta(days=duration_days)
    
    @property
    def is_active(self):
        """Check if subscription is active"""
        now = timezone.now()
        
        if self.status not in ['active', 'trialing']:
            return False
        
        if self.is_trial and self.trial_end and self.trial_end < now:
            return False
        
        if self.end_date and self.end_date < now:
            return False
        
        return True
    
    @property
    def is_expired(self):
        """Check if subscription is expired"""
        return not self.is_active
    
    @property
    def days_remaining(self):
        """Calculate days remaining in subscription"""
        if not self.is_active:
            return 0
        
        end_date = self.end_date or (self.trial_end if self.is_trial else None)
        
        if end_date:
            remaining = end_date - timezone.now()
            return max(0, remaining.days)
        
        return 0
    
    @property
    def trial_days_remaining(self):
        """Calculate trial days remaining"""
        if not self.is_trial or not self.trial_end:
            return 0
        
        remaining = self.trial_end - timezone.now()
        return max(0, remaining.days)
    
    @property
    def can_list_property(self):
        """Check if user can list a new property"""
        if not self.is_active:
            return False
        
        if self.plan.is_unlimited:
            return True
        
        return self.listings_used < self.plan.max_active_listings
    
    @property
    def can_feature_property(self):
        """Check if user can feature a property"""
        if not self.is_active:
            return False
        
        if self.plan.max_featured_listings == 0:
            return False
        
        return self.featured_used_this_month < self.plan.max_featured_listings
    
    @property
    def listings_remaining(self):
        """Get number of listings remaining"""
        if self.plan.is_unlimited:
            return 'Unlimited'
        
        remaining = self.plan.max_active_listings - self.listings_used
        return max(0, remaining)
    
    @property
    def featured_remaining(self):
        """Get featured listings remaining this month"""
        remaining = self.plan.max_featured_listings - self.featured_used_this_month
        return max(0, remaining)
    
    def increment_listing_count(self):
        """Increment used listing count"""
        if not self.plan.is_unlimited:
            self.listings_used += 1
            self.total_listings_created += 1
            self.save(update_fields=['listings_used', 'total_listings_created'])
    
    def decrement_listing_count(self):
        """Decrement used listing count"""
        if not self.plan.is_unlimited and self.listings_used > 0:
            self.listings_used -= 1
            self.save(update_fields=['listings_used'])
    
    def increment_featured_count(self):
        """Increment featured listing count"""
        if self.plan.max_featured_listings > 0:
            self.featured_used_this_month += 1
            self.save(update_fields=['featured_used_this_month'])
    
    def reset_monthly_counts(self):
        """Reset monthly usage counters"""
        # This should be called by a scheduled task
        self.featured_used_this_month = 0
        self.save(update_fields=['featured_used_this_month'])
    
    def cancel(self, reason=None, cancel_at_period_end=True):
        """Cancel subscription"""
        from membership.services import RazorpayService
        
        if cancel_at_period_end and self.auto_renew:
            # Cancel at period end (Razorpay subscription)
            if self.razorpay_subscription_id:
                try:
                    RazorpayService.cancel_subscription(
                        self.razorpay_subscription_id,
                        cancel_at_period_end=True
                    )
                except Exception as e:
                    # Log error but continue with local cancellation
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error canceling Razorpay subscription: {e}")
        
        self.status = 'canceled'
        self.canceled_at = timezone.now()
        self.auto_renew = False
        
        if reason:
            self.notes = f"Cancellation reason: {reason}\n{self.notes or ''}"
        
        self.save()
    
    def activate_trial(self, plan=None):
        """Activate trial subscription"""
        if plan:
            self.plan = plan
        
        self.is_trial = True
        self.status = 'trialing'
        self.start_date = timezone.now()
        self.end_date = None
        
        if plan and plan.has_trial:
            self.trial_end = timezone.now() + timedelta(days=plan.trial_days)
        
        self.save()
    
    def upgrade_plan(self, new_plan, duration='monthly'):
        """Upgrade to a new plan"""
        from membership.services import RazorpayService
        
        self.plan = new_plan
        self.duration = duration
        
        # Update Razorpay subscription if exists
        if self.razorpay_subscription_id:
            try:
                razorpay_plan_id = new_plan.get_razorpay_plan_id(duration)
                RazorpayService.update_subscription(
                    self.razorpay_subscription_id,
                    plan_id=razorpay_plan_id
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error updating Razorpay subscription: {e}")
        
        self.save()


class PaymentTransaction(models.Model):
    """Payment transaction tracking"""
    
    STATUS_CHOICES = (
        ('created', 'Created'),
        ('authorized', 'Authorized'),
        ('captured', 'Captured'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('card', 'Credit/Debit Card'),
        ('netbanking', 'Net Banking'),
        ('upi', 'UPI'),
        ('wallet', 'Wallet'),
        ('emi', 'EMI'),
    )
    
    # Core Relations
    subscription = models.ForeignKey(
        UserSubscription,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name=_('subscription'),
        blank=True,
        null=True
    )
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='payment_transactions',
        verbose_name=_('user')
    )
    
    plan = models.ForeignKey(
        MembershipPlan,
        on_delete=models.SET_NULL,
        related_name='transactions',
        verbose_name=_('membership plan'),
        blank=True,
        null=True
    )
    
    # Payment Details
    razorpay_order_id = models.CharField(
        _('Razorpay order ID'),
        max_length=255,
        db_index=True
    )
    
    razorpay_payment_id = models.CharField(
        _('Razorpay payment ID'),
        max_length=255,
        db_index=True,
        blank=True,
        null=True
    )
    
    razorpay_signature = models.CharField(
        _('Razorpay signature'),
        max_length=500,
        blank=True,
        null=True
    )
    
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='created'
    )
    
    payment_method = models.CharField(
        _('payment method'),
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        blank=True,
        null=True
    )
    
    # Amount Details
    amount = models.DecimalField(
        _('amount'),
        max_digits=10,
        decimal_places=2
    )
    
    currency = models.CharField(
        _('currency'),
        max_length=3,
        default='INR'
    )
    
    amount_refunded = models.DecimalField(
        _('amount refunded'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    # Metadata
    description = models.TextField(
        _('description'),
        blank=True,
        null=True
    )
    
    metadata = models.JSONField(
        _('metadata'),
        default=dict,
        blank=True
    )
    
    error_message = models.TextField(
        _('error message'),
        blank=True,
        null=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(
        _('paid at'),
        blank=True,
        null=True
    )
    
    class Meta:
        db_table = 'payment_transaction'
        verbose_name = _('payment transaction')
        verbose_name_plural = _('payment transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['razorpay_order_id']),
            models.Index(fields=['razorpay_payment_id']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.razorpay_order_id} - {self.amount} {self.currency}"
    
    @property
    def is_successful(self):
        """Check if payment was successful"""
        return self.status == 'captured'
    
    @property
    def is_refunded(self):
        """Check if payment was refunded"""
        return self.status == 'refunded'
    
    @property
    def amount_due(self):
        """Calculate amount due"""
        return self.amount - self.amount_refunded
    
    def mark_as_paid(self, payment_id, signature=None):
        """Mark transaction as paid"""
        self.status = 'captured'
        self.razorpay_payment_id = payment_id
        self.razorpay_signature = signature
        self.paid_at = timezone.now()
        self.save()
    
    def mark_as_failed(self, error_message):
        """Mark transaction as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.save()


class SubscriptionFeatureUsage(models.Model):
    """Track feature usage for subscriptions"""
    
    subscription = models.ForeignKey(
        UserSubscription,
        on_delete=models.CASCADE,
        related_name='feature_usage'
    )
    
    feature_type = models.CharField(
        max_length=50,
        choices=(
            ('listing_created', 'Listing Created'),
            ('listing_featured', 'Listing Featured'),
            ('virtual_tour', 'Virtual Tour'),
            ('property_video', 'Property Video'),
            ('bulk_upload', 'Bulk Upload'),
        )
    )
    
    usage_count = models.PositiveIntegerField(default=0)
    limit = models.PositiveIntegerField(default=0)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscription_feature_usage'
        unique_together = ['subscription', 'feature_type', 'period_start']
    
    @property
    def usage_percentage(self):
        """Calculate usage percentage"""
        if self.limit == 0:
            return 0
        return (self.usage_count / self.limit) * 100
    
    @property
    def remaining(self):
        """Calculate remaining usage"""
        return max(0, self.limit - self.usage_count)


class CreditPackage(models.Model):
    """Credit packages for featured listings and other premium features"""
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    
    # Credits
    featured_listing_credits = models.PositiveIntegerField(default=0)
    bump_up_credits = models.PositiveIntegerField(default=0)
    highlight_credits = models.PositiveIntegerField(default=0)
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    # Validity
    validity_days = models.PositiveIntegerField(default=365)
    is_active = models.BooleanField(default=True)
    
    # Razorpay
    razorpay_plan_id = models.CharField(max_length=100, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'credit_package'
        ordering = ['price']
    
    def __str__(self):
        return f"{self.name} - {self.price}"
    
    @property
    def discount_percentage(self):
        """Calculate discount percentage"""
        if self.original_price and self.original_price > self.price:
            return round(((self.original_price - self.price) / self.original_price) * 100, 2)
        return 0


class UserCredit(models.Model):
    """User's credit balance"""
    
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='credits'
    )
    
    featured_listing_credits = models.PositiveIntegerField(default=0)
    bump_up_credits = models.PositiveIntegerField(default=0)
    highlight_credits = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_credit'
    
    def __str__(self):
        return f"{self.user.email} - Credits"
    
    def has_featured_credit(self):
        """Check if user has featured listing credits"""
        return self.featured_listing_credits > 0
    
    def use_featured_credit(self):
        """Use one featured listing credit"""
        if self.featured_listing_credits > 0:
            self.featured_listing_credits -= 1
            self.save()
            return True
        return False
    
    def add_credits(self, package):
        """Add credits from a package"""
        self.featured_listing_credits += package.featured_listing_credits
        self.bump_up_credits += package.bump_up_credits
        self.highlight_credits += package.highlight_credits
        self.save()

# =======================================================================
#  User Membership Model
# =======================================================================
    
class UserMembership(models.Model):
    """User membership subscription model"""
    
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='membership',
        verbose_name=_('user')
    )
    
    plan = models.ForeignKey(
        MembershipPlan,
        on_delete=models.PROTECT,
        related_name='user_memberships',
        verbose_name=_('membership plan')
    )

    duration = models.CharField(
        _('duration'),
        max_length=20,
        choices=MembershipPlan.DURATION_CHOICES,
        default='monthly'
    )

    # Subscription details
    stripe_subscription_id = models.CharField(
        _('Stripe subscription ID'),
        max_length=255,
        blank=True,
        null=True
    )
    
    razorpay_subscription_id = models.CharField(
        _('Razorpay subscription ID'),
        max_length=255,
        blank=True,
        null=True
    )
    
    # Dates
    start_date = models.DateTimeField(
        _('start date'),
        default=timezone.now
    )
    
    end_date = models.DateTimeField(
        _('end date'),
        blank=True,
        null=True
    )
    
    trial_end = models.DateTimeField(
        _('trial end'),
        blank=True,
        null=True
    )
    
    # Status
    is_active = models.BooleanField(
        _('active'),
        default=True
    )
    
    is_trial = models.BooleanField(
        _('trial period'),
        default=False
    )
    
    auto_renew = models.BooleanField(
        _('auto renew'),
        default=True
    )
    
    # Usage tracking
    listings_used = models.PositiveIntegerField(
        _('listings used'),
        default=0
    )
    
    featured_used_this_month = models.PositiveIntegerField(
        _('featured listings used this month'),
        default=0
    )
    
    # Payment information
    last_payment_date = models.DateTimeField(
        _('last payment date'),
        blank=True,
        null=True
    )
    
    next_payment_date = models.DateTimeField(
        _('next payment date'),
        blank=True,
        null=True
    )
    
    amount_paid = models.DecimalField(
        _('total amount paid'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    # Cancellation
    cancelled_at = models.DateTimeField(
        _('cancelled at'),
        blank=True,
        null=True
    )
    
    cancellation_reason = models.TextField(
        _('cancellation reason'),
        blank=True,
        null=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_usermembership'
        verbose_name = _('user membership')
        verbose_name_plural = _('user memberships')
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['plan']),
            models.Index(fields=['start_date']),
            models.Index(fields=['end_date']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.plan.name}"
    
    def save(self, *args, **kwargs):
        """Override save to handle end date calculation"""
        # Calculate end date based on plan duration
        if self.plan and self.start_date and not self.end_date and not self.is_trial:
            # Use self.duration instead of self.plan.duration
            duration_days = {
                'monthly': 30,
                'quarterly': 90,
                'semi_annual': 180,
                'annual': 365,
                'lifetime': 36500,  # 100 years
            }.get(self.duration, 30)  # Changed from self.plan.duration to self.duration
            
            self.end_date = self.start_date + timezone.timedelta(days=duration_days)
        
        # Set trial end if applicable
        if self.is_trial and self.plan.has_trial and not self.trial_end:
            self.trial_end = self.start_date + timezone.timedelta(days=self.plan.trial_days)
        
        super().save(*args, **kwargs)
    
    @property
    def days_remaining(self):
        """Calculate days remaining in subscription"""
        if self.end_date and self.is_active:
            remaining = self.end_date - timezone.now()
            return max(0, remaining.days)
        return 0
    
    @property
    def is_expired(self):
        """Check if subscription is expired"""
        if not self.is_active:
            return True
        
        if self.end_date and self.end_date < timezone.now():
            return True
        
        if self.is_trial and self.trial_end and self.trial_end < timezone.now():
            return True
        
        return False
    
    @property
    def can_list_property(self):
        """Check if user can list a new property"""
        if not self.is_active or self.is_expired:
            return False
        
        if self.plan.is_unlimited:
            return True
        
        return self.listings_used < self.plan.max_active_listings
    
    @property
    def can_feature_property(self):
        """Check if user can feature a property"""
        if not self.is_active or self.is_expired:
            return False
        
        if self.plan.max_featured == 0:
            return False
        
        # Reset monthly counter (simplified - you might want to track monthly)
        return self.featured_used_this_month < self.plan.max_featured
    
    def increment_listing_count(self):
        """Increment used listing count"""
        if not self.plan.is_unlimited:
            self.listings_used += 1
            self.save(update_fields=['listings_used'])
    
    def decrement_listing_count(self):
        """Decrement used listing count"""
        if not self.plan.is_unlimited and self.listings_used > 0:
            self.listings_used -= 1
            self.save(update_fields=['listings_used'])
    
    def increment_featured_count(self):
        """Increment featured listing count"""
        if self.plan.max_featured > 0:
            self.featured_used_this_month += 1
            self.save(update_fields=['featured_used_this_month'])
    
    def reset_monthly_counts(self):
        """Reset monthly usage counters"""
        # This should be called by a scheduled task (celery/cron)
        self.featured_used_this_month = 0
        self.save(update_fields=['featured_used_this_month'])
    
    def cancel(self, reason=None):
        """Cancel subscription"""
        self.is_active = False
        self.cancelled_at = timezone.now()
        self.cancellation_reason = reason
        self.save()
    
    def renew(self, plan=None):
        """Renew subscription"""
        if plan:
            self.plan = plan
        
        self.start_date = timezone.now()
        self.end_date = None  # Will be calculated in save()
        self.is_active = True
        self.is_trial = False
        self.cancelled_at = None
        self.cancellation_reason = None
        self.save()

# =======================================================================
#  Property Inquiry Model
# ======================================================================= 
 
# class PropertyInquiry(models.Model):
#     """Property inquiries from buyers/tenants"""
    
#     property_link = models.ForeignKey(
#         Property,
#         on_delete=models.CASCADE,
#         related_name='inquiries',
#         verbose_name=_('property')
#     )
    
#     user = models.ForeignKey(
#         CustomUser,
#         on_delete=models.CASCADE,
#         related_name='inquiries',
#         verbose_name=_('inquirer'),
#         blank=True,
#         null=True
#     )
    
#     # Guest user information (if not logged in)
#     guest_name = models.CharField(
#         _('name'),
#         max_length=100,
#         blank=True,
#         null=True
#     )
    
#     guest_email = models.EmailField(
#         _('email'),
#         blank=True,
#         null=True
#     )
    
#     phone_regex = RegexValidator(
#         regex=r'^\+?1?\d{9,15}$',
#         message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
#     )
    
#     phone = models.CharField(
#         _('phone number'),
#         validators=[phone_regex],
#         max_length=17
#     )
    
#     message = models.TextField(
#         _('message'),
#         help_text=_('Your questions or requirements')
#     )
    
#     # Inquiry type
#     INQUIRY_TYPE_CHOICES = (
#         ('general', 'General Inquiry'),
#         ('viewing', 'Request Viewing'),
#         ('price', 'Price Negotiation'),
#         ('details', 'More Details'),
#         ('other', 'Other'),
#     )
    
#     inquiry_type = models.CharField(
#         _('inquiry type'),
#         max_length=20,
#         choices=INQUIRY_TYPE_CHOICES,
#         default='general'
#     )
    
#     # Preferred viewing time
#     preferred_date = models.DateField(
#         _('preferred date'),
#         blank=True,
#         null=True
#     )
    
#     preferred_time = models.TimeField(
#         _('preferred time'),
#         blank=True,
#         null=True
#     )
    
#     # Status tracking
#     STATUS_CHOICES = (
#         ('new', 'New'),
#         ('read', 'Read'),
#         ('contacted', 'Contacted'),
#         ('scheduled', 'Viewing Scheduled'),
#         ('negotiating', 'Negotiating'),
#         ('converted', 'Converted to Deal'),
#         ('closed', 'Closed'),
#         ('spam', 'Spam'),
#     )
    
#     status = models.CharField(
#         _('status'),
#         max_length=20,
#         choices=STATUS_CHOICES,
#         default='new'
#     )
    
#     is_read = models.BooleanField(
#         _('read'),
#         default=False
#     )
    
#     is_archived = models.BooleanField(
#         _('archived'),
#         default=False
#     )
    
#     # Response tracking
#     response = models.TextField(
#         _('response'),
#         blank=True,
#         null=True
#     )
    
#     responded_at = models.DateTimeField(
#         _('responded at'),
#         blank=True,
#         null=True
#     )
    
#     responded_by = models.ForeignKey(
#         CustomUser,
#         on_delete=models.SET_NULL,
#         related_name='responded_inquiries',
#         verbose_name=_('responded by'),
#         blank=True,
#         null=True
#     )
    
#     # Timestamps
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         db_table = 'core_propertyinquiry'
#         verbose_name = _('property inquiry')
#         verbose_name_plural = _('property inquiries')
#         ordering = ['-created_at']
#         indexes = [
#             models.Index(fields=['property_link', 'status']),
#             models.Index(fields=['user']),
#             models.Index(fields=['is_read']),
#             models.Index(fields=['status']),
#             models.Index(fields=['created_at']),
#         ]
    
#     def __str__(self):
#         if self.user:
#             return f"Inquiry from {self.user.email} for {self.property.title}"
#         return f"Inquiry from {self.guest_name or 'Guest'} for {self.property.title}"
    
#     def save(self, *args, **kwargs):
#         """Override save to increment property inquiry count"""
#         is_new = self.pk is None
#         super().save(*args, **kwargs)
        
#         if is_new:
#             self.property.increment_inquiry_count()
    
    
#     @property
#     def inquired_property(self):
#         """Get the property being inquired about"""
#         return self.property_link
    
#     @property
#     def inquirer_name(self):
#         """Get inquirer name"""
#         if self.user:
#             return self.user.full_name
#         return self.guest_name or 'Anonymous'
    
#     @property
#     def inquirer_email(self):
#         """Get inquirer email"""
#         if self.user:
#             return self.user.email
#         return self.guest_email
    
#     @property
#     def has_response(self):
#         """Check if inquiry has been responded to"""
#         return bool(self.response)
    
#     def mark_as_read(self, user=None):
#         """Mark inquiry as read"""
#         self.is_read = True
#         self.save(update_fields=['is_read'])
    
#     def respond(self, response, user=None):
#         """Add response to inquiry"""
#         self.response = response
#         self.responded_at = timezone.now()
#         self.responded_by = user
#         self.status = 'contacted'
#         self.save(update_fields=['response', 'responded_at', 'responded_by', 'status'])


class PropertyFavorite(models.Model):
    """User favorite/saved properties"""
    
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
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optional: Add notes for the saved property
    notes = models.TextField(
        _('notes'),
        blank=True,
        null=True,
        help_text=_('Private notes about this property')
    )
    
    # Tags/categories for organization
    tags = models.CharField(
        _('tags'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Comma-separated tags for organization')
    )
    
    class Meta:
        db_table = 'core_propertyfavorite'
        verbose_name = _('property favorite')
        verbose_name_plural = _('property favorites')
        unique_together = [['user', 'property']]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'property']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} favorited {self.property.title}"
    
    @classmethod
    def add_to_favorites(cls, user, property_obj, notes=None):
        """Add property to favorites"""
        favorite, created = cls.objects.get_or_create(
            user=user,
            property=property_obj,
            defaults={'notes': notes}
        )
        if not created and notes:
            favorite.notes = notes
            favorite.save()
        return favorite
    
    @classmethod
    def remove_from_favorites(cls, user, property_obj):
        """Remove property from favorites"""
        cls.objects.filter(user=user, property=property_obj).delete()


class PropertyView(models.Model):
    """Track property views for analytics"""
    
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='views',
        verbose_name=_('property')
    )
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name='property_views',
        verbose_name=_('user'),
        blank=True,
        null=True
    )
    
    session_key = models.CharField(
        _('session key'),
        max_length=100,
        blank=True,
        null=True,
        help_text=_('Anonymous user session key')
    )
    
    ip_address = models.GenericIPAddressField(
        _('IP address'),
        blank=True,
        null=True
    )
    
    user_agent = models.TextField(
        _('user agent'),
        blank=True,
        null=True
    )
    
    referrer = models.URLField(
        _('referrer'),
        blank=True,
        null=True
    )
    
    # Device information
    device_type = models.CharField(
        _('device type'),
        max_length=50,
        blank=True,
        null=True,
        choices=(
            ('desktop', 'Desktop'),
            ('tablet', 'Tablet'),
            ('mobile', 'Mobile'),
            ('bot', 'Bot/Crawler'),
        )
    )
    
    browser = models.CharField(
        _('browser'),
        max_length=100,
        blank=True,
        null=True
    )
    
    os = models.CharField(
        _('operating system'),
        max_length=100,
        blank=True,
        null=True
    )
    
    # View duration (if tracking JS events)
    duration_seconds = models.PositiveIntegerField(
        _('view duration'),
        default=0,
        help_text=_('Time spent on property page in seconds')
    )
    
    # Whether they scrolled through images/description
    images_viewed = models.PositiveIntegerField(
        _('images viewed'),
        default=0
    )
    
    description_read = models.BooleanField(
        _('description read'),
        default=False
    )
    
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'core_propertyview'
        verbose_name = _('property view')
        verbose_name_plural = _('property views')
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['property', 'viewed_at']),
            models.Index(fields=['user', 'viewed_at']),
            models.Index(fields=['ip_address', 'viewed_at']),
            models.Index(fields=['viewed_at']),
            models.Index(fields=['device_type']),
        ]
    
    def __str__(self):
        if self.user:
            return f"{self.user.email} viewed {self.property.title}"
        return f"Anonymous view of {self.property.title}"
    
    def save(self, *args, **kwargs):
        """Override save to increment property view count"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            self.property.increment_view_count()
    
    @classmethod
    def track_view(cls, property_obj, request, duration=0, images_viewed=0, description_read=False):
        """Track a property view"""
        user = None
        session_key = None
        
        if request.user.is_authenticated:
            user = request.user
        else:
            session_key = request.session.session_key
        
        # Parse user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        device_type = cls._get_device_type(user_agent)
        
        view = cls.objects.create(
            property=property_obj,
            user=user,
            session_key=session_key,
            ip_address=cls._get_client_ip(request),
            user_agent=user_agent,
            referrer=request.META.get('HTTP_REFERER'),
            device_type=device_type,
            duration_seconds=duration,
            images_viewed=images_viewed,
            description_read=description_read
        )
        
        return view
    
    @staticmethod
    def _get_client_ip(request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @staticmethod
    def _get_device_type(user_agent):
        """Determine device type from user agent"""
        if not user_agent:
            return 'desktop'
        
        user_agent = user_agent.lower()
        
        if any(device in user_agent for device in ['mobile', 'android', 'iphone']):
            return 'mobile'
        elif 'tablet' in user_agent or 'ipad' in user_agent:
            return 'tablet'
        elif any(bot in user_agent for bot in ['bot', 'crawler', 'spider']):
            return 'bot'
        else:
            return 'desktop'        

# =======================================================================
#  Contact Message Model
# =======================================================================

class ContactMessage(models.Model):
    """Contact form messages"""
    
    CATEGORY_CHOICES = (
        ('general', 'General Inquiry'),
        ('support', 'Technical Support'),
        ('billing', 'Billing/Payment'),
        ('feature', 'Feature Request'),
        ('bug', 'Bug Report'),
        ('partnership', 'Partnership'),
        ('other', 'Other'),
    )
    
    # Sender information
    name = models.CharField(
        _('name'),
        max_length=100
    )
    
    email = models.EmailField(
        _('email')
    )
    
    phone = models.CharField(
        _('phone'),
        max_length=17,
        blank=True,
        null=True
    )
    
    # Message details
    subject = models.CharField(
        _('subject'),
        max_length=200
    )
    
    category = models.CharField(
        _('category'),
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='general'
    )
    
    message = models.TextField(
        _('message')
    )
    
    # Attachments
    attachment = models.FileField(
        _('attachment'),
        upload_to='contact_attachments/',
        blank=True,
        null=True
    )
    
    # Status tracking
    STATUS_CHOICES = (
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    )
    
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='new'
    )
    
    priority = models.CharField(
        _('priority'),
        max_length=20,
        choices=(
            ('low', 'Low'),
            ('normal', 'Normal'),
            ('high', 'High'),
            ('urgent', 'Urgent'),
        ),
        default='normal'
    )
    
    is_resolved = models.BooleanField(
        _('resolved'),
        default=False
    )
    
    # Response tracking
    response = models.TextField(
        _('response'),
        blank=True,
        null=True
    )
    
    responded_at = models.DateTimeField(
        _('responded at'),
        blank=True,
        null=True
    )
    
    responded_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name='contact_responses',
        verbose_name=_('responded by'),
        blank=True,
        null=True
    )
    
    # User context (if logged in)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name='contact_messages',
        verbose_name=_('user'),
        blank=True,
        null=True
    )
    
    # Page context
    page_url = models.URLField(
        _('page URL'),
        blank=True,
        null=True,
        help_text=_('URL where the contact form was submitted from')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'core_contactmessage'
        verbose_name = _('contact message')
        verbose_name_plural = _('contact messages')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['is_resolved']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.subject} - {self.name}"
    
    def save(self, *args, **kwargs):
        """Override save to update is_resolved based on status"""
        if self.status == 'resolved':
            self.is_resolved = True
        super().save(*args, **kwargs)
    
    @property
    def full_name(self):
        """Get sender's full name"""
        return self.name
    
    def mark_as_resolved(self, response=None, user=None):
        """Mark message as resolved"""
        self.status = 'resolved'
        self.is_resolved = True
        if response:
            self.response = response
            self.responded_at = timezone.now()
            self.responded_by = user
        self.save()
    
    def assign_to_staff(self, user):
        """Assign message to staff member"""
        self.responded_by = user
        self.status = 'in_progress'
        self.save()


class NewsletterSubscription(models.Model):
    """Newsletter subscription model"""
    
    email = models.EmailField(
        _('email'),
        unique=True
    )
    
    name = models.CharField(
        _('name'),
        max_length=100,
        blank=True,
        null=True
    )
    
    # Preferences
    receive_property_alerts = models.BooleanField(
        _('property alerts'),
        default=True
    )
    
    receive_newsletter = models.BooleanField(
        _('newsletter'),
        default=True
    )
    
    receive_promotions = models.BooleanField(
        _('promotions'),
        default=False
    )
    
    # Verification
    is_verified = models.BooleanField(
        _('verified'),
        default=False
    )
    
    verification_token = models.UUIDField(
        default=uuid.uuid4,
        editable=False
    )
    
    # Status
    is_active = models.BooleanField(
        _('active'),
        default=True
    )
    
    subscribed_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'core_newslettersubscription'
        verbose_name = _('newsletter subscription')
        verbose_name_plural = _('newsletter subscriptions')
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['is_active']),
            models.Index(fields=['subscribed_at']),
        ]
    
    def __str__(self):
        return self.email


class SavedSearch(models.Model):
    """User saved searches for email alerts"""
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='saved_searches'
    )
    
    name = models.CharField(
        _('search name'),
        max_length=100,
        help_text=_('Give a name to this search')
    )
    
    # Search parameters
    city = models.CharField(max_length=100, blank=True, null=True)
    locality = models.CharField(max_length=100, blank=True, null=True)
    min_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    max_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    property_type = models.CharField(max_length=50, blank=True, null=True)
    min_bedrooms = models.PositiveIntegerField(blank=True, null=True)
    max_bedrooms = models.PositiveIntegerField(blank=True, null=True)
    min_bathrooms = models.PositiveIntegerField(blank=True, null=True)
    furnishing = models.CharField(max_length=20, blank=True, null=True)
    
    # Search frequency
    FREQUENCY_CHOICES = (
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('instant', 'Instant'),
    )
    
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default='daily'
    )
    
    is_active = models.BooleanField(default=True)
    last_notified = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'core_savedsearch'
        verbose_name = 'saved search'
        verbose_name_plural = 'saved searches'
        unique_together = ['user', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.user.email}"
    
    def get_search_params(self):
        """Get search parameters as dict"""
        params = {}
        
        if self.city:
            params['city'] = self.city
        if self.locality:
            params['locality'] = self.locality
        if self.min_price:
            params['min_price'] = self.min_price
        if self.max_price:
            params['max_price'] = self.max_price
        if self.property_type:
            params['property_type'] = self.property_type
        if self.min_bedrooms:
            params['min_bedrooms'] = self.min_bedrooms
        if self.max_bedrooms:
            params['max_bedrooms'] = self.max_bedrooms
        if self.min_bathrooms:
            params['min_bathrooms'] = self.min_bathrooms
        if self.furnishing:
            params['furnishing'] = self.furnishing
        
        return params        