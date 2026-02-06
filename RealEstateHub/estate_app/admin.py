# admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.conf import settings
import json
from datetime import timedelta, datetime
from .models import (
    CustomUser, UserProfile, MembershipPlan, UserMembership,
    Property, PropertyImage, PropertyInquiry, PropertyView,
    PropertyCategory, PropertyType
)


class CustomUserCreationForm(UserCreationForm):
    """Custom user creation form for admin"""
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('email', 'first_name', 'last_name', 'user_type')


class CustomUserChangeForm(UserChangeForm):
    """Custom user change form for admin"""
    class Meta:
        model = CustomUser
        fields = '__all__'


class UserProfileInline(admin.StackedInline):
    """Inline admin for UserProfile"""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('avatar', 'bio', 'agency_logo')
        }),
        ('Contact Information', {
            'fields': ('whatsapp_number', 'website', 'address', 'city', 'state', 'country', 'pincode')
        }),
        ('Professional Details', {
            'fields': ('agency_name', 'license', 'experience_years', 'specialization', 'languages')
        }),
        ('Social Media', {
            'fields': ('facebook', 'twitter', 'linkedin', 'instagram')
        }),
        ('Verification', {
            'fields': ('is_verified_agent', 'verification_documents')
        }),
        ('Statistics', {
            'fields': ('total_listings', 'total_sales', 'success_rate', 'avg_response_time', 'total_clicks', 'total_calls')
        }),
    )


class UserMembershipInline(admin.TabularInline):
    """Inline admin for UserMembership"""
    model = UserMembership
    can_delete = False
    verbose_name_plural = 'Membership'
    fk_name = 'user'
    
    fields = ('plan', 'status', 'starts_at', 'expires_at', 'listings_used', 'featured_used')
    readonly_fields = ('listings_used', 'featured_used')
    
    def has_add_permission(self, request, obj=None):
        return False


class PropertyInline(admin.TabularInline):
    """Inline admin for User's Properties"""
    model = Property
    extra = 0
    can_delete = False
    verbose_name_plural = 'Properties'
    
    fields = ('property_id', 'title', 'property_for', 'status', 'price', 'city')
    readonly_fields = ('property_id', 'title', 'property_for', 'status', 'price', 'city')
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """Custom User Admin with enhanced features"""
    
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    
    list_display = (
        'email', 'full_name', 'user_type', 'seller_type', 
        'is_active', 'is_staff', 'is_verified', 
        'property_count', 'membership_status', 'created_at'
    )
    
    list_filter = (
        'user_type', 'seller_type', 'is_active', 'is_staff', 
        'is_verified', 'verification_status', 'created_at'
    )
    
    search_fields = ('email', 'first_name', 'last_name', 'phone', 'agency_name')
    
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Login Credentials', {
            'fields': ('email', 'password')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'phone', 'alternate_phone')
        }),
        ('User Type & Role', {
            'fields': ('user_type', 'seller_type', 'agency_name')
        }),
        ('Verification', {
            'fields': (
                'is_verified', 'verification_status', 
                'verification_token', 'verification_sent_at',
                'pan_card', 'aadhar_card'
            )
        }),
        ('Privacy Settings', {
            'fields': ('show_phone_to', 'show_email', 'allow_calls_from', 'allow_calls_to')
        }),
        ('Social Login', {
            'fields': ('google_id', 'facebook_id')
        }),
        ('Dashboard Preferences', {
            'fields': ('dashboard_theme', 'notification_preferences')
        }),
        ('Permissions', {
            'fields': (
                'is_active', 'is_staff', 'is_superuser',
                'groups', 'user_permissions'
            )
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'first_name', 'last_name', 
                'user_type', 'password1', 'password2'
            ),
        }),
    )
    
    inlines = [UserProfileInline, UserMembershipInline, PropertyInline]
    
    readonly_fields = ('last_login', 'date_joined', 'created_at', 'updated_at')
    
    actions = [
        'approve_users',
        'verify_users',
        'make_premium_verified',
        'impersonate_users',
        'send_welcome_email',
        'export_user_data',
        'bulk_update_membership',
    ]
    
    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Full Name'
    
    def property_count(self, obj):
        count = obj.properties.count()
        url = reverse('admin:core_property_changelist') + f'?owner__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)
    property_count.short_description = 'Properties'
    
    def membership_status(self, obj):
        try:
            membership = obj.membership
            if membership.is_active:
                return format_html(
                    '<span class="badge badge-success">{}</span>',
                    f"{membership.plan.name if membership.plan else 'No Plan'}"
                )
            else:
                return format_html(
                    '<span class="badge badge-danger">Expired</span>'
                )
        except UserMembership.DoesNotExist:
            return format_html(
                '<span class="badge badge-warning">No Membership</span>'
            )
    membership_status.short_description = 'Membership'
    
    # Custom Actions
    def approve_users(self, request, queryset):
        updated = queryset.update(is_active=True, is_verified=True)
        self.message_user(
            request, 
            f'Successfully approved {updated} user(s).',
            messages.SUCCESS
        )
    approve_users.short_description = "✅ Approve selected users"
    
    def verify_users(self, request, queryset):
        updated = queryset.update(is_verified=True, verification_status='verified')
        self.message_user(
            request,
            f'Successfully verified {updated} user(s).',
            messages.SUCCESS
        )
    verify_users.short_description = "✅ Verify selected users"
    
    def make_premium_verified(self, request, queryset):
        updated = queryset.update(verification_status='premium_verified')
        self.message_user(
            request,
            f'Successfully upgraded {updated} user(s) to Premium Verified.',
            messages.SUCCESS
        )
    make_premium_verified.short_description = "⭐ Upgrade to Premium Verified"
    
    def impersonate_users(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                'Please select exactly one user to impersonate.',
                messages.ERROR
            )
            return
        
        user = queryset.first()
        from django.contrib.auth import login
        from django.contrib.auth.models import AnonymousUser
        
        # Store original user in session
        request.session['original_user_id'] = request.user.id
        request.session['impersonated_by'] = request.user.id
        
        # Log in as selected user
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)
        
        self.message_user(
            request,
            f'Now impersonating {user.email}. Use the "Stop Impersonating" button to return.',
            messages.SUCCESS
        )
        
        return HttpResponseRedirect('/seller/dashboard/')
    impersonate_users.short_description = "👤 Impersonate User"
    
    def send_welcome_email(self, request, queryset):
        for user in queryset:
            subject = 'Welcome to BHOOSPARSH - Your Account is Ready!'
            message = render_to_string('emails/welcome.html', {
                'user': user,
                'login_url': request.build_absolute_uri('/login/')
            })
            
            send_mail(
                subject,
                '',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=message,
                fail_silently=True
            )
        
        self.message_user(
            request,
            f'Welcome email sent to {queryset.count()} user(s).',
            messages.SUCCESS
        )
    send_welcome_email.short_description = "📧 Send Welcome Email"
    
    def export_user_data(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="users_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Email', 'Full Name', 'User Type', 'Phone', 
            'City', 'Join Date', 'Properties', 'Status'
        ])
        
        for user in queryset:
            try:
                city = user.profile.city
            except:
                city = ''
            
            writer.writerow([
                user.email,
                user.full_name,
                user.get_user_type_display(),
                user.phone,
                city,
                user.date_joined.strftime('%Y-%m-%d'),
                user.properties.count(),
                'Active' if user.is_active else 'Inactive'
            ])
        
        return response
    export_user_data.short_description = "📥 Export User Data (CSV)"
    
    def bulk_update_membership(self, request, queryset):
        # This would show a custom page for bulk membership update
        from django.shortcuts import render
        
        if 'apply' in request.POST:
            plan_id = request.POST.get('plan')
            if plan_id:
                plan = MembershipPlan.objects.get(id=plan_id)
                for user in queryset:
                    UserMembership.objects.update_or_create(
                        user=user,
                        defaults={
                            'plan': plan,
                            'status': 'active',
                            'starts_at': timezone.now(),
                            'expires_at': timezone.now() + timedelta(days=30)
                        }
                    )
                
                self.message_user(
                    request,
                    f'Successfully updated membership for {queryset.count()} user(s).',
                    messages.SUCCESS
                )
                return HttpResponseRedirect(request.get_full_path())
        
        plans = MembershipPlan.objects.filter(is_active=True)
        return render(request, 'admin/bulk_update_membership.html', {
            'users': queryset,
            'plans': plans,
            'title': 'Bulk Update Membership'
        })
    bulk_update_membership.short_description = "🔄 Bulk Update Membership"
    
    # Custom Admin Views
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('impersonate/<int:user_id>/', self.admin_site.admin_view(self.impersonate_view)),
            path('stop-impersonating/', self.admin_site.admin_view(self.stop_impersonating_view)),
            path('dashboard-stats/', self.admin_site.admin_view(self.dashboard_stats_view)),
            path('send-bulk-email/', self.admin_site.admin_view(self.send_bulk_email_view)),
            path('user-activity/<int:user_id>/', self.admin_site.admin_view(self.user_activity_view)),
        ]
        return custom_urls + urls
    
    def impersonate_view(self, request, user_id):
        """Impersonate a specific user"""
        try:
            user = CustomUser.objects.get(id=user_id)
            from django.contrib.auth import login
            
            # Store original user
            request.session['original_user_id'] = request.user.id
            request.session['impersonated_by'] = request.user.id
            
            # Log in as user
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            
            messages.success(request, f'Now impersonating {user.email}')
            return redirect('/seller/dashboard/')
        except CustomUser.DoesNotExist:
            messages.error(request, 'User not found')
            return redirect('admin:core_customuser_changelist')
    
    def stop_impersonating_view(self, request):
        """Stop impersonating and return to admin"""
        original_user_id = request.session.get('original_user_id')
        if original_user_id:
            try:
                original_user = CustomUser.objects.get(id=original_user_id)
                from django.contrib.auth import login
                
                original_user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, original_user)
                
                # Clear session
                del request.session['original_user_id']
                del request.session['impersonated_by']
                
                messages.success(request, 'Stopped impersonating')
            except CustomUser.DoesNotExist:
                messages.error(request, 'Original user not found')
        
        return redirect('admin:index')
    
    def dashboard_stats_view(self, request):
        """Admin dashboard with statistics"""
        # User Statistics
        total_users = CustomUser.objects.count()
        new_users_today = CustomUser.objects.filter(
            created_at__date=timezone.now().date()
        ).count()
        
        user_types = CustomUser.objects.values('user_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Property Statistics
        total_properties = Property.objects.count()
        active_properties = Property.objects.filter(status='active').count()
        featured_properties = Property.objects.filter(is_featured=True).count()
        
        # Lead Statistics
        total_leads = PropertyInquiry.objects.count()
        new_leads_today = PropertyInquiry.objects.filter(
            created_at__date=timezone.now().date()
        ).count()
        
        # Revenue Statistics
        # Assuming you have a Payment model
        # total_revenue = Payment.objects.filter(status='completed').aggregate(
        #     total=Sum('amount')
        # )['total'] or 0
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'Admin Dashboard',
            'total_users': total_users,
            'new_users_today': new_users_today,
            'user_types': user_types,
            'total_properties': total_properties,
            'active_properties': active_properties,
            'featured_properties': featured_properties,
            'total_leads': total_leads,
            'new_leads_today': new_leads_today,
            # 'total_revenue': total_revenue,
        }
        
        return render(request, 'admin/dashboard_stats.html', context)
    
    def send_bulk_email_view(self, request):
        """Send bulk email to users"""
        if request.method == 'POST':
            subject = request.POST.get('subject')
            message = request.POST.get('message')
            user_type = request.POST.get('user_type', 'all')
            
            if user_type == 'all':
                users = CustomUser.objects.filter(is_active=True)
            else:
                users = CustomUser.objects.filter(user_type=user_type, is_active=True)
            
            sent_count = 0
            for user in users:
                try:
                    send_mail(
                        subject,
                        '',
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                        html_message=message,
                        fail_silently=True
                    )
                    sent_count += 1
                except:
                    pass
            
            messages.success(request, f'Email sent to {sent_count} users')
            return redirect('admin:send-bulk-email')
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'Send Bulk Email',
        }
        return render(request, 'admin/send_bulk_email.html', context)
    
    def user_activity_view(self, request, user_id):
        """View detailed user activity"""
        user = CustomUser.objects.get(id=user_id)
        
        # Get user's recent activity
        recent_properties = Property.objects.filter(owner=user).order_by('-created_at')[:10]
        recent_inquiries = PropertyInquiry.objects.filter(property__owner=user).order_by('-created_at')[:10]
        
        context = {
            **self.admin_site.each_context(request),
            'title': f'Activity: {user.email}',
            'user': user,
            'recent_properties': recent_properties,
            'recent_inquiries': recent_inquiries,
        }
        
        return render(request, 'admin/user_activity.html', context)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin for UserProfile"""
    list_display = ('user', 'agency_name', 'city', 'is_verified_agent', 'total_listings')
    list_filter = ('is_verified_agent', 'city', 'state', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'agency_name', 'city')
    readonly_fields = ('total_listings', 'total_sales', 'success_rate', 'created_at', 'updated_at')
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Personal Information', {
            'fields': ('avatar', 'bio', 'agency_logo')
        }),
        ('Contact Information', {
            'fields': ('whatsapp_number', 'website', 'address', 'city', 'state', 'country', 'pincode')
        }),
        ('Professional Details', {
            'fields': ('agency_name', 'license', 'experience_years', 'specialization', 'languages')
        }),
        ('Social Media', {
            'fields': ('facebook', 'twitter', 'linkedin', 'instagram')
        }),
        ('Verification', {
            'fields': ('is_verified_agent', 'verification_documents')
        }),
        ('Statistics', {
            'fields': ('total_listings', 'total_sales', 'success_rate', 'avg_response_time', 'total_clicks', 'total_calls')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


class PropertyImageInline(admin.TabularInline):
    """Inline admin for Property Images"""
    model = PropertyImage
    extra = 1
    fields = ('image', 'caption', 'is_primary', 'display_order')
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('display_order', '-is_primary')


class PropertyInquiryInline(admin.TabularInline):
    """Inline admin for Property Inquiries"""
    model = PropertyInquiry
    extra = 0
    can_delete = False
    readonly_fields = ('name', 'email', 'phone', 'message', 'status', 'created_at')
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-created_at')[:5]


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    """Admin for Property"""
    
    list_display = (
        'title', 'owner', 'property_for', 'status', 
        'city', 'price_display', 'is_featured', 
        'view_count', 'inquiry_count', 'created_at'
    )
    
    list_filter = (
        'status', 'property_for', 'category', 'property_type',
        'city', 'state', 'is_featured', 'is_urgent', 'is_premium',
        'created_at'
    )
    
    search_fields = (
        'title', 'description', 'address', 'city', 'state',
        'property_id', 'owner__email', 'owner__first_name', 'owner__last_name'
    )
    
    list_editable = ('status', 'is_featured')
    
    readonly_fields = (
        'property_id', 'view_count', 'inquiry_count', 'favorite_count',
        'created_at', 'updated_at', 'published_at'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('property_id', 'owner', 'category', 'property_type')
        }),
        ('Property Details', {
            'fields': ('title', 'description', 'slug', 'property_for', 'listing_type', 'status')
        }),
        ('Location', {
            'fields': ('address', 'city', 'state', 'country', 'pincode', 'landmark',
                      'latitude', 'longitude', 'google_map_url')
        }),
        ('Pricing', {
            'fields': ('price', 'price_per_sqft', 'currency', 'maintenance_charges',
                      'booking_amount', 'price_negotiable')
        }),
        ('Area Details', {
            'fields': ('carpet_area', 'builtup_area', 'super_builtup_area', 'plot_area')
        }),
        ('Residential Details', {
            'fields': ('bedrooms', 'bathrooms', 'balconies', 'furnishing')
        }),
        ('Commercial Details', {
            'fields': ('commercial_type', 'floor_number', 'total_floors')
        }),
        ('Industrial Details', {
            'fields': ('industrial_type', 'ceiling_height', 'loading_dock', 'power_supply')
        }),
        ('Plot/Land Details', {
            'fields': ('plot_type', 'facing')
        }),
        ('Additional Details', {
            'fields': ('age_of_property', 'possession_status', 'amenities')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'contact_phone', 'contact_email', 'show_contact')
        }),
        ('Boost Features', {
            'fields': ('is_featured', 'is_urgent', 'is_premium', 'is_verified')
        }),
        ('Statistics', {
            'fields': ('view_count', 'inquiry_count', 'favorite_count')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'published_at', 'expired_at')
        }),
    )
    
    inlines = [PropertyImageInline, PropertyInquiryInline]
    
    actions = [
        'approve_properties',
        'reject_properties',
        'make_featured',
        'remove_featured',
        'mark_as_sold',
        'renew_properties',
        'export_properties',
    ]
    
    def price_display(self, obj):
        return obj.formatted_price
    price_display.short_description = 'Price'
    
    def approve_properties(self, request, queryset):
        updated = queryset.update(status='active', published_at=timezone.now())
        self.message_user(
            request,
            f'Successfully approved {updated} property(s).',
            messages.SUCCESS
        )
    approve_properties.short_description = "✅ Approve Properties"
    
    def reject_properties(self, request, queryset):
        updated = queryset.update(status='rejected')
        self.message_user(
            request,
            f'Successfully rejected {updated} property(s).',
            messages.SUCCESS
        )
    reject_properties.short_description = "❌ Reject Properties"
    
    def make_featured(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(
            request,
            f'Successfully featured {updated} property(s).',
            messages.SUCCESS
        )
    make_featured.short_description = "⭐ Make Featured"
    
    def remove_featured(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(
            request,
            f'Successfully removed featured from {updated} property(s).',
            messages.SUCCESS
        )
    remove_featured.short_description = "📌 Remove Featured"
    
    def mark_as_sold(self, request, queryset):
        updated = queryset.update(status='sold')
        self.message_user(
            request,
            f'Successfully marked {updated} property(s) as sold.',
            messages.SUCCESS
        )
    mark_as_sold.short_description = "💰 Mark as Sold"
    
    def renew_properties(self, request, queryset):
        from datetime import timedelta
        
        for property in queryset:
            if property.expired_at:
                property.expired_at = property.expired_at + timedelta(days=30)
                property.save()
        
        self.message_user(
            request,
            f'Successfully renewed {queryset.count()} property(s).',
            messages.SUCCESS
        )
    renew_properties.short_description = "🔄 Renew Properties"
    
    def export_properties(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="properties_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Title', 'Owner', 'Type', 'Status', 'City', 
            'Price', 'Area', 'Bedrooms', 'Bathrooms', 'Views', 'Leads'
        ])
        
        for property in queryset:
            writer.writerow([
                property.property_id,
                property.title[:50],
                property.owner.email,
                property.get_property_for_display(),
                property.get_status_display(),
                property.city,
                property.price,
                property.carpet_area,
                property.bedrooms or '',
                property.bathrooms or '',
                property.view_count,
                property.inquiry_count
            ])
        
        return response
    export_properties.short_description = "📥 Export Properties (CSV)"
    
    # Custom change form for better UX
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            property = Property.objects.get(id=object_id)
            extra_context['recent_inquiries'] = property.inquiries.all().order_by('-created_at')[:10]
            extra_context['total_views'] = property.view_count
        return super().changeform_view(request, object_id, form_url, extra_context)


@admin.register(PropertyInquiry)
class PropertyInquiryAdmin(admin.ModelAdmin):
    """Admin for Property Inquiries"""
    
    list_display = (
        'name', 'email', 'phone', 'property', 'status',
        'status_badge', 'source', 'created_at', 'response_status'
    )
    
    list_filter = ('status', 'source', 'property__owner', 'created_at')
    search_fields = ('name', 'email', 'phone', 'message', 'property__title')
    list_editable = ('status',)
    
    readonly_fields = ('created_at', 'updated_at', 'responded_at')
    
    fieldsets = (
        ('Lead Information', {
            'fields': ('property', 'user', 'name', 'email', 'phone', 'message')
        }),
        ('Additional Info', {
            'fields': ('budget', 'preferred_date', 'preferred_time')
        }),
        ('Status Management', {
            'fields': ('status', 'priority', 'response', 'responded_at', 'responded_by')
        }),
        ('Source Tracking', {
            'fields': ('source', 'ip_address', 'user_agent')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = [
        'mark_as_contacted',
        'mark_as_interested',
        'mark_as_converted',
        'assign_to_agent',
        'export_leads',
    ]
    
    def status_badge(self, obj):
        colors = {
            'new': 'blue',
            'contacted': 'green',
            'interested': 'purple',
            'converted': 'orange',
            'not_interested': 'red',
            'spam': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def response_status(self, obj):
        if obj.response:
            return format_html(
                '<span class="badge badge-success">Responded</span>'
            )
        else:
            return format_html(
                '<span class="badge badge-warning">Pending</span>'
            )
    response_status.short_description = 'Response'
    
    def mark_as_contacted(self, request, queryset):
        updated = queryset.update(status='contacted', responded_at=timezone.now(), responded_by=request.user)
        self.message_user(
            request,
            f'Marked {updated} lead(s) as contacted.',
            messages.SUCCESS
        )
    mark_as_contacted.short_description = "📞 Mark as Contacted"
    
    def mark_as_interested(self, request, queryset):
        updated = queryset.update(status='interested')
        self.message_user(
            request,
            f'Marked {updated} lead(s) as interested.',
            messages.SUCCESS
        )
    mark_as_interested.short_description = "⭐ Mark as Interested"
    
    def mark_as_converted(self, request, queryset):
        updated = queryset.update(status='converted')
        self.message_user(
            request,
            f'Marked {updated} lead(s) as converted.',
            messages.SUCCESS
        )
    mark_as_converted.short_description = "💰 Mark as Converted"
    
    def assign_to_agent(self, request, queryset):
        # This would show a custom page to assign leads to agents
        from django.shortcuts import render
        
        if 'apply' in request.POST:
            agent_id = request.POST.get('agent')
            if agent_id:
                agent = CustomUser.objects.get(id=agent_id)
                queryset.update(assigned_to=agent)
                
                self.message_user(
                    request,
                    f'Successfully assigned {queryset.count()} lead(s) to {agent.email}.',
                    messages.SUCCESS
                )
                return HttpResponseRedirect(request.get_full_path())
        
        agents = CustomUser.objects.filter(user_type__in=['agent', 'admin'])
        return render(request, 'admin/assign_leads.html', {
            'leads': queryset,
            'agents': agents,
            'title': 'Assign Leads to Agent'
        })
    assign_to_agent.short_description = "👥 Assign to Agent"
    
    def export_leads(self, request, queryset):
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="leads_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Date', 'Name', 'Email', 'Phone', 'Property', 
            'Status', 'Source', 'Response'
        ])
        
        for lead in queryset:
            writer.writerow([
                lead.created_at.strftime('%Y-%m-%d %H:%M'),
                lead.name,
                lead.email,
                lead.phone,
                lead.property.title,
                lead.get_status_display(),
                lead.get_source_display(),
                'Yes' if lead.response else 'No'
            ])
        
        return response
    export_leads.short_description = "📥 Export Leads (CSV)"
    
    # Custom form to make it easier to respond
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj and not obj.response:
            form.base_fields['response'].widget.attrs['placeholder'] = 'Enter your response here...'
            form.base_fields['response'].required = True
        return form


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    """Admin for Membership Plans with package enable/disable"""
    
    list_display = (
        'name', 'plan_type', 'price_display', 'monthly_price_display',
        'max_listings', 'max_featured', 'is_active', 'is_popular', 'display_order'
    )
    
    list_filter = ('plan_type', 'is_active', 'is_popular', 'created_at')
    search_fields = ('name', 'description', 'slug')
    list_editable = ('is_active', 'is_popular', 'display_order')
    
    readonly_fields = ('created_at', 'updated_at', 'monthly_price_display', 'yearly_price_display')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'plan_type')
        }),
        ('Pricing', {
            'fields': ('price', 'billing_cycle', 'monthly_price_display', 'yearly_price_display')
        }),
        ('Listing Limits', {
            'fields': ('max_listings', 'max_featured', 'max_active_listings', 'is_unlimited')
        }),
        ('Boost Features', {
            'fields': ('has_spotlight_boost', 'has_featured_listings', 
                      'has_urgent_tag', 'has_photo_highlight')
        }),
        ('Contact Features', {
            'fields': ('show_contact_details', 'whatsapp_notifications', 'sms_notifications')
        }),
        ('Support Features', {
            'fields': ('priority_support', 'dedicated_manager', 'analytics_dashboard')
        }),
        ('Display Settings', {
            'fields': ('is_active', 'is_popular', 'display_order')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = [
        'activate_plans',
        'deactivate_plans',
        'make_popular',
        'duplicate_plans',
        'reset_to_defaults',
    ]
    
    def price_display(self, obj):
        if obj.billing_cycle == 'monthly':
            return f"₹{obj.price}/month"
        elif obj.billing_cycle == 'quarterly':
            return f"₹{obj.price}/quarter"
        elif obj.billing_cycle == 'yearly':
            return f"₹{obj.price}/year"
        return f"₹{obj.price}"
    price_display.short_description = 'Price'
    
    def monthly_price_display(self, obj):
        monthly = obj.monthly_price
        return f"₹{monthly:,.2f}/month"
    monthly_price_display.short_description = 'Monthly Equivalent'
    
    def yearly_price_display(self, obj):
        yearly = obj.yearly_price
        return f"₹{yearly:,.2f}/year"
    yearly_price_display.short_description = 'Yearly Equivalent'
    
    def activate_plans(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f'Successfully activated {updated} plan(s).',
            messages.SUCCESS
        )
    activate_plans.short_description = "✅ Activate Plans"
    
    def deactivate_plans(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f'Successfully deactivated {updated} plan(s).',
            messages.SUCCESS
        )
    deactivate_plans.short_description = "❌ Deactivate Plans"
    
    def make_popular(self, request, queryset):
        # First, unset popular from all plans
        MembershipPlan.objects.update(is_popular=False)
        # Then set selected ones as popular
        updated = queryset.update(is_popular=True)
        self.message_user(
            request,
            f'Successfully marked {updated} plan(s) as popular.',
            messages.SUCCESS
        )
    make_popular.short_description = "⭐ Mark as Popular"
    
    def duplicate_plans(self, request, queryset):
        for plan in queryset:
            plan.pk = None
            plan.slug = f"{plan.slug}-copy"
            plan.name = f"{plan.name} (Copy)"
            plan.is_popular = False
            plan.display_order = plan.display_order + 100
            plan.save()
        
        self.message_user(
            request,
            f'Successfully duplicated {queryset.count()} plan(s).',
            messages.SUCCESS
        )
    duplicate_plans.short_description = "📋 Duplicate Plans"
    
    def reset_to_defaults(self, request, queryset):
        """Reset plans to default configurations"""
        default_plans = [
            {
                'name': 'Essential',
                'slug': 'essential',
                'price': 0,
                'max_listings': 5,
                'max_featured': 2,
                'is_unlimited': False,
            },
            {
                'name': 'Professional',
                'slug': 'professional',
                'price': 2499,
                'max_listings': 15,
                'max_featured': 5,
                'is_unlimited': False,
            },
            {
                'name': 'Enterprise',
                'slug': 'enterprise',
                'price': 4999,
                'max_listings': 999,
                'max_featured': 15,
                'is_unlimited': True,
            },
        ]
        
        for plan in queryset:
            for default in default_plans:
                if plan.slug == default['slug']:
                    plan.price = default['price']
                    plan.max_listings = default['max_listings']
                    plan.max_featured = default['max_featured']
                    plan.is_unlimited = default['is_unlimited']
                    plan.save()
                    break
        
        self.message_user(
            request,
            f'Successfully reset {queryset.count()} plan(s) to defaults.',
            messages.SUCCESS
        )
    reset_to_defaults.short_description = "🔄 Reset to Defaults"


@admin.register(UserMembership)
class UserMembershipAdmin(admin.ModelAdmin):
    """Admin for User Memberships"""
    
    list_display = (
        'user', 'plan', 'status_badge', 'starts_at', 
        'expires_at', 'days_until_expiry', 'listings_used',
        'auto_renew', 'created_at'
    )
    
    list_filter = ('status', 'plan', 'auto_renew', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'plan__name')
    list_editable = ('auto_renew',)
    
    readonly_fields = (
        'subscription_id', 'payment_method', 
        'listings_used', 'featured_used', 'boosts_used',
        'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('User & Plan', {
            'fields': ('user', 'plan')
        }),
        ('Subscription Details', {
            'fields': ('status', 'starts_at', 'expires_at')
        }),
        ('Payment Details', {
            'fields': ('subscription_id', 'payment_method')
        }),
        ('Usage Tracking', {
            'fields': ('listings_used', 'featured_used', 'boosts_used')
        }),
        ('Renewal Settings', {
            'fields': ('auto_renew', 'renews_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = [
        'activate_memberships',
        'extend_memberships',
        'cancel_memberships',
        'reset_usage',
        'enable_auto_renew',
        'disable_auto_renew',
    ]
    
    def status_badge(self, obj):
        colors = {
            'active': 'success',
            'expired': 'danger',
            'cancelled': 'warning',
            'pending': 'info'
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def days_until_expiry(self, obj):
        days = obj.days_until_expiry
        if days is None:
            return 'N/A'
        
        if days > 30:
            color = 'success'
        elif days > 7:
            color = 'warning'
        else:
            color = 'danger'
        
        return format_html(
            '<span class="badge badge-{}">{} days</span>',
            color,
            days
        )
    days_until_expiry.short_description = 'Expires In'
    
    def activate_memberships(self, request, queryset):
        updated = queryset.update(status='active')
        self.message_user(
            request,
            f'Successfully activated {updated} membership(s).',
            messages.SUCCESS
        )
    activate_memberships.short_description = "✅ Activate Memberships"
    
    def extend_memberships(self, request, queryset):
        for membership in queryset:
            if membership.expires_at:
                membership.expires_at = membership.expires_at + timedelta(days=30)
            else:
                membership.expires_at = timezone.now() + timedelta(days=30)
            membership.save()
        
        self.message_user(
            request,
            f'Successfully extended {queryset.count()} membership(s) by 30 days.',
            messages.SUCCESS
        )
    extend_memberships.short_description = "📅 Extend 30 Days"
    
    def cancel_memberships(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(
            request,
            f'Successfully cancelled {updated} membership(s).',
            messages.SUCCESS
        )
    cancel_memberships.short_description = "❌ Cancel Memberships"
    
    def reset_usage(self, request, queryset):
        updated = queryset.update(listings_used=0, featured_used=0, boosts_used=0)
        self.message_user(
            request,
            f'Successfully reset usage for {updated} membership(s).',
            messages.SUCCESS
        )
    reset_usage.short_description = "🔄 Reset Usage"
    
    def enable_auto_renew(self, request, queryset):
        updated = queryset.update(auto_renew=True)
        self.message_user(
            request,
            f'Successfully enabled auto-renew for {updated} membership(s).',
            messages.SUCCESS
        )
    enable_auto_renew.short_description = "🔁 Enable Auto Renew"
    
    def disable_auto_renew(self, request, queryset):
        updated = queryset.update(auto_renew=False)
        self.message_user(
            request,
            f'Successfully disabled auto-renew for {updated} membership(s).',
            messages.SUCCESS
        )
    disable_auto_renew.short_description = "⏸️ Disable Auto Renew"


admin.register(PropertyCategory)
@admin.register(PropertyCategory)
class PropertyCategoryAdmin(admin.ModelAdmin):
    """Admin for Property Categories"""

    list_display = (
        'name',
        'slug',
        'icon',
        'is_active',
        'display_order',
    )

    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    list_editable = ('is_active', 'display_order')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('display_order', 'name')


@admin.register(PropertyType)
class PropertyTypeAdmin(admin.ModelAdmin):
    """Admin for Property Types"""
    list_display = ('name', 'category', 'slug', 'is_active', 'property_count')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'category__name')
    prepopulated_fields = {'slug': ('name',)}
    
    def property_count(self, obj):
        count = obj.properties.count()
        url = reverse('admin:core_property_changelist') + f'?property_type__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)
    property_count.short_description = 'Properties'


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    """Admin for Property Images"""
    list_display = ('property', 'image_preview', 'caption', 'is_primary', 'display_order')
    list_filter = ('is_primary', 'property__owner')
    search_fields = ('property__title', 'caption')
    list_editable = ('is_primary', 'display_order')
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover;" />',
                obj.image.url
            )
        return '-'
    image_preview.short_description = 'Preview'


@admin.register(PropertyView)
class PropertyViewAdmin(admin.ModelAdmin):
    """Admin for Property Views"""
    list_display = ('property', 'user', 'ip_address', 'viewed_at')
    list_filter = ('viewed_at', 'property__owner')
    search_fields = ('property__title', 'user__email', 'ip_address')
    readonly_fields = ('viewed_at',)
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


# Custom Admin Site Configuration
class CustomAdminSite(admin.AdminSite):
    """Custom Admin Site with enhanced features"""
    site_header = "BHOOSPARSH Admin"
    site_title = "BHOOSPARSH Admin Portal"
    index_title = "Dashboard"
    
    def get_urls(self):
        urls = super().get_urls()
        from django.urls import path
        
        custom_urls = [
            path('impersonate/<int:user_id>/', self.admin_view(self.impersonate_user)),
            path('stop-impersonating/', self.admin_view(self.stop_impersonating)),
            path('system-settings/', self.admin_view(self.system_settings)),
            path('bulk-actions/', self.admin_view(self.bulk_actions)),
            path('reports/', self.admin_view(self.reports)),
        ]
        return custom_urls + urls
    
    def impersonate_user(self, request, user_id):
        """Admin impersonation view"""
        try:
            user = CustomUser.objects.get(id=user_id)
            from django.contrib.auth import login
            
            # Store original user
            request.session['original_user_id'] = request.user.id
            request.session['impersonated_by'] = request.user.id
            
            # Log in as user
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            
            messages.success(request, f'Now impersonating {user.email}')
            return redirect('/seller/dashboard/')
        except CustomUser.DoesNotExist:
            messages.error(request, 'User not found')
            return redirect('admin:index')
    
    def stop_impersonating(self, request):
        """Stop impersonation"""
        original_user_id = request.session.get('original_user_id')
        if original_user_id:
            try:
                original_user = CustomUser.objects.get(id=original_user_id)
                from django.contrib.auth import login
                
                original_user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, original_user)
                
                # Clear session
                del request.session['original_user_id']
                del request.session['impersonated_by']
                
                messages.success(request, 'Stopped impersonating')
            except CustomUser.DoesNotExist:
                messages.error(request, 'Original user not found')
        
        return redirect('admin:index')
    
    def system_settings(self, request):
        """System settings page"""
        if request.method == 'POST':
            # Handle settings update
            messages.success(request, 'Settings updated successfully')
            return redirect('admin:system-settings')
        
        context = {
            **self.each_context(request),
            'title': 'System Settings',
        }
        return render(request, 'admin/system_settings.html', context)
    
    def bulk_actions(self, request):
        """Bulk actions page"""
        context = {
            **self.each_context(request),
            'title': 'Bulk Actions',
        }
        return render(request, 'admin/bulk_actions.html', context)
    
    def reports(self, request):
        """Reports page"""
        # Generate reports data
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # User growth
        total_users = CustomUser.objects.count()
        new_users_week = CustomUser.objects.filter(created_at__gte=week_ago).count()
        new_users_month = CustomUser.objects.filter(created_at__gte=month_ago).count()
        
        # Property statistics
        total_properties = Property.objects.count()
        active_properties = Property.objects.filter(status='active').count()
        featured_properties = Property.objects.filter(is_featured=True).count()
        
        # Lead statistics
        total_leads = PropertyInquiry.objects.count()
        converted_leads = PropertyInquiry.objects.filter(status='converted').count()
        conversion_rate = (converted_leads / total_leads * 100) if total_leads > 0 else 0
        
        # Membership statistics
        active_memberships = UserMembership.objects.filter(status='active').count()
        expired_memberships = UserMembership.objects.filter(status='expired').count()
        
        context = {
            **self.each_context(request),
            'title': 'Reports & Analytics',
            'total_users': total_users,
            'new_users_week': new_users_week,
            'new_users_month': new_users_month,
            'total_properties': total_properties,
            'active_properties': active_properties,
            'featured_properties': featured_properties,
            'total_leads': total_leads,
            'converted_leads': converted_leads,
            'conversion_rate': round(conversion_rate, 2),
            'active_memberships': active_memberships,
            'expired_memberships': expired_memberships,
        }
        return render(request, 'admin/reports.html', context)


# Use custom admin site
admin_site = CustomAdminSite(name='custom_admin')

# Register all models with custom admin site
admin_site.register(CustomUser, CustomUserAdmin)
admin_site.register(UserProfile, UserProfileAdmin)
admin_site.register(MembershipPlan, MembershipPlanAdmin)
admin_site.register(UserMembership, UserMembershipAdmin)
admin_site.register(Property, PropertyAdmin)
admin_site.register(PropertyImage, PropertyImageAdmin)
admin_site.register(PropertyInquiry, PropertyInquiryAdmin)
admin_site.register(PropertyCategory, PropertyCategoryAdmin)
admin_site.register(PropertyType, PropertyTypeAdmin)
admin_site.register(PropertyView, PropertyViewAdmin)

# Replace default admin
admin.site = admin_site
admin.sites.site = admin_site