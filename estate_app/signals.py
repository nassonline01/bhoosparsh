from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import logging
from .models import CustomUser, UserProfile, MembershipPlan, UserMembership, BuyerProfile

logger = logging.getLogger(__name__)

@receiver(post_save, sender=CustomUser)
def create_user_profiles(sender, instance, created, **kwargs):
    """Create user profiles when a new user is created"""
    if created:
        # Create UserProfile
        UserProfile.objects.create(user=instance)
        
        # Create buyer profile for buyers
        if instance.user_type == 'buyer':
            BuyerProfile.objects.create(user=instance)
        
        # Assign basic membership plan for sellers/agents
        if instance.user_type in ['seller', 'agent']:
            try:
                basic_plan = MembershipPlan.objects.filter(name__icontains='basic', is_active=True).first()
                if basic_plan:
                    UserMembership.objects.create(user=instance, plan=basic_plan)
                else:
                    # Create a default basic plan if none exists
                    basic_plan = MembershipPlan.objects.create(
                        name='Basic',
                        slug='basic',
                        description='Free basic plan for new sellers',
                        price=0,
                        max_listings=1,
                        max_featured=0,
                        is_popular=False,
                        plan_type='free'
                    )
                    UserMembership.objects.create(user=instance, plan=basic_plan)
            except Exception as e:
                logger.error(f"Error creating membership for user {instance.id}: {e}")