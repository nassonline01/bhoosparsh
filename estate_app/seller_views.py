from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta, datetime
import json
from django.db.models import Q
from decimal import Decimal, InvalidOperation
from datetime import date
import uuid
import re
from django.db import transaction


from .models import (
    CustomUser, UserProfile, UserMembership, MembershipPlan,
    Property, PropertyImage, PropertyInquiry, PropertyView,
    PropertyCategory, PropertyType
)
from .forms import PropertyInquiryForm, LeadResponseForm, PackageSelectionForm, PropertyImageForm,UserProfileForm, CustomUserForm


# ======================================================
# Seller dashboard
# ======================================================

@login_required
def seller_dashboard(request):
    """Seller dashboard with stats and analytics"""
    user = request.user
    
    # Get user profile
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user)
    
    # Get user membership
    try:
        membership = user.membership
    except UserMembership.DoesNotExist:
        # Create basic membership if doesn't exist
        basic_plan = MembershipPlan.objects.filter(slug='basic').first()
        if not basic_plan:
            basic_plan = MembershipPlan.objects.create(
                name='Basic',
                slug='basic',
                price=0,
                max_listings=1,
                max_featured=0
            )
        membership = UserMembership.objects.create(user=user, plan=basic_plan)
    
    # Get user properties
    properties = Property.objects.filter(owner=user)
    active_properties = properties.filter(status='active')
    
    # Calculate date ranges
    today = timezone.now().date()
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)
    
    # Dashboard statistics
    total_views = PropertyView.objects.filter(
        property__in=active_properties,
        viewed_at__date__gte=last_7_days
    ).count()
    
    total_leads = PropertyInquiry.objects.filter(
        property__in=active_properties,
        created_at__date__gte=last_7_days
    ).count()
    
    # Response rate calculation
    responded_leads = PropertyInquiry.objects.filter(
        property__in=active_properties,
        response__isnull=False
    ).count()
    
    total_leads_all_time = PropertyInquiry.objects.filter(
        property__in=active_properties
    ).count()
    
    response_rate = (responded_leads / total_leads_all_time * 100) if total_leads_all_time > 0 else 0
    
    # Top properties - FIX: Use different annotation names that don't conflict
    top_properties = active_properties.annotate(
        recent_views=Count('views'),  # Changed from view_count to recent_views
        recent_leads=Count('inquiries')  # Changed from lead_count to recent_leads
    ).order_by('-recent_views')[:3]
    
    # Recent leads
    recent_leads = PropertyInquiry.objects.filter(
        property__in=active_properties
    ).select_related('user', 'property').order_by('-created_at')[:5]
    
    # Performance chart data
    chart_data = get_performance_chart_data(user, last_30_days)
    
    # Lead sources (demo data for now)
    lead_sources = [
        {'name': 'Website Form', 'value': 45, 'color': '#10B981'},
        {'name': 'Phone Calls', 'value': 30, 'color': '#0E68B9'},
        {'name': 'WhatsApp', 'value': 15, 'color': '#8B5CF6'},
        {'name': 'Email', 'value': 10, 'color': '#F59E0B'},
    ]
    
    # Calculate remaining listings
    listings_remaining = 0
    if membership and membership.plan:
        if membership.plan.is_unlimited:
            listings_remaining = 999
        else:
            listings_remaining = max(0, membership.plan.max_listings - membership.listings_used)
    
    # Calculate featured remaining
    featured_remaining = 0
    if membership and membership.plan:
        featured_remaining = max(0, membership.plan.max_featured - membership.featured_used)
    
    context = {
        'user': user,
        'profile': profile,
        'membership': membership,
        'stats': {
            'active_properties': active_properties.count(),
            'total_views': total_views,
            'total_leads': total_leads,
            'response_rate': round(response_rate, 1),
            'listings_used': membership.listings_used,
            'listings_remaining': listings_remaining,
            'featured_used': membership.featured_used,
            'featured_remaining': featured_remaining,
        },
        'top_properties': top_properties,
        'recent_leads': recent_leads,
        'chart_data': chart_data,
        'lead_sources': lead_sources,
        'user_plan': membership.plan.name if membership and membership.plan else 'No Plan',
        'plan_days_left': membership.days_until_expiry or 0,
    }
    
    return render(request, 'dashboard/seller/dashboard.html', context)

def get_performance_chart_data(user, start_date):
    """Generate performance chart data"""
    import random
    # Get user's active properties
    active_properties = Property.objects.filter(owner=user, status='active')  # FIX: Use status='active'
    
    # Demo data - in real app, calculate from actual data
    days = []
    views_data = []
    leads_data = []
    
    for i in range(30, 0, -1):
        date = start_date + timedelta(days=i)
        days.append(date.strftime('%d %b'))
        
        # Demo data - replace with actual calculations
        base_views = random.randint(30, 100)
        base_leads = random.randint(2, 10)
        
        # Add some trend
        views_data.append(base_views + int(i/2))
        leads_data.append(base_leads + int(i/5))
    
    return {
        'labels': days,
        'views': views_data,
        'leads': leads_data,
    }

def get_lead_sources_data(properties):
    """Generate lead sources data"""
    # Demo data - in real app, calculate from actual sources
    return [
        {'name': 'Website Form', 'value': 45, 'color': '#10B981'},
        {'name': 'Phone Calls', 'value': 30, 'color': '#0E68B9'},
        {'name': 'WhatsApp', 'value': 15, 'color': '#8B5CF6'},
        {'name': 'Email', 'value': 10, 'color': '#F59E0B'},
    ]

# ======================================================
# Seller profile
# ======================================================

@login_required
def seller_profile(request):
    """Seller profile page"""
    user = request.user
    profile = user.profile
    
    if request.method == 'POST':
        # Handle profile updates
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)
        user_form = CustomUserForm(request.POST, instance=user)
        
        if profile_form.is_valid() and user_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('seller_profile')
    else:
        profile_form = UserProfileForm(instance=profile)
        user_form = CustomUserForm(instance=user)
    
    context = {
        'user': user,
        'profile': profile,
        'profile_form': profile_form,
        'user_form': user_form,
    }
    
    return render(request, 'dashboard/seller/profile.html', context)


# ======================================================
# Seller packages
# ======================================================

@login_required
def seller_packages(request):
    """Seller packages/boost page"""
    user = request.user
    
    # Get user's current membership
    try:
        current_membership = user.membership
    except UserMembership.DoesNotExist:
        current_membership = None
    
    # Get available packages
    packages = MembershipPlan.objects.filter(is_active=True).order_by('price')
    
    # Get user's active boosts
    active_properties = Property.objects.filter(
        owner=user,
        status='active'
    )
    
    featured_count = active_properties.filter(is_featured=True).count()
    urgent_count = active_properties.filter(is_urgent=True).count()
    premium_count = active_properties.filter(is_premium=True).count()
    
    # Payment history (demo data)
    payment_history = [
        {
            'date': 'Jan 20, 2026',
            'description': 'Professional Package',
            'amount': 2499.00,
            'status': 'paid',
            'invoice': '#INV-2026-001'
        },
        {
            'date': 'Jan 15, 2026',
            'description': 'Spotlight Boost',
            'amount': 499.00,
            'status': 'paid',
            'invoice': '#INV-2026-002'
        },
        {
            'date': 'Jan 10, 2026',
            'description': 'Featured Listing',
            'amount': 299.00,
            'status': 'paid',
            'invoice': '#INV-2026-003'
        },
        {
            'date': 'Jan 5, 2026',
            'description': 'Urgent Tag',
            'amount': 199.00,
            'status': 'paid',
            'invoice': '#INV-2026-004'
        },
    ]
    
    # Boost services
    boost_services = [
        {
            'id': 'spotlight',
            'name': 'Spotlight Boost',
            'description': 'Top position in search results for 7 days',
            'price': 499,
            'duration': '7 days',
            'popular': True
        },
        {
            'id': 'featured',
            'name': 'Featured Listing',
            'description': 'Featured badge and priority placement for 30 days',
            'price': 299,
            'duration': '30 days',
            'value': True
        },
        {
            'id': 'urgent',
            'name': 'Urgent Tag',
            'description': '"Urgent" tag for quick sale/rent properties (14 days)',
            'price': 199,
            'duration': '14 days',
            'fast': True
        },
        {
            'id': 'photo',
            'name': 'Photo Highlight',
            'description': 'Professional photos with priority display',
            'price': 399,
            'duration': '30 days',
            'new': True
        },
    ]
    
    context = {
        'user': user,
        'current_membership': current_membership,
        'packages': packages,
        'active_boosts': {
            'featured': featured_count,
            'urgent': urgent_count,
            'premium': premium_count,
        },
        'payment_history': payment_history,
        'boost_services': boost_services,
        'user_plan': current_membership.plan.name if current_membership and current_membership.plan else 'No Plan',
        'plan_days_left': current_membership.days_until_expiry if current_membership else 0,
    }
    
    return render(request, 'dashboard/seller/packages.html', context)


@login_required
def seller_properties(request):
    """Seller properties management page"""
    user = request.user
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    property_for_filter = request.GET.get('property_for', 'all')
    search_query = request.GET.get('q', '')
    sort_by = request.GET.get('sort', '-created_at')
    
    # Base queryset
    properties = Property.objects.filter(owner=user)
    
    # Apply filters
    if status_filter != 'all':
        properties = properties.filter(status=status_filter)
    
    if property_for_filter != 'all':
        properties = properties.filter(property_for=property_for_filter)
    
    if search_query:
        properties = properties.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(address__icontains=search_query) |
            Q(city__icontains=search_query) |
            Q(property_id__icontains=search_query)
        )
    
    # Apply sorting
    if sort_by in ['price', '-price', 'created_at', '-created_at', 'view_count', '-view_count']:
        properties = properties.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(properties, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_properties = properties.count()
    active_properties = properties.filter(status='active').count()
    draft_properties = properties.filter(status='draft').count()
    sold_properties = properties.filter(status='sold').count()
    
    # Get user's membership to check limits
    try:
        membership = user.membership
        can_create = membership.can_create_listing() if membership else False
        listings_remaining = membership.listings_remaining if membership else 0
    except UserMembership.DoesNotExist:
        can_create = False
        listings_remaining = 0
    
    context = {
        'user': user,
        'page_obj': page_obj,
        'total_properties': total_properties,
        'active_properties': active_properties,
        'draft_properties': draft_properties,
        'sold_properties': sold_properties,
        'status_filter': status_filter,
        'property_for_filter': property_for_filter,
        'search_query': search_query,
        'sort_by': sort_by,
        'can_create': can_create,
        'listings_remaining': listings_remaining,
        'user_plan': membership.plan.name if membership and membership.plan else 'No Plan',
        'plan_days_left': membership.days_until_expiry if membership else 0,
    }
    
    return render(request, 'dashboard/seller/properties.html', context)


@login_required
def seller_property_detail(request, pk):
    """View property details"""
    user = request.user
    property_obj = get_object_or_404(Property, pk=pk, owner=user)
    
    # Get related data
    inquiries = property_obj.inquiries.all().order_by('-created_at')
    stats = {
        'views_today': property_obj.views.filter(viewed_at__date=datetime.today()).count(),
        'inquiries_today': property_obj.inquiries.filter(created_at__date=datetime.today()).count(),
        'views_week': property_obj.views.filter(viewed_at__gte=datetime.today() - timedelta(days=7)).count(),
    }
    
    context = {
        'property': property_obj,
        'inquiries': inquiries[:10],
        'stats': stats,
        'user': user,
        'user_plan': user.membership.plan.name if hasattr(user, 'membership') and user.membership.plan else 'No Plan',
        'plan_days_left': user.membership.days_until_expiry if hasattr(user, 'membership') else 0,
    }
    
    return render(request, 'dashboard/seller/property_detail.html', context)

@login_required
@require_POST
def seller_property_duplicate(request, pk):
    """Duplicate a property"""
    user = request.user
    property_obj = get_object_or_404(Property, pk=pk, owner=user)
    
    try:
        with transaction.atomic():
            # Create new property with similar data
            new_property = Property.objects.create(
                owner=user,
                title=f"{property_obj.title} (Copy)",
                description=property_obj.description,
                category=property_obj.category,
                property_type=property_obj.property_type,
                property_for=property_obj.property_for,
                listing_type=property_obj.listing_type,
                address=property_obj.address,
                locality=property_obj.locality,
                city=property_obj.city,
                state=property_obj.state,
                pincode=property_obj.pincode,
                landmark=property_obj.landmark,
                price=property_obj.price,
                carpet_area=property_obj.carpet_area,
                builtup_area=property_obj.builtup_area,
                super_builtup_area=property_obj.super_builtup_area,
                plot_area=property_obj.plot_area,
                bedrooms=property_obj.bedrooms,
                bathrooms=property_obj.bathrooms,
                balconies=property_obj.balconies,
                furnishing=property_obj.furnishing,
                contact_person=property_obj.contact_person,
                contact_phone=property_obj.contact_phone,
                contact_email=property_obj.contact_email,
                show_contact=property_obj.show_contact,
                amenities=property_obj.amenities,
                status='draft',
            )
            
            # Copy images if needed (you might want to copy images as well)
            
            return JsonResponse({
                'success': True,
                'property_id': new_property.id,
                'message': 'Property duplicated successfully'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def seller_property_report(request, pk):
    """Generate property report"""
    user = request.user
    property_obj = get_object_or_404(Property, pk=pk, owner=user)
    
    # Generate report data
    report_data = {
        'property': {
            'title': property_obj.title,
            'price': float(property_obj.price),
            'status': property_obj.get_status_display(),
            'created_at': property_obj.created_at.strftime('%Y-%m-%d %H:%M'),
        },
        'statistics': {
            'total_views': property_obj.view_count,
            'total_inquiries': property_obj.inquiry_count,
            'daily_avg_views': property_obj.view_count / max((datetime.now().date() - property_obj.created_at.date()).days, 1),
        },
        'inquiries_by_status': {
            'new': property_obj.inquiries.filter(status='new').count(),
            'contacted': property_obj.inquiries.filter(status='contacted').count(),
            'converted': property_obj.inquiries.filter(status='converted').count(),
        }
    }
    
    # In a real app, you would generate a PDF or Excel file
    # For now, return JSON response
    
    return JsonResponse({
        'success': True,
        'report': report_data,
        'message': 'Report generated successfully',
        # 'download_url': '/media/reports/report.pdf'  # If you generate a file
    })

# AJAX Views
@login_required
@require_POST
def ajax_update_property_status(request):
    """Update property status via AJAX"""
    try:
        data = json.loads(request.body)
        property_id = data.get('property_id')
        new_status = data.get('status')
        
        property_obj = Property.objects.get(id=property_id, owner=request.user)
        
        # Validate status transition
        valid_transitions = {
            'draft': ['pending', 'active'],
            'pending': ['active', 'draft'],
            'active': ['inactive', 'sold'],
            'inactive': ['active', 'sold'],
            'sold': ['inactive'],
        }
        
        if new_status not in valid_transitions.get(property_obj.status, []):
            return JsonResponse({
                'success': False,
                'error': f'Cannot change status from {property_obj.status} to {new_status}'
            })
        
        property_obj.status = new_status
        
        # Set published date when activating
        if new_status == 'active' and not property_obj.published_at:
            property_obj.published_at = timezone.now()
        
        property_obj.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Property status updated to {new_status}',
            'new_status': new_status,
            'status_display': property_obj.get_status_display(),
        })
        
    except Property.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Property not found'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@require_POST
def ajax_apply_boost(request):
    """Apply boost to property via AJAX"""
    try:
        data = json.loads(request.body)
        property_id = data.get('property_id')
        boost_type = data.get('boost_type')
        
        property_obj = Property.objects.get(id=property_id, owner=request.user)
        
        # Apply boost based on type
        if boost_type == 'featured':
            property_obj.is_featured = True
            property_obj.featured_until = timezone.now() + timedelta(days=30)
            message = 'Property marked as featured for 30 days'
        elif boost_type == 'urgent':
            property_obj.is_urgent = True
            property_obj.urgent_until = timezone.now() + timedelta(days=14)
            message = 'Property marked as urgent for 14 days'
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid boost type'
            })
        
        property_obj.save()
        
        # In real app, you would process payment here
        # For now, just update the property
        
        return JsonResponse({
            'success': True,
            'message': message,
            'boost_type': boost_type,
        })
        
    except Property.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Property not found'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@require_GET
def ajax_property_details(request, pk):
    """Get property details for AJAX requests"""
    try:
        property_obj = Property.objects.get(id=pk, owner=request.user)
        
        data = {
            'id': property_obj.id,
            'title': property_obj.title,
            'description': property_obj.description,
            'price': float(property_obj.price),
            'price_per_sqft': float(property_obj.price_per_sqft) if property_obj.price_per_sqft else None,
            'carpet_area': float(property_obj.carpet_area),
            'bedrooms': property_obj.bedrooms,
            'bathrooms': property_obj.bathrooms,
            'city': property_obj.city,
            'state': property_obj.state,
            'locality': property_obj.locality,
            'status': property_obj.status,
            'status_display': property_obj.get_status_display(),
            'property_for': property_obj.property_for,
            'property_for_display': property_obj.get_property_for_display(),
            'view_count': property_obj.view_count,
            'inquiry_count': property_obj.inquiry_count,
            'created_at': property_obj.created_at.strftime('%Y-%m-%d %H:%M'),
            'primary_image_url': property_obj.primary_image.url if property_obj.primary_image else None,
            'is_featured': property_obj.is_featured,
            'is_urgent': property_obj.is_urgent,
        }
        
        return JsonResponse({
            'success': True,
            'property': data,
        })
        
    except Property.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Property not found'
        })

# ======================================================
# Property Creation
# ======================================================

@login_required
def seller_property_create(request):
    """Create new property with dynamic field display"""
    user = request.user
    
    # Check if user can create listing
    try:
        membership = user.membership
        if not membership.can_create_listing():
            messages.warning(request, 'You have reached your listing limit. Please upgrade your plan.')
            return redirect('seller_packages')
    except UserMembership.DoesNotExist:
        messages.warning(request, 'You need a membership plan to create listings.')
        return redirect('seller_packages')
    
    # Get property categories
    categories = PropertyCategory.objects.filter(is_active=True)
    
    # Get selected category ID from request
    category_id = request.GET.get('category') or request.POST.get('category')
    
    # Get property types - initially empty or filtered by category
    property_types = PropertyType.objects.filter(is_active=True)
    if category_id:
        property_types = property_types.filter(category_id=category_id)
    
    # Get all property types for JavaScript (hidden)
    all_property_types = PropertyType.objects.filter(is_active=True)
    
    # Define property type categories mapping
    property_type_categories = {
        'residential': ['apartment', 'villa', 'house', 'penthouse', 'builder-floor', 'studio'],
        'commercial': ['office', 'shop', 'retail', 'warehouse', 'industrial', 'commercial-land'],
        'plot': ['plot', 'land', 'agricultural-land', 'residential-plot', 'commercial-plot'],
        'pg': ['pg', 'hostel', 'guest-house', 'co-living']
    }
    
    # Amenities list
    amenities_list = [
        {'id': 'parking', 'name': 'Parking'},
        {'id': 'security', 'name': '24/7 Security'},
        {'id': 'lift', 'name': 'Lift/Elevator'},
        {'id': 'power_backup', 'name': 'Power Backup'},
        {'id': 'swimming_pool', 'name': 'Swimming Pool'},
        {'id': 'gym', 'name': 'Gym/Fitness Center'},
        {'id': 'clubhouse', 'name': 'Club House'},
        {'id': 'garden', 'name': 'Garden/Park'},
        {'id': 'water_supply', 'name': '24/7 Water Supply'},
        {'id': 'play_area', 'name': 'Children Play Area'},
        {'id': 'internet', 'name': 'Internet/WiFi'},
        {'id': 'ac', 'name': 'Air Conditioning'},
        {'id': 'cctv', 'name': 'CCTV Security'},
        {'id': 'fire_safety', 'name': 'Fire Safety'},
        {'id': 'waste_disposal', 'name': 'Waste Disposal'},
        {'id': 'maintenance_staff', 'name': 'Maintenance Staff'},
    ]
    
    # Handle AJAX request for property types
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if request.GET.get('get_property_types'):
            category_id = request.GET.get('category_id')
            if category_id:
                types = PropertyType.objects.filter(category_id=category_id, is_active=True)
                data = [{'id': pt.id, 'name': pt.name, 'slug': pt.slug} for pt in types]
                return JsonResponse({'types': data})
            return JsonResponse({'types': []})
        
        if request.GET.get('get_property_type_info'):
            type_id = request.GET.get('type_id')
            try:
                prop_type = PropertyType.objects.get(id=type_id)
                # Determine category based on type name/slug
                category = 'residential'  # default
                for cat, types in property_type_categories.items():
                    if any(t in prop_type.slug.lower() for t in types):
                        category = cat
                        break
                
                return JsonResponse({
                    'id': prop_type.id,
                    'name': prop_type.name,
                    'slug': prop_type.slug,
                    'category': category
                })
            except PropertyType.DoesNotExist:
                return JsonResponse({'error': 'Type not found'}, status=404)
    
    if request.method == 'POST':
        try:
            # Check if saving as draft
            save_as_draft = request.POST.get('save_as_draft') == 'true'
            
            # Extract form data - Step 1
            title = request.POST.get('title', '').strip()
            description = request.POST.get('description', '').strip()
            category_id = request.POST.get('category')
            property_type_id = request.POST.get('property_type')
            property_for = request.POST.get('property_for')
            listing_type = request.POST.get('listing_type', 'basic')
            
            # Extract form data - Step 2
            address = request.POST.get('address', '').strip()
            locality = request.POST.get('locality', '').strip()
            city = request.POST.get('city', '').strip()
            state = request.POST.get('state', '').strip()
            pincode = request.POST.get('pincode', '').strip()
            landmark = request.POST.get('landmark', '').strip()
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            google_map_url = request.POST.get('google_map_url', '').strip()
            
            # Extract form data - Step 3 (dynamic based on property type)
            price_str = request.POST.get('price', '0')
            maintenance_charges_str = request.POST.get('maintenance_charges')
            booking_amount_str = request.POST.get('booking_amount')
            price_negotiable = request.POST.get('price_negotiable') == 'on'
            
            # Area fields
            carpet_area_str = request.POST.get('carpet_area', '0')
            builtup_area_str = request.POST.get('builtup_area')
            super_builtup_area_str = request.POST.get('super_builtup_area')
            plot_area_str = request.POST.get('plot_area')
            
            # Residential fields
            bedrooms_str = request.POST.get('bedrooms')
            bathrooms_str = request.POST.get('bathrooms')
            balconies_str = request.POST.get('balconies', '0')
            furnishing = request.POST.get('furnishing', '')
            
            # Commercial fields
            commercial_type = request.POST.get('commercial_type', '')
            floor_number_str = request.POST.get('floor_number')
            total_floors_str = request.POST.get('total_floors')
            
            # Plot fields
            plot_type = request.POST.get('plot_type', '')
            facing = request.POST.get('facing', '')
            
            # PG fields
            pg_type = request.POST.get('pg_type', '')
            meals_included = request.POST.get('meals_included', '')
            shared_bathroom = request.POST.get('shared_bathroom') == 'on'
            
            # Other details
            age_of_property = request.POST.get('age_of_property', '').strip()
            possession_status = request.POST.get('possession_status', '').strip()
            
            # Extract form data - Step 4
            contact_person = request.POST.get('contact_person', '').strip()
            contact_phone = request.POST.get('contact_phone', '').strip()
            contact_email = request.POST.get('contact_email', '').strip()
            show_contact = request.POST.get('show_contact') == 'on'
            
            # Boost features
            is_featured = request.POST.get('is_featured') == 'on'
            is_urgent = request.POST.get('is_urgent') == 'on'
            
            # Amenities
            amenities_selected = request.POST.getlist('amenities')
            
            # Primary image
            primary_image = request.FILES.get('primary_image')
            
            # Validation
            errors = {}
            
            # Required fields - Skip some validation for draft
            if not save_as_draft:
                # Step 1 validation
                if not title:
                    errors['title'] = 'Title is required'
                if not description:
                    errors['description'] = 'Description is required'
                if not category_id:
                    errors['category'] = 'Category is required'
                if not property_type_id:
                    errors['property_type'] = 'Property type is required'
                if not property_for:
                    errors['property_for'] = 'Please select property for'
                
                # Step 2 validation
                if not address:
                    errors['address'] = 'Address is required'
                if not locality:
                    errors['locality'] = 'Locality/Area is required'
                if not city:
                    errors['city'] = 'City is required'
                if not state:
                    errors['state'] = 'State is required'
                if not pincode:
                    errors['pincode'] = 'Pincode is required'
                
                # Step 3 validation
                try:
                    price = Decimal(price_str) if price_str else Decimal('0')
                    if price <= Decimal('0'):
                        errors['price'] = 'Valid price is required'
                except (InvalidOperation, ValueError):
                    errors['price'] = 'Invalid price format'
                
                try:
                    carpet_area = Decimal(carpet_area_str) if carpet_area_str else Decimal('0')
                    if carpet_area <= Decimal('0'):
                        errors['carpet_area'] = 'Valid carpet area is required'
                except (InvalidOperation, ValueError):
                    errors['carpet_area'] = 'Invalid area format'
                
                # Step 4 validation
                if not contact_person:
                    errors['contact_person'] = 'Contact person is required'
                if not contact_phone:
                    errors['contact_phone'] = 'Contact phone is required'
                if not primary_image:
                    errors['primary_image'] = 'Primary image is required'
            
            # Additional validation
            phone_pattern = re.compile(r'^[+]?[1-9][\d]{9,14}$')
            if contact_phone and not phone_pattern.match(contact_phone.replace(' ', '')):
                errors['contact_phone'] = 'Please enter a valid phone number (10-15 digits)'
            
            if contact_email and not '@' in contact_email:
                errors['contact_email'] = 'Please enter a valid email address'
            
            if errors:
                # Return with errors
                context = {
                    'errors': errors,
                    'categories': categories,
                    'property_types': property_types,
                    'all_property_types': all_property_types,
                    'property_type_categories': property_type_categories,
                    'amenities_list': amenities_list,
                    'form_data': request.POST,
                    'user': user,
                    'user_plan': membership.plan.name if membership and membership.plan else 'No Plan',
                    'plan_days_left': membership.days_until_expiry if membership else 0,
                    'selected_category_id': category_id,
                }
                messages.error(request, 'Please correct the errors below.')
                return render(request, 'dashboard/seller/property_form.html', context)
            
            # Convert numeric values
            try:
                price = Decimal(price_str) if price_str else Decimal('0')
            except (InvalidOperation, ValueError):
                price = Decimal('0')
            
            try:
                carpet_area = Decimal(carpet_area_str) if carpet_area_str else Decimal('0')
            except (InvalidOperation, ValueError):
                carpet_area = Decimal('0')
            
            try:
                maintenance_charges = Decimal(maintenance_charges_str) if maintenance_charges_str else None
            except (InvalidOperation, ValueError):
                maintenance_charges = None
            
            try:
                booking_amount = Decimal(booking_amount_str) if booking_amount_str else None
            except (InvalidOperation, ValueError):
                booking_amount = None
            
            try:
                builtup_area = Decimal(builtup_area_str) if builtup_area_str else None
            except (InvalidOperation, ValueError):
                builtup_area = None
            
            try:
                super_builtup_area = Decimal(super_builtup_area_str) if super_builtup_area_str else None
            except (InvalidOperation, ValueError):
                super_builtup_area = None
            
            try:
                plot_area = Decimal(plot_area_str) if plot_area_str else None
            except (InvalidOperation, ValueError):
                plot_area = None
            
            # Convert other numeric fields
            bedrooms = int(bedrooms_str) if bedrooms_str and bedrooms_str.isdigit() else None
            bathrooms = int(bathrooms_str) if bathrooms_str and bathrooms_str.isdigit() else None
            balconies = int(balconies_str) if balconies_str and balconies_str.isdigit() else 0
            floor_number = int(floor_number_str) if floor_number_str and floor_number_str.isdigit() else None
            total_floors = int(total_floors_str) if total_floors_str and total_floors_str.isdigit() else None
            
            # Calculate price per sqft
            price_per_sqft = None
            if carpet_area > 0:
                try:
                    price_per_sqft = price / carpet_area
                except (ZeroDivisionError, InvalidOperation):
                    price_per_sqft = None
            
            # Create property object
            property_obj = Property(
                owner=user,
                title=title,
                description=description,
                category_id=category_id,
                property_type_id=property_type_id,
                property_for=property_for,
                listing_type=listing_type,
                address=address,
                locality=locality,
                city=city,
                state=state,
                pincode=pincode,
                landmark=landmark,
                price=price,
                price_per_sqft=price_per_sqft,
                price_negotiable=price_negotiable,
                carpet_area=carpet_area,
                contact_person=contact_person,
                contact_phone=contact_phone,
                contact_email=contact_email,
                show_contact=show_contact,
                is_featured=is_featured,
                is_urgent=is_urgent,
                status='draft' if save_as_draft else 'pending'
            )
            
            # Optional fields
            if latitude:
                try:
                    property_obj.latitude = Decimal(latitude)
                except (InvalidOperation, ValueError):
                    pass
            
            if longitude:
                try:
                    property_obj.longitude = Decimal(longitude)
                except (InvalidOperation, ValueError):
                    pass
            
            if google_map_url:
                property_obj.google_map_url = google_map_url
            if maintenance_charges:
                property_obj.maintenance_charges = maintenance_charges
            if booking_amount:
                property_obj.booking_amount = booking_amount
            if builtup_area:
                property_obj.builtup_area = builtup_area
            if super_builtup_area:
                property_obj.super_builtup_area = super_builtup_area
            if plot_area:
                property_obj.plot_area = plot_area
            
            # Property type specific fields
            if bedrooms:
                property_obj.bedrooms = bedrooms
            if bathrooms:
                property_obj.bathrooms = bathrooms
            if balconies:
                property_obj.balconies = balconies
            if furnishing:
                property_obj.furnishing = furnishing
            if commercial_type:
                property_obj.commercial_type = commercial_type
            if floor_number:
                property_obj.floor_number = floor_number
            if total_floors:
                property_obj.total_floors = total_floors
            if plot_type:
                property_obj.plot_type = plot_type
            if facing:
                property_obj.facing = facing
            if age_of_property:
                property_obj.age_of_property = age_of_property
            if possession_status:
                property_obj.possession_status = possession_status
            
            # Additional fields for PG/Hostel (store in amenities JSON)
            pg_details = {}
            if pg_type:
                pg_details['pg_type'] = pg_type
            if meals_included:
                pg_details['meals_included'] = meals_included
            if shared_bathroom:
                pg_details['shared_bathroom'] = True
            
            # Save amenities as JSON
            if amenities_selected:
                property_obj.amenities = {'selected': amenities_selected, **pg_details}
            elif pg_details:
                property_obj.amenities = pg_details
            else:
                property_obj.amenities = {}
            
            # Generate unique property ID
            property_obj.property_id = f"PROP{str(property_obj.id)[:8].upper()}" if property_obj.id else f"PROP{uuid.uuid4().hex[:8].upper()}"
            
            property_obj.save()
            
            # Save primary image if provided
            if primary_image:
                primary_img = PropertyImage(
                    property=property_obj,
                    image=primary_image,
                    caption='Primary Image',
                    is_primary=True,
                    display_order=0
                )
                primary_img.save()
                
                # Update property's primary image reference
                property_obj.primary_image = primary_img.image
                property_obj.save()
            
            # Save additional images if provided
            additional_images = request.FILES.getlist('additional_images')
            for i, image in enumerate(additional_images[:9], 1):  # Max 9 additional images
                PropertyImage.objects.create(
                    property=property_obj,
                    image=image,
                    caption=f'Image {i}',
                    display_order=i
                )
            
            # Update user membership usage (only if not draft)
            if membership and not save_as_draft:
                membership.listings_used += 1
                membership.save()
            
            if save_as_draft:
                messages.success(request, 'Property saved as draft successfully!')
            else:
                messages.success(request, 'Property created successfully! It will be reviewed before publishing.')
            
            return redirect('seller_properties')
            
        except Exception as e:
            messages.error(request, f'Error creating property: {str(e)}')
            import traceback
            traceback.print_exc()
            
            # Return with errors
            context = {
                'errors': {'general': str(e)},
                'categories': categories,
                'property_types': property_types,
                'all_property_types': all_property_types,
                'property_type_categories': property_type_categories,
                'amenities_list': amenities_list,
                'form_data': request.POST,
                'user': user,
                'user_plan': membership.plan.name if membership and membership.plan else 'No Plan',
                'plan_days_left': membership.days_until_expiry if membership else 0,
                'selected_category_id': category_id,
            }
            return render(request, 'dashboard/seller/property_form.html', context)
    
    # GET request - show empty form
    context = {
        'categories': categories,
        'property_types': property_types,
        'all_property_types': all_property_types,
        'property_type_categories': property_type_categories,
        'amenities_list': amenities_list,
        'user': user,
        'user_plan': membership.plan.name if membership and membership.plan else 'No Plan',
        'plan_days_left': membership.days_until_expiry if membership else 0,
        'selected_category_id': category_id,
        'form_data': {},
    }
    
    return render(request, 'dashboard/seller/property_form.html', context)


@login_required
def seller_property_edit(request, pk):
    """Edit existing property without using PropertyForm"""
    user = request.user
    property_obj = get_object_or_404(Property, pk=pk, owner=user)

    # Get property categories and types for dynamic form
    categories = PropertyCategory.objects.filter(is_active=True)
    
    # Get property types based on current category
    property_types = PropertyType.objects.filter(is_active=True)
    if property_obj.category:
        property_types = property_types.filter(category=property_obj.category)

    # Amenities list
    amenities_list = [
        {'id': 'parking', 'name': 'Parking'},
        {'id': 'security', 'name': '24/7 Security'},
        {'id': 'lift', 'name': 'Lift/Elevator'},
        {'id': 'power_backup', 'name': 'Power Backup'},
        {'id': 'swimming_pool', 'name': 'Swimming Pool'},
        {'id': 'gym', 'name': 'Gym/Fitness Center'},
        {'id': 'clubhouse', 'name': 'Club House'},
        {'id': 'garden', 'name': 'Garden/Park'},
        {'id': 'water_supply', 'name': '24/7 Water Supply'},
        {'id': 'play_area', 'name': 'Children Play Area'},
        {'id': 'internet', 'name': 'Internet/WiFi'},
        {'id': 'ac', 'name': 'Air Conditioning'},
        {'id': 'cctv', 'name': 'CCTV Security'},
        {'id': 'fire_safety', 'name': 'Fire Safety'},
        {'id': 'waste_disposal', 'name': 'Waste Disposal'},
        {'id': 'maintenance_staff', 'name': 'Maintenance Staff'},
    ]

    # Get selected amenities
    selected_amenities = []
    if property_obj.amenities and 'selected' in property_obj.amenities:
        selected_amenities = property_obj.amenities['selected']
    
    if request.method == 'POST':
        try:
            # Check if saving as draft
            save_as_draft = request.POST.get('save_as_draft') == 'true'
            
            # Extract form data
            title = request.POST.get('title', '').strip()
            description = request.POST.get('description', '').strip()
            category_id = request.POST.get('category')
            property_type_id = request.POST.get('property_type')
            property_for = request.POST.get('property_for')
            listing_type = request.POST.get('listing_type', 'basic')
            
            # Location data
            address = request.POST.get('address', '').strip()
            locality = request.POST.get('locality', '').strip()
            city = request.POST.get('city', '').strip()
            state = request.POST.get('state', '').strip()
            pincode = request.POST.get('pincode', '').strip()
            landmark = request.POST.get('landmark', '').strip()
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            google_map_url = request.POST.get('google_map_url', '').strip()
            
            # Pricing data - Convert to decimal
            price_str = request.POST.get('price', '0')
            maintenance_charges_str = request.POST.get('maintenance_charges')
            booking_amount_str = request.POST.get('booking_amount')
            price_negotiable = request.POST.get('price_negotiable') == 'on'
            
            # Convert strings to decimal
            from decimal import Decimal, InvalidOperation
            
            try:
                price = Decimal(price_str) if price_str else Decimal('0')
            except (InvalidOperation, ValueError):
                price = Decimal('0')
            
            try:
                maintenance_charges = Decimal(maintenance_charges_str) if maintenance_charges_str else None
            except (InvalidOperation, ValueError):
                maintenance_charges = None
            
            try:
                booking_amount = Decimal(booking_amount_str) if booking_amount_str else None
            except (InvalidOperation, ValueError):
                booking_amount = None
            
            # Area data - Convert to decimal
            carpet_area_str = request.POST.get('carpet_area', '0')
            builtup_area_str = request.POST.get('builtup_area')
            super_builtup_area_str = request.POST.get('super_builtup_area')
            plot_area_str = request.POST.get('plot_area')
            
            try:
                carpet_area = Decimal(carpet_area_str) if carpet_area_str else Decimal('0')
            except (InvalidOperation, ValueError):
                carpet_area = Decimal('0')
            
            try:
                builtup_area = Decimal(builtup_area_str) if builtup_area_str else None
            except (InvalidOperation, ValueError):
                builtup_area = None
            
            try:
                super_builtup_area = Decimal(super_builtup_area_str) if super_builtup_area_str else None
            except (InvalidOperation, ValueError):
                super_builtup_area = None
            
            try:
                plot_area = Decimal(plot_area_str) if plot_area_str else None
            except (InvalidOperation, ValueError):
                plot_area = None
            
            # Residential fields
            bedrooms_str = request.POST.get('bedrooms')
            bathrooms_str = request.POST.get('bathrooms')
            balconies_str = request.POST.get('balconies', '0')
            furnishing = request.POST.get('furnishing', '')
            
            bedrooms = int(bedrooms_str) if bedrooms_str and bedrooms_str.isdigit() else None
            bathrooms = int(bathrooms_str) if bathrooms_str and bathrooms_str.isdigit() else None
            balconies = int(balconies_str) if balconies_str and balconies_str.isdigit() else 0
            
            # Commercial fields
            commercial_type = request.POST.get('commercial_type', '')
            floor_number_str = request.POST.get('floor_number')
            total_floors_str = request.POST.get('total_floors')
            
            floor_number = int(floor_number_str) if floor_number_str and floor_number_str.isdigit() else None
            total_floors = int(total_floors_str) if total_floors_str and total_floors_str.isdigit() else None
            
            # Plot fields
            plot_type = request.POST.get('plot_type', '')
            facing = request.POST.get('facing', '')
            
            # PG/Hostel fields
            pg_type = request.POST.get('pg_type', '')
            meals_included = request.POST.get('meals_included', '')
            
            # Other details
            age_of_property = request.POST.get('age_of_property', '').strip()
            possession_status = request.POST.get('possession_status', '').strip()
            
            # Contact info
            contact_person = request.POST.get('contact_person', '').strip()
            contact_phone = request.POST.get('contact_phone', '').strip()
            contact_email = request.POST.get('contact_email', '').strip()
            show_contact = request.POST.get('show_contact') == 'on'
            
            # Boost features
            is_featured = request.POST.get('is_featured') == 'on'
            is_urgent = request.POST.get('is_urgent') == 'on'
            
            # Amenities
            amenities_selected = request.POST.getlist('amenities')
            
            # Primary image
            primary_image = request.FILES.get('primary_image')
            
            # Validation
            errors = {}
            
            # Required fields - Skip validation for draft
            if not save_as_draft:
                if not title:
                    errors['title'] = 'Title is required'
                if not description:
                    errors['description'] = 'Description is required'
                if not category_id:
                    errors['category'] = 'Category is required'
                if not property_type_id:
                    errors['property_type'] = 'Property type is required'
                if not property_for:
                    errors['property_for'] = 'Please select property for'
                if not address:
                    errors['address'] = 'Address is required'
                if not locality:
                    errors['locality'] = 'Locality is required'
                if not city:
                    errors['city'] = 'City is required'
                if not state:
                    errors['state'] = 'State is required'
                if not pincode:
                    errors['pincode'] = 'Pincode is required'
                if price <= Decimal('0'):
                    errors['price'] = 'Valid price is required'
                if carpet_area <= Decimal('0'):
                    errors['carpet_area'] = 'Valid carpet area is required'
                if not contact_person:
                    errors['contact_person'] = 'Contact person is required'
                if not contact_phone:
                    errors['contact_phone'] = 'Contact phone is required'
                
                # Validate phone number format
                import re
                phone_pattern = re.compile(r'^[+]?[1-9][\d]{0,15}$')
                if contact_phone and not phone_pattern.match(contact_phone.replace(' ', '')):
                    errors['contact_phone'] = 'Please enter a valid phone number'
                
                # Validate email if provided
                if contact_email and '@' not in contact_email:
                    errors['contact_email'] = 'Please enter a valid email address'
            
            if errors:
                # Return with errors
                context = {
                    'property': property_obj,
                    'errors': errors,
                    'categories': categories,
                    'property_types': property_types,
                    'amenities_list': amenities_list,
                    'selected_amenities': selected_amenities,
                    'form_data': request.POST,
                    'images': property_obj.images.all(),
                    'user': user,
                    'user_plan': user.membership.plan.name if hasattr(user, 'membership') and user.membership.plan else 'No Plan',
                    'plan_days_left': user.membership.days_until_expiry if hasattr(user, 'membership') else 0,
                }
                messages.error(request, 'Please correct the errors below.')
                return render(request, 'dashboard/seller/property_form.html', context)
            
            # Calculate price per sqft
            price_per_sqft = None
            if carpet_area > 0:
                try:
                    price_per_sqft = price / carpet_area
                except (ZeroDivisionError, InvalidOperation):
                    price_per_sqft = None
            
            # Update property object
            property_obj.title = title
            property_obj.description = description
            property_obj.category_id = category_id
            property_obj.property_type_id = property_type_id
            property_obj.property_for = property_for
            property_obj.listing_type = listing_type
            property_obj.address = address
            property_obj.locality = locality
            property_obj.city = city
            property_obj.state = state
            property_obj.pincode = pincode
            property_obj.landmark = landmark
            property_obj.price = price
            property_obj.price_per_sqft = price_per_sqft
            property_obj.price_negotiable = price_negotiable
            property_obj.carpet_area = carpet_area
            property_obj.contact_person = contact_person
            property_obj.contact_phone = contact_phone
            property_obj.contact_email = contact_email
            property_obj.show_contact = show_contact
            property_obj.is_featured = is_featured
            property_obj.is_urgent = is_urgent
            
            # Optional fields
            if latitude:
                try:
                    property_obj.latitude = Decimal(latitude)
                except (InvalidOperation, ValueError):
                    property_obj.latitude = None
            else:
                property_obj.latitude = None
            
            if longitude:
                try:
                    property_obj.longitude = Decimal(longitude)
                except (InvalidOperation, ValueError):
                    property_obj.longitude = None
            else:
                property_obj.longitude = None
            
            if google_map_url:
                property_obj.google_map_url = google_map_url
            else:
                property_obj.google_map_url = ''
            
            if maintenance_charges:
                property_obj.maintenance_charges = maintenance_charges
            else:
                property_obj.maintenance_charges = None
            
            if booking_amount:
                property_obj.booking_amount = booking_amount
            else:
                property_obj.booking_amount = None
            
            if builtup_area:
                property_obj.builtup_area = builtup_area
            else:
                property_obj.builtup_area = None
            
            if super_builtup_area:
                property_obj.super_builtup_area = super_builtup_area
            else:
                property_obj.super_builtup_area = None
            
            if plot_area:
                property_obj.plot_area = plot_area
            else:
                property_obj.plot_area = None
            
            if bedrooms:
                property_obj.bedrooms = bedrooms
            else:
                property_obj.bedrooms = None
            
            if bathrooms:
                property_obj.bathrooms = bathrooms
            else:
                property_obj.bathrooms = None
            
            if balconies:
                property_obj.balconies = balconies
            else:
                property_obj.balconies = 0
            
            if furnishing:
                property_obj.furnishing = furnishing
            else:
                property_obj.furnishing = ''
            
            if commercial_type:
                property_obj.commercial_type = commercial_type
            else:
                property_obj.commercial_type = ''
            
            if floor_number:
                property_obj.floor_number = floor_number
            else:
                property_obj.floor_number = None
            
            if total_floors:
                property_obj.total_floors = total_floors
            else:
                property_obj.total_floors = None
            
            if plot_type:
                property_obj.plot_type = plot_type
            else:
                property_obj.plot_type = ''
            
            if facing:
                property_obj.facing = facing
            else:
                property_obj.facing = ''
            
            if pg_type:
                property_obj.pg_type = pg_type
            else:
                property_obj.pg_type = ''
            
            if meals_included:
                property_obj.meals_included = meals_included
            else:
                property_obj.meals_included = ''
            
            if age_of_property:
                property_obj.age_of_property = age_of_property
            else:
                property_obj.age_of_property = ''
            
            if possession_status:
                property_obj.possession_status = possession_status
            else:
                property_obj.possession_status = ''
            
            # Save amenities as JSON
            if amenities_selected:
                property_obj.amenities = {'selected': amenities_selected}
            else:
                property_obj.amenities = {}
            
            # Update status if saving as draft
            if save_as_draft:
                property_obj.status = 'draft'
            elif property_obj.status == 'draft':
                property_obj.status = 'pending'  # Submit for review
            
            property_obj.save()
            
            # Handle primary image
            if primary_image:
                # Delete existing primary image if any
                PropertyImage.objects.filter(property=property_obj, is_primary=True).delete()
                
                primary_img = PropertyImage(
                    property=property_obj,
                    image=primary_image,
                    caption='Primary Image',
                    is_primary=True,
                    display_order=0
                )
                primary_img.save()
                
                # Update property's primary image reference
                property_obj.primary_image = primary_img.image
                property_obj.save()
            
            # Handle image deletion
            delete_images = request.POST.getlist('delete_images')
            if delete_images:
                PropertyImage.objects.filter(id__in=delete_images, property=property_obj).delete()
            
            # Handle new additional images
            additional_images = request.FILES.getlist('additional_images')
            existing_images_count = property_obj.images.count()
            
            for i, image in enumerate(additional_images[:10 - existing_images_count], 1):
                PropertyImage.objects.create(
                    property=property_obj,
                    image=image,
                    caption=f'Image {existing_images_count + i}',
                    display_order=existing_images_count + i
                )
            
            if save_as_draft:
                messages.success(request, 'Property saved as draft successfully!')
            else:
                messages.success(request, 'Property updated successfully!')
            
            return redirect('seller_properties')
            
        except Exception as e:
            messages.error(request, f'Error updating property: {str(e)}')
            import traceback
            traceback.print_exc()
            
            # Return with errors
            context = {
                'property': property_obj,
                'errors': {'general': str(e)},
                'categories': categories,
                'property_types': property_types,
                'amenities_list': amenities_list,
                'selected_amenities': selected_amenities,
                'form_data': request.POST,
                'images': property_obj.images.all(),
                'user': user,
                'user_plan': user.membership.plan.name if hasattr(user, 'membership') and user.membership.plan else 'No Plan',
                'plan_days_left': user.membership.days_until_expiry if hasattr(user, 'membership') else 0,
            }
            return render(request, 'dashboard/seller/property_form.html', context)
    
    # GET request - show populated form
    form_data = {
        'title': property_obj.title,
        'description': property_obj.description,
        'category': property_obj.category_id,
        'property_type': property_obj.property_type_id,
        'property_for': property_obj.property_for,
        'listing_type': property_obj.listing_type,
        'address': property_obj.address,
        'locality': property_obj.locality,
        'city': property_obj.city,
        'state': property_obj.state,
        'pincode': property_obj.pincode,
        'landmark': property_obj.landmark,
        'latitude': str(property_obj.latitude) if property_obj.latitude else '',
        'longitude': str(property_obj.longitude) if property_obj.longitude else '',
        'google_map_url': property_obj.google_map_url,
        'price': str(property_obj.price) if property_obj.price else '',
        'maintenance_charges': str(property_obj.maintenance_charges) if property_obj.maintenance_charges else '',
        'booking_amount': str(property_obj.booking_amount) if property_obj.booking_amount else '',
        'price_negotiable': 'on' if property_obj.price_negotiable else '',
        'carpet_area': str(property_obj.carpet_area) if property_obj.carpet_area else '',
        'builtup_area': str(property_obj.builtup_area) if property_obj.builtup_area else '',
        'super_builtup_area': str(property_obj.super_builtup_area) if property_obj.super_builtup_area else '',
        'plot_area': str(property_obj.plot_area) if property_obj.plot_area else '',
        'bedrooms': str(property_obj.bedrooms) if property_obj.bedrooms else '',
        'bathrooms': str(property_obj.bathrooms) if property_obj.bathrooms else '',
        'balconies': str(property_obj.balconies) if property_obj.balconies else '0',
        'furnishing': property_obj.furnishing,
        'commercial_type': property_obj.commercial_type,
        'floor_number': str(property_obj.floor_number) if property_obj.floor_number else '',
        'total_floors': str(property_obj.total_floors) if property_obj.total_floors else '',
        'plot_type': property_obj.plot_type,
        'facing': property_obj.facing,
        'pg_type': property_obj.pg_type if hasattr(property_obj, 'pg_type') else '',
        'meals_included': property_obj.meals_included if hasattr(property_obj, 'meals_included') else '',
        'age_of_property': property_obj.age_of_property,
        'possession_status': property_obj.possession_status,
        'contact_person': property_obj.contact_person,
        'contact_phone': property_obj.contact_phone,
        'contact_email': property_obj.contact_email,
        'show_contact': 'on' if property_obj.show_contact else '',
        'is_featured': 'on' if property_obj.is_featured else '',
        'is_urgent': 'on' if property_obj.is_urgent else '',
    }
    
    context = {
        'property': property_obj,
        'categories': categories,
        'property_types': property_types,
        'amenities_list': amenities_list,
        'selected_amenities': selected_amenities,
        'form_data': form_data,
        'images': property_obj.images.all(),
        'user': user,
        'user_plan': user.membership.plan.name if hasattr(user, 'membership') and user.membership.plan else 'No Plan',
        'plan_days_left': user.membership.days_until_expiry if hasattr(user, 'membership') else 0,
    }
    
    # Handle AJAX request for property types
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if request.GET.get('get_property_types'):
            category_id = request.GET.get('category_id')
            if category_id:
                types = PropertyType.objects.filter(category_id=category_id, is_active=True)
                data = [{'id': pt.id, 'name': pt.name, 'slug': pt.slug} for pt in types]
                return JsonResponse({'types': data})
            return JsonResponse({'types': []})

        if request.GET.get('get_property_type_info'):
            type_id = request.GET.get('type_id')
            try:
                prop_type = PropertyType.objects.get(id=type_id)
                # Determine category based on type name/slug
                category = 'residential'  # default
                for cat, types in property_type_categories.items():
                    if any(t in prop_type.slug.lower() for t in types):
                        category = cat
                        break

                return JsonResponse({
                    'id': prop_type.id,
                    'name': prop_type.name,
                    'slug': prop_type.slug,
                    'category': category
                })
            except PropertyType.DoesNotExist:
                return JsonResponse({'error': 'Type not found'}, status=404)
    
    return render(request, 'dashboard/seller/property_form.html', context)

@login_required
def seller_property_delete(request, pk):
    """Delete property"""
    user = request.user
    property_obj = get_object_or_404(Property, pk=pk, owner=user)
    
    if request.method == 'POST':
        property_obj.delete()
        messages.success(request, 'Property deleted successfully!')
        return redirect('seller_properties')
    
    return render(request, 'dashboard/seller/property_confirm_delete.html', {'property': property_obj})


@login_required
def seller_leads(request):
    """Seller leads management page"""
    user = request.user
    
    # Get user's properties
    user_properties = Property.objects.filter(owner=user)
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    property_filter = request.GET.get('property', 'all')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    sort_by = request.GET.get('sort', '-created_at')
    search_query = request.GET.get('q', '')
    
    # Base queryset
    inquiries = PropertyInquiry.objects.filter(property__in=user_properties)
    
    # Store original queryset for statistics
    all_inquiries = inquiries
    
    # Apply filters
    if status_filter != 'all':
        inquiries = inquiries.filter(status=status_filter)
    
    if property_filter != 'all':
        inquiries = inquiries.filter(property_id=property_filter)
    
    if date_from:
        inquiries = inquiries.filter(created_at__date__gte=date_from)
    
    if date_to:
        inquiries = inquiries.filter(created_at__date__lte=date_to)
    
    if search_query:
        inquiries = inquiries.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(message__icontains=search_query)
        )
    
    # Apply sorting
    if sort_by in ['created_at', '-created_at', 'priority', '-priority']:
        inquiries = inquiries.order_by(sort_by)
    
    # Statistics - Use the filtered queryset BEFORE pagination
    total_leads = inquiries.count()
    new_leads = inquiries.filter(status='new').count()
    contacted_leads = inquiries.filter(status='contacted').count()
    converted_leads = inquiries.filter(status='converted').count()
    
    # Count interested leads from the filtered queryset
    interested_leads = inquiries.filter(status='interested').count()
    
    # Lead sources
    lead_sources = inquiries.values('source').annotate(
        count=Count('id')
    ).order_by('-count')

    # Calculate percentage in Python
    for source in lead_sources:
        source['percentage'] = (source['count'] * 100.0 / total_leads) if total_leads > 0 else 0
    
    # Response rate
    responded_leads = inquiries.exclude(response__exact='').count()
    response_rate = (responded_leads / total_leads * 100) if total_leads > 0 else 0
    
    # Average response time (demo data)
    avg_response_time = "2.5 hours"
    
    # Pagination - Apply AFTER statistics
    paginator = Paginator(inquiries, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'user': user,
        'page_obj': page_obj,
        'user_properties': user_properties,
        'total_leads': total_leads,
        'new_leads': new_leads,
        'contacted_leads': contacted_leads,
        'converted_leads': converted_leads,
        'interested_leads': interested_leads,  # Add this
        'lead_sources': lead_sources,
        'response_rate': round(response_rate, 1),
        'avg_response_time': avg_response_time,
        'status_filter': status_filter,
        'property_filter': property_filter,
        'date_from': date_from,
        'date_to': date_to,
        'sort_by': sort_by,
        'search_query': search_query,
        'user_plan': user.membership.plan.name if hasattr(user, 'membership') and user.membership.plan else 'No Plan',
        'plan_days_left': user.membership.days_until_expiry if hasattr(user, 'membership') else 0,
    }
    
    return render(request, 'dashboard/seller/leads.html', context)


@login_required
def seller_lead_detail(request, pk):
    """Lead detail view"""
    user = request.user
    inquiry = get_object_or_404(PropertyInquiry, pk=pk, property__owner=user)
    
    if request.method == 'POST':
        form = LeadResponseForm(request.POST, instance=inquiry)
        if form.is_valid():
            inquiry_obj = form.save(commit=False)
            inquiry_obj.responded_by = user
            inquiry_obj.responded_at = timezone.now()
            inquiry_obj.save()
            
            messages.success(request, 'Response sent successfully!')
            return redirect('seller_leads')
    else:
        form = LeadResponseForm(instance=inquiry)
    
    # Get similar inquiries for same property
    similar_inquiries = PropertyInquiry.objects.filter(
        property=inquiry.property
    ).exclude(id=inquiry.id).order_by('-created_at')[:5]
    
    context = {
        'inquiry': inquiry,
        'form': form,
        'similar_inquiries': similar_inquiries,
        'user': user,
    }
    
    return render(request, 'dashboard/seller/lead_detail.html', context)


@login_required
def seller_lead_export(request):
    """Export leads as CSV"""
    user = request.user
    user_properties = Property.objects.filter(owner=user)
    inquiries = PropertyInquiry.objects.filter(property__in=user_properties)
    
    # Create CSV response
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="leads_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Name', 'Email', 'Phone', 'Property', 'Message', 'Status', 'Source'])
    
    for inquiry in inquiries:
        writer.writerow([
            inquiry.created_at.strftime('%Y-%m-%d %H:%M'),
            inquiry.name,
            inquiry.email,
            inquiry.phone,
            inquiry.property.title,
            inquiry.message[:100],
            inquiry.get_status_display(),
            inquiry.get_source_display(),
        ])
    
    return response


@login_required
def seller_analytics(request):
    """Seller analytics dashboard"""
    user = request.user
    user_properties = Property.objects.filter(owner=user)
    
    # Date ranges
    today = timezone.now().date()
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)
    
    # Property statistics
    active_properties = user_properties.filter(status='active')
    total_views = PropertyView.objects.filter(
        property__in=active_properties,
        viewed_at__date__gte=last_30_days
    ).count()
    
    total_leads = PropertyInquiry.objects.filter(
        property__in=active_properties,
        created_at__date__gte=last_30_days
    ).count()
    
    # Top performing properties
    top_properties = active_properties.annotate(
        views_count=Count('views'),
        lead_count=Count('inquiries')
    ).order_by('-views_count')[:5]
    
    # Monthly performance data
    monthly_data = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i*30)
        month_start = date.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        month_views = PropertyView.objects.filter(
            property__in=active_properties,
            viewed_at__date__range=[month_start, month_end]
        ).count()
        
        month_leads = PropertyInquiry.objects.filter(
            property__in=active_properties,
            created_at__date__range=[month_start, month_end]
        ).count()
        
        monthly_data.append({
            'month': month_start.strftime('%b %Y'),
            'views': month_views,
            'leads': month_leads,
        })
    
    # Lead sources
    lead_sources = PropertyInquiry.objects.filter(
        property__in=active_properties,
        created_at__date__gte=last_30_days
    ).values('source').annotate(count=Count('id')).order_by('-count')
    
    # Device breakdown (demo data)
    device_breakdown = [
        {'device': 'Mobile', 'count': 856, 'percentage': 69},
        {'device': 'Desktop', 'count': 312, 'percentage': 25},
        {'device': 'Tablet', 'count': 72, 'percentage': 6},
    ]
    
    # Best time for leads (demo data)
    best_times = [
        {'time': '9AM - 12PM', 'leads': 28, 'percentage': 35},
        {'time': '1PM - 5PM', 'leads': 32, 'percentage': 40},
        {'time': '6PM - 9PM', 'leads': 20, 'percentage': 25},
    ]
    
    context = {
        'user': user,
        'total_properties': user_properties.count(),
        'active_properties': active_properties.count(),
        'total_views': total_views,
        'total_leads': total_leads,
        'top_properties': top_properties,
        'monthly_data': monthly_data,
        'lead_sources': lead_sources,
        'device_breakdown': device_breakdown,
        'best_times': best_times,
        'user_plan': user.membership.plan.name if hasattr(user, 'membership') and user.membership.plan else 'No Plan',
        'plan_days_left': user.membership.days_until_expiry if hasattr(user, 'membership') else 0,
    }
    
    return render(request, 'dashboard/seller/analytics.html', context)


# AJAX Views
@login_required
@require_POST
def ajax_update_lead_status(request):
    """AJAX view to update lead status"""
    try:
        data = json.loads(request.body)
        lead_id = data.get('lead_id')
        new_status = data.get('status')
        
        inquiry = PropertyInquiry.objects.get(
            id=lead_id,
            property__owner=request.user
        )
        inquiry.status = new_status
        inquiry.save()
        
        return JsonResponse({'success': True, 'new_status': inquiry.get_status_display()})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def ajax_apply_boost(request):
    """AJAX view to apply boost to property"""
    try:
        data = json.loads(request.body)
        property_id = data.get('property_id')
        boost_type = data.get('boost_type')
        
        property_obj = Property.objects.get(
            id=property_id,
            owner=request.user
        )
        
        # Apply boost based on type
        if boost_type == 'featured':
            property_obj.is_featured = True
            property_obj.featured_until = timezone.now() + timedelta(days=30)
            message = 'Featured boost applied for 30 days!'
        elif boost_type == 'urgent':
            property_obj.is_urgent = True
            property_obj.urgent_until = timezone.now() + timedelta(days=14)
            message = 'Urgent tag applied for 14 days!'
        elif boost_type == 'spotlight':
            property_obj.is_premium = True
            property_obj.premium_until = timezone.now() + timedelta(days=7)
            message = 'Spotlight boost applied for 7 days!'
        else:
            return JsonResponse({'success': False, 'error': 'Invalid boost type'})
        
        property_obj.save()
        
        # In real app, you would:
        # 1. Deduct payment
        # 2. Create transaction record
        # 3. Send confirmation email
        
        return JsonResponse({
            'success': True,
            'message': message,
            'boost_type': boost_type,
            'property_id': property_id
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_GET
def ajax_get_property_types(request):
    """AJAX view to get property types for selected category"""
    category_id = request.GET.get('category_id')
    
    if category_id:
        property_types = PropertyType.objects.filter(
            category_id=category_id,
            is_active=True
        ).values('id', 'name')
        
        return JsonResponse(list(property_types), safe=False)
    
    return JsonResponse([], safe=False)

# ===================================================
# Seller Settings
# ===================================================

from .forms import (
    PrivacySettingsForm, NotificationSettingsForm, 
    PasswordChangeForm, AccountDeletionForm
)

@login_required
def seller_settings(request):
    """Seller settings page"""
    user = request.user
    
    # Get user's membership for stats
    try:
        membership = user.membership
    except UserMembership.DoesNotExist:
        membership = None
    
    # Get user's active properties for stats
    active_properties = Property.objects.filter(owner=user, status='active').count()
    
    # Active tab
    active_tab = request.GET.get('tab', 'profile')
    
    # Initialize forms
    privacy_form = None
    notification_form = None
    password_form = None
    deletion_form = None
    
    # Handle form submissions based on active tab
    if request.method == 'POST':
        if active_tab == 'privacy':
            privacy_form = PrivacySettingsForm(request.POST, instance=user)
            if privacy_form.is_valid():
                privacy_form.save()
                messages.success(request, 'Privacy settings updated successfully!')
                return redirect('seller_settings') + '?tab=privacy'
            else:
                messages.error(request, 'Please correct the errors below.')
        
        elif active_tab == 'notifications':
            notification_form = NotificationSettingsForm(request.POST, instance=user)
            if notification_form.is_valid():
                notification_form.save()
                messages.success(request, 'Notification settings updated successfully!')
                return redirect('seller_settings') + '?tab=notifications'
            else:
                messages.error(request, 'Please correct the errors below.')
        
        elif active_tab == 'password':
            password_form = PasswordChangeForm(request.POST, user=user)
            if password_form.is_valid():
                user.set_password(password_form.cleaned_data['new_password'])
                user.save()
                update_session_auth_hash(request, user)  # Keep user logged in
                messages.success(request, 'Password changed successfully!')
                return redirect('seller_settings') + '?tab=password'
            else:
                messages.error(request, 'Please correct the errors below.')
        
        elif active_tab == 'danger':
            deletion_form = AccountDeletionForm(request.POST, user=user)
            if deletion_form.is_valid():
                # Delete user account
                user.delete()
                messages.success(request, 'Your account has been deleted successfully.')
                return redirect('home')
            else:
                messages.error(request, 'Please correct the errors below.')
    
    # Initialize forms for GET request or if POST failed
    if privacy_form is None:
        privacy_form = PrivacySettingsForm(instance=user)
    if notification_form is None:
        notification_form = NotificationSettingsForm(instance=user)
    if password_form is None:
        password_form = PasswordChangeForm(user=user)
    if deletion_form is None:
        deletion_form = AccountDeletionForm(user=user)
    
    # Prepare context
    context = {
        'user': user,
        'privacy_form': privacy_form,
        'notification_form': notification_form,
        'password_form': password_form,
        'deletion_form': deletion_form,
        'active_tab': active_tab,
        'user_plan': membership.plan.name if membership and membership.plan else 'No Plan',
        'plan_days_left': membership.days_until_expiry if membership else 0,
        'stats': {
            'listings_used': membership.listings_used if membership else 0,
            'featured_used': membership.featured_used if membership else 0,
        },
        'membership': membership,
    }
    
    return render(request, 'dashboard/seller/settings.html', context)