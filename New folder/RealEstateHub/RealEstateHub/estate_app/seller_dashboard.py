"""
99acres-style Seller Dashboard Views
"""
import json
import csv
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import (
    Count, Sum, Avg, Max, Min, Q, F,
    Case, When, Value, IntegerField, FloatField,
    ExpressionWrapper, DurationField, Func, Window
)
from django.db.models.functions import (
    TruncDate, TruncMonth, TruncYear, TruncDay,
    ExtractHour, ExtractWeekDay, Coalesce, Concat,
    Cast, JSONObject
)
from django.core.paginator import Paginator
from django.http import (
    JsonResponse, HttpResponse, HttpResponseBadRequest,
    HttpResponseForbidden, HttpResponseRedirect
)
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from django.urls import reverse
from django.template.loader import render_to_string
from django.db import transaction, connection

from .models import (
    CustomUser, UserProfile, Property, PropertyImage,
    PropertyInquiry, LeadInteraction, PropertyView,
    DailyPropertyStats, SavedSearch, UserMembership,
    MembershipPlan, PaymentTransaction, UserCredit
)
from .forms import (
    DashboardFilterForm, PropertyFilterForm, LeadFilterForm,
    BulkActionForm, BoostListingForm, RenewListingForm,
    LeadUpdateForm, LeadInteractionForm, BulkLeadActionForm,
    AnalyticsComparisonForm, ExportDataForm, ProfileSettingsForm,
    NotificationSettingsForm, PrivacySettingsForm, AccountSettingsForm,
    DashboardWidgetForm, PropertyQuickEditForm, PropertyImageReorderForm,
    AddOnServiceForm
)

logger = logging.getLogger(__name__)


# ===========================================================================
#  Helper Functions
# ===========================================================================

def get_seller_context(user, active_tab='overview'):
    """Get base context for seller dashboard"""
    
    # Get dashboard stats
    stats = user.get_dashboard_stats()
    
    # Get alerts
    alerts = get_seller_alerts(user)
    
    # Get recent leads (last 5)
    recent_leads = PropertyInquiry.objects.filter(
        property_link__owner=user,
        status='new'
    ).select_related(
        'property_link'
    ).order_by('-created_at')[:5]
    
    # Get top performing properties
    top_properties = Property.objects.filter(
        owner=user,
        is_active=True
    ).order_by('-view_count')[:3]
    
    # Get package info
    try:
        membership = user.membership
        plan = membership.plan
        subscription_info = {
            'plan_name': plan.name,
            'status': membership.status,
            'days_remaining': membership.days_remaining,
            'listings_used': membership.listings_used,
            'listings_limit': plan.max_active_listings if not plan.is_unlimited else 'Unlimited',
            'featured_used': membership.featured_used_this_month,
            'featured_limit': plan.max_featured_listings,
            'renews_on': membership.current_period_end if membership.current_period_end else None,
        }
    except UserMembership.DoesNotExist:
        subscription_info = {
            'plan_name': 'No Package',
            'status': 'inactive',
            'listings_used': 0,
            'listings_limit': 0,
            'featured_used': 0,
            'featured_limit': 0,
        }
    
    # Quick actions
    quick_actions = [
    {'title': '➕ Post New Property', 'url': reverse('seller_property_create'), 'icon': 'plus', 'class': 'btn-primary'},
    {'title': '📊 Boost Listing', 'url': '#', 'icon': 'chart-line', 'class': 'btn-warning', 'modal': 'boostModal'},
    {'title': '📤 Share All', 'url': '#', 'icon': 'share', 'class': 'btn-info', 'modal': 'shareModal'},
    {'title': '📥 Download Leads', 'url': reverse('export_leads'), 'icon': 'download', 'class': 'btn-success'},
    {'title': '🔄 Renew Expiring', 'url': '#', 'icon': 'sync', 'class': 'btn-secondary', 'modal': 'renewModal'},
    ]
    
    context = {
        'user': user,
        'active_tab': active_tab,
        'stats': stats,
        'alerts': alerts,
        'recent_leads': recent_leads,
        'top_properties': top_properties,
        'subscription_info': subscription_info,
        'quick_actions': quick_actions,
    }
    
    return context


def get_seller_alerts(user):
    """Get alerts for seller dashboard"""
    alerts = []
    
    # Check for expiring listings
    expiring_listings = Property.objects.filter(
        owner=user,
        is_active=True,
        expires_at__isnull=False,
        expires_at__lte=timezone.now() + timedelta(days=3),
        expires_at__gt=timezone.now()
    ).count()
    
    if expiring_listings > 0:
        alerts.append({
            'type': 'warning',
            'title': f'{expiring_listings} Listing(s) Expiring Soon',
            'message': f'You have {expiring_listings} listing(s) expiring in the next 3 days.',
            'action': {'text': 'Renew Now', 'url': reverse('my_properties') + '?status=expiring'},
        })
    
    # Check for unresponded leads
    unresponded_leads = PropertyInquiry.objects.filter(
        property_link__owner=user,
        status='new',
        created_at__gte=timezone.now() - timedelta(days=3)
    ).count()
    
    if unresponded_leads > 0:
        alerts.append({
            'type': 'danger',
            'title': f'{unresponded_leads} Unresponded Lead(s)',
            'message': f'You have {unresponded_leads} new lead(s) waiting for response.',
            'action': {'text': 'View Leads', 'url': reverse('seller_leads')},
        })
    
    # Check for low performing listings
    low_performing = Property.objects.filter(
        owner=user,
        is_active=True,
        view_count__lt=10,
        created_at__lte=timezone.now() - timedelta(days=7)
    ).count()
    
    if low_performing > 0:
        alerts.append({
            'type': 'info',
            'title': f'{low_performing} Low Performing Listing(s)',
            'message': f'{low_performing} of your listings have less than 10 views.',
            'action': {'text': 'Improve Now', 'url': reverse('my_properties') + '?performance=low_views'},
        })
    
    # Check membership status
    try:
        membership = user.membership
        if membership.days_remaining <= 7:
            alerts.append({
                'type': 'warning',
                'title': 'Membership Expiring Soon',
                'message': f'Your {membership.plan.name} plan expires in {membership.days_remaining} days.',
                'action': {'text': 'Renew Now', 'url': reverse('pricing')},
            })
        
        if not membership.plan.is_unlimited:
            usage_percentage = (membership.listings_used / membership.plan.max_active_listings) * 100
            if usage_percentage >= 80:
                alerts.append({
                    'type': 'info' if usage_percentage < 90 else 'warning',
                    'title': 'Listing Limit Approaching',
                    'message': f'You have used {membership.listings_used} of {membership.plan.max_active_listings} listings.',
                    'action': {'text': 'Upgrade Plan', 'url': reverse('pricing')},
                })
    except UserMembership.DoesNotExist:
        alerts.append({
            'type': 'danger',
            'title': 'No Active Membership',
            'message': 'You need a membership to list properties.',
            'action': {'text': 'Choose a Plan', 'url': reverse('pricing')},
        })
    
    return alerts


def calculate_performance_metrics(user, start_date, end_date):
    """Calculate performance metrics for the given period"""
    
    # Get properties in the period
    properties = Property.objects.filter(
        owner=user,
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    # Get views in the period
    views = PropertyView.objects.filter(
        property__owner=user,
        viewed_at__gte=start_date,
        viewed_at__lte=end_date
    )
    
    # Get leads in the period
    leads = PropertyInquiry.objects.filter(
        property_link__owner=user,
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    # Calculate metrics
    metrics = {
        'total_properties': properties.count(),
        'active_properties': properties.filter(is_active=True).count(),
        'featured_properties': properties.filter(is_featured=True).count(),
        
        'total_views': views.count(),
        'unique_visitors': views.values('session_key').distinct().count(),
        'avg_duration': views.aggregate(avg=Avg('duration_seconds'))['avg'] or 0,
        
        'total_leads': leads.count(),
        'new_leads': leads.filter(status='new').count(),
        'contacted_leads': leads.filter(status='contacted').count(),
        'converted_leads': leads.filter(status__in=['closed_won', 'negotiation']).count(),
        
        'response_rate': calculate_response_rate(user, start_date, end_date),
        'conversion_rate': calculate_conversion_rate(user, start_date, end_date),
        'avg_response_time': calculate_avg_response_time(user, start_date, end_date),
    }
    
    # Add calculated fields
    if metrics['total_views'] > 0:
        metrics['lead_conversion_rate'] = (metrics['total_leads'] / metrics['total_views']) * 100
    else:
        metrics['lead_conversion_rate'] = 0
    
    return metrics


def calculate_response_rate(user, start_date, end_date):
    """Calculate response rate for leads"""
    total_leads = PropertyInquiry.objects.filter(
        property_link__owner=user,
        created_at__gte=start_date,
        created_at__lte=end_date
    ).count()
    
    responded_leads = PropertyInquiry.objects.filter(
        property_link__owner=user,
        created_at__gte=start_date,
        created_at__lte=end_date,
        responded_at__isnull=False
    ).count()
    
    if total_leads > 0:
        return (responded_leads / total_leads) * 100
    return 0


def calculate_conversion_rate(user, start_date, end_date):
    """Calculate conversion rate (leads to deals)"""
    total_leads = PropertyInquiry.objects.filter(
        property_link__owner=user,
        created_at__gte=start_date,
        created_at__lte=end_date
    ).count()
    
    converted_leads = PropertyInquiry.objects.filter(
        property_link__owner=user,
        created_at__gte=start_date,
        created_at__lte=end_date,
        status='closed_won'
    ).count()
    
    if total_leads > 0:
        return (converted_leads / total_leads) * 100
    return 0


def calculate_avg_response_time(user, start_date, end_date):
    """Calculate average response time"""
    responded_leads = PropertyInquiry.objects.filter(
        property_link__owner=user,
        created_at__gte=start_date,
        created_at__lte=end_date,
        responded_at__isnull=False
    ).annotate(
        response_time=ExpressionWrapper(
            F('responded_at') - F('created_at'),
            output_field=DurationField()
        )
    )
    
    if responded_leads.exists():
        avg_seconds = responded_leads.aggregate(
            avg_time=Avg('response_time')
        )['avg_time'].total_seconds()
        return avg_seconds / 3600  # Convert to hours
    
    return 0


# ===========================================================================
#  Dashboard Views
# ===========================================================================

@login_required
def seller_dashboard_overview(request):
    """Main seller dashboard overview page"""
    user = request.user
    
    if user.user_type not in ['seller', 'agent', 'builder']:
        messages.error(request, 'This dashboard is only for sellers and agents.')
        return redirect('dashboard')
    
    # Get filter form
    filter_form = DashboardFilterForm(request.GET or None)
    
    # Get date range
    if filter_form.is_valid():
        start_date, end_date = filter_form.get_date_range()
    else:
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
    
    # Get base context
    context = get_seller_context(user, 'overview')
    
    # Add performance metrics
    metrics = calculate_performance_metrics(user, start_date, end_date)
    context['metrics'] = metrics
    
    # Get performance graph data
    graph_data = get_performance_graph_data(user, start_date, end_date)
    context['graph_data'] = json.dumps(graph_data)
    
    # Get lead sources breakdown
    lead_sources = get_lead_sources_breakdown(user, start_date, end_date)
    context['lead_sources'] = lead_sources
    
    # Get device breakdown
    device_breakdown = get_device_breakdown(user, start_date, end_date)
    context['device_breakdown'] = device_breakdown
    
    # Get peak hours
    peak_hours = get_peak_hours(user, start_date, end_date)
    context['peak_hours'] = peak_hours
    
    # Get recommendations
    recommendations = get_recommendations(user)
    context['recommendations'] = recommendations
    
    # Add filter form
    context['filter_form'] = filter_form
    
    return render(request, 'dashboard/seller/overview.html', context)


@login_required
def seller_dashboard_properties(request):
    """My Properties management page"""
    user = request.user
    
    if user.user_type not in ['seller', 'agent', 'builder']:
        messages.error(request, 'This dashboard is only for sellers and agents.')
        return redirect('dashboard')
    
    # Get filter form
    filter_form = PropertyFilterForm(request.GET or None)
    filter_form.user = user
    
    # Get bulk action form
    bulk_form = BulkActionForm()
    
    # Get properties
    if filter_form.is_valid():
        property_filters = filter_form.get_property_filters(user)
        sort_by = filter_form.cleaned_data.get('sort_by', '-created_at')
    else:
        property_filters = Q(owner=user)
        sort_by = '-created_at'
    
    properties = Property.objects.filter(property_filters).order_by(sort_by)
    
    # Pagination
    paginator = Paginator(properties, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get context
    context = get_seller_context(user, 'properties')
    context.update({
        'properties': page_obj,
        'filter_form': filter_form,
        'bulk_form': bulk_form,
        'total_properties': properties.count(),
        'active_count': properties.filter(is_active=True).count(),
        'draft_count': properties.filter(status='draft').count(),
        'expiring_count': properties.filter(
            expires_at__gte=timezone.now(),
            expires_at__lte=timezone.now() + timedelta(days=7)
        ).count(),
    })
    
    return render(request, 'dashboard/seller/properties.html', context)


@login_required
def seller_dashboard_property_detail(request, slug):
    """Property detail with analytics"""
    user = request.user
    property_obj = get_object_or_404(Property, slug=slug, owner=user)
    
    # Get filter form
    filter_form = DashboardFilterForm(request.GET or None)
    
    # Get date range
    if filter_form.is_valid():
        start_date, end_date = filter_form.get_date_range()
    else:
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
    
    # Get property statistics
    stats = get_property_statistics(property_obj, start_date, end_date)
    
    # Get performance graph data
    graph_data = get_property_performance_graph(property_obj, start_date, end_date)
    
    # Get lead timeline
    leads = PropertyInquiry.objects.filter(
        property_link=property_obj,
        created_at__gte=start_date,
        created_at__lte=end_date
    ).order_by('-created_at')
    
    # Get similar properties (for comparison)
    similar_properties = property_obj.get_similar_properties(limit=5)
    
    context = get_seller_context(user, 'properties')
    context.update({
        'property': property_obj,
        'stats': stats,
        'graph_data': json.dumps(graph_data),
        'leads': leads,
        'similar_properties': similar_properties,
        'filter_form': filter_form,
    })
    
    return render(request, 'dashboard/seller/property_detail.html', context)


@login_required
def seller_dashboard_leads(request):
    """Leads management page"""
    user = request.user
    
    if user.user_type not in ['seller', 'agent', 'builder']:
        messages.error(request, 'This dashboard is only for sellers and agents.')
        return redirect('dashboard')
    
    # Get filter form
    filter_form = LeadFilterForm(request.GET or None)
    filter_form.user = user
    
    # Get bulk lead action form
    bulk_lead_form = BulkLeadActionForm()
    
    # Get leads
    if filter_form.is_valid():
        lead_filters = filter_form.get_lead_filters()
        start_date, end_date = filter_form.get_date_range()
        lead_filters &= Q(created_at__gte=start_date, created_at__lte=end_date)
    else:
        lead_filters = Q(property_link__owner=user)
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
        lead_filters &= Q(created_at__gte=start_date, created_at__lte=end_date)
    
    leads = PropertyInquiry.objects.filter(lead_filters).select_related(
        'property_link'
    ).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(leads, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get lead statistics
    lead_stats = get_lead_statistics(user, start_date, end_date)
    
    context = get_seller_context(user, 'leads')
    context.update({
        'leads': page_obj,
        'filter_form': filter_form,
        'bulk_lead_form': bulk_lead_form,
        'lead_stats': lead_stats,
        'total_leads': leads.count(),
        'new_leads': leads.filter(status='new').count(),
        'hot_leads': leads.filter(priority='hot').count(),
    })
    
    return render(request, 'dashboard/seller/leads.html', context)


@login_required
def seller_dashboard_lead_detail(request, lead_id):
    """Lead detail page with interaction history"""
    user = request.user
    lead = get_object_or_404(PropertyInquiry, id=lead_id, property_link__owner=user)
    
    # Get interaction forms
    update_form = LeadUpdateForm(instance=lead)
    interaction_form = LeadInteractionForm()
    
    # Get interaction history
    interactions = LeadInteraction.objects.filter(lead=lead).order_by('-created_at')
    
    # Get lead timeline
    timeline = get_lead_timeline(lead)
    
    # Get similar leads (same person)
    similar_leads = PropertyInquiry.objects.filter(
        Q(email=lead.email) | Q(phone=lead.phone),
        property_link__owner=user
    ).exclude(id=lead.id).order_by('-created_at')[:5]
    
    context = get_seller_context(user, 'leads')
    context.update({
        'lead': lead,
        'update_form': update_form,
        'interaction_form': interaction_form,
        'interactions': interactions,
        'timeline': timeline,
        'similar_leads': similar_leads,
    })
    
    return render(request, 'dashboard/seller/lead_detail.html', context)


@login_required
def seller_dashboard_analytics(request):
    """Advanced analytics page"""
    user = request.user
    
    if user.user_type not in ['seller', 'agent', 'builder']:
        messages.error(request, 'This dashboard is only for sellers and agents.')
        return redirect('dashboard')
    
    # Get filter form
    filter_form = DashboardFilterForm(request.GET or None)
    
    # Get comparison form
    comparison_form = AnalyticsComparisonForm(request.GET or None)
    
    # Get date range
    if filter_form.is_valid():
        start_date, end_date = filter_form.get_date_range()
    else:
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
    
    # Get analytics data
    analytics_data = get_advanced_analytics(user, start_date, end_date)
    
    # Get comparison data
    if comparison_form.is_valid():
        compare_with = comparison_form.cleaned_data.get('compare_with')
        comparison_data = get_comparison_data(user, start_date, end_date, compare_with)
    else:
        comparison_data = get_comparison_data(user, start_date, end_date, 'market_average')
    
    context = get_seller_context(user, 'analytics')
    context.update({
        'analytics_data': analytics_data,
        'comparison_data': comparison_data,
        'filter_form': filter_form,
        'comparison_form': comparison_form,
        'graph_data': json.dumps(analytics_data.get('graphs', {})),
        'comparison_graph_data': json.dumps(comparison_data.get('graphs', {})),
    })
    
    return render(request, 'dashboard/seller/analytics.html', context)


@login_required
def seller_dashboard_packages(request):
    """Packages and billing page"""
    user = request.user
    
    # Get current subscription
    try:
        subscription = user.membership
        current_plan = subscription.plan
    except UserMembership.DoesNotExist:
        subscription = None
        current_plan = None
    
    # Get all active plans
    all_plans = MembershipPlan.objects.filter(is_active=True).order_by('monthly_price')
    
    # Get billing history
    billing_history = PaymentTransaction.objects.filter(
        user=user,
        status='captured'
    ).order_by('-created_at')[:20]
    
    # Get credit balance
    try:
        credit_balance = user.credits.balance
    except UserCredit.DoesNotExist:
        credit_balance = 0
    
    # Get add-on services form
    addon_form = AddOnServiceForm()
    addon_form.user = user
    
    context = get_seller_context(user, 'packages')
    context.update({
        'subscription': subscription,
        'current_plan': current_plan,
        'all_plans': all_plans,
        'billing_history': billing_history,
        'credit_balance': credit_balance,
        'addon_form': addon_form,
    })
    
    return render(request, 'dashboard/seller/packages.html', context)


@login_required
def seller_dashboard_settings(request):
    """Settings page"""
    user = request.user
    
    # Get all settings forms
    profile_form = ProfileSettingsForm(instance=user)
    notification_form = NotificationSettingsForm()
    privacy_form = PrivacySettingsForm(instance=user)
    account_form = AccountSettingsForm()
    
    # Load notification preferences
    if user.notification_preferences:
        notification_form.initial = {
            'push_new_leads': user.notification_preferences.get('push', {}).get('new_leads', True),
            'push_price_drops': user.notification_preferences.get('push', {}).get('price_drops', True),
            'push_listing_expiry': user.notification_preferences.get('push', {}).get('listing_expiry', True),
            'push_promotions': user.notification_preferences.get('push', {}).get('promotions', False),
            'email_daily_summary': user.notification_preferences.get('email', {}).get('daily_summary', True),
            'email_weekly_report': user.notification_preferences.get('email', {}).get('weekly_report', True),
            'email_market_updates': user.notification_preferences.get('email', {}).get('market_updates', False),
            'whatsapp_instant_alerts': user.notification_preferences.get('whatsapp', {}).get('instant_alerts', True),
            'whatsapp_payment_reminders': user.notification_preferences.get('whatsapp', {}).get('payment_reminders', True),
        }
    
    context = get_seller_context(user, 'settings')
    context.update({
        'profile_form': profile_form,
        'notification_form': notification_form,
        'privacy_form': privacy_form,
        'account_form': account_form,
        'active_settings_tab': 'profile',
    })
    
    return render(request, 'dashboard/seller/settings.html', context)


@login_required
def seller_dashboard_help(request):
    """Help and support page"""
    user = request.user
    
    context = get_seller_context(user, 'help')
    
    return render(request, 'dashboard/seller/help.html', context)


# ===========================================================================
#  AJAX Views
# ===========================================================================

@login_required
@require_GET
def ajax_dashboard_stats(request):
    """Get dashboard stats via AJAX"""
    user = request.user
    
    # Get filter form
    filter_form = DashboardFilterForm(request.GET or None)
    
    if filter_form.is_valid():
        start_date, end_date = filter_form.get_date_range()
    else:
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
    
    # Calculate metrics
    metrics = calculate_performance_metrics(user, start_date, end_date)
    
    # Get quick stats
    quick_stats = {
        'active_ads': Property.objects.filter(owner=user, is_active=True).count(),
        'total_views_today': PropertyView.objects.filter(
            property__owner=user,
            viewed_at__date=timezone.now().date()
        ).count(),
        'new_inquiries_today': PropertyInquiry.objects.filter(
            property_link__owner=user,
            created_at__date=timezone.now().date()
        ).count(),
        'response_rate': metrics['response_rate'],
    }
    
    # Get recent leads
    recent_leads = list(PropertyInquiry.objects.filter(
        property_link__owner=user,
        status='new'
    ).select_related('property_link').order_by('-created_at')[:5].values(
        'id', 'name', 'phone', 'email', 'message',
        'created_at', 'property_link__title'
    ))
    
    # Get top properties
    top_properties = list(Property.objects.filter(
        owner=user,
        is_active=True
    ).order_by('-view_count')[:3].values(
        'id', 'title', 'view_count', 'inquiry_count',
        'price', 'city'
    ))
    
    return JsonResponse({
        'success': True,
        'quick_stats': quick_stats,
        'metrics': metrics,
        'recent_leads': recent_leads,
        'top_properties': top_properties,
        'alerts': get_seller_alerts(user),
    })


@login_required
@require_POST
def ajax_bulk_action(request):
    """Handle bulk actions via AJAX"""
    user = request.user
    
    form = BulkActionForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'success': False, 'error': 'Invalid form data'})
    
    action = form.cleaned_data['action']
    item_ids = form.cleaned_data['item_ids']
    
    if not item_ids:
        return JsonResponse({'success': False, 'error': 'No items selected'})
    
    try:
        item_ids = [int(id) for id in item_ids.split(',')]
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid item IDs'})
    
    # Get properties
    properties = Property.objects.filter(id__in=item_ids, owner=user)
    
    if not properties.exists():
        return JsonResponse({'success': False, 'error': 'No properties found'})
    
    success_count = 0
    error_messages = []
    
    with transaction.atomic():
        for property_obj in properties:
            try:
                if action == 'boost':
                    if property_obj.boost(user):
                        success_count += 1
                    else:
                        error_messages.append(f'{property_obj.title}: Already featured')
                elif action == 'renew':
                    if property_obj.renew(user):
                        success_count += 1
                    else:
                        error_messages.append(f'{property_obj.title}: Cannot renew active listing')
                elif action == 'pause':
                    if property_obj.pause(user):
                        success_count += 1
                    else:
                        error_messages.append(f'{property_obj.title}: Already inactive')
                elif action == 'activate':
                    if property_obj.unpause(user):
                        success_count += 1
                    else:
                        error_messages.append(f'{property_obj.title}: Cannot activate')
                elif action == 'delete':
                    property_obj.is_active = False
                    property_obj.status = 'archived'
                    property_obj.save()
                    success_count += 1
                elif action == 'archive':
                    if property_obj.archive(user):
                        success_count += 1
                    else:
                        error_messages.append(f'{property_obj.title}: Cannot archive')
            except Exception as e:
                error_messages.append(f'{property_obj.title}: {str(e)}')
    
    response = {
        'success': True,
        'processed': success_count,
        'total': len(item_ids),
    }
    
    if error_messages:
        response['errors'] = error_messages[:5]  # Limit to 5 errors
    
    return JsonResponse(response)


@login_required
@require_POST
def ajax_boost_listing(request, property_id):
    """Boost a listing via AJAX"""
    user = request.user
    property_obj = get_object_or_404(Property, id=property_id, owner=user)
    
    form = BoostListingForm(request.POST, user=user)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors})
    
    duration = int(form.cleaned_data['duration'])
    payment_method = form.cleaned_data['payment_method']
    
    try:
        with transaction.atomic():
            if payment_method == 'credits':
                # Deduct credits
                user_credits = user.credits
                cost = 299 if duration == 7 else (499 if duration == 15 else 899)
                
                if user_credits.balance < cost:
                    return JsonResponse({
                        'success': False,
                        'error': f'Insufficient credits. Need {cost}, have {user_credits.balance}'
                    })
                
                user_credits.deduct(cost, f'Boost listing for {duration} days')
                user_credits.save()
                
                # Create payment transaction
                PaymentTransaction.objects.create(
                    user=user,
                    amount=cost,
                    currency='INR',
                    status='captured',
                    payment_method='credits',
                    description=f'Boost listing: {property_obj.title}',
                    metadata={
                        'property_id': property_id,
                        'duration_days': duration,
                        'type': 'boost',
                    }
                )
            
            # Boost the listing
            property_obj.boost(user, duration)
            
            return JsonResponse({
                'success': True,
                'message': f'Listing boosted for {duration} days successfully!',
                'property': {
                    'id': property_obj.id,
                    'title': property_obj.title,
                    'is_featured': property_obj.is_featured,
                    'featured_until': property_obj.featured_until.isoformat() if property_obj.featured_until else None,
                }
            })
    
    except Exception as e:
        logger.error(f"Error boosting listing: {e}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while boosting the listing'
        })


@login_required
@require_POST
def ajax_update_lead_status(request, lead_id):
    """Update lead status via AJAX"""
    user = request.user
    lead = get_object_or_404(PropertyInquiry, id=lead_id, property_link__owner=user)
    
    form = LeadUpdateForm(request.POST, instance=lead)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors})
    
    try:
        form.save()
        
        # If marking as contacted, update last_contacted
        if form.cleaned_data['status'] == 'contacted' and not lead.last_contacted:
            lead.last_contacted = timezone.now()
            lead.save(update_fields=['last_contacted'])
        
        return JsonResponse({
            'success': True,
            'message': 'Lead updated successfully',
            'lead': {
                'id': lead.id,
                'status': lead.get_status_display(),
                'priority': lead.get_priority_display(),
                'notes': lead.notes,
            }
        })
    
    except Exception as e:
        logger.error(f"Error updating lead: {e}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while updating the lead'
        })


@login_required
@require_POST
def ajax_log_interaction(request, lead_id):
    """Log lead interaction via AJAX"""
    user = request.user
    lead = get_object_or_404(PropertyInquiry, id=lead_id, property_link__owner=user)
    
    form = LeadInteractionForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors})
    
    try:
        interaction = form.save(commit=False)
        interaction.lead = lead
        interaction.performed_by = user
        interaction.save()
        
        # Update lead last_contacted
        lead.last_contacted = timezone.now()
        lead.save(update_fields=['last_contacted'])
        
        return JsonResponse({
            'success': True,
            'message': 'Interaction logged successfully',
            'interaction': {
                'id': interaction.id,
                'type': interaction.get_interaction_type_display(),
                'subject': interaction.subject,
                'message': interaction.message,
                'created_at': interaction.created_at.isoformat(),
            }
        })
    
    except Exception as e:
        logger.error(f"Error logging interaction: {e}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while logging the interaction'
        })


@login_required
@require_POST
def ajax_update_notifications(request):
    """Update notification preferences via AJAX"""
    user = request.user
    
    form = NotificationSettingsForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors})
    
    try:
        form.save_to_user(user)
        return JsonResponse({
            'success': True,
            'message': 'Notification preferences updated successfully'
        })
    
    except Exception as e:
        logger.error(f"Error updating notifications: {e}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while updating preferences'
        })


@login_required
@require_POST
def ajax_update_privacy(request):
    """Update privacy settings via AJAX"""
    user = request.user

    form = PrivacySettingsForm(request.POST, instance=user)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors})

    try:
        form.save()
        return JsonResponse({
            'success': True,
            'message': 'Privacy settings updated successfully'
        })

    except Exception as e:
        logger.error(f"Error updating privacy settings: {e}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while updating settings'
        })


@login_required
@require_POST
def ajax_update_profile(request):
    """Update profile settings via AJAX"""
    user = request.user

    # Handle profile form data
    profile_data = request.POST.copy()

    # Update user fields
    user_fields = ['first_name', 'last_name', 'phone', 'alternate_phone', 'seller_type', 'pan_card', 'aadhar_card']
    for field in user_fields:
        if field in profile_data:
            setattr(user, field, profile_data[field])

    # Handle avatar upload
    if 'avatar' in request.FILES:
        avatar = request.FILES['avatar']
        # Validate file type and size
        if avatar.content_type not in ['image/jpeg', 'image/png', 'image/jpg']:
            return JsonResponse({'success': False, 'error': 'Invalid file type. Only JPG and PNG are allowed.'})

        if avatar.size > 2 * 1024 * 1024:  # 2MB limit
            return JsonResponse({'success': False, 'error': 'File size too large. Maximum 2MB allowed.'})

        # Save avatar to user profile
        if hasattr(user, 'profile'):
            user.profile.avatar = avatar
        else:
            # Create profile if it doesn't exist
            UserProfile.objects.create(user=user, avatar=avatar)

    # Update or create user profile
    profile, created = UserProfile.objects.get_or_create(user=user)

    profile_fields = [
        'agency_name', 'license', 'experience_years', 'specialization',
        'address', 'city', 'state', 'country', 'pincode',
        'website', 'whatsapp_number', 'facebook', 'twitter', 'linkedin', 'instagram', 'bio'
    ]

    for field in profile_fields:
        if field in profile_data:
            setattr(profile, field, profile_data[field])

    try:
        with transaction.atomic():
            user.save()
            profile.save()

        return JsonResponse({
            'success': True,
            'message': 'Profile updated successfully'
        })

    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while updating profile'
        })


# ===========================================================================
#  Data Export Views
# ===========================================================================

@login_required
def export_leads_csv(request):
    """Export leads to CSV"""
    user = request.user
    
    # Get filter form
    filter_form = ExportDataForm(request.GET or None)
    
    if filter_form.is_valid():
        data_type = filter_form.cleaned_data['data_type']
        date_range = filter_form.cleaned_data['date_range']
        
        if date_range == 'custom':
            start_date = filter_form.cleaned_data['custom_start_date']
            end_date = filter_form.cleaned_data['custom_end_date']
            if start_date and end_date:
                start_date = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
                end_date = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
            else:
                start_date = timezone.now() - timedelta(days=30)
                end_date = timezone.now()
        else:
            # Use DashboardFilterForm to get date range
            temp_form = DashboardFilterForm({'time_period': date_range})
            if temp_form.is_valid():
                start_date, end_date = temp_form.get_date_range()
            else:
                start_date = timezone.now() - timedelta(days=30)
                end_date = timezone.now()
    else:
        data_type = 'leads'
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()
    
    if data_type == 'leads':
        return export_leads_to_csv(user, start_date, end_date)
    elif data_type == 'properties':
        return export_properties_to_csv(user, start_date, end_date)
    elif data_type == 'analytics':
        return export_analytics_to_csv(user, start_date, end_date)
    else:
        return HttpResponseBadRequest('Invalid data type')


def export_leads_to_csv(user, start_date, end_date):
    """Export leads to CSV file"""
    leads = PropertyInquiry.objects.filter(
        property_link__owner=user,
        created_at__gte=start_date,
        created_at__lte=end_date
    ).select_related('property_link').order_by('-created_at')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="leads_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Date', 'Time', 'Name', 'Phone', 'Email', 'Property',
        'Budget', 'Message', 'Status', 'Priority', 'Source'
    ])
    
    for lead in leads:
        writer.writerow([
            lead.created_at.strftime('%Y-%m-%d'),
            lead.created_at.strftime('%H:%M:%S'),
            lead.name,
            lead.phone,
            lead.email or '',
            lead.property_link.title,
            lead.budget or '',
            lead.message or '',
            lead.get_status_display(),
            lead.get_priority_display(),
            lead.get_contact_method_display(),
        ])
    
    return response


def export_properties_to_csv(user, start_date, end_date):
    """Export properties to CSV file"""
    properties = Property.objects.filter(
        owner=user,
        created_at__gte=start_date,
        created_at__lte=end_date
    ).order_by('-created_at')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="properties_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Title', 'Type', 'City', 'Locality', 'Price', 'Area',
        'Bedrooms', 'Bathrooms', 'Status', 'Views', 'Leads',
        'Created Date', 'Expiry Date'
    ])
    
    for prop in properties:
        writer.writerow([
            prop.title,
            prop.category.name,
            prop.city,
            prop.locality,
            prop.price,
            prop.area,
            prop.bedrooms,
            prop.bathrooms,
            prop.get_status_display(),
            prop.view_count,
            prop.inquiry_count,
            prop.created_at.strftime('%Y-%m-%d'),
            prop.expires_at.strftime('%Y-%m-%d') if prop.expires_at else '',
        ])
    
    return response


def export_analytics_to_csv(user, start_date, end_date):
    """Export analytics to CSV file"""
    # Get daily stats
    daily_stats = DailyPropertyStats.objects.filter(
        property__owner=user,
        date__gte=start_date.date(),
        date__lte=end_date.date()
    ).select_related('property').order_by('date')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="analytics_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Date', 'Property', 'Views', 'Unique Visitors', 'Avg Duration',
        'Inquiries', 'Phone Inquiries', 'WhatsApp Inquiries', 'Email Inquiries',
        'Contact Clicks', 'WhatsApp Clicks', 'Call Clicks'
    ])
    
    for stat in daily_stats:
        writer.writerow([
            stat.date.strftime('%Y-%m-%d'),
            stat.property.title,
            stat.total_views,
            stat.unique_visitors,
            stat.avg_duration,
            stat.total_inquiries,
            stat.phone_inquiries,
            stat.whatsapp_inquiries,
            stat.email_inquiries,
            stat.contact_clicks,
            stat.whatsapp_clicks,
            stat.call_clicks,
        ])
    
    return response


# ===========================================================================
#  Analytics Helper Functions
# ===========================================================================

def get_performance_graph_data(user, start_date, end_date):
    """Get performance graph data for the given period"""
    # Get daily views and leads
    days_data = []
    current_date = start_date.date()
    end_date_date = end_date.date()
    
    while current_date <= end_date_date:
        daily_views = PropertyView.objects.filter(
            property__owner=user,
            viewed_at__date=current_date
        ).count()
        
        daily_leads = PropertyInquiry.objects.filter(
            property_link__owner=user,
            created_at__date=current_date
        ).count()
        
        days_data.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'views': daily_views,
            'leads': daily_leads,
        })
        
        current_date += timedelta(days=1)
    
    # Get lead sources breakdown
    lead_sources = PropertyInquiry.objects.filter(
        property_link__owner=user,
        created_at__gte=start_date,
        created_at__lte=end_date
    ).values('contact_method').annotate(
        count=Count('id')
    ).order_by('-count')
    
    lead_source_data = {
        'labels': [],
        'data': [],
    }
    
    for source in lead_sources:
        lead_source_data['labels'].append(source['contact_method'].title())
        lead_source_data['data'].append(source['count'])
    
    # Get device breakdown
    device_breakdown = PropertyView.objects.filter(
        property__owner=user,
        viewed_at__gte=start_date,
        viewed_at__lte=end_date
    ).values('device_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    device_data = {
        'labels': [],
        'data': [],
    }
    
    for device in device_breakdown:
        device_data['labels'].append(device['device_type'].title())
        device_data['data'].append(device['count'])
    
    return {
        'days': days_data,
        'lead_sources': lead_source_data,
        'devices': device_data,
    }


def get_lead_sources_breakdown(user, start_date, end_date):
    """Get lead sources breakdown"""
    return PropertyInquiry.objects.filter(
        property_link__owner=user,
        created_at__gte=start_date,
        created_at__lte=end_date
    ).values('contact_method').annotate(
        count=Count('id'),
        percentage=Count('id') * 100.0 / PropertyInquiry.objects.filter(
            property_link__owner=user,
            created_at__gte=start_date,
            created_at__lte=end_date
        ).count()
    ).order_by('-count')


def get_device_breakdown(user, start_date, end_date):
    """Get device breakdown"""
    return PropertyView.objects.filter(
        property__owner=user,
        viewed_at__gte=start_date,
        viewed_at__lte=end_date
    ).values('device_type').annotate(
        count=Count('id'),
        percentage=Count('id') * 100.0 / PropertyView.objects.filter(
            property__owner=user,
            viewed_at__gte=start_date,
            viewed_at__lte=end_date
        ).count()
    ).order_by('-count')


def get_peak_hours(user, start_date, end_date):
    """Get peak hours for leads"""
    peak_hours = PropertyInquiry.objects.filter(
        property_link__owner=user,
        created_at__gte=start_date,
        created_at__lte=end_date
    ).annotate(
        hour=ExtractHour('created_at')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')
    
    # Format hours
    hours_data = []
    for hour_data in peak_hours:
        hour = hour_data['hour']
        count = hour_data['count']
        
        if hour < 12:
            period = f"{hour if hour != 0 else 12} AM - {hour + 1} AM"
        elif hour == 12:
            period = "12 PM - 1 PM"
        else:
            period = f"{hour - 12} PM - {hour - 11} PM"
        
        hours_data.append({
            'period': period,
            'count': count,
            'hour': hour,
        })
    
    # Sort by count
    hours_data.sort(key=lambda x: x['count'], reverse=True)
    
    return hours_data[:5]  # Return top 5 hours


def get_recommendations(user):
    """Get smart recommendations for user"""
    recommendations = []
    
    # Check for properties with few images
    low_image_properties = Property.objects.filter(
        owner=user,
        is_active=True,
        images__lt=5
    )[:3]
    
    for prop in low_image_properties:
        image_count = prop.images.count()
        recommendations.append({
            'type': 'warning',
            'title': f'Add more photos to "{prop.title}"',
            'message': f'This property has only {image_count} photos. Add more photos for 40% more views.',
            'action': {'text': 'Add Photos', 'url': reverse('edit', kwargs={'slug': prop.slug})},
        })
    
    # Check for properties without virtual tours
    no_virtual_tour = Property.objects.filter(
        owner=user,
        is_active=True,
        virtual_tour__isnull=True,
        price__gte=10000000  # Properties above 1Cr
    )[:2]
    
    for prop in no_virtual_tour:
        recommendations.append({
            'type': 'info',
            'title': f'Add virtual tour to "{prop.title}"',
            'message': 'High-value properties with virtual tours get 60% more engagement.',
            'action': {'text': 'Add Virtual Tour', 'url': reverse('edit', kwargs={'slug': prop.slug})},
        })
    
    # Check for slow response times
    slow_response_leads = PropertyInquiry.objects.filter(
        property_link__owner=user,
        status='new',
        created_at__lte=timezone.now() - timedelta(hours=24)
    )[:2]
    
    for lead in slow_response_leads:
        hours_old = int((timezone.now() - lead.created_at).total_seconds() / 3600)
        recommendations.append({
            'type': 'danger',
            'title': f'Respond to lead from {lead.name}',
            'message': f'This lead is {hours_old} hours old. Fast responses increase conversion by 300%.',
            'action': {'text': 'Respond Now', 'url': reverse('seller_lead_detail', kwargs={'lead_id': lead.id})},
        })
    
    return recommendations


def get_property_statistics(property_obj, start_date, end_date):
    """Get detailed statistics for a property"""
    # Get views
    views = PropertyView.objects.filter(
        property=property_obj,
        viewed_at__gte=start_date,
        viewed_at__lte=end_date
    )
    
    # Get leads
    leads = PropertyInquiry.objects.filter(
        property_link=property_obj,
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    # Calculate statistics
    stats = {
        'total_views': views.count(),
        'unique_visitors': views.values('session_key').distinct().count(),
        'avg_duration': views.aggregate(avg=Avg('duration_seconds'))['avg'] or 0,
        
        'total_leads': leads.count(),
        'phone_leads': leads.filter(contact_method='phone').count(),
        'whatsapp_leads': leads.filter(contact_method='whatsapp').count(),
        'email_leads': leads.filter(contact_method='email').count(),
        'form_leads': leads.filter(contact_method='form').count(),
        
        'new_leads': leads.filter(status='new').count(),
        'contacted_leads': leads.filter(status='contacted').count(),
        'interested_leads': leads.filter(status='interested').count(),
        'converted_leads': leads.filter(status='closed_won').count(),
        
        'hot_leads': leads.filter(priority='hot').count(),
        'high_leads': leads.filter(priority='high').count(),
        'medium_leads': leads.filter(priority='medium').count(),
        'low_leads': leads.filter(priority='low').count(),
    }
    
    # Calculate rates
    if stats['total_views'] > 0:
        stats['lead_conversion_rate'] = (stats['total_leads'] / stats['total_views']) * 100
    else:
        stats['lead_conversion_rate'] = 0
    
    if stats['total_leads'] > 0:
        stats['response_rate'] = (leads.filter(response__isnull=False).count() / stats['total_leads']) * 100
        stats['conversion_rate'] = (stats['converted_leads'] / stats['total_leads']) * 100
    else:
        stats['response_rate'] = 0
        stats['conversion_rate'] = 0
    
    return stats


def get_property_performance_graph(property_obj, start_date, end_date):
    """Get performance graph data for a property"""
    # Get daily stats
    daily_stats = DailyPropertyStats.objects.filter(
        property=property_obj,
        date__gte=start_date.date(),
        date__lte=end_date.date()
    ).order_by('date')
    
    # Prepare data
    days_data = []
    views_data = []
    leads_data = []
    
    for stat in daily_stats:
        days_data.append(stat.date.strftime('%Y-%m-%d'))
        views_data.append(stat.total_views)
        leads_data.append(stat.total_inquiries)
    
    return {
        'days': days_data,
        'views': views_data,
        'leads': leads_data,
    }


def get_lead_statistics(user, start_date, end_date):
    """Get lead statistics"""
    leads = PropertyInquiry.objects.filter(
        property_link__owner=user,
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    stats = {
        'total': leads.count(),
        'by_status': list(leads.values('status').annotate(count=Count('id')).order_by('-count')),
        'by_priority': list(leads.values('priority').annotate(count=Count('id')).order_by('-count')),
        'by_source': list(leads.values('contact_method').annotate(count=Count('id')).order_by('-count')),
        'by_property': list(leads.values('property_link__title').annotate(count=Count('id')).order_by('-count')[:10]),
    }
    
    return stats


def get_lead_timeline(lead):
    """Get timeline for a lead"""
    timeline = []
    
    # Add inquiry creation
    timeline.append({
        'date': lead.created_at,
        'event': 'Inquiry Created',
        'description': f'{lead.name} inquired about {lead.property_link.title}',
        'icon': 'envelope',
    })
    
    # Add response if exists
    if lead.responded_at:
        timeline.append({
            'date': lead.responded_at,
            'event': 'Response Sent',
            'description': f'Responded by {lead.responded_by.full_name if lead.responded_by else "System"}',
            'icon': 'reply',
        })
    
    # Add last contacted if exists
    if lead.last_contacted:
        timeline.append({
            'date': lead.last_contacted,
            'event': 'Last Contacted',
            'description': f'Last contacted via {lead.get_contact_method_display()}',
            'icon': 'phone',
        })
    
    # Add interactions
    interactions = LeadInteraction.objects.filter(lead=lead).order_by('created_at')
    for interaction in interactions:
        timeline.append({
            'date': interaction.created_at,
            'event': f'{interaction.get_interaction_type_display()}',
            'description': interaction.subject or interaction.message[:100] if interaction.message else '',
            'icon': get_interaction_icon(interaction.interaction_type),
        })
    
    # Sort by date
    timeline.sort(key=lambda x: x['date'])
    
    return timeline


def get_interaction_icon(interaction_type):
    """Get icon for interaction type"""
    icons = {
        'call': 'phone',
        'whatsapp': 'comment',
        'email': 'envelope',
        'sms': 'sms',
        'visit': 'home',
        'meeting': 'users',
        'note': 'sticky-note',
    }
    return icons.get(interaction_type, 'circle')


def get_advanced_analytics(user, start_date, end_date):
    """Get advanced analytics data"""
    # Get overall metrics
    metrics = calculate_performance_metrics(user, start_date, end_date)
    
    # Get trend data
    trend_data = get_trend_data(user, start_date, end_date)
    
    # Get property performance ranking
    property_ranking = get_property_ranking(user, start_date, end_date)
    
    # Get lead quality analysis
    lead_quality = get_lead_quality_analysis(user, start_date, end_date)
    
    # Get market comparison
    market_comparison = get_market_comparison(user, start_date, end_date)
    
    return {
        'metrics': metrics,
        'trends': trend_data,
        'property_ranking': property_ranking,
        'lead_quality': lead_quality,
        'market_comparison': market_comparison,
        'graphs': {
            'trend_graph': trend_data.get('graph', {}),
            'property_performance_graph': property_ranking.get('graph', {}),
        }
    }


def get_trend_data(user, start_date, end_date):
    """Get trend data for analytics"""
    # Calculate trend for key metrics
    previous_start = start_date - (end_date - start_date)
    previous_end = start_date
    
    current_metrics = calculate_performance_metrics(user, start_date, end_date)
    previous_metrics = calculate_performance_metrics(user, previous_start, previous_end)
    
    trends = {}
    for key in ['total_views', 'total_leads', 'response_rate', 'conversion_rate']:
        current = current_metrics.get(key, 0)
        previous = previous_metrics.get(key, 0)
        
        if previous > 0:
            change = ((current - previous) / previous) * 100
            trends[key] = {
                'current': current,
                'previous': previous,
                'change': round(change, 1),
                'trend': 'up' if change > 0 else 'down' if change < 0 else 'same',
            }
        else:
            trends[key] = {
                'current': current,
                'previous': 0,
                'change': 0,
                'trend': 'same',
            }
    
    # Get monthly trend graph
    monthly_data = get_monthly_trend_data(user, start_date, end_date)
    
    return {
        'trends': trends,
        'graph': monthly_data,
    }


def get_monthly_trend_data(user, start_date, end_date):
    """Get monthly trend data for graph"""
    # Aggregate by month
    monthly_stats = DailyPropertyStats.objects.filter(
        property__owner=user,
        date__gte=start_date.date(),
        date__lte=end_date.date()
    ).annotate(
        month=TruncMonth('date')
    ).values('month').annotate(
        total_views=Sum('total_views'),
        total_leads=Sum('total_inquiries'),
        avg_duration=Avg('avg_duration')
    ).order_by('month')
    
    months = []
    views = []
    leads = []
    
    for stat in monthly_stats:
        months.append(stat['month'].strftime('%b %Y'))
        views.append(stat['total_views'] or 0)
        leads.append(stat['total_leads'] or 0)
    
    return {
        'labels': months,
        'datasets': [
            {
                'label': 'Views',
                'data': views,
                'borderColor': '#4CAF50',
                'backgroundColor': 'rgba(76, 175, 80, 0.1)',
            },
            {
                'label': 'Leads',
                'data': leads,
                'borderColor': '#2196F3',
                'backgroundColor': 'rgba(33, 150, 243, 0.1)',
            }
        ]
    }


def get_property_ranking(user, start_date, end_date):
    """Rank properties by performance"""
    properties = Property.objects.filter(
        owner=user,
        created_at__gte=start_date,
        created_at__lte=end_date
    ).annotate(
        lead_conversion_rate=Case(
            When(view_count=0, then=Value(0)),
            default=F('inquiry_count') * 100.0 / F('view_count'),
            output_field=FloatField()
        ),
        engagement_score=Case(
            When(view_count=0, then=Value(0)),
            default=F('inquiry_count') * 10.0 + F('view_count') * 0.1,
            output_field=FloatField()
        )
    ).order_by('-engagement_score')[:10]
    
    # Prepare data for graph
    property_names = []
    views_data = []
    leads_data = []
    
    for prop in properties:
        property_names.append(prop.title[:20] + ('...' if len(prop.title) > 20 else ''))
        views_data.append(prop.view_count)
        leads_data.append(prop.inquiry_count)
    
    return {
        'properties': properties,
        'graph': {
            'labels': property_names,
            'datasets': [
                {
                    'label': 'Views',
                    'data': views_data,
                    'backgroundColor': 'rgba(54, 162, 235, 0.5)',
                },
                {
                    'label': 'Leads',
                    'data': leads_data,
                    'backgroundColor': 'rgba(255, 99, 132, 0.5)',
                }
            ]
        }
    }


def get_lead_quality_analysis(user, start_date, end_date):
    """Analyze lead quality"""
    leads = PropertyInquiry.objects.filter(
        property_link__owner=user,
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    # Calculate lead scores based on various factors
    high_quality_leads = leads.filter(
        Q(priority='hot') |
        Q(budget__gte=10000000) |  # Budget > 1Cr
        Q(timeline__icontains='immediate') |
        Q(status__in=['interested', 'scheduled', 'negotiation'])
    ).count()
    
    medium_quality_leads = leads.filter(
        Q(priority='high') |
        Q(budget__gte=5000000) |  # Budget > 50L
        Q(timeline__icontains='month') |
        Q(status='contacted')
    ).exclude(
        Q(priority='hot') |
        Q(budget__gte=10000000) |
        Q(timeline__icontains='immediate') |
        Q(status__in=['interested', 'scheduled', 'negotiation'])
    ).count()
    
    low_quality_leads = leads.filter(
        Q(priority__in=['medium', 'low']) |
        Q(budget__lt=5000000) |
        Q(status__in=['new', 'closed_lost', 'spam'])
    ).exclude(
        Q(priority__in=['hot', 'high']) |
        Q(budget__gte=5000000) |
        Q(status__in=['interested', 'scheduled', 'negotiation', 'contacted'])
    ).count()
    
    total_leads = leads.count()
    
    return {
        'high_quality': high_quality_leads,
        'medium_quality': medium_quality_leads,
        'low_quality': low_quality_leads,
        'total': total_leads,
        'high_percentage': (high_quality_leads / total_leads * 100) if total_leads > 0 else 0,
        'medium_percentage': (medium_quality_leads / total_leads * 100) if total_leads > 0 else 0,
        'low_percentage': (low_quality_leads / total_leads * 100) if total_leads > 0 else 0,
    }


def get_market_comparison(user, start_date, end_date):
    """Compare user performance with market average"""
    # Note: In a real application, this would compare with actual market data
    # For now, we'll use simulated data
    
    user_metrics = calculate_performance_metrics(user, start_date, end_date)
    
    # Simulated market averages (these would come from a market data API)
    market_averages = {
        'response_time': 8.5,  # hours
        'views_per_listing': 120,  # per month
        'lead_conversion': 3.5,  # percentage
        'response_rate': 45.0,  # percentage
    }
    
    comparison = {}
    for key, market_avg in market_averages.items():
        user_value = 0
        
        if key == 'response_time':
            user_value = user_metrics.get('avg_response_time', 0)
        elif key == 'views_per_listing':
            active_properties = Property.objects.filter(owner=user, is_active=True).count()
            user_value = (user_metrics.get('total_views', 0) / max(active_properties, 1)) / ((end_date - start_date).days / 30)
        elif key == 'lead_conversion':
            user_value = user_metrics.get('lead_conversion_rate', 0)
        elif key == 'response_rate':
            user_value = user_metrics.get('response_rate', 0)
        
        difference = user_value - market_avg
        percentage_diff = (difference / market_avg * 100) if market_avg > 0 else 0
        
        comparison[key] = {
            'user': round(user_value, 1),
            'market': round(market_avg, 1),
            'difference': round(difference, 1),
            'percentage_diff': round(percentage_diff, 1),
            'status': 'better' if difference > 0 else 'worse' if difference < 0 else 'same',
        }
    
    return comparison


def get_comparison_data(user, start_date, end_date, compare_with):
    """Get comparison data based on selected comparison type"""
    if compare_with == 'market_average':
        return get_market_comparison(user, start_date, end_date)
    elif compare_with == 'previous_period':
        return get_previous_period_comparison(user, start_date, end_date)
    elif compare_with == 'top_performers':
        return get_top_performers_comparison(user, start_date, end_date)
    else:
        return {}


def get_previous_period_comparison(user, start_date, end_date):
    """Compare with previous period"""
    period_days = (end_date - start_date).days
    previous_start = start_date - timedelta(days=period_days)
    previous_end = start_date
    
    current_metrics = calculate_performance_metrics(user, start_date, end_date)
    previous_metrics = calculate_performance_metrics(user, previous_start, previous_end)
    
    comparison = {}
    for key in ['total_views', 'total_leads', 'response_rate', 'conversion_rate', 'avg_response_time']:
        current = current_metrics.get(key, 0)
        previous = previous_metrics.get(key, 0)
        
        if previous > 0:
            change = ((current - previous) / previous) * 100
        else:
            change = 100 if current > 0 else 0
        
        comparison[key] = {
            'current': round(current, 1),
            'previous': round(previous, 1),
            'change': round(change, 1),
            'trend': 'up' if change > 0 else 'down' if change < 0 else 'same',
        }
    
    return comparison


def get_top_performers_comparison(user, start_date, end_date):
    """Compare with top performers in the same category"""
    # Note: This would require aggregating data from all users
    # For now, we'll use simulated data
    
    user_metrics = calculate_performance_metrics(user, start_date, end_date)
    
    # Simulated top performer data
    top_performer_metrics = {
        'response_time': 1.5,  # hours
        'views_per_listing': 250,  # per month
        'lead_conversion': 8.2,  # percentage
        'response_rate': 85.0,  # percentage
    }
    
    comparison = {}
    for key, top_value in top_performer_metrics.items():
        user_value = 0
        
        if key == 'response_time':
            user_value = user_metrics.get('avg_response_time', 0)
        elif key == 'views_per_listing':
            active_properties = Property.objects.filter(owner=user, is_active=True).count()
            user_value = (user_metrics.get('total_views', 0) / max(active_properties, 1)) / ((end_date - start_date).days / 30)
        elif key == 'lead_conversion':
            user_value = user_metrics.get('lead_conversion_rate', 0)
        elif key == 'response_rate':
            user_value = user_metrics.get('response_rate', 0)
        
        difference = top_value - user_value
        percentage_diff = (difference / top_value * 100) if top_value > 0 else 0
        
        comparison[key] = {
            'user': round(user_value, 1),
            'top_performer': round(top_value, 1),
            'difference': round(difference, 1),
            'percentage_diff': round(percentage_diff, 1),
            'status': 'better' if user_value > top_value else 'worse' if user_value < top_value else 'same',
        }
    
    return comparison