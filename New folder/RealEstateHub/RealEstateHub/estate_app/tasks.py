"""
Celery tasks for membership management
"""
from celery import shared_task
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from .models import UserSubscription
from membership.services import MembershipService
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_subscription_reminders():
    """Send subscription renewal reminders"""
    try:
        MembershipService.send_subscription_reminders()
        logger.info("Subscription reminders sent successfully")
        return True
    except Exception as e:
        logger.error(f"Error sending subscription reminders: {e}")
        return False


@shared_task
def reset_monthly_usage_counts():
    """Reset monthly usage counters for all subscriptions"""
    try:
        # Reset featured listing counts
        UserSubscription.objects.filter(
            status__in=['active', 'trialing']
        ).update(featured_used_this_month=0)
        
        logger.info("Monthly usage counts reset successfully")
        return True
    except Exception as e:
        logger.error(f"Error resetting monthly usage counts: {e}")
        return False


@shared_task
def expire_trials():
    """Expire ended trial subscriptions"""
    try:
        expired_trials = UserSubscription.objects.filter(
            is_trial=True,
            trial_end__lt=timezone.now(),
            status='trialing'
        )
        
        for subscription in expired_trials:
            subscription.status = 'expired'
            subscription.save()
            
            # Send expiration email
            send_trial_expired_email.delay(subscription.user.id)
        
        logger.info(f"Expired {expired_trials.count()} trial subscriptions")
        return True
    except Exception as e:
        logger.error(f"Error expiring trials: {e}")
        return False


@shared_task
def send_trial_expired_email(user_id):
    """Send trial expiration email"""
    from django.contrib.auth import get_user_model
    
    CustomUser = get_user_model()
    
    try:
        user = CustomUser.objects.get(id=user_id)
        subscription = user.subscription
        
        subject = f"Your Trial Has Ended - {settings.SITE_NAME}"
        
        context = {
            'user': user,
            'subscription': subscription,
            'site_name': settings.SITE_NAME,
            'site_url': settings.SITE_URL,
        }
        
        html_content = render_to_string(
            'membership/email/trial_ending.html',
            context
        )
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=True)
        
        logger.info(f"Sent trial expiration email to {user.email}")
        
    except Exception as e:
        logger.error(f"Error sending trial expiration email: {e}")


@shared_task
def sync_plans_with_razorpay():
    """Sync all plans with Razorpay"""
    from .models import MembershipPlan
    from membership.services import RazorpayService
    
    try:
        razorpay_service = RazorpayService()
        plans = MembershipPlan.objects.filter(is_active=True)
        
        for plan in plans:
            razorpay_service.sync_plan_to_razorpay(plan)
        
        logger.info(f"Synced {plans.count()} plans with Razorpay")
        return True
    except Exception as e:
        logger.error(f"Error syncing plans with Razorpay: {e}")
        return False