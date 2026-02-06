# core/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, UserProfile, PropertyCategory, PropertySubCategory,
    Property, PropertyImage, Amenity, PropertyAmenity,
    MembershipPlan, UserMembership, PropertyInquiry,
    PropertyFavorite, PropertyView, ContactMessage,
    NewsletterSubscription, SavedSearch
)


# Add these admin classes BEFORE PropertyAdmin
class PropertyCategoryAdmin(admin.ModelAdmin):
    """Admin for PropertyCategory model"""
    list_display = ('name', 'property_type', 'is_active', 'display_order')
    search_fields = ('name', 'description')
    list_filter = ('property_type', 'is_active')
    prepopulated_fields = {'slug': ('name',)}


class PropertySubCategoryAdmin(admin.ModelAdmin):
    """Admin for PropertySubCategory model"""
    list_display = ('name', 'category', 'is_active')
    search_fields = ('name', 'category__name')
    list_filter = ('category', 'is_active')
    prepopulated_fields = {'slug': ('name',)}


class CustomUserAdmin(UserAdmin):
    """Custom admin for CustomUser"""
    list_display = ('email', 'full_name', 'user_type', 'is_verified', 'is_active', 'date_joined')
    list_filter = ('user_type', 'is_verified', 'is_active', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone', 'user_type')}),
        ('Permissions', {'fields': ('is_verified', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'user_type', 'password1', 'password2'),
        }),
    )


class AmenityAdmin(admin.ModelAdmin):
    """Admin for Amenity model"""
    list_display = ('name', 'category', 'icon', 'is_active')
    search_fields = ('name', 'description')
    list_filter = ('category', 'is_active')


class PropertyImageInline(admin.TabularInline):
    """Inline for property images"""
    model = PropertyImage
    extra = 1
    fields = ('image', 'thumbnail', 'caption', 'is_primary', 'order')
    readonly_fields = ('thumbnail',)


class PropertyAmenityInline(admin.TabularInline):
    """Inline for property amenities"""
    model = PropertyAmenity
    extra = 1
    autocomplete_fields = ['amenity']  # This references Amenity model


class PropertyAdmin(admin.ModelAdmin):
    """Admin for Property model"""
    list_display = ('title', 'ref_id', 'city', 'price', 'status', 'is_featured', 'is_verified', 'is_active', 'created_at')
    list_filter = ('status', 'is_featured', 'is_verified', 'is_active', 'city', 'category', 'created_at')
    search_fields = ('title', 'ref_id', 'description', 'address', 'city')
    list_editable = ('is_featured', 'is_verified', 'is_active')
    readonly_fields = ('ref_id', 'slug', 'view_count', 'inquiry_count', 'created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'ref_id', 'description', 'owner', 'listing_type')
        }),
        ('Price & Status', {
            'fields': ('price', 'price_negotiable', 'security_deposit', 'status', 'is_sold_rented')
        }),
        ('Property Details', {
            'fields': ('category', 'subcategory', 'area', 'area_unit', 'bedrooms', 'bathrooms', 
                      'balconies', 'parking', 'furnishing', 'condition', 'year_built')
        }),
        ('Location', {
            'fields': ('address', 'city', 'locality', 'landmark', 'pincode', 'state', 'country',
                      'latitude', 'longitude')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'contact_email', 'contact_phone')
        }),
        ('Features & Media', {
            'fields': ('virtual_tour', 'video_url', 'floor_plan', 'rera_registered', 'rera_number')
        }),
        ('Display & SEO', {
            'fields': ('is_featured', 'featured_until', 'is_premium', 'is_verified', 'is_active',
                      'meta_title', 'meta_description')
        }),
        ('Statistics', {
            'fields': ('view_count', 'inquiry_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    inlines = [PropertyImageInline, PropertyAmenityInline]
    autocomplete_fields = ['owner', 'category', 'subcategory']  # These need search_fields in their respective admins
    date_hierarchy = 'created_at'


class PropertyInquiryAdmin(admin.ModelAdmin):
    # Use actual field names from the model
    list_display = ('id', 'name', 'email', 'phone', 'property_link', 
                    'status', 'contact_method', 'created_at')
    
    list_filter = ('status', 'contact_method', 'lead_source', 'created_at')
    
    search_fields = ('name', 'email', 'phone', 'property_link__title', 
                     'property_link__city')
    
    list_editable = ('status',)  # Remove 'is_read' since it doesn't exist
    
    ordering = ('-created_at',)
    
    raw_id_fields = ('property_link', 'user', 'responded_by')
    
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Lead Information', {
            'fields': ('name', 'email', 'phone', 'whatsapp_enabled', 'message')
        }),
        ('Property Details', {
            'fields': ('property_link', 'user')
        }),
        ('Lead Details', {
            'fields': ('budget', 'timeline', 'contact_method', 'lead_source', 'priority')
        }),
        ('Status & Response', {
            'fields': ('status', 'response', 'responded_at', 'responded_by')
        }),
        ('Additional Information', {
            'fields': ('notes', 'consent_given', 'last_contacted')
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    # Add custom methods for display
    def property_title(self, obj):
        return obj.property_link.title if obj.property_link else ''
    property_title.short_description = 'Property Title'
    
    def inquirer_name(self, obj):
        return obj.name  # Use the actual 'name' field
    inquirer_name.short_description = 'Name'
    
    def inquirer_email(self, obj):
        return obj.email  # Use the actual 'email' field
    inquirer_email.short_description = 'Email'
    
    # Add these to list_display if you want custom columns
    list_display = ('id', 'inquirer_name', 'inquirer_email', 'phone', 
                    'property_title', 'status', 'contact_method', 'created_at')


# class MembershipPlanAdmin(admin.ModelAdmin):
#     """Admin for MembershipPlan model"""
#     list_display = ('name', 'price', 'duration', 'max_listings', 'max_featured', 'is_popular', 'is_active')
#     list_filter = ('is_popular', 'is_active', 'duration')
#     search_fields = ('name', 'description')
#     list_editable = ('is_popular', 'is_active')
#     readonly_fields = ('slug', 'created_at', 'updated_at')
#     fieldsets = (
#         ('Basic Information', {
#             'fields': ('name', 'slug', 'description', 'display_order')
#         }),
#         ('Pricing', {
#             'fields': ('price', 'duration')
#         }),
#         ('Features', {
#             'fields': ('max_listings', 'max_featured', 'max_images_per_listing',
#                       'has_priority_ranking', 'has_advanced_analytics',
#                       'has_dedicated_support', 'can_use_virtual_tour', 'can_use_video')
#         }),
#         ('Display', {
#             'fields': ('is_popular', 'is_active', 'badge_text', 'badge_color')
#         }),
#         ('Trial', {
#             'fields': ('has_trial', 'trial_days')
#         }),
#         ('SEO', {
#             'fields': ('meta_title', 'meta_description')
#         }),
#     )


# class UserMembershipAdmin(admin.ModelAdmin):
#     """Admin for UserMembership model"""
#     list_display = ('user', 'plan', 'is_active', 'is_trial', 'start_date', 'end_date', 'days_remaining')
#     list_filter = ('is_active', 'is_trial', 'plan', 'start_date')
#     search_fields = ('user__email', 'user__first_name', 'user__last_name', 'stripe_subscription_id')
#     readonly_fields = ('created_at', 'updated_at', 'cancelled_at')
#     fieldsets = (
#         ('Membership Details', {
#             'fields': ('user', 'plan', 'is_active', 'is_trial', 'auto_renew')
#         }),
#         ('Subscription Dates', {
#             'fields': ('start_date', 'end_date', 'trial_end')
#         }),
#         ('Usage Tracking', {
#             'fields': ('listings_used', 'featured_used_this_month')
#         }),
#         ('Payment Information', {
#             'fields': ('stripe_subscription_id', 'razorpay_subscription_id',
#                       'last_payment_date', 'next_payment_date', 'amount_paid')
#         }),
#         ('Cancellation', {
#             'fields': ('cancelled_at', 'cancellation_reason')
#         }),
#     )


# Register all models with their admin classes
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(UserProfile)
admin.site.register(PropertyCategory, PropertyCategoryAdmin)  # Added with search_fields
admin.site.register(PropertySubCategory, PropertySubCategoryAdmin)  # Added with search_fields
admin.site.register(Property, PropertyAdmin)
admin.site.register(PropertyImage)
admin.site.register(Amenity, AmenityAdmin)  # Added with search_fields
admin.site.register(PropertyAmenity)
# admin.site.register(MembershipPlan, MembershipPlanAdmin)
# admin.site.register(UserMembership, UserMembershipAdmin)
admin.site.register(PropertyInquiry, PropertyInquiryAdmin)
admin.site.register(PropertyFavorite)
admin.site.register(PropertyView)
admin.site.register(ContactMessage)
admin.site.register(NewsletterSubscription)
admin.site.register(SavedSearch)