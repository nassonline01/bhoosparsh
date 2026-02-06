from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.utils import timezone
from .models import Property, PropertyImage, PropertyView, UserMembership,CustomUser, UserProfile, MembershipPlan, UserMembership
from .utils import PropertyCacheManager
import logging

logger = logging.getLogger(__name__)

# =====================================================================
# Property Signals
# =====================================================================

@receiver(pre_save, sender=Property)
def property_pre_save(sender, instance, **kwargs):
    """Handle pre-save operations for property"""
    
    # Generate slug if not exists
    if not instance.slug and instance.title and instance.city and instance.owner_id:
        from .utils import generate_property_slug
        instance.slug = generate_property_slug(
            instance.title, 
            instance.city, 
            instance.owner_id
        )
    
    # Generate ref_id if not exists
    if not instance.ref_id:
        import uuid
        instance.ref_id = f"PROP{str(uuid.uuid4())[:8].upper()}"


@receiver(post_save, sender=Property)
def property_post_save(sender, instance, created, **kwargs):
    """Handle post-save operations for property"""
    
    # Invalidate cache
    PropertyCacheManager.invalidate_property_cache(instance.id)
    
    # Update user's listing count if created
    if created and hasattr(instance.owner, 'usermembership'):
        try:
            instance.owner.usermembership.increment_listing_count()
        except Exception as e:
            logger.error(f"Error updating listing count: {e}")
    
    # Log property creation/update
    action = "created" if created else "updated"
    logger.info(f"Property {action}: {instance.id} - {instance.title}")


@receiver(post_delete, sender=Property)
def property_post_delete(sender, instance, **kwargs):
    """Handle post-delete operations"""
    
    # Decrement user's listing count
    if hasattr(instance.owner, 'usermembership'):
        try:
            instance.owner.usermembership.decrement_listing_count()
        except Exception as e:
            logger.error(f"Error updating listing count on delete: {e}")
    
    # Invalidate cache
    PropertyCacheManager.invalidate_property_cache(instance.id)
    
    logger.info(f"Property deleted: {instance.id} - {instance.title}")


@receiver(post_save, sender=PropertyImage)
def property_image_post_save(sender, instance, created, **kwargs):
    """Handle property image post-save"""
    
    if instance.is_primary:
        # Ensure no other primary images for this property
        PropertyImage.objects.filter(
            property=instance.property,
            is_primary=True
        ).exclude(id=instance.id).update(is_primary=False)
    
    # Invalidate property cache
    PropertyCacheManager.invalidate_property_cache(instance.property.id)


@receiver(post_save, sender=PropertyView)
def property_view_post_save(sender, instance, created, **kwargs):
    """Handle property view tracking"""
    
    if created:
        # Update property view count in background
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE core_property SET view_count = view_count + 1 WHERE id = %s",
                [instance.property_id]
            )
        
        # Log view for analytics (could send to external service)
        logger.debug(f"Property viewed: {instance.property_id} by {instance.user_id or 'anonymous'}")

# =====================================================================
# User Profile Signals
# =====================================================================

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """Create user profile when a new user is created"""
    if created:
        UserProfile.objects.create(user=instance)
        
        # Assign basic membership plan for sellers/agents
        if instance.user_type in ['seller', 'agent']:
            try:
                basic_plan = MembershipPlan.objects.filter(name__icontains='basic', is_active=True).first()
                if basic_plan:
                    UserMembership.objects.create(user=instance, plan=basic_plan)
            except Exception as e:
                logger.error(f"Error creating membership for user {instance.id}: {e}")
                # Create a default basic plan if none exists
                basic_plan = MembershipPlan.objects.create(
                    name='Basic',
                    slug='basic',
                    description='Free basic plan for new sellers',
                    price=0,
                    max_listings=1,
                    max_featured=0,
                    is_popular=False
                )
                UserMembership.objects.create(user=instance, plan=basic_plan)


# Removed the save_user_profile signal to prevent recursion
# Profile saving should be handled explicitly in views/forms
