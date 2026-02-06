# views.py - Add buyer specific views
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Min, Max
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Property, PropertyFavorite, PropertyComparison, SiteVisit, BuyerProfile, PropertyInquiry,PropertyCategory, PropertyType
from .forms import PropertyInquiryForm

@login_required
def buyer_dashboard(request):
    """Buyer dashboard view"""
    user = request.user
    
    # Get buyer profile
    try:
        buyer_profile = user.buyer_profile
    except BuyerProfile.DoesNotExist:
        buyer_profile = BuyerProfile.objects.create(user=user)
    
    # Get user's favorites
    favorites = PropertyFavorite.objects.filter(user=user)
    saved_count = favorites.count()
    
    # Get upcoming site visits
    upcoming_visits = SiteVisit.objects.filter(
        user=user,
        scheduled_date__gte=timezone.now().date(),
        status='confirmed'
    ).order_by('scheduled_date', 'scheduled_time')[:3]
    
    # Get recent inquiries
    recent_inquiries = PropertyInquiry.objects.filter(
        user=user
    ).select_related('property').order_by('-created_at')[:5]
    
    # Get recommended properties based on buyer preferences
    recommended_properties = get_recommended_properties(buyer_profile)
    
    # Get comparison lists
    comparison_lists = PropertyComparison.objects.filter(user=user)
    
    # Statistics
    total_searches = buyer_profile.total_searches
    properties_viewed = buyer_profile.properties_viewed
    properties_saved = saved_count
    site_visits_completed = SiteVisit.objects.filter(
        user=user,
        status='completed'
    ).count()
    
    # Market insights (demo data)
    market_insights = {
        'avg_price': get_average_price(buyer_profile.preferred_locations),
        'trend': get_market_trend(),
        'hot_locations': get_hot_locations(),
    }
    
    context = {
        'user': user,
        'buyer_profile': buyer_profile,
        'favorites': favorites[:5],
        'saved_count': saved_count,
        'upcoming_visits': upcoming_visits,
        'recent_inquiries': recent_inquiries,
        'recommended_properties': recommended_properties[:4],
        'comparison_lists': comparison_lists,
        'stats': {
            'total_searches': total_searches,
            'properties_viewed': properties_viewed,
            'properties_saved': properties_saved,
            'site_visits_completed': site_visits_completed,
        },
        'market_insights': market_insights,
    }
    
    return render(request, 'dashboard/buyer/dashboard.html', context)


def get_recommended_properties(buyer_profile):
    """Get AI-recommended properties based on buyer preferences"""
    # Base query
    properties = Property.objects.filter(status='active')
    
    # Apply buyer preferences
    if buyer_profile.min_budget:
        properties = properties.filter(price__gte=buyer_profile.min_budget)
    
    if buyer_profile.max_budget:
        properties = properties.filter(price__lte=buyer_profile.max_budget)
    
    if buyer_profile.min_bedrooms:
        properties = properties.filter(bedrooms__gte=buyer_profile.min_bedrooms)
    
    if buyer_profile.min_bathrooms:
        properties = properties.filter(bathrooms__gte=buyer_profile.min_bathrooms)
    
    if buyer_profile.min_area:
        properties = properties.filter(carpet_area__gte=buyer_profile.min_area)
    
    if buyer_profile.max_area:
        properties = properties.filter(carpet_area__lte=buyer_profile.max_area)
    
    if buyer_profile.property_for:
        properties = properties.filter(property_for=buyer_profile.property_for)
    
    if buyer_profile.furnishing_preference:
        properties = properties.filter(furnishing=buyer_profile.furnishing_preference)
    
    if buyer_profile.preferred_locations:
        location_q = Q()
        for location in buyer_profile.preferred_locations:
            location_q |= Q(city__icontains=location) | Q(state__icontains=location)
        if location_q:
            properties = properties.filter(location_q)
    
    # Order by relevance (you can add more sophisticated ranking)
    return properties.annotate(
        relevance_score=Count('id')  # Placeholder for actual relevance scoring
    ).order_by('-relevance_score', '-created_at')


def get_average_price(locations):
    """Get average price for preferred locations"""
    # Demo data - in real app, calculate from database
    return "₹1.2 Cr"


def get_market_trend():
    """Get market trend data"""
    # Demo data
    return {
        'direction': 'up',
        'percentage': 8.5,
        'trend': 'Prices rising steadily'
    }


def get_hot_locations():
    """Get hot locations"""
    # Demo data
    return [
        {'name': 'Whitefield, Bangalore', 'growth': '12%'},
        {'name': 'Andheri West, Mumbai', 'growth': '9%'},
        {'name': 'Gurgaon Sector 54', 'growth': '7%'},
    ]


@login_required
def buyer_properties(request):
    """Properties search and listing for buyers"""
    user = request.user
    
    # Get filter parameters
    category = request.GET.get('category', '')
    property_type = request.GET.get('property_type', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    bedrooms = request.GET.get('bedrooms', '')
    bathrooms = request.GET.get('bathrooms', '')
    min_area = request.GET.get('min_area', '')
    max_area = request.GET.get('max_area', '')
    city = request.GET.get('city', '')
    sort_by = request.GET.get('sort', '-created_at')
    search_query = request.GET.get('q', '')
    property_for = request.GET.get('property_for', '')
    furnishing = request.GET.get('furnishing', '')
    
    # Base queryset
    properties = Property.objects.filter(status='active')
    
    # Apply filters
    if category:
        properties = properties.filter(category__slug=category)
    
    if property_type:
        properties = properties.filter(property_type__slug=property_type)
    
    if min_price:
        properties = properties.filter(price__gte=min_price)
    
    if max_price:
        properties = properties.filter(price__lte=max_price)
    
    if bedrooms:
        properties = properties.filter(bedrooms__gte=bedrooms)
    
    if bathrooms:
        properties = properties.filter(bathrooms__gte=bathrooms)
    
    if min_area:
        properties = properties.filter(carpet_area__gte=min_area)
    
    if max_area:
        properties = properties.filter(carpet_area__lte=max_area)
    
    if city:
        properties = properties.filter(city__icontains=city)
    
    if property_for:
        properties = properties.filter(property_for=property_for)
    
    if furnishing:
        properties = properties.filter(furnishing=furnishing)
    
    if search_query:
        properties = properties.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(address__icontains=search_query) |
            Q(city__icontains=search_query) |
            Q(landmark__icontains=search_query)
        )
    
    # Apply sorting
    if sort_by in ['price', '-price', 'created_at', '-created_at', 'carpet_area', '-carpet_area', 'view_count', '-view_count']:
        properties = properties.order_by(sort_by)
    
    # Get user's favorites for comparison
    user_favorites = PropertyFavorite.objects.filter(user=user).values_list('property_id', flat=True)
    
    # Pagination
    paginator = Paginator(properties, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    categories = PropertyCategory.objects.filter(is_active=True)
    property_types = PropertyType.objects.filter(is_active=True)
    
    context = {
        'user': user,
        'page_obj': page_obj,
        'categories': categories,
        'property_types': property_types,
        'user_favorites': list(user_favorites),
        'category_filter': category,
        'property_type_filter': property_type,
        'min_price_filter': min_price,
        'max_price_filter': max_price,
        'bedrooms_filter': bedrooms,
        'bathrooms_filter': bathrooms,
        'min_area_filter': min_area,
        'max_area_filter': max_area,
        'city_filter': city,
        'sort_by': sort_by,
        'search_query': search_query,
        'property_for_filter': property_for,
        'furnishing_filter': furnishing,
    }
    
    return render(request, 'dashboard/buyer/properties.html', context)


@login_required
def buyer_property_detail(request, slug):
    """Property detail view for buyers"""
    user = request.user
    property_obj = get_object_or_404(Property, slug=slug, status='active')
    
    # Track view
    property_obj.increment_view_count()
    
    # Check if property is favorited
    is_favorited = PropertyFavorite.objects.filter(user=user, property=property_obj).exists()
    
    # Get similar properties
    similar_properties = property_obj.get_similar_properties()
    
    # Check if user has already inquired
    has_inquired = PropertyInquiry.objects.filter(user=user, property=property_obj).exists()
    
    # Get seller info
    seller = property_obj.owner
    
    # Get property images
    images = property_obj.images.all()
    
    context = {
        'property': property_obj,
        'user': user,
        'is_favorited': is_favorited,
        'similar_properties': similar_properties,
        'has_inquired': has_inquired,
        'seller': seller,
        'images': images,
    }
    
    return render(request, 'dashboard/buyer/property_detail.html', context)


@login_required
def buyer_favorites(request):
    """User's favorite properties"""
    user = request.user
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    sort_by = request.GET.get('sort', '-created_at')
    
    # Base queryset
    favorites = PropertyFavorite.objects.filter(user=user)
    
    # Apply filters
    if status_filter != 'all':
        favorites = favorites.filter(status=status_filter)
    
    # Apply sorting
    if sort_by in ['created_at', '-created_at', 'priority', '-priority']:
        favorites = favorites.order_by(sort_by)
    
    # Get statistics
    interested_count = favorites.filter(status='interested').count()
    shortlisted_count = favorites.filter(status='shortlisted').count()
    scheduled_count = favorites.filter(status='view_scheduled').count()
    offered_count = favorites.filter(status='offered').count()
    
    context = {
        'user': user,
        'favorites': favorites,
        'status_filter': status_filter,
        'sort_by': sort_by,
        'stats': {
            'interested': interested_count,
            'shortlisted': shortlisted_count,
            'scheduled': scheduled_count,
            'offered': offered_count,
        }
    }
    
    return render(request, 'dashboard/buyer/favorites.html', context)


@login_required
def buyer_comparisons(request):
    """Property comparison lists"""
    user = request.user
    
    if request.method == 'POST':
        # Create new comparison list
        name = request.POST.get('name')
        if name:
            comparison = PropertyComparison.objects.create(
                user=user,
                name=name
            )
            messages.success(request, 'Comparison list created successfully!')
            return redirect('buyer_comparison_detail', pk=comparison.pk)
    
    # Get user's comparison lists
    comparisons = PropertyComparison.objects.filter(user=user)
    
    context = {
        'user': user,
        'comparisons': comparisons,
    }
    
    return render(request, 'dashboard/buyer/comparisons.html', context)


@login_required
def buyer_comparison_detail(request, pk):
    """Comparison list detail"""
    user = request.user
    comparison = get_object_or_404(PropertyComparison, pk=pk, user=user)
    
    if request.method == 'POST':
        # Add/remove properties from comparison
        property_id = request.POST.get('property_id')
        action = request.POST.get('action')
        
        if property_id and action:
            try:
                property_obj = Property.objects.get(id=property_id, status='active')
                
                if action == 'add':
                    comparison.properties.add(property_obj)
                    messages.success(request, 'Property added to comparison!')
                elif action == 'remove':
                    comparison.properties.remove(property_obj)
                    messages.success(request, 'Property removed from comparison!')
                
            except Property.DoesNotExist:
                messages.error(request, 'Property not found!')
    
    # Calculate price and area ranges for summary
    properties = comparison.properties.all()
    price_range = {
        'min': properties.aggregate(Min('price'))['price__min'] or 0,
        'max': properties.aggregate(Max('price'))['price__max'] or 0,
    }
    
    area_range = {
        'min': properties.aggregate(Min('carpet_area'))['carpet_area__min'] or 0,
        'max': properties.aggregate(Max('carpet_area'))['carpet_area__max'] or 0,
    }
    
    context = {
        'user': user,
        'comparison': comparison,
        'properties': comparison.properties.all(),
        'price_range': price_range,
        'area_range': area_range,
    }
    
    return render(request, 'dashboard/buyer/comparison_detail.html', context)


@login_required
def buyer_site_visits(request):
    """Site visit scheduling and management"""
    user = request.user
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Base queryset
    visits = SiteVisit.objects.filter(user=user)
    
    # Apply filters
    if status_filter != 'all':
        visits = visits.filter(status=status_filter)
    
    if date_from:
        visits = visits.filter(scheduled_date__gte=date_from)
    
    if date_to:
        visits = visits.filter(scheduled_date__lte=date_to)
    
    # Order by date
    visits = visits.order_by('scheduled_date', 'scheduled_time')
    
    # Statistics
    upcoming_count = visits.filter(
        scheduled_date__gte=timezone.now().date(),
        status='confirmed'
    ).count()
    
    completed_count = visits.filter(status='completed').count()
    
    context = {
        'user': user,
        'visits': visits,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'stats': {
            'upcoming': upcoming_count,
            'completed': completed_count,
        }
    }
    
    return render(request, 'dashboard/buyer/site_visits.html', context)


@login_required
def buyer_schedule_visit(request, property_id):
    """Schedule a site visit"""
    user = request.user
    property_obj = get_object_or_404(Property, id=property_id, status='active')
    
    if request.method == 'POST':
        try:
            scheduled_date = request.POST.get('scheduled_date')
            scheduled_time = request.POST.get('scheduled_time')
            contact_person = request.POST.get('contact_person', '')
            contact_phone = request.POST.get('contact_phone', '')
            notes = request.POST.get('notes', '')
            
            # Validate date and time
            visit_date = datetime.strptime(scheduled_date, '%Y-%m-%d').date()
            visit_time = datetime.strptime(scheduled_time, '%H:%M').time()
            
            # Check if date is in the past
            if visit_date < timezone.now().date():
                messages.error(request, 'Cannot schedule visit in the past!')
                return redirect('buyer_property_detail', slug=property_obj.slug)
            
            # Check if date is too far in the future (max 90 days)
            if (visit_date - timezone.now().date()).days > 90:
                messages.error(request, 'Cannot schedule visit more than 90 days in advance!')
                return redirect('buyer_property_detail', slug=property_obj.slug)
            
            # Create site visit
            site_visit = SiteVisit.objects.create(
                property=property_obj,
                user=user,
                scheduled_date=visit_date,
                scheduled_time=visit_time,
                contact_person=contact_person or user.get_full_name(),
                contact_phone=contact_phone or user.phone,
                notes=notes,
                status='pending'
            )
            
            messages.success(request, 'Site visit scheduled successfully! The seller will confirm shortly.')
            return redirect('buyer_site_visits')
            
        except Exception as e:
            messages.error(request, f'Error scheduling visit: {str(e)}')
    
    context = {
        'user': user,
        'property': property_obj,
    }
    
    return render(request, 'dashboard/buyer/schedule_visit.html', context)


@login_required
def buyer_inquiries(request):
    """Property inquiries made by buyer"""
    user = request.user
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    sort_by = request.GET.get('sort', '-created_at')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Base queryset
    inquiries = PropertyInquiry.objects.filter(user=user)
    
    # Apply filters
    if status_filter != 'all':
        inquiries = inquiries.filter(status=status_filter)
    
    # Date filters
    if date_from:
        try:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            inquiries = inquiries.filter(created_at__date__gte=from_date)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
            inquiries = inquiries.filter(created_at__date__lte=to_date)
        except ValueError:
            pass
    
    # Apply sorting
    if sort_by in ['created_at', '-created_at', 'updated_at', '-updated_at']:
        inquiries = inquiries.order_by(sort_by)
    
    context = {
        'user': user,
        'inquiries': inquiries,
        'status_filter': status_filter,
        'sort_by': sort_by,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'dashboard/buyer/inquiries.html', context)


@login_required
def buyer_profile(request):
    """Buyer profile settings"""
    user = request.user
    
    try:
        buyer_profile = user.buyer_profile
    except BuyerProfile.DoesNotExist:
        buyer_profile = BuyerProfile.objects.create(user=user)
    
    if request.method == 'POST':
        # Update buyer preferences
        buyer_profile.min_budget = request.POST.get('min_budget', 0)
        buyer_profile.max_budget = request.POST.get('max_budget', 100000000)
        buyer_profile.min_bedrooms = request.POST.get('min_bedrooms', 1)
        buyer_profile.min_bathrooms = request.POST.get('min_bathrooms', 1)
        buyer_profile.min_area = request.POST.get('min_area', 500)
        buyer_profile.max_area = request.POST.get('max_area', 5000)
        buyer_profile.property_for = request.POST.get('property_for', 'sale')
        buyer_profile.furnishing_preference = request.POST.get('furnishing_preference', '')
        buyer_profile.possession_preference = request.POST.get('possession_preference', 'any')
        buyer_profile.receive_notifications = request.POST.get('receive_notifications') == 'on'
        buyer_profile.notification_frequency = request.POST.get('notification_frequency', 'daily')
        
        # Save location preferences
        locations = request.POST.getlist('locations[]')
        if locations:
            buyer_profile.preferred_locations = locations
        
        buyer_profile.save()
        messages.success(request, 'Preferences updated successfully!')
        return redirect('buyer_profile')
    
    # Get property types for selection
    property_types = PropertyType.objects.filter(is_active=True)
    
    context = {
        'user': user,
        'buyer_profile': buyer_profile,
        'property_types': property_types,
    }
    
    return render(request, 'dashboard/buyer/profile.html', context)


# AJAX Views
@login_required
def ajax_toggle_favorite(request):
    """AJAX view to toggle property favorite"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            property_id = data.get('property_id')
            action = data.get('action')  # 'add' or 'remove'
            
            property_obj = Property.objects.get(id=property_id, status='active')
            
            if action == 'add':
                favorite, created = PropertyFavorite.objects.get_or_create(
                    user=request.user,
                    property=property_obj,
                    defaults={'status': 'interested'}
                )
                if created:
                    return JsonResponse({
                        'success': True,
                        'action': 'added',
                        'message': 'Added to favorites!'
                    })
            elif action == 'remove':
                PropertyFavorite.objects.filter(
                    user=request.user,
                    property=property_obj
                ).delete()
                return JsonResponse({
                    'success': True,
                    'action': 'removed',
                    'message': 'Removed from favorites!'
                })
            
            return JsonResponse({'success': False, 'error': 'Invalid action'})
            
        except Property.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Property not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def ajax_send_inquiry(request):
    """AJAX view to send property inquiry"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            property_id = data.get('property_id')
            message = data.get('message', '')
            phone = data.get('phone', request.user.phone)
            preferred_date = data.get('preferred_date')
            preferred_time = data.get('preferred_time')
            
            property_obj = Property.objects.get(id=property_id, status='active')
            
            # Create inquiry
            inquiry = PropertyInquiry.objects.create(
                property=property_obj,
                user=request.user,
                name=request.user.get_full_name(),
                email=request.user.email,
                phone=phone,
                message=message,
                preferred_date=preferred_date,
                preferred_time=preferred_time,
                source='website'
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Inquiry sent successfully!',
                'inquiry_id': inquiry.id
            })
            
        except Property.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Property not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def ajax_update_favorite_status(request):
    """AJAX view to update favorite status"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            favorite_id = data.get('favorite_id')
            new_status = data.get('status')
            
            favorite = PropertyFavorite.objects.get(id=favorite_id, user=request.user)
            favorite.status = new_status
            favorite.save()
            
            return JsonResponse({
                'success': True,
                'new_status': favorite.get_status_display()
            })
            
        except PropertyFavorite.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Favorite not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def ajax_remove_favorite(request):
    """AJAX view to remove favorite"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            favorite_id = data.get('favorite_id')
            
            favorite = PropertyFavorite.objects.get(id=favorite_id, user=request.user)
            property_id = favorite.property_id
            favorite.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Removed from favorites'
            })
            
        except PropertyFavorite.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Favorite not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def comparison_lists_json(request):
    """Get user's comparison lists as JSON"""
    comparisons = PropertyComparison.objects.filter(user=request.user)
    data = {
        'comparisons': [
            {
                'id': comp.id,
                'name': comp.name,
                'properties_count': comp.properties.count()
            }
            for comp in comparisons
        ]
    }
    return JsonResponse(data)


@login_required
def add_to_comparison(request, pk):
    """Add property to comparison list"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            property_id = data.get('property_id')
            
            comparison = PropertyComparison.objects.get(pk=pk, user=request.user)
            property_obj = Property.objects.get(id=property_id, status='active')
            
            comparison.properties.add(property_obj)
            
            return JsonResponse({
                'success': True,
                'message': 'Added to comparison list'
            })
            
        except PropertyComparison.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Comparison list not found'})
        except Property.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Property not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def create_comparison(request):
    """Create new comparison list"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            property_id = data.get('property_id')
            
            if not name:
                return JsonResponse({'success': False, 'error': 'Name is required'})
            
            comparison = PropertyComparison.objects.create(
                user=request.user,
                name=name
            )
            
            if property_id:
                try:
                    property_obj = Property.objects.get(id=property_id, status='active')
                    comparison.properties.add(property_obj)
                except Property.DoesNotExist:
                    pass
            
            return JsonResponse({
                'success': True,
                'id': comparison.id,
                'message': 'Comparison list created'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def confirm_visit(request, visit_id):
    """Confirm a site visit"""
    visit = get_object_or_404(SiteVisit, id=visit_id, user=request.user)
    
    if visit.status != 'pending':
        return JsonResponse({'success': False, 'error': 'Visit cannot be confirmed'})
    
    visit.status = 'confirmed'
    visit.save()
    
    return JsonResponse({'success': True, 'message': 'Visit confirmed successfully'})

@login_required
def reschedule_visit(request, visit_id):
    """Reschedule a site visit"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            visit = get_object_or_404(SiteVisit, id=visit_id, user=request.user)
            
            new_date = datetime.strptime(data.get('new_date'), '%Y-%m-%d').date()
            new_time = datetime.strptime(data.get('new_time'), '%H:%M').time()
            
            # Validate new date
            if new_date < timezone.now().date():
                return JsonResponse({'success': False, 'error': 'Cannot reschedule to past date'})
            
            # Update visit
            visit.scheduled_date = new_date
            visit.scheduled_time = new_time
            visit.status = 'rescheduled'
            visit.notes = f"Rescheduled: {data.get('reason', 'No reason provided')}"
            visit.save()
            
            return JsonResponse({'success': True, 'message': 'Visit rescheduled successfully'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def cancel_visit(request, visit_id):
    """Cancel a site visit"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            visit = get_object_or_404(SiteVisit, id=visit_id, user=request.user)
            
            if visit.status in ['completed', 'cancelled']:
                return JsonResponse({'success': False, 'error': 'Visit cannot be cancelled'})
            
            reason = data.get('reason', '')
            if data.get('reason') == 'other':
                reason = data.get('other_reason', 'Other')
            
            visit.status = 'cancelled'
            visit.notes = f"Cancelled: {reason}"
            visit.save()
            
            return JsonResponse({'success': True, 'message': 'Visit cancelled successfully'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})