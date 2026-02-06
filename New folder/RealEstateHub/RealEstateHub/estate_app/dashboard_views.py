"""
Advanced dashboard views for all user types with analytics and management
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import (
    Count, Sum, Avg, Max, Min, Q, F,
    Case, When, Value, IntegerField,
    ExpressionWrapper, DurationField
)
from django.db.models.functions import (
    TruncDate, TruncMonth, TruncYear,
    ExtractMonth, ExtractYear, Coalesce
)
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.core.cache import cache
import json
import logging
from decimal import Decimal
from django.urls import reverse

from .models import (
    CustomUser, UserProfile, Property, PropertyInquiry,
    PropertyFavorite, PropertyView, PropertyImage,
    MembershipPlan, UserMembership, PaymentTransaction,
    PropertyAmenity, Amenity, ContactMessage,
    NewsletterSubscription, SavedSearch
)
from .models import UserSubscription, CreditPackage, UserCredit
from .forms import PropertySearchForm

logger = logging.getLogger(__name__)


# ===========================================================================
#  Common Dashboard Functions
# ===========================================================================

def get_dashboard_stats(user, time_period='30d'):
    """Get comprehensive dashboard statistics"""
    
    # Calculate date range
    end_date = timezone.now()
    if time_period == '7d':
        start_date = end_date - timedelta(days=7)
    elif time_period == '30d':
        start_date = end_date - timedelta(days=30)
    elif time_period == '90d':
        start_date = end_date - timedelta(days=90)
    else:  # 'all'
        start_date = None
    
    stats = {}
    
    if user.user_type in ['seller', 'agent']:
        stats = get_seller_dashboard_stats(user, start_date, end_date)
    elif user.user_type == 'buyer':
        stats = get_buyer_dashboard_stats(user, start_date, end_date)
    elif user.user_type == 'admin':
        stats = get_admin_dashboard_stats(start_date, end_date)
    
    return stats


def get_seller_dashboard_stats(user, start_date, end_date):
    """Get seller dashboard statistics"""
    
    # Base queryset filter
    base_filter = Q(owner=user)
    if start_date:
        base_filter &= Q(created_at__gte=start_date)
    
    # Property statistics
    properties = Property.objects.filter(base_filter)
    
    total_properties = properties.count()
    active_properties = properties.filter(is_active=True).count()
    featured_properties = properties.filter(is_featured=True, is_active=True).count()
    
    # Status breakdown
    status_breakdown = properties.values('status').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # View and inquiry statistics
    view_stats = PropertyView.objects.filter(
        property__owner=user,
        viewed_at__range=(start_date, end_date) if start_date else Q()
    ).aggregate(
        total_views=Count('id'),
        unique_visitors=Count('user', distinct=True) + Count('session_key', distinct=True),
        avg_duration=Avg('duration_seconds')
    )
    
    inquiry_stats = PropertyInquiry.objects.filter(
        property_link__owner=user,
        created_at__range=(start_date, end_date) if start_date else Q()
    ).aggregate(
        total_inquiries=Count('id'),
        new_inquiries=Count('id', filter=Q(status='new')),
        converted_inquiries=Count('id', filter=Q(status__in=['converted', 'closed']))
    )
    
    # Performance metrics
    performance_stats = {
        'conversion_rate': (
            (inquiry_stats.get('converted_inquiries', 0) / 
             view_stats.get('total_views', 1) * 100)
            if view_stats.get('total_views', 0) > 0 else 0
        ),
        'response_rate': (
            (PropertyInquiry.objects.filter(
                property_link__owner=user,
                response__isnull=False
            ).count() / 
            PropertyInquiry.objects.filter(
                property_link__owner=user
            ).count() * 100)
            if PropertyInquiry.objects.filter(property_link__owner=user).count() > 0 else 0
        ),
    }
    
    # Membership/Subscription stats
    subscription_stats = {}
    try:
        subscription = user.subscription
        subscription_stats = {
            'plan_name': subscription.plan.name,
            'status': subscription.status,
            'days_remaining': subscription.days_remaining,
            'listings_used': subscription.listings_used,
            'listings_limit': subscription.plan.max_active_listings,
            'featured_used': subscription.featured_used_this_month,
            'featured_limit': subscription.plan.max_featured_listings,
            'listings_remaining': subscription.listings_remaining,
            'is_active': subscription.is_active,
        }
    except UserSubscription.DoesNotExist:
        subscription_stats = {'has_subscription': False}
    
    # Revenue statistics (if any)
    revenue_stats = PaymentTransaction.objects.filter(
        user=user,
        status='captured'
    ).aggregate(
        total_revenue=Sum('amount'),
        avg_transaction=Avg('amount'),
        max_transaction=Max('amount')
    )
    
    # Monthly trends
    monthly_trends = get_monthly_trends(user, 'seller')
    
    return {
        'property_stats': {
            'total': total_properties,
            'active': active_properties,
            'featured': featured_properties,
            'status_breakdown': list(status_breakdown),
        },
        'engagement_stats': {
            **view_stats,
            **inquiry_stats,
        },
        'performance_stats': performance_stats,
        'subscription_stats': subscription_stats,
        'revenue_stats': revenue_stats,
        'monthly_trends': monthly_trends,
        'time_period': f"{start_date.date() if start_date else 'All'} to {end_date.date()}",
    }


def get_buyer_dashboard_stats(user, start_date, end_date):
    """Get buyer dashboard statistics"""
    
    # Base filter
    base_filter = Q(user=user)
    if start_date:
        base_filter &= Q(created_at__range=(start_date, end_date))
    
    # Favorites statistics
    favorites = PropertyFavorite.objects.filter(base_filter)
    total_favorites = favorites.count()
    
    # Recent favorites with property details
    recent_favorites = favorites.select_related(
        'property'
    ).order_by('-created_at')[:5]
    
    # Inquiry statistics
    inquiries = PropertyInquiry.objects.filter(base_filter)
    total_inquiries = inquiries.count()
    
    inquiry_status = inquiries.values('status').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # View history
    view_history = PropertyView.objects.filter(
        user=user,
        viewed_at__range=(start_date, end_date) if start_date else Q()
    ).select_related('property').order_by('-viewed_at')[:10]
    
    # Saved searches
    saved_searches = SavedSearch.objects.filter(user=user, is_active=True)
    
    # Preferences (based on behavior)
    preferences = analyze_buyer_preferences(user)
    
    # Recommendations
    recommendations = get_buyer_recommendations(user)
    
    return {
        'favorite_stats': {
            'total': total_favorites,
            'recent': list(recent_favorites),
        },
        'inquiry_stats': {
            'total': total_inquiries,
            'status_breakdown': list(inquiry_status),
            'pending': inquiries.filter(status='new').count(),
            'responded': inquiries.filter(response__isnull=False).count(),
        },
        'view_history': list(view_history),
        'saved_searches': list(saved_searches),
        'preferences': preferences,
        'recommendations': recommendations,
        'time_period': f"{start_date.date() if start_date else 'All'} to {end_date.date()}",
    }


def get_admin_dashboard_stats(start_date, end_date):
    """Get admin dashboard statistics"""
    
    # Base filter
    if start_date:
        date_filter = Q(created_at__range=(start_date, end_date))
    else:
        date_filter = Q()
    
    # User statistics
    user_stats = CustomUser.objects.filter(date_filter).aggregate(
        total_users=Count('id'),
        new_users_today=Count('id', filter=Q(date_joined__date=timezone.now().date())),
        verified_users=Count('id', filter=Q(is_verified=True)),
        active_users=Count('id', filter=Q(is_active=True)),
    )
    
    user_growth = CustomUser.objects.annotate(
        month=TruncMonth('date_joined')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')[:12]
    
    # Property statistics
    property_stats = Property.objects.filter(date_filter).aggregate(
        total_properties=Count('id'),
        active_properties=Count('id', filter=Q(is_active=True)),
        featured_properties=Count('id', filter=Q(is_featured=True)),
        verified_properties=Count('id', filter=Q(is_verified=True)),
        new_today=Count('id', filter=Q(created_at__date=timezone.now().date())),
    )
    
    property_status = Property.objects.filter(date_filter).values(
        'status'
    ).annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Revenue statistics
    revenue_stats = PaymentTransaction.objects.filter(
        date_filter,
        status='captured'
    ).aggregate(
        total_revenue=Sum('amount'),
        today_revenue=Sum('amount', filter=Q(created_at__date=timezone.now().date())),
        avg_transaction=Avg('amount'),
        total_transactions=Count('id')
    )
    
    # Subscription statistics
    subscription_stats = UserSubscription.objects.filter(date_filter).aggregate(
        total_subscriptions=Count('id'),
        active_subscriptions=Count('id', filter=Q(is_active=True)),
        trial_subscriptions=Count('id', filter=Q(is_trial=True)),
        cancelled_subscriptions=Count('id', filter=Q(status='cancelled')),
    )
    
    # Platform performance
    platform_stats = {
        'avg_response_time': calculate_avg_response_time(),
        'user_satisfaction': calculate_user_satisfaction(),
        'system_uptime': 99.9,  # This would come from monitoring
    }
    
    # Recent activities
    recent_activities = get_recent_admin_activities()
    
    return {
        'user_stats': {**user_stats, 'growth_trend': list(user_growth)},
        'property_stats': {**property_stats, 'status_breakdown': list(property_status)},
        'revenue_stats': revenue_stats,
        'subscription_stats': subscription_stats,
        'platform_stats': platform_stats,
        'recent_activities': recent_activities,
        'time_period': f"{start_date.date() if start_date else 'All'} to {end_date.date()}",
    }


def get_monthly_trends(user, user_type):
    """Get monthly trends for the last 6 months"""
    six_months_ago = timezone.now() - timedelta(days=180)
    
    if user_type == 'seller':
        # Seller trends: properties, views, inquiries
        trends = Property.objects.filter(
            owner=user,
            created_at__gte=six_months_ago
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            properties_added=Count('id'),
            total_views=Sum('view_count'),
            total_inquiries=Sum('inquiry_count'),
        ).order_by('month')
    
    elif user_type == 'buyer':
        # Buyer trends: favorites, inquiries, views
        trends = PropertyFavorite.objects.filter(
            user=user,
            created_at__gte=six_months_ago
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            favorites_added=Count('id'),
        ).order_by('month')
    
    else:  # admin
        # Admin trends: users, properties, revenue
        trends = CustomUser.objects.filter(
            date_joined__gte=six_months_ago
        ).annotate(
            month=TruncMonth('date_joined')
        ).values('month').annotate(
            new_users=Count('id'),
        ).order_by('month')
    
    return list(trends)


def analyze_buyer_preferences(user):
    """Analyze buyer preferences based on behavior"""
    preferences = {
        'preferred_cities': [],
        'preferred_property_types': [],
        'price_range': {'min': 0, 'max': 0},
        'bedroom_range': {'min': 0, 'max': 0},
    }
    
    try:
        # Get favorite properties
        favorites = PropertyFavorite.objects.filter(user=user).select_related('property')
        
        if favorites.exists():
            # Analyze cities
            cities = favorites.values_list('property__city', flat=True).distinct()
            preferences['preferred_cities'] = list(cities)[:5]
            
            # Analyze property types
            categories = favorites.values_list(
                'property__category__name', flat=True
            ).distinct()
            preferences['preferred_property_types'] = list(categories)[:5]
            
            # Analyze price range
            prices = favorites.values_list('property__price', flat=True)
            if prices:
                preferences['price_range'] = {
                    'min': min(prices),
                    'max': max(prices),
                }
            
            # Analyze bedroom range
            bedrooms = favorites.values_list('property__bedrooms', flat=True)
            if bedrooms:
                preferences['bedroom_range'] = {
                    'min': min(bedrooms),
                    'max': max(bedrooms),
                }
    
    except Exception as e:
        logger.error(f"Error analyzing buyer preferences: {e}")
    
    return preferences


def get_buyer_recommendations(user, limit=5):
    """Get personalized property recommendations for buyer"""
    try:
        # Get buyer's preferences
        preferences = analyze_buyer_preferences(user)
        
        if not preferences['preferred_cities']:
            return []
        
        # Build query based on preferences
        query = Q(is_active=True)
        
        # Filter by preferred cities
        if preferences['preferred_cities']:
            query &= Q(city__in=preferences['preferred_cities'][:3])
        
        # Filter by price range
        if preferences['price_range']['max'] > 0:
            query &= Q(price__range=(
                preferences['price_range']['min'] * 0.8,
                preferences['price_range']['max'] * 1.2
            ))
        
        # Filter by bedroom range
        if preferences['bedroom_range']['max'] > 0:
            query &= Q(bedrooms__range=(
                preferences['bedroom_range']['min'],
                preferences['bedroom_range']['max'] + 1
            ))
        
        # Exclude already favorited properties
        favorite_ids = PropertyFavorite.objects.filter(
            user=user
        ).values_list('property_id', flat=True)
        
        if favorite_ids:
            query &= ~Q(id__in=favorite_ids)
        
        # Get recommendations
        recommendations = Property.objects.filter(query).select_related(
            'owner', 'category'
        ).prefetch_related(
            'images'
        ).order_by(
            '-is_featured', '-created_at'
        )[:limit]
        
        return list(recommendations)
    
    except Exception as e:
        logger.error(f"Error getting buyer recommendations: {e}")
        return []


def calculate_avg_response_time():
    """Calculate average response time for inquiries"""
    try:
        responded_inquiries = PropertyInquiry.objects.filter(
            response__isnull=False,
            responded_at__isnull=False,
            created_at__isnull=False
        ).annotate(
            response_time=ExpressionWrapper(
                F('responded_at') - F('created_at'),
                output_field=DurationField()
            )
        )
        
        if responded_inquiries.exists():
            avg_seconds = responded_inquiries.aggregate(
                avg_time=Avg('response_time')
            )['avg_time'].total_seconds()
            
            # Convert to hours
            avg_hours = avg_seconds / 3600
            return round(avg_hours, 1)
    
    except Exception:
        pass
    
    return 0


def calculate_user_satisfaction():
    """Calculate user satisfaction score"""
    # This would typically come from surveys or ratings
    # For now, using a placeholder
    return 4.5  # out of 5


def get_recent_admin_activities():
    """Get recent admin activities"""
    activities = []
    
    # Recent property approvals
    recent_properties = Property.objects.filter(
        is_verified=False,
        is_active=True
    ).order_by('-created_at')[:5]
    
    for prop in recent_properties:
        activities.append({
            'type': 'property_approval',
            'title': f'Property needs approval: {prop.title}',
            'time': prop.created_at,
            'action_url': f'/admin/core/property/{prop.id}/change/',
        })
    
    # Recent user verifications needed
    pending_verifications = CustomUser.objects.filter(
        is_verified=False,
        is_active=True
    ).order_by('-date_joined')[:5]
    
    for user in pending_verifications:
        activities.append({
            'type': 'user_verification',
            'title': f'User needs verification: {user.email}',
            'time': user.date_joined,
            'action_url': f'/admin/core/customuser/{user.id}/change/',
        })
    
    # Recent support messages
    recent_messages = ContactMessage.objects.filter(
        status='new'
    ).order_by('-created_at')[:5]
    
    for msg in recent_messages:
        activities.append({
            'type': 'support_message',
            'title': f'New support message: {msg.subject}',
            'time': msg.created_at,
            'action_url': f'/admin/core/contactmessage/{msg.id}/change/',
        })
    
    return activities[:10]  # Return top 10 activities


# ===========================================================================
#  Dashboard Views
# ===========================================================================

@login_required
def dashboard_view(request):
    """Main dashboard view - redirects to appropriate dashboard"""
    user = request.user
    
    if user.user_type == 'admin':
        return redirect('admin_dashboard')
    elif user.user_type in ['seller', 'agent']:
        return redirect('seller_dashboard')
    else:  # buyer/tenant
        return redirect('buyer_dashboard')


@login_required
def seller_dashboard_view(request):
    """Seller/Agent Dashboard with comprehensive analytics"""
    user = request.user
    
    # Get time period from request
    time_period = request.GET.get('period', '30d')
    
    # Get dashboard statistics
    stats = get_seller_dashboard_stats(
        user,
        *(get_date_range_for_period(time_period))
    )
    
    # Get user's properties with pagination
    properties = Property.objects.filter(owner=user).order_by('-created_at')
    
    paginator = Paginator(properties, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get recent inquiries
    recent_inquiries = PropertyInquiry.objects.filter(
        property_link__owner=user
    ).select_related(
        'property_link', 'user'
    ).order_by('-created_at')[:10]
    
    # Get subscription details
    subscription = None
    credit_balance = None
    try:
        subscription = user.subscription
        credit_balance = user.credits
    except (UserSubscription.DoesNotExist, UserCredit.DoesNotExist):
        pass
    
    # Get performance alerts
    alerts = get_seller_alerts(user)
    
    # Quick actions
    quick_actions = [
        {'title': 'Add New Property', 'url': reverse('create'), 'icon': 'plus'},
        {'title': 'View All Properties', 'url': reverse('my_properties'), 'icon': 'list'},
        {'title': 'Manage Inquiries', 'url': '#inquiries-section', 'icon': 'envelope'},
        {'title': 'Upgrade Plan', 'url': reverse('upgrade'), 'icon': 'arrow-up'},
    ]
    
    context = {
        'title': 'Seller Dashboard',
        'user': user,
        'stats': stats,
        'properties': page_obj,
        'recent_inquiries': recent_inquiries,
        'subscription': subscription,
        'credit_balance': credit_balance,
        'alerts': alerts,
        'quick_actions': quick_actions,
        'time_period': time_period,
        'time_periods': [
            {'value': '7d', 'label': 'Last 7 Days'},
            {'value': '30d', 'label': 'Last 30 Days'},
            {'value': '90d', 'label': 'Last 90 Days'},
            {'value': 'all', 'label': 'All Time'},
        ],
    }
    
    return render(request, 'dashboard/seller_dashboard.html', context)


@login_required
def buyer_dashboard_view(request):
    """Buyer/Tenant Dashboard with personalized content"""
    user = request.user
    
    # Get time period from request
    time_period = request.GET.get('period', '30d')
    
    # Get dashboard statistics
    stats = get_buyer_dashboard_stats(
        user,
        *(get_date_range_for_period(time_period))
    )
    
    # Get saved properties (favorites)
    favorites = PropertyFavorite.objects.filter(user=user).select_related(
        'property'
    ).order_by('-created_at')
    
    paginator = Paginator(favorites, 12)
    page_number = request.GET.get('page', 1)
    favorites_page = paginator.get_page(page_number)
    
    # Get recent inquiries
    recent_inquiries = PropertyInquiry.objects.filter(
        user=user
    ).select_related(
        'property_link'
    ).order_by('-created_at')[:10]
    
    # Get saved searches
    saved_searches = SavedSearch.objects.filter(user=user, is_active=True)
    
    # Get recommendations
    recommendations = get_buyer_recommendations(user, 6)
    
    # Quick actions
    quick_actions = [
        {'title': 'Search Properties', 'url': reverse('list'), 'icon': 'search'},
        {'title': 'Saved Properties', 'url': '#favorites-section', 'icon': 'heart'},
        {'title': 'My Inquiries', 'url': '#inquiries-section', 'icon': 'envelope'},
        {'title': 'Saved Searches', 'url': '#searches-section', 'icon': 'save'},
    ]
    
    # Property alert suggestions
    alert_suggestions = get_property_alert_suggestions(user)
    
    context = {
        'title': 'Buyer Dashboard',
        'user': user,
        'stats': stats,
        'favorites': favorites_page,
        'recent_inquiries': recent_inquiries,
        'saved_searches': saved_searches,
        'recommendations': recommendations,
        'quick_actions': quick_actions,
        'alert_suggestions': alert_suggestions,
        'time_period': time_period,
        'time_periods': [
            {'value': '7d', 'label': 'Last 7 Days'},
            {'value': '30d', 'label': 'Last 30 Days'},
            {'value': '90d', 'label': 'All Time'},
        ],
    }
    
    return render(request, 'dashboard/buyer_dashboard.html', context)


@login_required
def admin_dashboard_view(request):
    """Admin Dashboard with platform analytics"""
    if not request.user.is_staff:
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard')
    
    # Get time period from request
    time_period = request.GET.get('period', '30d')
    
    # Get dashboard statistics
    stats = get_admin_dashboard_stats(
        *(get_date_range_for_period(time_period))
    )
    
    # Get recent activities
    recent_users = CustomUser.objects.all().order_by('-date_joined')[:10]
    recent_properties = Property.objects.all().order_by('-created_at')[:10]
    recent_transactions = PaymentTransaction.objects.filter(
        status='captured'
    ).order_by('-created_at')[:10]
    
    # System alerts
    system_alerts = get_system_alerts()
    
    # Quick statistics
    quick_stats = {
        'pending_approvals': Property.objects.filter(
            is_verified=False, is_active=True
        ).count(),
        'pending_verifications': CustomUser.objects.filter(
            is_verified=False, is_active=True
        ).count(),
        'unread_messages': ContactMessage.objects.filter(
            is_resolved=False
        ).count(),
        'failed_payments': PaymentTransaction.objects.filter(
            status='failed',
            created_at__date=timezone.now().date()
        ).count(),
    }
    
    # Revenue chart data
    revenue_data = get_revenue_chart_data()
    
    # User growth data
    user_growth_data = get_user_growth_data()
    
    # Quick actions
    quick_actions = [
        {'title': 'Manage Users', 'url': '/admin/core/customuser/', 'icon': 'users'},
        {'title': 'Manage Properties', 'url': '/admin/core/property/', 'icon': 'home'},
        {'title': 'View Transactions', 'url': '/admin/membership/paymenttransaction/', 'icon': 'credit-card'},
        {'title': 'System Settings', 'url': '/admin/', 'icon': 'cog'},
    ]
    
    context = {
        'title': 'Admin Dashboard',
        'user': request.user,
        'stats': stats,
        'recent_users': recent_users,
        'recent_properties': recent_properties,
        'recent_transactions': recent_transactions,
        'system_alerts': system_alerts,
        'quick_stats': quick_stats,
        'revenue_data': json.dumps(revenue_data),
        'user_growth_data': json.dumps(user_growth_data),
        'quick_actions': quick_actions,
        'time_period': time_period,
        'time_periods': [
            {'value': '7d', 'label': 'Last 7 Days'},
            {'value': '30d', 'label': 'Last 30 Days'},
            {'value': '90d', 'label': 'Last 90 Days'},
            {'value': 'all', 'label': 'All Time'},
        ],
    }
    
    return render(request, 'dashboard/admin_dashboard.html', context)


def get_date_range_for_period(period):
    """Get date range for time period"""
    end_date = timezone.now()
    
    if period == '7d':
        start_date = end_date - timedelta(days=7)
    elif period == '30d':
        start_date = end_date - timedelta(days=30)
    elif period == '90d':
        start_date = end_date - timedelta(days=90)
    else:  # 'all'
        start_date = None
    
    return start_date, end_date


def get_seller_alerts(user):
    """Get alerts for seller dashboard"""
    alerts = []
    
    try:
        subscription = user.subscription
        
        # Subscription alerts
        if not subscription.is_active:
            alerts.append({
                'type': 'warning',
                'title': 'Subscription Inactive',
                'message': 'Your subscription is not active. Please renew to continue listing properties.',
                'action': {'text': 'Renew Now', 'url': reverse('pricing')},
            })
        elif subscription.days_remaining <= 7:
            alerts.append({
                'type': 'info',
                'title': 'Subscription Expiring Soon',
                'message': f'Your subscription expires in {subscription.days_remaining} days.',
                'action': {'text': 'Renew Now', 'url': reverse('upgrade')},
            })
        
        # Listing limit alerts
        if not subscription.plan.is_unlimited:
            usage_percentage = (subscription.listings_used / subscription.plan.max_active_listings) * 100
            if usage_percentage >= 80:
                alerts.append({
                    'type': 'warning' if usage_percentage >= 90 else 'info',
                    'title': 'Listing Limit Approaching',
                    'message': f'You have used {subscription.listings_used} of {subscription.plan.max_active_listings} listings.',
                    'action': {'text': 'Upgrade Plan', 'url': reverse('upgrade')},
                })
        
        # Inactive properties alert
        inactive_properties = Property.objects.filter(
            owner=user,
            is_active=False
        ).count()
        
        if inactive_properties > 0:
            alerts.append({
                'type': 'info',
                'title': 'Inactive Properties',
                'message': f'You have {inactive_properties} inactive properties.',
                'action': {'text': 'Manage Properties', 'url': reverse('my_properties')},
            })
        
        # Unresponded inquiries alert
        unresponded_inquiries = PropertyInquiry.objects.filter(
            property_link__owner=user,
            response__isnull=True,
            created_at__gte=timezone.now() - timedelta(days=3)
        ).count()
        
        if unresponded_inquiries > 0:
            alerts.append({
                'type': 'warning',
                'title': 'Pending Inquiries',
                'message': f'You have {unresponded_inquiries} unresponded inquiries.',
                'action': {'text': 'View Inquiries', 'url': '#inquiries-section'},
            })
    
    except UserSubscription.DoesNotExist:
        alerts.append({
            'type': 'danger',
            'title': 'No Active Subscription',
            'message': 'You need a subscription to list properties.',
            'action': {'text': 'Choose a Plan', 'url': reverse('pricing')},
        })
    
    # Profile completion alert
    profile_completion = calculate_profile_completion(user)
    if profile_completion < 80:
        alerts.append({
            'type': 'info',
            'title': 'Complete Your Profile',
            'message': f'Your profile is {profile_completion}% complete.',
            'action': {'text': 'Edit Profile', 'url': reverse('edit_profile')},
        })
    
    return alerts


def get_system_alerts():
    """Get system alerts for admin dashboard"""
    alerts = []
    
    # Low disk space (placeholder)
    alerts.append({
        'type': 'warning',
        'title': 'Storage Warning',
        'message': 'Disk usage is at 85%. Consider cleaning up old files.',
        'action': {'text': 'View Storage', 'url': '/admin/logs/'},
    })
    
    # Pending approvals
    pending_approvals = Property.objects.filter(
        is_verified=False, is_active=True
    ).count()
    
    if pending_approvals > 0:
        alerts.append({
            'type': 'info',
            'title': 'Pending Approvals',
            'message': f'{pending_approvals} properties need verification.',
            'action': {'text': 'Review Now', 'url': '/admin/core/property/'},
        })
    
    # Failed payments today
    failed_payments = PaymentTransaction.objects.filter(
        status='failed',
        created_at__date=timezone.now().date()
    ).count()
    
    if failed_payments > 0:
        alerts.append({
            'type': 'danger',
            'title': 'Failed Payments',
            'message': f'{failed_payments} payment(s) failed today.',
            'action': {'text': 'View Transactions', 'url': '/admin/membership/paymenttransaction/'},
        })
    
    # Unread support messages
    unread_messages = ContactMessage.objects.filter(
        is_resolved=False
    ).count()
    
    if unread_messages > 0:
        alerts.append({
            'type': 'warning',
            'title': 'Unread Messages',
            'message': f'{unread_messages} unread support messages.',
            'action': {'text': 'View Messages', 'url': '/admin/core/contactmessage/'},
        })
    
    return alerts


def calculate_profile_completion(user):
    """Calculate user profile completion percentage"""
    try:
        profile = user.profile
        total_fields = 10  # Adjust based on important fields
        completed_fields = 0
        
        # Check important fields
        important_fields = [
            user.phone,
            profile.avatar,
            profile.bio,
            profile.address,
            profile.city,
            profile.state,
            profile.country,
            profile.pincode,
        ]
        
        if user.user_type in ['seller', 'agent']:
            important_fields.extend([
                profile.agency_name,
                profile.license,
            ])
        
        completed_fields = sum(1 for field in important_fields if field)
        
        return int((completed_fields / len(important_fields)) * 100)
    
    except UserProfile.DoesNotExist:
        return 0


def get_property_alert_suggestions(user):
    """Get property alert suggestions for buyer"""
    suggestions = []
    
    # Based on favorites
    favorite_cities = PropertyFavorite.objects.filter(
        user=user
    ).values_list(
        'property__city', flat=True
    ).distinct()[:3]
    
    for city in favorite_cities:
        new_properties = Property.objects.filter(
            city=city,
            is_active=True,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        if new_properties > 0:
            suggestions.append({
                'city': city,
                'count': new_properties,
                'url': f"{reverse('list')}?city={city}&sort=newest",
            })
    
    return suggestions


def get_revenue_chart_data():
    """Get revenue chart data for admin dashboard"""
    # Last 12 months revenue
    end_date = timezone.now()
    start_date = end_date - timedelta(days=365)
    
    revenue_data = PaymentTransaction.objects.filter(
        status='captured',
        created_at__range=(start_date, end_date)
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        revenue=Sum('amount')
    ).order_by('month')
    
    # Format for chart
    chart_data = {
        'labels': [],
        'datasets': [{
            'label': 'Revenue (₹)',
            'data': [],
            'borderColor': '#4CAF50',
            'backgroundColor': 'rgba(76, 175, 80, 0.1)',
        }]
    }
    
    for item in revenue_data:
        chart_data['labels'].append(item['month'].strftime('%b %Y'))
        chart_data['datasets'][0]['data'].append(float(item['revenue'] or 0))
    
    return chart_data


def get_user_growth_data():
    """Get user growth chart data for admin dashboard"""
    # Last 12 months user growth
    end_date = timezone.now()
    start_date = end_date - timedelta(days=365)
    
    growth_data = CustomUser.objects.filter(
        date_joined__range=(start_date, end_date)
    ).annotate(
        month=TruncMonth('date_joined')
    ).values('month').annotate(
        new_users=Count('id')
    ).order_by('month')
    
    # Format for chart
    chart_data = {
        'labels': [],
        'datasets': [{
            'label': 'New Users',
            'data': [],
            'borderColor': '#2196F3',
            'backgroundColor': 'rgba(33, 150, 243, 0.1)',
        }]
    }
    
    cumulative = 0
    for item in growth_data:
        cumulative += item['new_users']
        chart_data['labels'].append(item['month'].strftime('%b %Y'))
        chart_data['datasets'][0]['data'].append(cumulative)
    
    return chart_data


# ===========================================================================
#  AJAX Dashboard Views
# ===========================================================================

@login_required
@require_GET
def ajax_dashboard_stats_view(request):
    """Get dashboard statistics via AJAX"""
    user = request.user
    time_period = request.GET.get('period', '30d')
    
    try:
        if user.user_type == 'admin':
            stats = get_admin_dashboard_stats(
                *(get_date_range_for_period(time_period))
            )
        elif user.user_type in ['seller', 'agent']:
            stats = get_seller_dashboard_stats(
                user,
                *(get_date_range_for_period(time_period))
            )
        else:
            stats = get_buyer_dashboard_stats(
                user,
                *(get_date_range_for_period(time_period))
            )
        
        return JsonResponse({
            'success': True,
            'stats': stats,
            'time_period': time_period,
        })
    
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to load statistics',
        })


@login_required
@require_GET
def ajax_recent_activity_view(request):
    """Get recent activity via AJAX"""
    user = request.user
    activity_type = request.GET.get('type', 'all')
    limit = int(request.GET.get('limit', 10))
    
    activities = []
    
    if user.user_type in ['seller', 'agent']:
        # Seller activities
        if activity_type in ['all', 'inquiries']:
            inquiries = PropertyInquiry.objects.filter(
                property_link__owner=user
            ).select_related(
                'property_link', 'user'
            ).order_by('-created_at')[:limit]
            
            for inquiry in inquiries:
                activities.append({
                    'type': 'inquiry',
                    'title': f'New inquiry for {inquiry.property_link.title}',
                    'description': inquiry.message[:100] + '...' if len(inquiry.message) > 100 else inquiry.message,
                    'time': inquiry.created_at.isoformat(),
                    'icon': 'envelope',
                    'color': 'primary',
                    'url': '#',
                })
        
        if activity_type in ['all', 'views']:
            views = PropertyView.objects.filter(
                property__owner=user
            ).select_related('property').order_by('-viewed_at')[:limit]
            
            for view in views:
                activities.append({
                    'type': 'view',
                    'title': f'Property viewed: {view.property.title}',
                    'description': f'Viewed by {view.user.email if view.user else "Guest"}',
                    'time': view.viewed_at.isoformat(),
                    'icon': 'eye',
                    'color': 'info',
                    'url': reverse('detail', kwargs={'slug': view.property.slug}),
                })
    
    elif user.user_type == 'buyer':
        # Buyer activities
        if activity_type in ['all', 'favorites']:
            favorites = PropertyFavorite.objects.filter(
                user=user
            ).select_related('property').order_by('-created_at')[:limit]
            
            for favorite in favorites:
                activities.append({
                    'type': 'favorite',
                    'title': f'Property saved: {favorite.property.title}',
                    'description': f'Added to favorites',
                    'time': favorite.created_at.isoformat(),
                    'icon': 'heart',
                    'color': 'danger',
                    'url': reverse('detail', kwargs={'slug': favorite.property.slug}),
                })
        
        if activity_type in ['all', 'inquiries']:
            inquiries = PropertyInquiry.objects.filter(
                user=user
            ).select_related('property_link').order_by('-created_at')[:limit]
            
            for inquiry in inquiries:
                activities.append({
                    'type': 'inquiry',
                    'title': f'Inquiry sent: {inquiry.property_link.title}',
                    'description': inquiry.message[:100] + '...' if len(inquiry.message) > 100 else inquiry.message,
                    'time': inquiry.created_at.isoformat(),
                    'icon': 'send',
                    'color': 'success',
                    'url': '#',
                })
    
    elif user.user_type == 'admin':
        # Admin activities
        if activity_type in ['all', 'users']:
            recent_users = CustomUser.objects.all().order_by('-date_joined')[:limit]
            
            for user_obj in recent_users:
                activities.append({
                    'type': 'user',
                    'title': f'New user registered: {user_obj.email}',
                    'description': f'User type: {user_obj.get_user_type_display()}',
                    'time': user_obj.date_joined.isoformat(),
                    'icon': 'user-plus',
                    'color': 'info',
                    'url': f'/admin/core/customuser/{user_obj.id}/change/',
                })
        
        if activity_type in ['all', 'properties']:
            recent_properties = Property.objects.all().order_by('-created_at')[:limit]
            
            for prop in recent_properties:
                activities.append({
                    'type': 'property',
                    'title': f'New property listed: {prop.title}',
                    'description': f'By {prop.owner.email}',
                    'time': prop.created_at.isoformat(),
                    'icon': 'home',
                    'color': 'warning',
                    'url': f'/admin/core/property/{prop.id}/change/',
                })
    
    # Sort by time
    activities.sort(key=lambda x: x['time'], reverse=True)
    
    return JsonResponse({
        'success': True,
        'activities': activities[:limit],
    })


@login_required
@require_GET
def ajax_property_analytics_view(request, property_id):
    """Get property analytics via AJAX"""
    property_obj = get_object_or_404(Property, id=property_id, owner=request.user)
    
    try:
        # Views over time (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        daily_views = PropertyView.objects.filter(
            property=property_obj,
            viewed_at__gte=thirty_days_ago
        ).extra({
            'date': "DATE(viewed_at)"
        }).values('date').annotate(
            views=Count('id'),
            unique_visitors=Count('user', distinct=True) + Count('session_key', distinct=True)
        ).order_by('date')
        
        # Device breakdown
        device_breakdown = PropertyView.objects.filter(
            property=property_obj,
            viewed_at__gte=thirty_days_ago
        ).values('device_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Source breakdown
        source_breakdown = PropertyView.objects.filter(
            property=property_obj,
            viewed_at__gte=thirty_days_ago,
            referrer__isnull=False
        ).exclude(referrer='').values('referrer').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Inquiry statistics
        inquiry_stats = PropertyInquiry.objects.filter(
            property_link=property_obj
        ).aggregate(
            total=Count('id'),
            responded=Count('id', filter=Q(response__isnull=False)),
            converted=Count('id', filter=Q(status__in=['converted', 'closed']))
        )
        
        return JsonResponse({
            'success': True,
            'daily_views': list(daily_views),
            'device_breakdown': list(device_breakdown),
            'source_breakdown': list(source_breakdown),
            'inquiry_stats': inquiry_stats,
            'total_views': property_obj.view_count,
            'total_inquiries': property_obj.inquiry_count,
        })
    
    except Exception as e:
        logger.error(f"Error getting property analytics: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to load analytics',
        })


@login_required
@require_POST
def ajax_update_dashboard_preferences_view(request):
    """Update dashboard preferences via AJAX"""
    try:
        data = json.loads(request.body)
        
        # Store preferences in user session
        request.session['dashboard_preferences'] = {
            'default_time_period': data.get('default_time_period', '30d'),
            'show_quick_stats': data.get('show_quick_stats', True),
            'show_recent_activity': data.get('show_recent_activity', True),
            'show_alerts': data.get('show_alerts', True),
            'theme': data.get('theme', 'light'),
        }
        
        return JsonResponse({
            'success': True,
            'message': 'Preferences updated successfully',
        })
    
    except Exception as e:
        logger.error(f"Error updating dashboard preferences: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to update preferences',
        })


# ===========================================================================
#  Dashboard Widget Views
# ===========================================================================

@login_required
@require_GET
def widget_quick_stats_view(request):
    """Get quick stats widget data"""
    user = request.user
    
    if user.user_type in ['seller', 'agent']:
        # Seller quick stats
        stats = {
            'active_properties': Property.objects.filter(
                owner=user, is_active=True
            ).count(),
            'total_views_today': PropertyView.objects.filter(
                property__owner=user,
                viewed_at__date=timezone.now().date()
            ).count(),
            'new_inquiries_today': PropertyInquiry.objects.filter(
                property_link__owner=user,
                created_at__date=timezone.now().date()
            ).count(),
            'conversion_rate': calculate_seller_conversion_rate(user),
        }
    
    elif user.user_type == 'buyer':
        # Buyer quick stats
        stats = {
            'saved_properties': PropertyFavorite.objects.filter(
                user=user
            ).count(),
            'active_inquiries': PropertyInquiry.objects.filter(
                user=user,
                status__in=['new', 'contacted', 'scheduled']
            ).count(),
            'properties_viewed_today': PropertyView.objects.filter(
                user=user,
                viewed_at__date=timezone.now().date()
            ).count(),
            'recommendations_available': len(get_buyer_recommendations(user)),
        }
    
    else:  # admin
        # Admin quick stats
        stats = {
            'new_users_today': CustomUser.objects.filter(
                date_joined__date=timezone.now().date()
            ).count(),
            'new_properties_today': Property.objects.filter(
                created_at__date=timezone.now().date()
            ).count(),
            'revenue_today': PaymentTransaction.objects.filter(
                status='captured',
                created_at__date=timezone.now().date()
            ).aggregate(Sum('amount'))['amount__sum'] or 0,
            'pending_approvals': Property.objects.filter(
                is_verified=False, is_active=True
            ).count(),
        }
    
    return JsonResponse({
        'success': True,
        'stats': stats,
        'timestamp': timezone.now().isoformat(),
    })


@login_required
@require_GET
def widget_revenue_chart_view(request):
    """Get revenue chart widget data"""
    user = request.user
    
    if user.user_type in ['seller', 'agent']:
        # Seller revenue (if any)
        revenue_data = get_seller_revenue_data(user)
    elif user.user_type == 'admin':
        # Platform revenue
        revenue_data = get_platform_revenue_data()
    else:
        revenue_data = {'labels': [], 'datasets': []}
    
    return JsonResponse({
        'success': True,
        'chart_data': revenue_data,
    })


def calculate_seller_conversion_rate(user):
    """Calculate seller's inquiry to conversion rate"""
    try:
        total_inquiries = PropertyInquiry.objects.filter(
            property_link__owner=user
        ).count()
        
        converted_inquiries = PropertyInquiry.objects.filter(
            property_link__owner=user,
            status__in=['converted', 'closed']
        ).count()
        
        if total_inquiries > 0:
            return (converted_inquiries / total_inquiries) * 100
        return 0
    except Exception:
        return 0


def get_seller_revenue_data(user):
    """Get seller revenue data for chart"""
    # Last 6 months revenue from transactions
    six_months_ago = timezone.now() - timedelta(days=180)
    
    revenue_data = PaymentTransaction.objects.filter(
        user=user,
        status='captured',
        created_at__gte=six_months_ago
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        revenue=Sum('amount')
    ).order_by('month')
    
    chart_data = {
        'labels': [],
        'datasets': [{
            'label': 'Revenue (₹)',
            'data': [],
            'borderColor': '#4CAF50',
            'backgroundColor': 'rgba(76, 175, 80, 0.1)',
        }]
    }
    
    for item in revenue_data:
        chart_data['labels'].append(item['month'].strftime('%b %Y'))
        chart_data['datasets'][0]['data'].append(float(item['revenue'] or 0))
    
    return chart_data


def get_platform_revenue_data():
    """Get platform revenue data for chart"""
    # Last 12 months platform revenue
    twelve_months_ago = timezone.now() - timedelta(days=365)
    
    revenue_data = PaymentTransaction.objects.filter(
        status='captured',
        created_at__gte=twelve_months_ago
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        revenue=Sum('amount')
    ).order_by('month')
    
    chart_data = {
        'labels': [],
        'datasets': [{
            'label': 'Platform Revenue (₹)',
            'data': [],
            'borderColor': '#9C27B0',
            'backgroundColor': 'rgba(156, 39, 176, 0.1)',
        }]
    }
    
    for item in revenue_data:
        chart_data['labels'].append(item['month'].strftime('%b %Y'))
        chart_data['datasets'][0]['data'].append(float(item['revenue'] or 0))
    
    return chart_data