"""
Advanced Razorpay integration service with comprehensive error handling and webhook processing
"""
import json
import hmac
import hashlib
import logging
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q

import razorpay
from razorpay.errors import (
    BadRequestError, ServerError, SignatureVerificationError
)

from estate_app.models import CustomUser
from estate_app.models import (
    MembershipPlan, UserSubscription, PaymentTransaction,
    CreditPackage, UserCredit
)

logger = logging.getLogger(__name__)


class RazorpayService:
    """Advanced Razorpay service for handling payments and subscriptions"""
    
    def __init__(self):
        self.client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
    
    # ===========================================================================
    #  Plan Management
    # ===========================================================================
    
    def create_plan(self, plan: MembershipPlan) -> Optional[Dict]:
        """Create a plan in Razorpay"""
        try:
            plan_data = {
                'period': 'monthly',
                'interval': 1,
                'item': {
                    'name': f"{plan.name} - Monthly",
                    'amount': int(plan.monthly_price * 100),  # Convert to paise
                    'currency': 'INR',
                    'description': plan.description[:100] if plan.description else ''
                },
                'notes': {
                    'plan_id': str(plan.id),
                    'tier': plan.tier,
                    'max_listings': str(plan.max_active_listings)
                }
            }
            
            response = self.client.plan.create(plan_data)
            
            # Save Razorpay plan ID
            plan.razorpay_plan_id_monthly = response['id']
            plan.save(update_fields=['razorpay_plan_id_monthly'])
            
            logger.info(f"Created monthly Razorpay plan: {response['id']} for plan: {plan.id}")
            
            # Create annual plan if annual price is different
            if plan.annual_price and plan.annual_price != plan.monthly_price * 12:
                annual_plan_data = {
                    'period': 'yearly',
                    'interval': 1,
                    'item': {
                        'name': f"{plan.name} - Annual",
                        'amount': int(plan.annual_price * 100),
                        'currency': 'INR',
                        'description': f"Annual subscription for {plan.name}"
                    },
                    'notes': {
                        'plan_id': str(plan.id),
                        'tier': plan.tier,
                        'type': 'annual'
                    }
                }
                
                annual_response = self.client.plan.create(annual_plan_data)
                plan.razorpay_plan_id_annual = annual_response['id']
                plan.save(update_fields=['razorpay_plan_id_annual'])
                
                logger.info(f"Created annual Razorpay plan: {annual_response['id']}")
            
            return response
            
        except BadRequestError as e:
            logger.error(f"Bad request creating Razorpay plan: {e}")
            raise
        except ServerError as e:
            logger.error(f"Razorpay server error creating plan: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating Razorpay plan: {e}")
            raise
    
    def sync_plan_to_razorpay(self, plan: MembershipPlan) -> bool:
        """Sync plan with Razorpay"""
        try:
            # Check if plan already exists in Razorpay
            if plan.razorpay_plan_id_monthly:
                try:
                    existing_plan = self.client.plan.fetch(plan.razorpay_plan_id_monthly)
                    logger.info(f"Plan already exists in Razorpay: {existing_plan['id']}")
                    return True
                except BadRequestError:
                    # Plan doesn't exist, create it
                    pass
            
            # Create new plan
            self.create_plan(plan)
            return True
            
        except Exception as e:
            logger.error(f"Error syncing plan to Razorpay: {e}")
            return False
    
    # ===========================================================================
    #  Subscription Management
    # ===========================================================================
    
    def create_subscription(
        self,
        user: CustomUser,
        plan: MembershipPlan,
        duration: str = 'monthly',
        trial_days: int = 0
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """Create a subscription in Razorpay"""
        
        try:
            # Get Razorpay plan ID for duration
            razorpay_plan_id = plan.get_razorpay_plan_id(duration)
            
            if not razorpay_plan_id:
                raise ValueError(f"No Razorpay plan ID found for duration: {duration}")
            
            # Create customer if not exists
            customer_id = self.get_or_create_customer(user)
            
            # Prepare subscription data
            subscription_data = {
                'plan_id': razorpay_plan_id,
                'customer_id': customer_id,
                'total_count': 12 if duration == 'annual' else 1,  # For annual, 12 monthly payments
                'quantity': 1,
                'notes': {
                    'user_id': str(user.id),
                    'plan_id': str(plan.id),
                    'duration': duration,
                    'email': user.email
                }
            }
            
            # Add trial if applicable
            if trial_days > 0:
                subscription_data['start_at'] = int(
                    (timezone.now() + timedelta(days=trial_days)).timestamp()
                )
            
            # Create subscription
            subscription = self.client.subscription.create(subscription_data)
            
            # Create pending subscription in database
            with transaction.atomic():
                user_subscription = UserSubscription.objects.create(
                    user=user,
                    plan=plan,
                    duration=duration,
                    status='pending',
                    razorpay_subscription_id=subscription['id'],
                    razorpay_customer_id=customer_id,
                    razorpay_plan_id=razorpay_plan_id,
                    is_trial=(trial_days > 0),
                    trial_start=timezone.now() if trial_days > 0 else None,
                    trial_end=timezone.now() + timedelta(days=trial_days) if trial_days > 0 else None,
                    current_period_start=timezone.now(),
                    current_period_end=timezone.now() + timedelta(days=30),
                    auto_renew=True
                )
                
                # Create initial payment transaction
                PaymentTransaction.objects.create(
                    user=user,
                    subscription=user_subscription,
                    plan=plan,
                    razorpay_order_id=subscription['id'],
                    amount=plan.get_price_for_duration(duration),
                    currency='INR',
                    status='created',
                    description=f"Subscription to {plan.name} ({duration})"
                )
            
            logger.info(f"Created subscription: {subscription['id']} for user: {user.id}")
            return subscription, subscription['id']
            
        except BadRequestError as e:
            logger.error(f"Bad request creating subscription: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating subscription: {e}", exc_info=True)
            raise
    
    def get_or_create_customer(self, user: CustomUser) -> str:
        """Get or create Razorpay customer"""
        cache_key = f"razorpay_customer:{user.id}"
        customer_id = cache.get(cache_key)
        
        if customer_id:
            return customer_id
        
        try:
            # Check if customer already exists
            if hasattr(user, 'subscription') and user.subscription.razorpay_customer_id:
                customer_id = user.subscription.razorpay_customer_id
                cache.set(cache_key, customer_id, 3600)  # Cache for 1 hour
                return customer_id
            
            # Create new customer
            customer_data = {
                'name': user.full_name,
                'email': user.email,
                'contact': user.phone if user.phone else '',
                'notes': {
                    'user_id': str(user.id),
                    'registered_at': user.created_at.isoformat()
                }
            }
            
            customer = self.client.customer.create(customer_data)
            customer_id = customer['id']
            
            # Cache the customer ID
            cache.set(cache_key, customer_id, 3600)
            
            return customer_id
            
        except Exception as e:
            logger.error(f"Error creating Razorpay customer: {e}")
            raise
    
    def fetch_subscription(self, subscription_id: str) -> Optional[Dict]:
        """Fetch subscription details from Razorpay"""
        try:
            return self.client.subscription.fetch(subscription_id)
        except BadRequestError as e:
            logger.error(f"Error fetching subscription {subscription_id}: {e}")
            return None
    
    def cancel_subscription(
        self, 
        subscription_id: str, 
        cancel_at_period_end: bool = True
    ) -> bool:
        """Cancel subscription in Razorpay"""
        try:
            if cancel_at_period_end:
                # Cancel at period end
                self.client.subscription.cancel(subscription_id, {
                    'cancel_at_cycle_end': 1
                })
            else:
                # Cancel immediately
                self.client.subscription.cancel(subscription_id)
            
            logger.info(f"Cancelled subscription: {subscription_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling subscription {subscription_id}: {e}")
            return False
    
    def update_subscription(
        self,
        subscription_id: str,
        plan_id: str = None,
        quantity: int = None
    ) -> Optional[Dict]:
        """Update subscription details"""
        try:
            update_data = {}
            
            if plan_id:
                update_data['plan_id'] = plan_id
            
            if quantity:
                update_data['quantity'] = quantity
            
            if update_data:
                return self.client.subscription.update(subscription_id, update_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error updating subscription {subscription_id}: {e}")
            return None
    
    # ===========================================================================
    #  Payment Management
    # ===========================================================================
    
    def create_order(
        self,
        amount: Decimal,
        currency: str = 'INR',
        notes: Dict = None
    ) -> Optional[Dict]:
        """Create a Razorpay order"""
        try:
            order_data = {
                'amount': int(amount * 100),  # Convert to paise
                'currency': currency,
                'payment_capture': 1,  # Auto-capture payment
                'notes': notes or {}
            }
            
            order = self.client.order.create(order_data)
            return order
            
        except Exception as e:
            logger.error(f"Error creating Razorpay order: {e}")
            raise
    
    def verify_payment_signature(
        self,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str
    ) -> bool:
        """Verify Razorpay payment signature"""
        try:
            # Create signature verification string
            body = f"{razorpay_order_id}|{razorpay_payment_id}"
            
            # Generate expected signature
            secret = settings.RAZORPAY_KEY_SECRET.encode('utf-8')
            expected_signature = hmac.new(
                secret,
                body.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Verify signature
            is_valid = hmac.compare_digest(expected_signature, razorpay_signature)
            
            if not is_valid:
                logger.warning(f"Invalid payment signature for order: {razorpay_order_id}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error verifying payment signature: {e}")
            return False
    
    def capture_payment(self, payment_id: str, amount: Decimal) -> bool:
        """Capture a payment"""
        try:
            self.client.payment.capture(payment_id, int(amount * 100))
            return True
        except Exception as e:
            logger.error(f"Error capturing payment {payment_id}: {e}")
            return False
    
    def refund_payment(
        self,
        payment_id: str,
        amount: Decimal = None,
        notes: Dict = None
    ) -> Optional[Dict]:
        """Refund a payment"""
        try:
            refund_data = {}
            
            if amount:
                refund_data['amount'] = int(amount * 100)
            
            if notes:
                refund_data['notes'] = notes
            
            refund = self.client.payment.refund(payment_id, refund_data)
            return refund
            
        except Exception as e:
            logger.error(f"Error refunding payment {payment_id}: {e}")
            return None
    
    # ===========================================================================
    #  Webhook Processing
    # ===========================================================================
    
    def verify_webhook_signature(
        self,
        body: bytes,
        signature: str
    ) -> bool:
        """Verify Razorpay webhook signature"""
        try:
            secret = settings.RAZORPAY_WEBHOOK_SECRET.encode('utf-8')
            expected_signature = hmac.new(
                secret,
                body,
                hashlib.sha256
            ).hexdigest()
            
            is_valid = hmac.compare_digest(expected_signature, signature)
            
            if not is_valid:
                logger.warning("Invalid webhook signature")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False
    
    def process_webhook(self, event: Dict) -> bool:
        """Process Razorpay webhook event"""
        try:
            event_type = event.get('event')
            payload = event.get('payload', {})
            
            logger.info(f"Processing webhook event: {event_type}")
            
            # Route to appropriate handler
            handlers = {
                'subscription.charged': self._handle_subscription_charged,
                'subscription.activated': self._handle_subscription_activated,
                'subscription.cancelled': self._handle_subscription_cancelled,
                'subscription.pending': self._handle_subscription_pending,
                'subscription.halted': self._handle_subscription_halted,
                'payment.captured': self._handle_payment_captured,
                'payment.failed': self._handle_payment_failed,
                'refund.processed': self._handle_refund_processed,
            }
            
            handler = handlers.get(event_type)
            if handler:
                return handler(payload)
            
            logger.warning(f"No handler for event type: {event_type}")
            return False
            
        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)
            return False
    
    def _handle_subscription_charged(self, payload: Dict) -> bool:
        """Handle subscription.charged webhook"""
        try:
            subscription_payload = payload.get('subscription', {})
            payment_payload = payload.get('payment', {})
            
            subscription_id = subscription_payload.get('id')
            payment_id = payment_payload.get('id')
            
            # Update subscription
            subscription = UserSubscription.objects.filter(
                razorpay_subscription_id=subscription_id
            ).first()
            
            if subscription:
                subscription.status = 'active'
                subscription.last_payment_date = timezone.now()
                subscription.next_payment_date = timezone.now() + timedelta(days=30)
                subscription.amount_paid += Decimal(payment_payload.get('amount', 0)) / 100
                subscription.save()
                
                # Update payment transaction
                transaction = PaymentTransaction.objects.filter(
                    razorpay_order_id=subscription_id
                ).first()
                
                if transaction:
                    transaction.mark_as_paid(payment_id)
                
                logger.info(f"Subscription charged: {subscription_id}")
                return True
            
            logger.warning(f"Subscription not found: {subscription_id}")
            return False
            
        except Exception as e:
            logger.error(f"Error handling subscription.charged: {e}")
            return False
    
    def _handle_subscription_activated(self, payload: Dict) -> bool:
        """Handle subscription.activated webhook"""
        try:
            subscription_payload = payload.get('subscription', {})
            subscription_id = subscription_payload.get('id')
            
            subscription = UserSubscription.objects.filter(
                razorpay_subscription_id=subscription_id
            ).first()
            
            if subscription:
                subscription.status = 'active'
                subscription.start_date = timezone.now()
                subscription.current_period_start = timezone.now()
                subscription.current_period_end = timezone.now() + timedelta(days=30)
                subscription.save()
                
                logger.info(f"Subscription activated: {subscription_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling subscription.activated: {e}")
            return False
    
    def _handle_subscription_cancelled(self, payload: Dict) -> bool:
        """Handle subscription.cancelled webhook"""
        try:
            subscription_payload = payload.get('subscription', {})
            subscription_id = subscription_payload.get('id')
            
            subscription = UserSubscription.objects.filter(
                razorpay_subscription_id=subscription_id
            ).first()
            
            if subscription:
                subscription.status = 'canceled'
                subscription.canceled_at = timezone.now()
                subscription.auto_renew = False
                subscription.save()
                
                logger.info(f"Subscription cancelled: {subscription_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling subscription.cancelled: {e}")
            return False
    
    def _handle_payment_captured(self, payload: Dict) -> bool:
        """Handle payment.captured webhook"""
        try:
            payment_payload = payload.get('payment', {})
            payment_id = payment_payload.get('id')
            order_id = payment_payload.get('order_id')
            
            # Find transaction
            transaction = PaymentTransaction.objects.filter(
                Q(razorpay_payment_id=payment_id) | Q(razorpay_order_id=order_id)
            ).first()
            
            if transaction:
                transaction.mark_as_paid(payment_id)
                
                # If this is for a subscription, update it
                if transaction.subscription:
                    transaction.subscription.status = 'active'
                    transaction.subscription.last_payment_date = timezone.now()
                    transaction.subscription.save()
                
                logger.info(f"Payment captured: {payment_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling payment.captured: {e}")
            return False
    
    def _handle_payment_failed(self, payload: Dict) -> bool:
        """Handle payment.failed webhook"""
        try:
            payment_payload = payload.get('payment', {})
            payment_id = payment_payload.get('id')
            
            transaction = PaymentTransaction.objects.filter(
                razorpay_payment_id=payment_id
            ).first()
            
            if transaction:
                transaction.status = 'failed'
                transaction.error_message = payment_payload.get('error_description', 'Payment failed')
                transaction.save()
                
                # Update subscription if exists
                if transaction.subscription:
                    transaction.subscription.payment_failed_count += 1
                    transaction.subscription.save()
                
                logger.info(f"Payment failed: {payment_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling payment.failed: {e}")
            return False
    
    def _handle_refund_processed(self, payload: Dict) -> bool:
        """Handle refund.processed webhook"""
        try:
            refund_payload = payload.get('refund', {})
            payment_id = refund_payload.get('payment_id')
            refund_amount = Decimal(refund_payload.get('amount', 0)) / 100
            
            transaction = PaymentTransaction.objects.filter(
                razorpay_payment_id=payment_id
            ).first()
            
            if transaction:
                transaction.status = 'refunded'
                transaction.amount_refunded = refund_amount
                transaction.save()
                
                logger.info(f"Refund processed: {payment_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling refund.processed: {e}")
            return False
    
    def _handle_subscription_pending(self, payload: Dict) -> bool:
        """Handle subscription.pending webhook"""
        try:
            subscription_payload = payload.get('subscription', {})
            subscription_id = subscription_payload.get('id')
            
            subscription = UserSubscription.objects.filter(
                razorpay_subscription_id=subscription_id
            ).first()
            
            if subscription:
                subscription.status = 'pending'
                subscription.save()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling subscription.pending: {e}")
            return False
    
    def _handle_subscription_halted(self, payload: Dict) -> bool:
        """Handle subscription.halted webhook"""
        try:
            subscription_payload = payload.get('subscription', {})
            subscription_id = subscription_payload.get('id')
            
            subscription = UserSubscription.objects.filter(
                razorpay_subscription_id=subscription_id
            ).first()
            
            if subscription:
                subscription.status = 'past_due'
                subscription.save()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error handling subscription.halted: {e}")
            return False


class MembershipService:
    """Service for membership-related operations"""
    
    @staticmethod
    def get_available_plans(user: CustomUser = None) -> List[MembershipPlan]:
        """Get available membership plans"""
        # Get base queryset
        plans = MembershipPlan.objects.filter(
            is_active=True
        ).order_by('display_order', 'monthly_price')

        # Filter plans based on user's current subscription
        if user:
            current_plan = MembershipService.get_user_current_plan(user)
            if current_plan:
                # Don't show plans with lower tier
                tier_order = ['basic', 'professional', 'enterprise']
                current_tier_index = tier_order.index(current_plan.tier)
                plans = plans.filter(tier__in=tier_order[current_tier_index + 1:])

        return plans
    
    @staticmethod
    def get_user_current_plan(user: CustomUser) -> Optional[MembershipPlan]:
        """Get user's current active plan"""
        if not user or not user.is_authenticated:
            return None

        try:
            subscription = user.subscription
            if subscription.is_active:
                return subscription.plan
        except UserSubscription.DoesNotExist:
            pass

        return None
    
    @staticmethod
    def can_user_upgrade(user: CustomUser, target_plan: MembershipPlan) -> Tuple[bool, str]:
        """Check if user can upgrade to target plan"""
        try:
            current_subscription = user.subscription
            
            # Check if user already has this plan
            if current_subscription.plan == target_plan:
                return False, "You are already on this plan."
            
            # Check if target plan is actually an upgrade
            tier_order = ['basic', 'professional', 'enterprise']
            current_tier_index = tier_order.index(current_subscription.plan.tier)
            target_tier_index = tier_order.index(target_plan.tier)
            
            if target_tier_index <= current_tier_index:
                return False, "Please select a higher tier plan to upgrade."
            
            # Check if current subscription is active
            if not current_subscription.is_active:
                return False, "Your current subscription is not active."
            
            return True, ""
            
        except UserSubscription.DoesNotExist:
            # User has no subscription, they can choose any plan
            return True, ""
    
    @staticmethod
    @transaction.atomic
    def activate_trial(user: CustomUser, plan: MembershipPlan) -> bool:
        """Activate trial for user"""
        try:
            # Check if user already has a subscription
            try:
                subscription = user.subscription
                if subscription.is_active and not subscription.is_trial:
                    return False, "You already have an active subscription."
                
                if subscription.is_trial:
                    return False, "You have already used your trial."
                
            except UserSubscription.DoesNotExist:
                subscription = None
            
            # Check if plan has trial
            if not plan.has_trial or plan.trial_days == 0:
                return False, "This plan does not offer a trial."
            
            # Create or update subscription
            if subscription:
                subscription.activate_trial(plan)
            else:
                UserSubscription.objects.create(
                    user=user,
                    plan=plan,
                    status='trialing',
                    is_trial=True,
                    trial_start=timezone.now(),
                    trial_end=timezone.now() + timedelta(days=plan.trial_days)
                )
            
            # Update user's profile
            user.user_type = 'seller' if user.user_type == 'buyer' else user.user_type
            user.save()
            
            logger.info(f"Trial activated for user: {user.id}, plan: {plan.id}")
            return True, f"Trial activated! You have {plan.trial_days} days to explore."
            
        except Exception as e:
            logger.error(f"Error activating trial: {e}")
            return False, "An error occurred while activating trial."
    
    @staticmethod
    def get_subscription_analytics(user: CustomUser) -> Dict:
        """Get subscription analytics for user"""
        try:
            subscription = user.subscription
            
            # Calculate usage statistics
            total_listings = user.properties.count()
            active_listings = user.properties.filter(is_active=True).count()
            featured_listings = user.properties.filter(is_featured=True, is_active=True).count()
            
            # Calculate monthly views and inquiries
            thirty_days_ago = timezone.now() - timedelta(days=30)
            monthly_views = sum(
                user.properties.filter(is_active=True).values_list('view_count', flat=True)
            )
            
            monthly_inquiries = sum(
                user.properties.filter(is_active=True).values_list('inquiry_count', flat=True)
            )
            
            return {
                'subscription': subscription,
                'usage': {
                    'total_listings': total_listings,
                    'active_listings': active_listings,
                    'featured_listings': featured_listings,
                    'listings_remaining': subscription.listings_remaining,
                    'featured_remaining': subscription.featured_remaining,
                    'listings_used_percentage': (
                        (active_listings / subscription.plan.max_active_listings * 100)
                        if not subscription.plan.is_unlimited else 0
                    ),
                    'featured_used_percentage': (
                        (featured_listings / subscription.plan.max_featured_listings * 100)
                        if subscription.plan.max_featured_listings > 0 else 0
                    ),
                },
                'performance': {
                    'monthly_views': monthly_views,
                    'monthly_inquiries': monthly_inquiries,
                    'conversion_rate': (
                        (monthly_inquiries / monthly_views * 100) if monthly_views > 0 else 0
                    ),
                    'average_price': user.properties.filter(
                        is_active=True
                    ).aggregate(avg_price=models.Avg('price'))['avg_price'] or 0,
                }
            }
            
        except UserSubscription.DoesNotExist:
            return {
                'subscription': None,
                'usage': {},
                'performance': {}
            }
    
    @staticmethod
    def send_subscription_reminders():
        """Send subscription renewal reminders"""
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        
        try:
            # Find subscriptions expiring in 7, 3, and 1 days
            today = timezone.now().date()
            
            for days in [7, 3, 1]:
                expiry_date = today + timedelta(days=days)
                
                subscriptions = UserSubscription.objects.filter(
                    status='active',
                    end_date__date=expiry_date,
                    auto_renew=True
                ).select_related('user', 'plan')
                
                for subscription in subscriptions:
                    # Send email reminder
                    subject = f"Your {subscription.plan.name} subscription expires in {days} day(s)"
                    
                    context = {
                        'user': subscription.user,
                        'subscription': subscription,
                        'days_remaining': days,
                        'renewal_date': subscription.end_date,
                        'plan': subscription.plan,
                        'site_name': settings.SITE_NAME,
                        'site_url': settings.SITE_URL,
                    }
                    
                    html_content = render_to_string(
                        'membership/email/renewal_reminder.html',
                        context
                    )
                    
                    email = EmailMultiAlternatives(
                        subject=subject,
                        body=html_content,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[subscription.user.email]
                    )
                    email.attach_alternative(html_content, "text/html")
                    email.send(fail_silently=True)
                    
                    logger.info(f"Sent renewal reminder to {subscription.user.email}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending subscription reminders: {e}")
            return False