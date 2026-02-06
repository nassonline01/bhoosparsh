import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.cache import cache
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q
from django.utils import timezone
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _

from .models import (
    CustomUser,
    UserProfile,
    MembershipPlan,
    UserSubscription,
    CreditPackage,
    UserCredit,
    PropertyInquiry,
    LeadInteraction,
    SavedSearch,
)

from estate_app.models import (
    Property,
    PropertyCategory,
    PropertySubCategory,
    PropertyImage,
    Amenity,
    PropertyAmenity,
    UserMembership,
)

from estate_app.membership.services import MembershipService, RazorpayService

User = get_user_model()

# forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q
import re
from .models import Property, PropertyCategory, PropertySubCategory, Amenity, PropertyImage
from django.forms import inlineformset_factory


class DynamicPropertyForm(forms.ModelForm):
    """Dynamic form that changes based on property type"""
    
    # Step 1: Basic Information
    listing_type = forms.ChoiceField(
        choices=Property.LISTING_TYPES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'onchange': 'updateFormFields()'
        })
    )
    
    category = forms.ModelChoiceField(
        queryset=PropertyCategory.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'onchange': 'loadSubcategories()'
        })
    )
    
    subcategory = forms.ModelChoiceField(
        queryset=PropertySubCategory.objects.none(),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'onchange': 'updateDynamicFields()'
        })
    )
    
    # Price fields with conditional requirements
    price = forms.DecimalField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 7500000',
            'step': '0.01'
        })
    )
    
    security_deposit = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 50000'
        })
    )
    
    maintenance_charges = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2000'
        })
    )
    
    booking_amount = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 50000'
        })
    )
    
    # Area fields
    super_area = forms.DecimalField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 1500'
        })
    )

    available_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    carpet_area = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 1200'
        })
    )
    
    plot_area = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2400'
        })
    )
    
    class Meta:
        model = Property
        fields = [
            'listing_type', 'category', 'subcategory', 'title', 'description',
            'price', 'price_negotiable', 'security_deposit', 'maintenance_charges',
            'booking_amount', 'super_area', 'carpet_area', 'plot_area', 'area_unit',
            'contact_person', 'contact_email', 'contact_phone', 'available_from'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 3BHK Luxury Apartment in Bandra West'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Describe your property in detail...'
            }),
            'price_negotiable': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'area_unit': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Set initial values
        if self.user:
            if 'contact_person' in self.fields:
                self.fields['contact_person'].initial = self.user.get_full_name()
            if 'contact_email' in self.fields:
                self.fields['contact_email'].initial = self.user.email
            if 'contact_phone' in self.fields:
                self.fields['contact_phone'].initial = self.user.phone
        
        # Make security deposit required for rent listings
        if self.instance.listing_type == 'rent':
            self.fields['security_deposit'].required = True
        
        # Update subcategory queryset based on selected category
        if 'category' in self.data:
            try:
                category_id = int(self.data.get('category'))
                self.fields['subcategory'].queryset = PropertySubCategory.objects.filter(
                    category_id=category_id, is_active=True
                ).order_by('display_order')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.category:
            self.fields['subcategory'].queryset = self.instance.category.subcategories.filter(
                is_active=True
            ).order_by('display_order')
        
        # Add dynamic fields based on category
        self.add_dynamic_fields()
    
    def add_dynamic_fields(self):
        """Add dynamic fields based on selected category"""
        category = None

        # Get category from instance or form data
        if self.instance and hasattr(self.instance, 'category') and self.instance.category_id:
            try:
                category = self.instance.category
            except Property.category.RelatedObjectDoesNotExist:
                pass
        elif 'category' in self.data:
            try:
                category_id = int(self.data.get('category'))
                category = PropertyCategory.objects.get(id=category_id)
            except (ValueError, TypeError, PropertyCategory.DoesNotExist):
                pass

        if category:
            # Residential/Commercial fields
            if category.has_bedrooms:
                self.fields['bedrooms'] = forms.IntegerField(
                    required=True,
                    min_value=1,
                    max_value=20,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control',
                        'placeholder': 'e.g., 3'
                    })
                )
                self.fields['bathrooms'] = forms.IntegerField(
                    required=True,
                    min_value=1,
                    max_value=20,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control',
                        'placeholder': 'e.g., 2'
                    })
                )
            
            if category.has_balconies:
                self.fields['balconies'] = forms.IntegerField(
                    required=False,
                    min_value=0,
                    max_value=10,
                    initial=0,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control',
                        'placeholder': 'e.g., 2'
                    })
                )
            
            if category.has_floor:
                self.fields['floor_number'] = forms.IntegerField(
                    required=False,
                    min_value=0,
                    max_value=200,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control',
                        'placeholder': 'e.g., 5'
                    })
                )
                self.fields['total_floors'] = forms.IntegerField(
                    required=False,
                    min_value=1,
                    max_value=200,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control',
                        'placeholder': 'e.g., 15'
                    })
                )
            
            if category.has_furnishing:
                self.fields['furnishing'] = forms.ChoiceField(
                    required=False,
                    choices=Property.FURNISHING_CHOICES,
                    widget=forms.Select(attrs={'class': 'form-select'})
                )
            
            if category.has_age:
                self.fields['age_of_property'] = forms.ChoiceField(
                    required=False,
                    choices=Property.AGE_CHOICES,
                    widget=forms.Select(attrs={'class': 'form-select'})
                )
                self.fields['possession_status'] = forms.ChoiceField(
                    required=False,
                    choices=Property.POSSESSION_CHOICES,
                    widget=forms.Select(attrs={'class': 'form-select'})
                )
            
            if category.has_facing:
                self.fields['facing'] = forms.ChoiceField(
                    required=False,
                    choices=Property.FACING_CHOICES,
                    widget=forms.Select(attrs={'class': 'form-select'})
                )
            
            if category.has_pantry:
                self.fields['pantry'] = forms.BooleanField(
                    required=False,
                    initial=False,
                    widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
                )
                self.fields['conference_room'] = forms.BooleanField(
                    required=False,
                    initial=False,
                    widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
                )
            
            if category.has_washrooms:
                self.fields['washrooms'] = forms.IntegerField(
                    required=False,
                    min_value=0,
                    max_value=20,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control',
                        'placeholder': 'e.g., 4'
                    })
                )
            
            if category.has_power_backup:
                self.fields['power_backup'] = forms.ChoiceField(
                    required=False,
                    choices=Property.POWER_BACKUP_CHOICES,
                    widget=forms.Select(attrs={'class': 'form-select'})
                )
            
            if category.has_clear_height:
                self.fields['clear_height'] = forms.DecimalField(
                    required=False,
                    min_value=0,
                    max_digits=5,
                    decimal_places=2,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control',
                        'placeholder': 'e.g., 12.5'
                    })
                )
            
            if category.has_floor_loading:
                self.fields['floor_loading'] = forms.DecimalField(
                    required=False,
                    min_value=0,
                    max_digits=8,
                    decimal_places=2,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control',
                        'placeholder': 'e.g., 150.00'
                    })
                )
            
            if category.has_dimensions:
                self.fields['plot_length'] = forms.DecimalField(
                    required=False,
                    min_value=0,
                    max_digits=8,
                    decimal_places=2,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control',
                        'placeholder': 'Length'
                    })
                )
                self.fields['plot_breadth'] = forms.DecimalField(
                    required=False,
                    min_value=0,
                    max_digits=8,
                    decimal_places=2,
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control',
                        'placeholder': 'Breadth'
                    })
                )
            
            if category.has_soil_type:
                self.fields['soil_type'] = forms.ChoiceField(
                    required=False,
                    choices=Property.SOIL_TYPE_CHOICES,
                    widget=forms.Select(attrs={'class': 'form-select'})
                )
                self.fields['irrigation_facilities'] = forms.CharField(
                    required=False,
                    widget=forms.Textarea(attrs={
                        'class': 'form-control',
                        'rows': 3,
                        'placeholder': 'Borewell, Canal, Rain-fed, etc.'
                    })
                )
    
    def clean(self):
        """Custom validation for dynamic fields"""
        cleaned_data = super().clean()
        
        # Validate price based on area
        price = cleaned_data.get('price')
        super_area = cleaned_data.get('super_area')
        
        if price and super_area and super_area > 0:
            price_per_sqft = price / super_area
            
            # Validate reasonable price per sqft (adjust based on your market)
            if price_per_sqft < 500:  # Minimum ₹500 per sqft
                self.add_error('price', 'Price seems too low for the given area.')
            elif price_per_sqft > 50000:  # Maximum ₹50,000 per sqft
                self.add_error('price', 'Price seems too high for the given area.')
        
        # Validate carpet area <= super area
        carpet_area = cleaned_data.get('carpet_area')
        if carpet_area and super_area and carpet_area > super_area:
            self.add_error('carpet_area', 'Carpet area cannot be greater than super area.')
        
        # Validate plot dimensions
        plot_length = cleaned_data.get('plot_length')
        plot_breadth = cleaned_data.get('plot_breadth')
        plot_area = cleaned_data.get('plot_area')
        
        if plot_length and plot_breadth and not plot_area:
            # Auto-calculate plot area
            calculated_area = plot_length * plot_breadth
            cleaned_data['plot_area'] = calculated_area
        
        # Validate for rent properties
        listing_type = cleaned_data.get('listing_type')
        if listing_type == 'rent':
            if not cleaned_data.get('security_deposit'):
                self.add_error('security_deposit', 'Security deposit is required for rental properties.')
            if not cleaned_data.get('available_from'):
                self.add_error('available_from', 'Available from date is required for rental properties.')
        
        return cleaned_data


class LocationForm(forms.ModelForm):
    """Form for location details"""
    
    class Meta:
        model = Property
        fields = [
            'address', 'city', 'locality', 'landmark', 'pincode',
            'state', 'country', 'latitude', 'longitude'
        ]
        widgets = {
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Complete address including street, building, etc.'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Mumbai',
                'list': 'cities-list'
            }),
            'locality': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Bandra West'
            }),
            'landmark': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Near Bandra Station'
            }),
            'pincode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 400050',
                'pattern': '[0-9]{6}'
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Maharashtra'
            }),
            'country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., India'
            }),
            'latitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'placeholder': 'e.g., 19.076090'
            }),
            'longitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'placeholder': 'e.g., 72.877426'
            }),
        }
    
    def clean_pincode(self):
        """Validate Indian pincode format"""
        pincode = self.cleaned_data.get('pincode')
        if pincode and len(pincode) != 6:
            raise ValidationError('Pincode must be 6 digits.')
        return pincode


class ContactForm(forms.ModelForm):
    """Form for contact details"""
    
    class Meta:
        model = Property
        fields = [
            'contact_person', 'contact_email', 'contact_phone',
            'alternate_phone', 'whatsapp_enabled', 'preferred_contact_time',
            'preferred_tenants', 'available_from'
        ]
        widgets = {
            'contact_person': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., John Doe'
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., john@example.com'
            }),
            'contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+91 98765 43210',
                'pattern': '[0-9+\s()-]{10,15}'
            }),
            'alternate_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+91 98765 43211 (Optional)'
            }),
            'whatsapp_enabled': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'preferred_contact_time': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 10 AM to 6 PM'
            }),
            'preferred_tenants': forms.Select(attrs={
                'class': 'form-select'
            }),
            'available_from': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }
    
    def clean_contact_phone(self):
        """Validate phone number"""
        phone = self.cleaned_data.get('contact_phone')
        if phone:
            # Remove all non-digit characters except +
            cleaned = re.sub(r'[^\d+]', '', phone)
            if len(cleaned) < 10:
                raise ValidationError('Please enter a valid phone number.')
        return phone


class AmenityForm(forms.Form):
    """Form for selecting amenities"""
    
    def __init__(self, *args, **kwargs):
        self.property_category = kwargs.pop('property_category', None)
        super().__init__(*args, **kwargs)
        
        # Get amenities based on property category
        amenities = Amenity.objects.filter(is_active=True)
        
        if self.property_category:
            amenities = amenities.filter(
                Q(applicable_to=self.property_category) | Q(applicable_to='all')
            )
        
        # Group amenities by category
        amenity_categories = {}
        for amenity in amenities:
            category = amenity.get_category_display()
            if category not in amenity_categories:
                amenity_categories[category] = []
            amenity_categories[category].append(amenity)
        
        # Create fields for each amenity
        for category, amenity_list in amenity_categories.items():
            for amenity in amenity_list:
                field_name = f"amenity_{amenity.id}"
                self.fields[field_name] = forms.BooleanField(
                    required=False,
                    label=amenity.name,
                    widget=forms.CheckboxInput(attrs={
                        'class': 'form-check-input',
                        'data-category': amenity.category
                    })
                )


class PropertyImageForm(forms.ModelForm):
    """Form for uploading property images"""
    
    class Meta:
        model = PropertyImage
        fields = ['image', 'caption', 'is_primary']
        widgets = {
            'caption': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional image caption'
            }),
            'is_primary': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def clean_image(self):
        """Validate uploaded image"""
        image = self.cleaned_data.get('image')
        
        if image:
            # Check file size (max 10MB)
            if image.size > 10 * 1024 * 1024:
                raise ValidationError('Image size should not exceed 10MB.')
            
            # Check file type
            import os
            ext = os.path.splitext(image.name)[1].lower()
            valid_extensions = ['.jpg', '.jpeg', '.png', '.webp']
            if ext not in valid_extensions:
                raise ValidationError('Unsupported file format. Please upload JPG, PNG, or WebP images.')
        
        return image


# Formset for multiple images
PropertyImageFormSet = inlineformset_factory(
    Property,
    PropertyImage,
    form=PropertyImageForm,
    extra=10,
    max_num=20,
    can_delete=True
)


class LegalForm(forms.ModelForm):
    """Form for legal and verification details"""
    
    class Meta:
        model = Property
        fields = [
            'rera_registered', 'rera_number', 'legal_documents',
            'ownership_type'
        ]
        widgets = {
            'rera_registered': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'onchange': 'toggleReraField()'
            }),
            'rera_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., P52100000001'
            }),
            'legal_documents': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'List all available legal documents...'
            }),
            'ownership_type': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
    
    def clean(self):
        """Validate RERA details"""
        cleaned_data = super().clean()
        
        rera_registered = cleaned_data.get('rera_registered')
        rera_number = cleaned_data.get('rera_number')
        
        if rera_registered and not rera_number:
            self.add_error('rera_number', 'RERA number is required when RERA registered is checked.')
        
        return cleaned_data


class PublishForm(forms.Form):
    """Form for publishing options"""
    
    PUBLISH_OPTIONS = (
        ('draft', 'Save as Draft'),
        ('publish', 'Publish Now'),
        ('schedule', 'Schedule for Later'),
        ('premium', 'Publish as Premium Listing'),
    )
    
    publish_option = forms.ChoiceField(
        choices=PUBLISH_OPTIONS,
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input',
            'onchange': 'toggleScheduleField()'
        })
    )
    
    schedule_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    
    agree_terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='I agree to the Terms & Conditions'
    )
    
    def clean(self):
        """Validate schedule date"""
        cleaned_data = super().clean()
        
        publish_option = cleaned_data.get('publish_option')
        schedule_date = cleaned_data.get('schedule_date')
        
        if publish_option == 'schedule' and not schedule_date:
            self.add_error('schedule_date', 'Please select a schedule date.')
        
        if schedule_date and schedule_date < timezone.now():
            self.add_error('schedule_date', 'Schedule date cannot be in the past.')
        
        return cleaned_data


# ===================================================================
#  Dashboard Filter Forms
# ===================================================================

class DashboardFilterForm(forms.Form):
    """Base filter form for dashboard"""
    
    TIME_PERIOD_CHOICES = (
        ('today', 'Today'),
        ('yesterday', 'Yesterday'),
        ('last_7d', 'Last 7 Days'),
        ('last_30d', 'Last 30 Days'),
        ('last_90d', 'Last 90 Days'),
        ('this_month', 'This Month'),
        ('last_month', 'Last Month'),
        ('custom', 'Custom Range'),
    )
    
    time_period = forms.ChoiceField(
        choices=TIME_PERIOD_CHOICES,
        initial='last_30d',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
            'onchange': 'this.form.submit()'
        })
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control form-control-sm'
        })
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control form-control-sm'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        time_period = cleaned_data.get('time_period')
        
        if time_period == 'custom':
            start_date = cleaned_data.get('start_date')
            end_date = cleaned_data.get('end_date')
            
            if not start_date or not end_date:
                raise ValidationError(_('Please select both start and end dates for custom range.'))
            
            if start_date > end_date:
                raise ValidationError(_('Start date cannot be after end date.'))
            
            if (end_date - start_date).days > 365:
                raise ValidationError(_('Custom range cannot exceed 365 days.'))
        
        return cleaned_data
    
    def get_date_range(self) -> Tuple[datetime, datetime]:
        """Get date range based on selected period"""
        time_period = self.cleaned_data.get('time_period', 'last_30d')
        
        end_date = timezone.now()
        
        if time_period == 'today':
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_period == 'yesterday':
            start_date = end_date - timedelta(days=1)
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif time_period == 'last_7d':
            start_date = end_date - timedelta(days=7)
        elif time_period == 'last_30d':
            start_date = end_date - timedelta(days=30)
        elif time_period == 'last_90d':
            start_date = end_date - timedelta(days=90)
        elif time_period == 'this_month':
            start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif time_period == 'last_month':
            start_date = (end_date.replace(day=1) - timedelta(days=1)).replace(day=1)
            end_date = start_date + timedelta(days=32)
            end_date = end_date.replace(day=1) - timedelta(days=1)
            end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif time_period == 'custom':
            start_date = timezone.make_aware(
                datetime.combine(self.cleaned_data['start_date'], datetime.min.time())
            )
            end_date = timezone.make_aware(
                datetime.combine(self.cleaned_data['end_date'], datetime.max.time())
            )
        else:
            start_date = end_date - timedelta(days=30)
        
        return start_date, end_date


class PropertyFilterForm(DashboardFilterForm):
    """Filter form for properties dashboard"""
    
    STATUS_CHOICES = (
        ('', 'All Status'),
        ('active', 'Active'),
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('expired', 'Expired'),
        ('archived', 'Archived'),
        ('sold', 'Sold/Rented'),
    )
    
    TYPE_CHOICES = (
        ('', 'All Types'),
        ('apartment', 'Apartment'),
        ('villa', 'Villa'),
        ('plot', 'Plot'),
        ('commercial', 'Commercial'),
    )
    
    PERFORMANCE_CHOICES = (
        ('', 'All Performance'),
        ('high_views', 'High Views'),
        ('low_views', 'Low Views'),
        ('most_leads', 'Most Leads'),
        ('no_leads', 'No Leads'),
        ('expiring_soon', 'Expiring Soon'),
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
            'onchange': 'this.form.submit()'
        })
    )
    
    property_type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
            'onchange': 'this.form.submit()'
        })
    )
    
    performance = forms.ChoiceField(
        choices=PERFORMANCE_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
            'onchange': 'this.form.submit()'
        })
    )
    
    city = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Filter by city',
            'list': 'city-options'
        })
    )
    
    sort_by = forms.ChoiceField(
        choices=(
            ('-created_at', 'Most Recent'),
            ('-view_count', 'Most Views'),
            ('-inquiry_count', 'Most Leads'),
            ('-price', 'Highest Price'),
            ('price', 'Lowest Price'),
            ('expires_at', 'Expiring Soon'),
            ('performance_score', 'Best Performance'),
        ),
        initial='-created_at',
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
            'onchange': 'this.form.submit()'
        })
    )
    
    def get_property_filters(self, user) -> Q:
        """Get Q object for property filtering"""
        filters = Q(owner=user)
        
        status = self.cleaned_data.get('status')
        if status == 'active':
            filters &= Q(is_active=True, status__in=['for_sale', 'for_rent'])
        elif status == 'draft':
            filters &= Q(status='draft')
        elif status == 'pending':
            filters &= Q(is_active=False, status__in=['for_sale', 'for_rent'])
        elif status == 'expired':
            filters &= Q(status='expired') | Q(expires_at__lt=timezone.now())
        elif status == 'archived':
            filters &= Q(status='archived')
        elif status == 'sold':
            filters &= Q(status__in=['sold', 'rented'])
        
        performance = self.cleaned_data.get('performance')
        if performance == 'high_views':
            filters &= Q(view_count__gte=100)
        elif performance == 'low_views':
            filters &= Q(view_count__lt=10)
        elif performance == 'most_leads':
            filters &= Q(inquiry_count__gte=5)
        elif performance == 'no_leads':
            filters &= Q(inquiry_count=0, view_count__gte=50)
        elif performance == 'expiring_soon':
            filters &= Q(
                expires_at__gte=timezone.now(),
                expires_at__lte=timezone.now() + timedelta(days=7)
            )
        
        city = self.cleaned_data.get('city')
        if city:
            filters &= Q(city__icontains=city)
        
        return filters


class LeadFilterForm(DashboardFilterForm):
    """Filter form for leads dashboard"""
    
    STATUS_CHOICES = (
        ('', 'All Status'),
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('interested', 'Interested'),
        ('scheduled', 'Site Visit Scheduled'),
        ('negotiation', 'Under Negotiation'),
        ('closed_won', 'Closed - Won'),
        ('closed_lost', 'Closed - Lost'),
    )
    
    PRIORITY_CHOICES = (
        ('', 'All Priority'),
        ('hot', 'Hot'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    )
    
    SOURCE_CHOICES = (
        ('', 'All Sources'),
        ('phone', 'Phone'),
        ('whatsapp', 'WhatsApp'),
        ('email', 'Email'),
        ('form', 'Contact Form'),
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
            'onchange': 'this.form.submit()'
        })
    )
    
    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
            'onchange': 'this.form.submit()'
        })
    )
    
    source = forms.ChoiceField(
        choices=SOURCE_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
            'onchange': 'this.form.submit()'
        })
    )
    
    property = forms.ModelChoiceField(
        queryset=Property.objects.none(),
        required=False,
        empty_label='All Properties',
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
            'onchange': 'this.form.submit()'
        })
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Search by name, phone, email...'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            self.fields['property'].queryset = Property.objects.filter(
                owner=self.user
            ).order_by('title')
    
    def get_lead_filters(self) -> Q:
        """Get Q object for lead filtering"""
        filters = Q(property_link__owner=self.user)
        
        status = self.cleaned_data.get('status')
        if status:
            filters &= Q(status=status)
        
        priority = self.cleaned_data.get('priority')
        if priority:
            filters &= Q(priority=priority)
        
        source = self.cleaned_data.get('source')
        if source:
            filters &= Q(contact_method=source)
        
        property_obj = self.cleaned_data.get('property')
        if property_obj:
            filters &= Q(property_link=property_obj)
        
        search = self.cleaned_data.get('search')
        if search:
            filters &= (
                Q(name__icontains=search) |
                Q(phone__icontains=search) |
                Q(email__icontains=search) |
                Q(message__icontains=search)
            )
        
        return filters


# ===================================================================
#  Quick Action Forms
# ===================================================================

class BulkActionForm(forms.Form):
    """Form for bulk actions"""
    
    ACTION_CHOICES = (
        ('', 'Select Action'),
        ('boost', 'Boost Selected'),
        ('renew', 'Renew Selected'),
        ('pause', 'Pause Selected'),
        ('activate', 'Activate Selected'),
        ('delete', 'Delete Selected'),
        ('archive', 'Archive Selected'),
    )
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select form-select-sm',
            'id': 'bulk-action-select'
        })
    )
    
    item_ids = forms.CharField(
        widget=forms.HiddenInput(attrs={
            'id': 'bulk-item-ids'
        })
    )
    
    confirm = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput(attrs={
            'id': 'bulk-confirm'
        })
    )


class BoostListingForm(forms.Form):
    """Form for boosting a listing"""
    
    DURATION_CHOICES = (
        (7, '7 Days - ₹299'),
        (15, '15 Days - ₹499'),
        (30, '30 Days - ₹899'),
    )
    
    duration = forms.ChoiceField(
        choices=DURATION_CHOICES,
        initial=7,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    payment_method = forms.ChoiceField(
        choices=(
            ('credits', 'Use Credits'),
            ('razorpay', 'Pay Now'),
        ),
        initial='credits',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            # Check if user has enough credits
            try:
                user_credits = self.user.credits.balance
                if user_credits >= 299:  # Minimum boost cost
                    self.fields['payment_method'].choices = (
                        ('credits', f'Use Credits ({user_credits} available)'),
                        ('razorpay', 'Pay Now'),
                    )
            except UserCredit.DoesNotExist:
                self.fields['payment_method'].choices = (
                    ('razorpay', 'Pay Now'),
                )
    
    def clean(self):
        cleaned_data = super().clean()
        
        payment_method = cleaned_data.get('payment_method')
        
        if payment_method == 'credits' and self.user:
            try:
                user_credits = self.user.credits.balance
                duration = int(cleaned_data.get('duration', 7))
                cost = 299 if duration == 7 else (499 if duration == 15 else 899)
                
                if user_credits < cost:
                    raise ValidationError(
                        f'You need {cost} credits to boost for {duration} days. '
                        f'You have only {user_credits} credits.'
                    )
            except UserCredit.DoesNotExist:
                raise ValidationError('You have no credits. Please purchase credits first.')
        
        return cleaned_data


class RenewListingForm(forms.Form):
    """Form for renewing a listing"""
    
    DURATION_CHOICES = (
        (30, '30 Days - Free'),
        (90, '90 Days - ₹199'),
        (180, '180 Days - ₹349'),
        (365, '365 Days - ₹599'),
    )
    
    duration = forms.ChoiceField(
        choices=DURATION_CHOICES,
        initial=90,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        duration = int(cleaned_data.get('duration', 90))
        
        # Check if user can renew for free
        if duration == 30:
            # Free renewal allowed once per property
            pass
        
        return cleaned_data


# ===================================================================
#  Lead Management Forms
# ===================================================================

class LeadUpdateForm(forms.ModelForm):
    """Form for updating lead status and details"""
    
    class Meta:
        model = PropertyInquiry
        fields = ['status', 'priority', 'notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Add notes about this lead...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Customize status choices based on current status
        current_status = self.instance.status if self.instance else 'new'
        
        if current_status == 'new':
            self.fields['status'].choices = [
                ('new', 'New'),
                ('contacted', 'Contacted'),
                ('spam', 'Spam'),
            ]
        elif current_status == 'contacted':
            self.fields['status'].choices = [
                ('contacted', 'Contacted'),
                ('interested', 'Interested'),
                ('closed_lost', 'Closed - Lost'),
            ]
        elif current_status == 'interested':
            self.fields['status'].choices = [
                ('interested', 'Interested'),
                ('scheduled', 'Site Visit Scheduled'),
                ('negotiation', 'Under Negotiation'),
            ]
        elif current_status == 'scheduled':
            self.fields['status'].choices = [
                ('scheduled', 'Site Visit Scheduled'),
                ('negotiation', 'Under Negotiation'),
                ('closed_won', 'Closed - Won'),
                ('closed_lost', 'Closed - Lost'),
            ]


class LeadInteractionForm(forms.ModelForm):
    """Form for logging lead interactions"""
    
    class Meta:
        model = LeadInteraction
        fields = ['interaction_type', 'subject', 'message', 'duration', 'follow_up_date']
        widgets = {
            'interaction_type': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Subject of interaction'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Details of the interaction...'
            }),
            'duration': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'HH:MM:SS',
                'type': 'time'
            }),
            'follow_up_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }


class BulkLeadActionForm(forms.Form):
    """Form for bulk lead actions"""
    
    ACTION_CHOICES = (
        ('', 'Select Action'),
        ('export_csv', 'Export to CSV'),
        ('mark_contacted', 'Mark as Contacted'),
        ('mark_interested', 'Mark as Interested'),
        ('mark_closed', 'Mark as Closed'),
        ('send_whatsapp', 'Send WhatsApp Message'),
        ('send_email', 'Send Email'),
        ('assign_agent', 'Assign to Agent'),
    )
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    
    lead_ids = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Message to send...'
        })
    )
    
    agent = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(user_type__in=['agent', 'admin']),
        required=False,
        empty_label='Select Agent',
        widget=forms.Select(attrs={'class': 'form-select'})
    )


# ===================================================================
#  Analytics Forms
# ===================================================================

class AnalyticsComparisonForm(forms.Form):
    """Form for analytics comparison"""
    
    COMPARE_WITH_CHOICES = (
        ('market_average', 'Market Average'),
        ('previous_period', 'Previous Period'),
        ('top_performers', 'Top Performers'),
        ('competitor', 'Specific Competitor'),
    )
    
    compare_with = forms.ChoiceField(
        choices=COMPARE_WITH_CHOICES,
        initial='market_average',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    competitor = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Competitor name or URL'
        })
    )
    
    include_own_data = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class ExportDataForm(forms.Form):
    """Form for exporting data"""
    
    FORMAT_CHOICES = (
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('pdf', 'PDF'),
        ('json', 'JSON'),
    )
    
    DATA_TYPE_CHOICES = (
        ('properties', 'Properties'),
        ('leads', 'Leads'),
        ('analytics', 'Analytics'),
        ('transactions', 'Transactions'),
    )
    
    data_type = forms.ChoiceField(
        choices=DATA_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    format = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        initial='csv',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    include_all_fields = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    date_range = forms.ChoiceField(
        choices=DashboardFilterForm.TIME_PERIOD_CHOICES,
        initial='last_30d',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    custom_start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    custom_end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )


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


class NotificationSettingsForm(forms.Form):
    """Form for notification settings"""
    
    # Push notifications
    push_new_leads = forms.BooleanField(
        initial=True,
        required=False,
        label='New Leads',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    push_price_drops = forms.BooleanField(
        initial=True,
        required=False,
        label='Price Drops',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    push_listing_expiry = forms.BooleanField(
        initial=True,
        required=False,
        label='Listing Expiry',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    push_promotions = forms.BooleanField(
        initial=False,
        required=False,
        label='Promotions',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    # Email notifications
    email_daily_summary = forms.BooleanField(
        initial=True,
        required=False,
        label='Daily Summary',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    email_weekly_report = forms.BooleanField(
        initial=True,
        required=False,
        label='Weekly Report',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    email_market_updates = forms.BooleanField(
        initial=False,
        required=False,
        label='Market Updates',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    # WhatsApp notifications
    whatsapp_instant_alerts = forms.BooleanField(
        initial=True,
        required=False,
        label='Instant Lead Alerts',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    whatsapp_payment_reminders = forms.BooleanField(
        initial=True,
        required=False,
        label='Payment Reminders',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def save_to_user(self, user):
        """Save notification preferences to user"""
        preferences = {
            'push': {
                'new_leads': self.cleaned_data.get('push_new_leads', True),
                'price_drops': self.cleaned_data.get('push_price_drops', True),
                'listing_expiry': self.cleaned_data.get('push_listing_expiry', True),
                'promotions': self.cleaned_data.get('push_promotions', False),
            },
            'email': {
                'daily_summary': self.cleaned_data.get('email_daily_summary', True),
                'weekly_report': self.cleaned_data.get('email_weekly_report', True),
                'market_updates': self.cleaned_data.get('email_market_updates', False),
            },
            'whatsapp': {
                'instant_alerts': self.cleaned_data.get('whatsapp_instant_alerts', True),
                'payment_reminders': self.cleaned_data.get('whatsapp_payment_reminders', True),
            }
        }
        
        user.notification_preferences = preferences
        user.save(update_fields=['notification_preferences'])


class PrivacySettingsForm(forms.ModelForm):
    """Form for privacy settings"""
    
    class Meta:
        model = CustomUser
        fields = ['show_phone_to', 'show_email', 'allow_calls_from', 'allow_calls_to']
        widgets = {
            'show_phone_to': forms.Select(attrs={'class': 'form-select'}),
            'show_email': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_calls_from': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'allow_calls_to': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
        }


class AccountSettingsForm(forms.Form):
    """Form for account settings"""
    
    current_password = forms.CharField(
        label='Current Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False
    )
    
    new_password = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        min_length=8
    )
    
    confirm_password = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False
    )
    
    two_factor_auth = forms.BooleanField(
        label='Enable Two-Factor Authentication',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    data_sharing = forms.ChoiceField(
        label='Data Sharing',
        choices=(
            ('personalization', 'Allow for Personalization'),
            ('never', 'Never Share'),
        ),
        initial='personalization',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password or confirm_password:
            if not cleaned_data.get('current_password'):
                raise ValidationError('Current password is required to change password.')
            
            if new_password != confirm_password:
                raise ValidationError('New passwords do not match.')
        
        return cleaned_data


# ===================================================================
#  Dashboard Widget Forms
# ===================================================================

class DashboardWidgetForm(forms.Form):
    """Form for customizing dashboard widgets"""
    
    WIDGET_CHOICES = (
        ('quick_stats', 'Quick Stats'),
        ('recent_leads', 'Recent Leads'),
        ('performance_chart', 'Performance Chart'),
        ('top_properties', 'Top Properties'),
        ('alerts', 'Alerts & Notifications'),
        ('revenue_chart', 'Revenue Chart'),
        ('competitor_analysis', 'Competitor Analysis'),
        ('recommendations', 'Smart Recommendations'),
    )
    
    widgets = forms.MultipleChoiceField(
        choices=WIDGET_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        initial=['quick_stats', 'recent_leads', 'performance_chart', 'top_properties']
    )
    
    layout = forms.ChoiceField(
        choices=(
            ('grid', 'Grid Layout'),
            ('single_column', 'Single Column'),
            ('two_columns', 'Two Columns'),
        ),
        initial='grid',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    theme = forms.ChoiceField(
        choices=(
            ('light', 'Light Theme'),
            ('dark', 'Dark Theme'),
            ('auto', 'Auto (System)'),
        ),
        initial='light',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )


# ===================================================================
#  Enhanced Property Forms
# ===================================================================

class PropertyQuickEditForm(forms.ModelForm):
    """Form for quick editing property details"""
    
    class Meta:
        model = Property
        fields = ['title', 'price', 'status', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'price': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'status': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PropertyImageReorderForm(forms.Form):
    """Form for reordering property images"""
    
    image_order = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    def clean_image_order(self):
        order_data = self.cleaned_data.get('image_order', '')
        try:
            # Validate order data format
            order_pairs = order_data.split(',')
            for pair in order_pairs:
                if ':' not in pair:
                    raise ValidationError('Invalid order format')
                img_id, order = pair.split(':')
                int(img_id)
                int(order)
            return order_data
        except (ValueError, IndexError):
            raise ValidationError('Invalid order data format')


# ===================================================================
#  Saved Search Forms
# ===================================================================

# class SavedSearchForm(forms.ModelForm):
#     """Form for saving search criteria"""
    
#     class Meta:
#         model = SavedSearch
#         fields = ['name', 'email_alerts', 'whatsapp_alerts', 'push_alerts', 'alert_frequency']
#         widgets = {
#             'name': forms.TextInput(attrs={
#                 'class': 'form-control',
#                 'placeholder': 'E.g., 2BHK in Mumbai under 1.5Cr'
#             }),
#             'email_alerts': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
#             'whatsapp_alerts': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
#             'push_alerts': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
#             'alert_frequency': forms.Select(attrs={'class': 'form-select'}),
#         }


# ===================================================================
#  Add-on Services Forms
# ===================================================================

class AddOnServiceForm(forms.Form):
    """Form for purchasing add-on services"""
    
    SERVICE_CHOICES = (
        ('photography', 'Professional Photography - ₹1,999'),
        ('virtual_tour', 'Virtual Tour Creation - ₹2,999'),
        ('valuation', 'Property Valuation Report - ₹999'),
        ('top_placement', 'Top Placement (7 days) - ₹1,499'),
        ('social_media', 'Social Media Promotion - ₹799'),
        ('video_shoot', 'Professional Video Shoot - ₹3,999'),
    )
    
    service = forms.ChoiceField(
        choices=SERVICE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    property = forms.ModelChoiceField(
        queryset=Property.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    payment_method = forms.ChoiceField(
        choices=(
            ('credits', 'Use Credits'),
            ('razorpay', 'Pay Now'),
        ),
        initial='razorpay',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            self.fields['property'].queryset = Property.objects.filter(
                owner=self.user,
                is_active=True
            ).order_by('title')


# ===================================================================
# Membership Forms
# ===================================================================

class MembershipPlanSelectionForm(forms.Form):
    """Form for selecting membership plan"""
    
    plan = forms.ModelChoiceField(
        queryset=MembershipPlan.objects.filter(is_active=True),
        widget=forms.RadioSelect,
        label=_('Select a Plan'),
        empty_label=None
    )
    
    duration = forms.ChoiceField(
        choices=MembershipPlan.DURATION_CHOICES,
        initial='monthly',
        widget=forms.RadioSelect,
        label=_('Billing Duration')
    )
    
    accept_terms = forms.BooleanField(
        required=True,
        label=_('I agree to the Terms of Service and Privacy Policy'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter plans based on user's current plan
        if self.user:
            available_plans = MembershipService.get_available_plans(self.user)
            self.fields['plan'].queryset = available_plans
        
        # Add CSS classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.RadioSelect):
                field.widget.attrs.update({'class': 'form-check-input'})
    
    def clean(self):
        """Validate form data"""
        cleaned_data = super().clean()
        
        plan = cleaned_data.get('plan')
        duration = cleaned_data.get('duration')
        
        if plan and duration and self.user:
            # Check if user can select this plan
            can_upgrade, message = MembershipService.can_user_upgrade(self.user, plan)
            if not can_upgrade:
                raise ValidationError(message)
            
            # Validate duration for annual plans
            if duration == 'annual' and not plan.annual_price:
                raise ValidationError(
                    _('Annual billing is not available for this plan.')
                )
        
        return cleaned_data
    
    def get_total_amount(self):
        """Calculate total amount"""
        if self.is_valid():
            plan = self.cleaned_data['plan']
            duration = self.cleaned_data['duration']
            
            if duration == 'annual':
                return plan.annual_price or plan.monthly_price * 12
            return plan.monthly_price
        
        return 0


class SubscriptionUpgradeForm(forms.Form):
    """Form for upgrading subscription"""
    
    plan = forms.ModelChoiceField(
        queryset=MembershipPlan.objects.filter(is_active=True),
        widget=forms.RadioSelect,
        label=_('Select New Plan'),
        empty_label=None
    )
    
    duration = forms.ChoiceField(
        choices=MembershipPlan.DURATION_CHOICES,
        initial='monthly',
        widget=forms.RadioSelect,
        label=_('Billing Duration')
    )
    
    prorate = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Prorate remaining balance'),
        help_text=_('Apply credit from your current plan to the new plan'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            # Only show plans that are upgrades
            available_plans = MembershipService.get_available_plans(self.user)
            self.fields['plan'].queryset = available_plans
    
    def clean(self):
        """Validate upgrade"""
        cleaned_data = super().clean()
        
        plan = cleaned_data.get('plan')
        
        if plan and self.user:
            # Check if user can upgrade to this plan
            can_upgrade, message = MembershipService.can_user_upgrade(self.user, plan)
            if not can_upgrade:
                raise ValidationError(message)
        
        return cleaned_data
    
    def calculate_prorated_amount(self, current_subscription):
        """Calculate prorated amount for upgrade"""
        if not self.cleaned_data.get('prorate', True):
            return 0
        
        # Calculate unused portion of current subscription
        days_used = (timezone.now() - current_subscription.current_period_start).days
        total_days = (current_subscription.current_period_end - 
                     current_subscription.current_period_start).days
        
        if days_used <= 0 or total_days <= 0:
            return 0
        
        unused_ratio = 1 - (days_used / total_days)
        unused_amount = current_subscription.plan.monthly_price * unused_ratio
        
        return max(0, unused_amount)


class CreditPurchaseForm(forms.Form):
    """Form for purchasing credits"""
    
    package = forms.ModelChoiceField(
        queryset=CreditPackage.objects.filter(is_active=True),
        widget=forms.RadioSelect,
        label=_('Select Credit Package'),
        empty_label=None
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        """Validate credit purchase"""
        cleaned_data = super().clean()
        
        package = cleaned_data.get('package')
        
        if package and package.price <= 0:
            raise ValidationError(_('Invalid package selected.'))
        
        return cleaned_data


class SubscriptionCancellationForm(forms.Form):
    """Form for cancelling subscription"""
    
    REASON_CHOICES = (
        ('too_expensive', 'Too expensive'),
        ('missing_features', 'Missing features I need'),
        ('not_using', 'Not using the service enough'),
        ('poor_experience', 'Poor user experience'),
        ('found_better', 'Found a better alternative'),
        ('temporary', 'Temporary break'),
        ('other', 'Other reason'),
    )
    
    cancel_reason = forms.ChoiceField(
        choices=REASON_CHOICES,
        widget=forms.RadioSelect,
        label=_('Why are you cancelling?'),
        required=True
    )
    
    cancel_reason_other = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': _('Please specify your reason...')
        }),
        label=_('Other reason')
    )
    
    cancel_at_period_end = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Continue until end of billing period'),
        help_text=_('You will have access until the end of your current billing period.'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    feedback = forms.CharField(
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': _('Any feedback to help us improve?')
        }),
        label=_('Feedback (optional)')
    )
    
    def __init__(self, *args, **kwargs):
        self.subscription = kwargs.pop('subscription', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        """Validate cancellation"""
        cleaned_data = super().clean()
        
        if self.subscription and not self.subscription.is_active:
            raise ValidationError(_('Your subscription is not active.'))
        
        return cleaned_data
    
    def get_cancellation_reason(self):
        """Get formatted cancellation reason"""
        reason = self.cleaned_data.get('cancel_reason')
        reason_other = self.cleaned_data.get('cancel_reason_other')
        
        reason_display = dict(self.REASON_CHOICES).get(reason, '')
        
        if reason == 'other' and reason_other:
            return f"{reason_display}: {reason_other}"
        
        return reason_display


class BillingInformationForm(forms.ModelForm):
    """Form for updating billing information"""
    
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].disabled = True  # Email cannot be changed


class PaymentMethodForm(forms.Form):
    """Form for managing payment methods"""
    
    payment_method = forms.ChoiceField(
        choices=(
            ('razorpay', 'Razorpay (Credit/Debit Card, Net Banking, UPI)'),
            ('manual', 'Manual Payment/Invoice'),
        ),
        widget=forms.RadioSelect,
        label=_('Payment Method')
    )
    
    auto_renew = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Auto-renew subscription'),
        help_text=_('Automatically renew my subscription at the end of each billing period.'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        self.subscription = kwargs.pop('subscription', None)
        super().__init__(*args, **kwargs)
        
        if self.subscription:
            self.fields['auto_renew'].initial = self.subscription.auto_renew


# ===================================================================
# User Forms
# ===================================================================

class UserRegistrationForm(forms.ModelForm):
    """Form for user registration"""
    
    password1 = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create a strong password'
        }),
        min_length=8,
        help_text=_("Password must be at least 8 characters long.")
    )
    
    password2 = forms.CharField(
        label=_("Confirm Password"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password'
        })
    )
    
    user_type = forms.ChoiceField(
        label=_("I want to"),
        choices=CustomUser.USER_TYPE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial='buyer'
    )

    agency_name = forms.CharField(
        label=_("Agency Name (Optional)"),
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your agency name'
        }),
        help_text=_('If you represent a real estate agency, enter the agency name.')
    )

    terms = forms.BooleanField(
        label=_("I agree to the Terms & Conditions and Privacy Policy"),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make agency_name required for sellers and agents
        user_type = self.data.get('user_type') if self.data else self.initial.get('user_type')
        if user_type in ['seller', 'agent']:
            self.fields['agency_name'].required = True
            self.fields['agency_name'].label = _("Agency Name")
        else:
            self.fields['agency_name'].required = False
            self.fields['agency_name'].label = _("Agency Name (Optional)")

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone', 'user_type']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your first name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your last name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your email address'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1234567890'
            }),
        }
    
    def clean_email(self):
        """Validate email uniqueness"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError(_("A user with this email already exists."))
        return email.lower()
    
    def clean_phone(self):
        """Validate phone number"""
        phone = self.cleaned_data.get('phone')
        if phone and User.objects.filter(phone=phone).exists():
            raise ValidationError(_("This phone number is already registered."))
        return phone
    
    def clean_password2(self):
        """Check that the two password entries match"""
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError(_("Passwords don't match"))
        return password2
    
    def save(self, commit=True):
        """Save the user with encrypted password"""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.is_active = True  # Can set to False if email verification required
        
        if commit:
            user.save()
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
    




# ===================================================================
# Base Property Form with common validation and security
# ===================================================================

class BasePropertyForm(forms.ModelForm):
    """Base form with common validation and security"""
    
    class Meta:
        model = Property
        exclude = ['slug', 'ref_id', 'owner', 'is_active', 'is_verified', 
                  'view_count', 'inquiry_count', 'created_at', 'updated_at']
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Add CSS classes for better UI
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.NumberInput, forms.EmailInput)):
                field.widget.attrs.update({'class': 'form-control'})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'form-control', 'rows': 4})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
    
    def clean(self):
        """Global validation"""
        cleaned_data = super().clean()
        
        # Security: Sanitize user input
        for field in ['title', 'description', 'address', 'locality', 'landmark']:
            if field in cleaned_data:
                cleaned_data[field] = self._sanitize_input(cleaned_data[field])
        
        # Business logic validation
        self._validate_price_area_ratio(cleaned_data)
        self._validate_location_data(cleaned_data)
        self._validate_bedroom_bathroom_ratio(cleaned_data)
        
        return cleaned_data
    
    def _sanitize_input(self, value: str) -> str:
        """Sanitize HTML input to prevent XSS"""
        if not value:
            return value
        
        # Remove potentially dangerous tags
        dangerous_patterns = [
            r'<script.*?>.*?</script>',
            r'<iframe.*?>.*?</iframe>',
            r'on\w+=".*?"',
            r'javascript:',
            r'vbscript:',
            r'expression\(',
        ]
        
        for pattern in dangerous_patterns:
            value = re.sub(pattern, '', value, flags=re.IGNORECASE)
        
        return escape(value).strip()
    
    def _validate_price_area_ratio(self, cleaned_data: Dict):
        """Validate price per sqft is within reasonable limits"""
        price = cleaned_data.get('price')
        area = cleaned_data.get('area')
        
        if price and area and area > 0:
            price_per_sqft = price / area
            
            # Define reasonable limits (adjust based on your market)
            min_price_per_sqft = 500  # e.g., $500 per sqft minimum
            max_price_per_sqft = 10000  # e.g., $10,000 per sqft maximum
            
            if price_per_sqft < min_price_per_sqft:
                raise ValidationError({
                    'price': _('Price seems too low for the given area.'),
                    'area': _('Please verify the area or price.')
                })
            
            if price_per_sqft > max_price_per_sqft:
                raise ValidationError({
                    'price': _('Price seems too high for the given area.'),
                    'area': _('Please verify the area or price.')
                })
    
    def _validate_location_data(self, cleaned_data: Dict):
        """Validate location coordinates"""
        latitude = cleaned_data.get('latitude')
        longitude = cleaned_data.get('longitude')
        
        if latitude and longitude:
            # Validate coordinate ranges
            if not (-90 <= latitude <= 90):
                self.add_error('latitude', _('Latitude must be between -90 and 90.'))
            
            if not (-180 <= longitude <= 180):
                self.add_error('longitude', _('Longitude must be between -180 and 180.'))
            
            # Check if coordinates are valid (not in ocean/remote areas)
            try:
                # This would require a geocoding service
                # For now, just validate format
                pass
            except Exception:
                self.add_error('latitude', _('Invalid coordinates. Please check and try again.'))
    
    def _validate_bedroom_bathroom_ratio(self, cleaned_data: Dict):
        """Validate reasonable bedroom/bathroom ratio"""
        bedrooms = cleaned_data.get('bedrooms', 0)
        bathrooms = cleaned_data.get('bathrooms', 0)
        
        if bedrooms > 0 and bathrooms > bedrooms * 2:
            self.add_error(
                'bathrooms', 
                _('Number of bathrooms seems unusually high for the number of bedrooms.')
            )
        
        if bedrooms > 10 and bathrooms == 0:
            self.add_error(
                'bathrooms',
                _('Properties with many bedrooms typically have at least one bathroom.')
            )


# class PropertyCreationForm(BasePropertyForm):
#     """Form for creating new properties with membership validation - 99acres style"""
    
#     # Additional fields for 99acres style
#     amenities = forms.ModelMultipleChoiceField(
#         queryset=Amenity.objects.filter(is_active=True),
#         widget=forms.CheckboxSelectMultiple,
#         required=False,
#         label=_('Select Amenities')
#     )
    
#     # 99acres specific fields
#     possession_status = forms.ChoiceField(
#         choices=[
#             ('', 'Select Possession Status'),
#             ('ready_to_move', 'Ready to Move'),
#             ('under_construction', 'Under Construction'),
#             ('resale', 'Resale'),
#             ('new_booking', 'New Booking Available'),
#         ],
#         required=False,
#         label=_('Possession Status')
#     )
    
#     ownership_type = forms.ChoiceField(
#         choices=[
#             ('', 'Select Ownership'),
#             ('freehold', 'Freehold'),
#             ('leasehold', 'Leasehold'),
#             ('cooperative', 'Cooperative Society'),
#             ('power_of_attorney', 'Power of Attorney'),
#         ],
#         required=False,
#         label=_('Ownership Type')
#     )
    
#     preferred_tenants = forms.ChoiceField(
#         choices=[
#             ('', 'Select Preferred Tenants'),
#             ('family', 'Family Only'),
#             ('bachelors', 'Bachelors Allowed'),
#             ('company', 'Company Lease'),
#             ('anyone', 'Anyone'),
#         ],
#         required=False,
#         label=_('Preferred Tenants (For Rent)')
#     )
    
#     age_of_property = forms.IntegerField(
#         min_value=0,
#         max_value=100,
#         required=False,
#         label=_('Age of Property (Years)'),
#         widget=forms.NumberInput(attrs={'placeholder': 'e.g., 5'})
#     )
    
#     facing = forms.ChoiceField(
#         choices=[
#             ('', 'Select Facing'),
#             ('north', 'North'),
#             ('south', 'South'),
#             ('east', 'East'),
#             ('west', 'West'),
#             ('north_east', 'North-East'),
#             ('north_west', 'North-West'),
#             ('south_east', 'South-East'),
#             ('south_west', 'South-West'),
#         ],
#         required=False,
#         label=_('Facing Direction')
#     )
    
#     total_floors = forms.IntegerField(
#         min_value=0,
#         max_value=200,
#         required=False,
#         label=_('Total Floors in Building'),
#         widget=forms.NumberInput(attrs={'placeholder': 'e.g., 10'})
#     )
    
#     floor_number = forms.IntegerField(
#         min_value=0,
#         max_value=200,
#         required=False,
#         label=_('Floor Number'),
#         widget=forms.NumberInput(attrs={'placeholder': 'e.g., 3'})
#     )
    
#     super_builtup_area = forms.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#         required=False,
#         min_value=0,
#         label=_('Super Built-up Area'),
#         widget=forms.NumberInput(attrs={'placeholder': 'Super built-up area'})
#     )
    
#     carpet_area = forms.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#         required=False,
#         min_value=0,
#         label=_('Carpet Area'),
#         widget=forms.NumberInput(attrs={'placeholder': 'Carpet area'})
#     )
    
#     maintenance_charges = forms.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#         required=False,
#         min_value=0,
#         label=_('Monthly Maintenance (₹)'),
#         widget=forms.NumberInput(attrs={'placeholder': 'e.g., 2000'})
#     )
    
#     available_from = forms.DateField(
#         required=False,
#         label=_('Available From'),
#         widget=forms.DateInput(attrs={'type': 'date'})
#     )
    
#     booking_amount = forms.DecimalField(
#         max_digits=10,
#         decimal_places=2,
#         required=False,
#         min_value=0,
#         label=_('Booking Amount (₹)'),
#         widget=forms.NumberInput(attrs={'placeholder': 'Booking amount'})
#     )
    
#     class Meta(BasePropertyForm.Meta):
#         fields = [
#             'title', 'description', 'category', 'subcategory',
#             'price', 'price_negotiable', 'security_deposit',
#             'area', 'area_unit', 'bedrooms', 'bathrooms', 
#             'balconies', 'parking', 'status', 'furnishing',
#             'condition', 'year_built', 'address', 'city',
#             'locality', 'landmark', 'pincode', 'state', 'country',
#             'latitude', 'longitude', 'listing_type',
#             'contact_person', 'contact_email', 'contact_phone',
#             'virtual_tour', 'video_url', 'floor_plan',
#             'rera_registered', 'rera_number'
#         ]
#         widgets = {
#             'description': forms.Textarea(attrs={
#                 'rows': 6,
#                 'placeholder': 'Describe your property in detail. Include key features, amenities, nearby facilities...'
#             }),
#             'address': forms.Textarea(attrs={
#                 'rows': 3,
#                 'placeholder': 'Complete address including street, building name, etc.'
#             }),
#             'contact_phone': forms.TextInput(attrs={
#                 'placeholder': '+91 98765 43210'
#             }),
#         }
    
#     def __init__(self, *args, **kwargs):
#         self.user = kwargs.pop('user', None)
#         self.request = kwargs.pop('request', None)
#         super().__init__(*args, **kwargs)

#         # Set initial values
#         self.fields['contact_person'].initial = self.user.get_full_name() if self.user else ''
#         self.fields['contact_email'].initial = self.user.email if self.user else ''
#         self.fields['contact_phone'].initial = self.user.phone if self.user else ''

#         # Set default values for required fields
#         self.fields['country'].initial = 'India'
#         self.fields['listing_type'].initial = 'owner'

#         # Add placeholders and help text
#         self.fields['title'].widget.attrs.update({
#             'placeholder': 'e.g., 3BHK Luxury Apartment in Bandra West with Sea View'
#         })
#         self.fields['price'].widget.attrs.update({
#             'placeholder': 'e.g., 15000000'
#         })
#         self.fields['area'].widget.attrs.update({
#             'placeholder': 'e.g., 1800'
#         })
#         self.fields['locality'].widget.attrs.update({
#             'placeholder': 'e.g., Bandra West, Linking Road'
#         })

#         # Make fields required conditionally
#         if self.request and self.request.method == 'POST':
#             status = self.request.POST.get('status', '')
#             if status == 'for_rent':
#                 self.fields['security_deposit'].required = True
#                 self.fields['available_from'].required = True

#         # Dynamic category filtering with AJAX
#         self.fields['subcategory'].queryset = PropertySubCategory.objects.none()

#         if 'category' in self.data:
#             try:
#                 category_id = int(self.data.get('category'))
#                 self.fields['subcategory'].queryset = PropertySubCategory.objects.filter(
#                     category_id=category_id, is_active=True
#                 )
#             except (ValueError, TypeError):
#                 pass
#         elif self.instance and self.instance.pk and self.instance.category:
#             self.fields['subcategory'].queryset = self.instance.category.subcategories.filter(is_active=True)
    
#     def clean(self):
#         """Additional validation for property creation"""
#         cleaned_data = super().clean()
        
#         # Validate membership limits
#         if self.user:
#             try:
#                 membership = self.user.membership
#                 if not membership.can_list_property:
#                     raise ValidationError(
#                         _('You have reached your listing limit for your current membership plan. '
#                         'Please upgrade your plan or contact support.')
#                     )
#             except UserMembership.DoesNotExist:
#                 raise ValidationError(
#                     _('You need an active membership to list properties.')
#                 )
        
#         # Validate image count - IMPORTANT: We check request.FILES directly
#         if self.request:
#             images = self.request.FILES.getlist('images')
#             if len(images) < 3:
#                 raise ValidationError(_('Please upload at least 3 images.'))
#             if len(images) > 20:
#                 raise ValidationError(_('Maximum 20 images allowed.'))
#             # Validate image sizes - 99acres allows up to 10MB
#             for image in images:
#                 if image.size > 10 * 1024 * 1024:  # 10MB
#                     raise ValidationError(
#                         _('Image size should not exceed 10MB. '
#                         f'"{image.name}" is {image.size/1024/1024:.1f}MB.')
#                     )
                
#                 # Validate image file type
#                 import os
#                 ext = os.path.splitext(image.name)[1].lower()
#                 valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
#                 if ext not in valid_extensions:
#                     raise ValidationError(
#                         _('Invalid file type. Allowed types: JPG, JPEG, PNG, WebP, GIF.')
#                     )
                
#                 # Validate image dimensions (optional)
#                 try:
#                     from PIL import Image
#                     import io
                    
#                     # Read image without saving
#                     img_data = image.read()
#                     img = Image.open(io.BytesIO(img_data))
#                     width, height = img.size
                    
#                     # Reset file pointer
#                     image.seek(0)
                    
#                     # Minimum dimensions check
#                     if width < 400 or height < 300:
#                         raise ValidationError(
#                             _('Image dimensions too small. Minimum 400x300 pixels required.')
#                         )
                    
#                 except ImportError:
#                     # PIL not installed, skip dimension check
#                     pass
#                 except Exception:
#                     # If we can't read dimensions, still accept the image
#                     pass
        
#         # Validate price based on city average
#         price = cleaned_data.get('price')
#         city = cleaned_data.get('city')
#         area = cleaned_data.get('area')
        
#         if price and city and area and area > 0:
#             # Calculate price per sqft
#             price_per_sqft = price / area
            
#             # Get average price for the city (you might want to cache this)
#             from django.db.models import Avg
#             avg_price = Property.objects.filter(
#                 city=city,
#                 is_active=True,
#                 area__gt=0
#             ).aggregate(avg=Avg('price'))['avg']
            
#             if avg_price:
#                 avg_per_sqft = avg_price / 1000  # Assuming average area of 1000 sqft
#                 if price_per_sqft < avg_per_sqft * 0.3:  # 30% below average
#                     self.add_error('price', _('Price seems too low for this location. Please verify.'))
#                 elif price_per_sqft > avg_per_sqft * 3:  # 300% above average
#                     self.add_error('price', _('Price seems too high for this location. Please verify.'))
        
#         # Validate year built
#         year_built = cleaned_data.get('year_built')
#         if year_built:
#             current_year = timezone.now().year
#             if year_built > current_year + 5:  # Allow 5 years future for new constructions
#                 self.add_error('year_built', _('Year built cannot be more than 5 years in the future.'))
#             if year_built < 1800:
#                 self.add_error('year_built', _('Year built seems invalid.'))
        
#         # Validate area
#         area = cleaned_data.get('area')
#         if area and area <= 0:
#             self.add_error('area', _('Area must be greater than 0.'))
        
#         # Validate description length
#         description = cleaned_data.get('description')
#         if description and len(description) < 100:
#             self.add_error('description', _('Description must be at least 100 characters.'))
        
#         # Validate contact phone
#         contact_phone = cleaned_data.get('contact_phone')
#         if contact_phone:
#             # Basic phone validation
#             import re
#             phone_pattern = re.compile(r'^\+?[0-9\s\-\(\)]{10,15}$')
#             if not phone_pattern.match(contact_phone):
#                 self.add_error('contact_phone', _('Please enter a valid phone number.'))
        
#         # Validate RERA number if RERA registered is checked
#         rera_registered = cleaned_data.get('rera_registered')
#         rera_number = cleaned_data.get('rera_number')
#         if rera_registered and not rera_number:
#             self.add_error('rera_number', _('Please provide RERA registration number.'))
#         if rera_number and not rera_registered:
#             cleaned_data['rera_registered'] = True
        
#         return cleaned_data
    
#     def save(self, commit=True):
#         """Save the form with additional 99acres fields"""
#         instance = super().save(commit=False)
        
#         # Save additional fields if they exist in the model
#         additional_fields = [
#             'possession_status', 'ownership_type', 'preferred_tenants',
#             'age_of_property', 'facing', 'total_floors', 'floor_number',
#             'super_builtup_area', 'carpet_area', 'maintenance_charges',
#             'available_from', 'booking_amount'
#         ]
        
#         for field in additional_fields:
#             if hasattr(instance, field) and field in self.cleaned_data:
#                 setattr(instance, field, self.cleaned_data[field])
        
#         if commit:
#             instance.save()
#             self.save_m2m()
        
#         return instance
# 


class PropertySearchForm(forms.Form):
    """Advanced property search form"""
    
    # Basic search
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search by keyword, location, or address...'),
            'hx-get': '/properties/search/suggest/',
            'hx-target': '#search-suggestions',
            'hx-trigger': 'keyup changed delay:500ms'
        })
    )
    
    # Location
    city = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('City'),
            'list': 'city-options'
        })
    )
    
    locality = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Locality/Neighborhood')
        })
    )
    
    pincode = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Pincode'),
            'pattern': '[0-9]*',
            'maxlength': '10'
        })
    )
    
    # Price range with validation
    min_price = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': _('Min Price')
        })
    )
    
    max_price = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': _('Max Price')
        })
    )
    
    # Property details
    property_type = forms.ChoiceField(
        required=False,
        choices=[('', _('All Types'))] + list(PropertyCategory.PROPERTY_TYPES),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    category = forms.ModelChoiceField(
        required=False,
        queryset=PropertyCategory.objects.filter(is_active=True),
        empty_label=_('All Categories'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    bedrooms = forms.ChoiceField(
        required=False,
        choices=[
            ('', _('Any')),
            ('1', '1'),
            ('2', '2'),
            ('3', '3'),
            ('4', '4+')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    bathrooms = forms.ChoiceField(
        required=False,
        choices=[
            ('', _('Any')),
            ('1', '1'),
            ('2', '2'),
            ('3', '3+')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    min_area = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': _('Min Area')
        })
    )
    
    max_area = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': _('Max Area')
        })
    )
    
    # Status and furnishing
    status = forms.ChoiceField(
        required=False,
        choices=[('', _('All'))] + list(Property.STATUS_CHOICES),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    furnishing = forms.ChoiceField(
        required=False,
        choices=[('', _('Any'))] + list(Property.FURNISHING_CHOICES),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Advanced filters
    has_parking = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    rera_registered = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    is_verified = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    # Sort options
    SORT_CHOICES = [
        ('-created_at', _('Newest First')),
        ('created_at', _('Oldest First')),
        ('price', _('Price: Low to High')),
        ('-price', _('Price: High to Low')),
        ('area', _('Area: Small to Large')),
        ('-area', _('Area: Large to Small')),
        ('-view_count', _('Most Popular')),
    ]
    
    sort_by = forms.ChoiceField(
        required=False,
        choices=SORT_CHOICES,
        initial='-created_at',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def clean(self):
        """Validate search form"""
        cleaned_data = super().clean()
        
        # Validate price range
        min_price = cleaned_data.get('min_price')
        max_price = cleaned_data.get('max_price')
        
        if min_price and max_price and min_price > max_price:
            raise ValidationError(_('Minimum price cannot be greater than maximum price.'))
        
        # Validate area range
        min_area = cleaned_data.get('min_area')
        max_area = cleaned_data.get('max_area')
        
        if min_area and max_area and min_area > max_area:
            raise ValidationError(_('Minimum area cannot be greater than maximum area.'))
        
        # Sanitize search query
        query = cleaned_data.get('q')
        if query:
            cleaned_data['q'] = self._sanitize_search_query(query)
        
        return cleaned_data
    
    def _sanitize_search_query(self, query: str) -> str:
        """Sanitize search query to prevent injection"""
        # Remove SQL injection patterns
        sql_patterns = [
            r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|EXEC)\b)',
            r'(\-\-|\#|\/\*)',  # SQL comments
            r'(\b(OR|AND)\s+\d+=\d+\b)',  # Always true conditions
        ]
        
        for pattern in sql_patterns:
            query = re.sub(pattern, '', query, flags=re.IGNORECASE)
        
        # Limit length
        if len(query) > 200:
            query = query[:200]
        
        return query.strip()
    
    def get_search_queryset(self):
        """Convert form data to queryset filters"""
        filters = Q(is_active=True)
        
        # Keyword search (search across multiple fields)
        query = self.cleaned_data.get('q')
        if query:
            search_filters = Q()
            search_fields = ['title', 'description', 'address', 'city', 'locality', 'landmark']
            
            for field in search_fields:
                search_filters |= Q(**{f'{field}__icontains': query})
            
            filters &= search_filters
        
        # Location filters
        if self.cleaned_data.get('city'):
            filters &= Q(city__iexact=self.cleaned_data['city'])
        
        if self.cleaned_data.get('locality'):
            filters &= Q(locality__icontains=self.cleaned_data['locality'])
        
        if self.cleaned_data.get('pincode'):
            filters &= Q(pincode=self.cleaned_data['pincode'])
        
        # Price filters
        if self.cleaned_data.get('min_price'):
            filters &= Q(price__gte=self.cleaned_data['min_price'])
        
        if self.cleaned_data.get('max_price'):
            filters &= Q(price__lte=self.cleaned_data['max_price'])
        
        # Property type and category
        if self.cleaned_data.get('property_type'):
            filters &= Q(category__property_type=self.cleaned_data['property_type'])
        
        if self.cleaned_data.get('category'):
            filters &= Q(category=self.cleaned_data['category'])
        
        # Bedrooms and bathrooms
        if self.cleaned_data.get('bedrooms'):
            bedrooms = self.cleaned_data['bedrooms']
            if bedrooms == '4':
                filters &= Q(bedrooms__gte=4)
            else:
                filters &= Q(bedrooms=int(bedrooms))
        
        if self.cleaned_data.get('bathrooms'):
            bathrooms = self.cleaned_data['bathrooms']
            if bathrooms == '3':
                filters &= Q(bathrooms__gte=3)
            else:
                filters &= Q(bathrooms=int(bathrooms))
        
        # Area filters
        if self.cleaned_data.get('min_area'):
            filters &= Q(area__gte=self.cleaned_data['min_area'])
        
        if self.cleaned_data.get('max_area'):
            filters &= Q(area__lte=self.cleaned_data['max_area'])
        
        # Status and furnishing
        if self.cleaned_data.get('status'):
            filters &= Q(status=self.cleaned_data['status'])
        
        if self.cleaned_data.get('furnishing'):
            filters &= Q(furnishing=self.cleaned_data['furnishing'])
        
        # Advanced filters
        if self.cleaned_data.get('has_parking'):
            filters &= Q(parking__gt=0)
        
        if self.cleaned_data.get('rera_registered'):
            filters &= Q(rera_registered=True)
        
        if self.cleaned_data.get('is_verified'):
            filters &= Q(is_verified=True)
        
        return filters    