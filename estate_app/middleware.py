from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from .models import CustomUser
import time
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.utils import timezone
from .models import PropertyView
import logging


logger = logging.getLogger(__name__)

# =====================================================================
# Property Analytics Middleware
# =====================================================================

class PropertyAnalyticsMiddleware(MiddlewareMixin):
    """Middleware for tracking property views and analytics"""
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """Track property views"""
        # Check if this is a property detail view
        if hasattr(view_func, '__name__') and view_func.__name__ == 'PropertyDetailView':
            # Get property slug from kwargs
            slug = view_kwargs.get('slug')
            if slug:
                # Rate limiting: track views per IP
                ip = self.get_client_ip(request)
                cache_key = f"view_rate:{ip}:{slug}"
                view_count = cache.get(cache_key, 0)
                
                if view_count < 10:  # Limit 10 views per IP per property
                    cache.set(cache_key, view_count + 1, 3600)  # 1 hour
                    
                    # Track view asynchronously (could use Celery)
                    self.track_property_view_async(slug, request)
        
        return None
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def track_property_view_async(self, slug, request):
        """Track property view asynchronously"""
        # In production, this would use Celery or similar
        # For now, we'll do it synchronously but could be optimized
        
        from django.db import transaction
        from .models import Property
        
        try:
            with transaction.atomic():
                property_obj = Property.objects.select_for_update().get(slug=slug)
                property_obj.view_count += 1
                property_obj.save(update_fields=['view_count'])
                
                # Create detailed view record
                PropertyView.objects.create(
                    property=property_obj,
                    user=request.user if request.user.is_authenticated else None,
                    session_key=request.session.session_key if not request.user.is_authenticated else None,
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    referrer=request.META.get('HTTP_REFERER', ''),
                    device_type=self.get_device_type(request),
                )
                
        except Property.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Error tracking property view: {e}")
    
    def get_device_type(self, request):
        """Determine device type from user agent"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        if any(device in user_agent for device in ['mobile', 'android', 'iphone']):
            return 'mobile'
        elif 'tablet' in user_agent or 'ipad' in user_agent:
            return 'tablet'
        elif any(bot in user_agent for bot in ['bot', 'crawler', 'spider']):
            return 'bot'
        else:
            return 'desktop'

# =====================================================================
# User Last Seen Middleware
# =====================================================================

class UpdateLastSeenMiddleware(MiddlewareMixin):
    """Update user's last seen timestamp"""
    
    def process_response(self, request, response):
        if request.user.is_authenticated:
            # Update last_seen every 5 minutes to reduce database writes
            user = request.user
            if not hasattr(user, 'last_seen'):
                return response
            
            now = timezone.now()
            if not user.last_seen or (now - user.last_seen).seconds > 300:
                CustomUser.objects.filter(pk=user.pk).update(last_seen=now)
        
        return response