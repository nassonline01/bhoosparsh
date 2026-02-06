"""
Utility functions for property management
"""
import logging
import hashlib
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from django.db.models import Q, Count, Avg, Max, Min
from django.db import connection
from django.http import HttpRequest
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Property, PropertyImage, UserMembership

logger = logging.getLogger(__name__)


class PropertyUtils:
    """Utility class for property operations"""
    
    @staticmethod
    def generate_property_slug(title: str, city: str, owner_id: int) -> str:
        """Generate unique slug for property"""
        base_slug = slugify(f"{title} {city}")
        
        # Add owner ID to ensure uniqueness
        unique_slug = f"{base_slug}-{owner_id}"
        
        # Check if slug exists and modify if needed
        counter = 1
        final_slug = unique_slug
        
        while Property.objects.filter(slug=final_slug).exists():
            final_slug = f"{unique_slug}-{counter}"
            counter += 1
        
        return final_slug
    
@staticmethod
def validate_membership_limits(user) -> Tuple[bool, Optional[str]]:
    """Validate if user can create new property"""
    try:
        # FIXED: Changed from usermembership to membership
        membership = user.membership
        
        if not membership.is_active or membership.is_expired:
            return False, "Your membership is not active or has expired."
        
        if not membership.can_list_property:
            return False, (
                f"You have reached your listing limit ({membership.listings_used}/"
                f"{membership.plan.max_listings}). Please upgrade your plan."
            )
        
        return True, None
        
    except UserMembership.DoesNotExist:
        return False, "You need an active membership to list properties."
    
    @staticmethod
    def calculate_price_per_sqft(price: float, area: float) -> float:
        """Calculate price per square foot"""
        if area > 0:
            return price / area
        return 0
    
    @staticmethod
    def get_property_statistics(city: str = None, 
                               category: str = None) -> Dict[str, Any]:
        """Get property statistics for dashboard"""
        cache_key = f"property_stats:{city}:{category}"
        stats = cache.get(cache_key)
        
        if stats is None:
            filters = Q(is_active=True)
            
            if city:
                filters &= Q(city=city)
            
            if category:
                filters &= Q(category__slug=category)
            
            queryset = Property.objects.filter(filters)
            
            stats = queryset.aggregate(
                total=Count('id'),
                avg_price=Avg('price'),
                min_price=Min('price'),
                max_price=Max('price'),
                avg_area=Avg('area'),
                avg_bedrooms=Avg('bedrooms'),
                for_sale=Count('id', filter=Q(status='for_sale')),
                for_rent=Count('id', filter=Q(status='for_rent')),
                sold=Count('id', filter=Q(status='sold')),
                featured=Count('id', filter=Q(is_featured=True))
            )
            
            cache.set(cache_key, stats, 1800)  # Cache for 30 minutes
        
        return stats
    
    @staticmethod
    def optimize_property_images(property_obj) -> None:
        """Optimize property images (would integrate with image processing)"""
        # This would use Pillow or a service like ImageKit
        pass


class PropertyCacheManager:
    """Manage property-related caching"""
    
    @staticmethod
    def get_or_set(key: str, func, timeout: int = 300):
        """Get from cache or set using provided function"""
        return cache.get_or_set(key, func, timeout)
    
    @staticmethod
    def invalidate_property_cache(property_id: int):
        """Invalidate all caches related to a property"""
        cache_keys = [
            f'property:{property_id}',
            f'similar_properties:{property_id}',
            f'nearby_properties:{property_id}',
        ]
        
        for key in cache_keys:
            cache.delete(key)
    
    @staticmethod
    def get_cached_property(slug: str) -> Optional[Property]:
        """Get property from cache"""
        cache_key = f"property_detail:{slug}"
        property_data = cache.get(cache_key)
        
        if property_data:
            return property_data
        
        return None
    
    @staticmethod
    def set_cached_property(property_obj: Property, timeout: int = 300):
        """Cache property object"""
        cache_key = f"property_detail:{property_obj.slug}"
        cache.set(cache_key, property_obj, timeout)


class PropertyEmailService:
    """Handle property-related emails"""
    
    @staticmethod
    def send_property_creation_email(request, property_obj):
        """Send email notification for new property"""
        try:
            subject = f"Property Listed Successfully: {property_obj.title}"
            
            context = {
                'property': property_obj,
                'user': request.user,
                'site_name': settings.SITE_NAME,
                'site_url': settings.SITE_URL,
            }
            
            message = render_to_string('properties/email/property_created.html', context)
            
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[request.user.email],
                cc=[settings.ADMIN_EMAIL] if hasattr(settings, 'ADMIN_EMAIL') else None
            )
            email.content_subtype = 'html'
            
            email.send(fail_silently=True)
            
        except Exception as e:
            logger.error(f"Error sending property creation email: {e}")
    
    @staticmethod
    def send_property_approval_email(property_obj):
        """Send email when property is approved"""
        pass
    
    @staticmethod
    def send_property_expiry_notice(property_obj):
        """Send email when property is about to expire"""
        pass


class PropertySearchEngine:
    """Advanced property search engine"""
    
    @staticmethod
    def search_properties(search_params: Dict[str, Any], 
                         page: int = 1, 
                         per_page: int = 20) -> Dict[str, Any]:
        """Search properties with advanced filters"""
        
        filters = Q(is_active=True)
        
        # Apply filters
        if search_params.get('q'):
            query = search_params['q']
            filters &= (
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(address__icontains=query) |
                Q(city__icontains=query) |
                Q(locality__icontains=query)
            )
        
        if search_params.get('city'):
            filters &= Q(city__iexact=search_params['city'])
        
        if search_params.get('min_price'):
            filters &= Q(price__gte=search_params['min_price'])
        
        if search_params.get('max_price'):
            filters &= Q(price__lte=search_params['max_price'])
        
        if search_params.get('category'):
            filters &= Q(category_id=search_params['category'])
        
        if search_params.get('bedrooms'):
            filters &= Q(bedrooms=search_params['bedrooms'])
        
        # Execute query with optimization
        queryset = Property.objects.filter(filters).select_related(
            'owner'
        ).prefetch_related(
            'images'
        ).only(
            'id', 'title', 'slug', 'price', 'city', 'locality',
            'bedrooms', 'bathrooms', 'area', 'status', 'created_at',
            'is_featured', 'is_verified'
        )
        
        # Apply sorting
        sort_by = search_params.get('sort_by', '-created_at')
        queryset = queryset.order_by(sort_by)
        
        # Pagination
        paginator = Paginator(queryset, per_page)
        
        try:
            properties_page = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            properties_page = paginator.page(1)
        
        # Calculate stats
        stats = {
            'total': paginator.count,
            'pages': paginator.num_pages,
            'current_page': properties_page.number,
            'has_next': properties_page.has_next(),
            'has_previous': properties_page.has_previous(),
        }
        
        return {
            'properties': list(properties_page),
            'stats': stats,
            'suggestions': PropertySearchEngine.get_search_suggestions(search_params)
        }
    
    @staticmethod
    def get_search_suggestions(search_params: Dict[str, Any]) -> Dict[str, List]:
        """Get search suggestions based on current filters"""
        suggestions = {}
        
        # Get popular cities
        if not search_params.get('city'):
            suggestions['cities'] = list(
                Property.objects.filter(is_active=True)
                .values_list('city', flat=True)
                .annotate(count=Count('id'))
                .order_by('-count')[:5]
            )
        
        # Get popular localities in selected city
        if search_params.get('city'):
            suggestions['localities'] = list(
                Property.objects.filter(
                    city=search_params['city'],
                    is_active=True
                )
                .values_list('locality', flat=True)
                .distinct()[:10]
            )
        
        return suggestions


def cache_key_generator(*args, **kwargs) -> str:
    """Generate cache key from function arguments"""
    key_parts = []
    
    for arg in args:
        if hasattr(arg, 'id'):
            key_parts.append(str(arg.id))
        else:
            key_parts.append(str(arg))
    
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}:{v}")
    
    key_string = ":".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


def send_property_creation_email(request, property_obj):
    """Wrapper for email service"""
    PropertyEmailService.send_property_creation_email(request, property_obj)


def validate_membership_limits(user):
    """Wrapper for membership validation"""
    return PropertyUtils.validate_membership_limits(user)


def generate_property_slug(title, city, owner_id):
    """Wrapper for slug generation"""
    return PropertyUtils.generate_property_slug(title, city, owner_id)