"""
Advanced membership views with Razorpay integration, analytics, and management
"""
import json
import logging
from typing import Dict, List, Optional
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.db import transaction
from django.http import (
    HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse,
    HttpResponseBadRequest, HttpResponseForbidden, HttpResponseServerError
)
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    TemplateView, ListView, DetailView, FormView, UpdateView
)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.cache import cache
from django.core.paginator import Paginator
from django.conf import settings

from .models import CustomUser, Property
from .models import (
    MembershipPlan, UserSubscription, PaymentTransaction,
    CreditPackage, UserCredit
)
from .forms import (
    MembershipPlanSelectionForm, SubscriptionUpgradeForm,
    CreditPurchaseForm, SubscriptionCancellationForm,
    BillingInformationForm, PaymentMethodForm
)
from estate_app.membership.services import (
    RazorpayService, MembershipService
)

logger = logging.getLogger(__name__)


# ===========================================================================
#  Mixins and Decorators
# ===========================================================================

class SellerRequiredMixin(LoginRequiredMixin):
    """Ensure user is a seller"""
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type not in ['seller', 'agent', 'admin']:
            messages.error(
                request, 
                'This feature is available only for sellers and agents.'
            )
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)


class SubscriptionRequiredMixin:
    """Ensure user has active subscription"""
    
    def dispatch(self, request, *args, **kwargs):
        # Allow admins to bypass
        if request.user.is_staff:
            return super().dispatch(request, *args, **kwargs)
        
        # Check if user has active subscription
        try:
            subscription = request.user.subscription
            if not subscription.is_active:
                messages.error(
                    request,
                    'You need an active subscription to access this feature. '
                    'Please subscribe to a plan.'
                )
                return redirect('pricing')
        except UserSubscription.DoesNotExist:
            messages.error(
                request,
                'You need a subscription to access this feature. '
                'Please subscribe to a plan.'
            )
            return redirect('pricing')
        
        return super().dispatch(request, *args, **kwargs)


class MembershipFeatureMixin:
    """Check specific membership feature access"""
    
    feature_name = None
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_staff:
            return super().dispatch(request, *args, **kwargs)
        
        try:
            subscription = request.user.subscription
            
            # Check feature access
            if self.feature_name == 'list_property':
                if not subscription.can_list_property:
                    messages.error(
                        request,
                        f'You have reached your listing limit ({subscription.listings_used}/'
                        f'{subscription.plan.max_active_listings}). '
                        'Please upgrade your plan.'
                    )
                    return redirect('membership_upgrade')
            
            elif self.feature_name == 'feature_property':
                if not subscription.can_feature_property:
                    messages.error(
                        request,
                        f'You have used all your featured listings for this month '
                        f'({subscription.featured_used_this_month}/'
                        f'{subscription.plan.max_featured_listings}). '
                        'Please upgrade your plan or wait until next month.'
                    )
                    return redirect('membership_upgrade')
        
        except UserSubscription.DoesNotExist:
            messages.error(request, 'You need a subscription to access this feature.')
            return redirect('membership_pricing')
        
        return super().dispatch(request, *args, **kwargs)


# ===========================================================================
#  Membership Views
# ===========================================================================

class MembershipPricingView(TemplateView):
    """Pricing page with plan comparison"""
    template_name = 'membership/pricing.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get available plans
        plans = MembershipService.get_available_plans(self.request.user)
        
        # Group plans by tier
        basic_plans = [p for p in plans if p.tier == 'basic']
        professional_plans = [p for p in plans if p.tier == 'professional']
        enterprise_plans = [p for p in plans if p.tier == 'enterprise']
        
        context.update({
            'plans': plans,
            'basic_plans': basic_plans,
            'professional_plans': professional_plans,
            'enterprise_plans': enterprise_plans,
            'current_plan': MembershipService.get_user_current_plan(self.request.user),
            'features_matrix': self._get_features_matrix(plans),
        })
        
        return context
    
    def _get_features_matrix(self, plans):
        """Create features comparison matrix"""
        features = [
            ('Active Listings', 'max_active_listings'),
            ('Featured Listings/Month', 'max_featured_listings'),
            ('Images per Listing', 'max_images_per_listing'),
            ('Priority Ranking', 'has_priority_ranking'),
            ('Advanced Analytics', 'has_advanced_analytics'),
            ('Dedicated Support', 'has_dedicated_support'),
            ('Virtual Tour', 'can_use_virtual_tour'),
            ('Property Videos', 'can_use_video'),
            ('Agency Profile', 'has_agency_profile'),
            ('Bulk Upload', 'has_bulk_upload'),
            ('Verification Badge', 'badge_text'),
        ]
        
        matrix = []
        for feature_name, field_name in features:
            row = {'name': feature_name}
            for plan in plans:
                value = getattr(plan, field_name, None)
                if field_name.endswith('_listings'):
                    row[plan.id] = 'Unlimited' if value == 0 else value
                elif field_name in ['has_priority_ranking', 'has_advanced_analytics',
                                  'has_dedicated_support', 'can_use_virtual_tour',
                                  'can_use_video', 'has_agency_profile', 'has_bulk_upload']:
                    row[plan.id] = '✓' if value else '✗'
                elif field_name == 'badge_text':
                    row[plan.id] = value if value else '-'
                else:
                    row[plan.id] = value
            matrix.append(row)
        
        return matrix

# SellerRequiredMixin, LoginRequiredMixin,
class PlanSelectionView( FormView):
    """Plan selection and checkout view"""
    template_name = 'membership/plan_selection.html'
    form_class = MembershipPlanSelectionForm
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get available plans
        plans = MembershipService.get_available_plans(self.request.user)
        context['plans'] = plans

        # Get selected plan from URL
        plan_slug = self.request.GET.get('plan')
        if plan_slug:
            try:
                plan = MembershipPlan.objects.get(slug=plan_slug, is_active=True)
                context['selected_plan'] = plan

                # Set initial form data
                if 'form' not in context or not context['form'].initial:
                    context['form'].initial = {
                        'plan': plan.id,
                        'duration': 'monthly'
                    }
            except MembershipPlan.DoesNotExist:
                pass

        # Add Razorpay key
        context['razorpay_key_id'] = settings.RAZORPAY_KEY_ID

        return context
    
    def form_valid(self, form):
        """Process plan selection"""
        plan = form.cleaned_data['plan']
        duration = form.cleaned_data['duration']
        
        # Create Razorpay subscription
        razorpay_service = RazorpayService()
        
        try:
            # Check if user wants trial
            trial_days = 0
            if plan.has_trial and not self.request.user.subscription:
                trial_days = plan.trial_days
            
            # Create subscription
            subscription, subscription_id = razorpay_service.create_subscription(
                user=self.request.user,
                plan=plan,
                duration=duration,
                trial_days=trial_days
            )
            
            # Store subscription data in session for checkout
            self.request.session['subscription_data'] = {
                'subscription_id': subscription_id,
                'plan_id': plan.id,
                'duration': duration,
                'amount': float(subscription.get('amount', 0) / 100),
                'razorpay_order_id': subscription.get('id'),
            }
            
            # Redirect to payment page
            return redirect('membership_checkout')
            
        except Exception as e:
            logger.error(f"Error creating subscription: {e}", exc_info=True)
            messages.error(
                self.request,
                'An error occurred while creating your subscription. '
                'Please try again or contact support.'
            )
            return self.form_invalid(form)

# SellerRequiredMixin, LoginRequiredMixin,
class CheckoutView( TemplateView):
    """Checkout and payment view"""
    template_name = 'membership/checkout.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Check if subscription data exists in session
        if 'subscription_data' not in request.session:
            messages.warning(request, 'Please select a plan first.')
            return redirect('membership_pricing')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        subscription_data = self.request.session['subscription_data']
        
        # Get plan details
        try:
            plan = MembershipPlan.objects.get(id=subscription_data['plan_id'])
        except MembershipPlan.DoesNotExist:
            messages.error(self.request, 'Invalid plan selected.')
            return redirect('membership_pricing')
        
        # Get subscription details from Razorpay
        razorpay_service = RazorpayService()
        subscription = razorpay_service.fetch_subscription(
            subscription_data['subscription_id']
        )
        
        if not subscription:
            messages.error(self.request, 'Subscription not found.')
            return redirect('membership_pricing')
        
        context.update({
            'plan': plan,
            'subscription': subscription,
            'subscription_data': subscription_data,
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'order_id': subscription.get('id'),
            'amount': subscription_data['amount'],
            'currency': 'INR',
            'user': self.request.user,
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle payment verification"""
        razorpay_service = RazorpayService()
        
        try:
            # Get payment data
            razorpay_payment_id = request.POST.get('razorpay_payment_id')
            razorpay_order_id = request.POST.get('razorpay_order_id')
            razorpay_signature = request.POST.get('razorpay_signature')
            
            # Verify payment signature
            is_valid = razorpay_service.verify_payment_signature(
                razorpay_order_id,
                razorpay_payment_id,
                razorpay_signature
            )
            
            if not is_valid:
                messages.error(request, 'Payment verification failed.')
                return redirect('membership_checkout')
            
            # Get subscription data from session
            subscription_data = request.session.get('subscription_data', {})
            
            # Update subscription in database
            subscription = UserSubscription.objects.get(
                razorpay_subscription_id=subscription_data.get('subscription_id')
            )
            
            subscription.status = 'active'
            subscription.razorpay_payment_id = razorpay_payment_id
            subscription.razorpay_signature = razorpay_signature
            subscription.last_payment_date = timezone.now()
            subscription.amount_paid = Decimal(subscription_data.get('amount', 0))
            subscription.save()
            
            # Update payment transaction
            transaction = PaymentTransaction.objects.get(
                razorpay_order_id=razorpay_order_id
            )
            transaction.mark_as_paid(razorpay_payment_id, razorpay_signature)
            
            # Update user type to seller if not already
            if request.user.user_type == 'buyer':
                request.user.user_type = 'seller'
                request.user.save()
            
            # Clear session data
            if 'subscription_data' in request.session:
                del request.session['subscription_data']
            
            # Send confirmation email
            self._send_confirmation_email(request.user, subscription)
            
            messages.success(
                request,
                f'Welcome to {plan.name}! Your subscription is now active. '
                f'You can now start listing properties.'
            )
            
            return redirect('subscription_dashboard')
            
        except Exception as e:
            logger.error(f"Error processing payment: {e}", exc_info=True)
            messages.error(
                request,
                'An error occurred while processing your payment. '
                'Please contact support if the amount was deducted.'
            )
            return redirect('membership_checkout')
    
    def _send_confirmation_email(self, user, subscription):
        """Send subscription confirmation email"""
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        
        try:
            subject = f"Welcome to {subscription.plan.name} - {settings.SITE_NAME}"
            
            context = {
                'user': user,
                'subscription': subscription,
                'plan': subscription.plan,
                'site_name': settings.SITE_NAME,
                'site_url': settings.SITE_URL,
                'start_date': subscription.start_date,
                'end_date': subscription.end_date,
            }
            
            html_content = render_to_string(
                'membership/email/subscription_confirmation.html',
                context
            )
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=html_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
                cc=[settings.ADMIN_EMAIL] if hasattr(settings, 'ADMIN_EMAIL') else None
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=True)
            
            logger.info(f"Sent subscription confirmation to {user.email}")
            
        except Exception as e:
            logger.error(f"Error sending confirmation email: {e}")

# SellerRequiredMixin, LoginRequiredMixin,
class SubscriptionDashboardView( TemplateView):
    """User's subscription dashboard"""
    template_name = 'membership/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        try:
            subscription = user.subscription
        except UserSubscription.DoesNotExist:
            subscription = None
        
        # Get subscription analytics
        analytics = MembershipService.get_subscription_analytics(user)
        
        # Get recent transactions
        recent_transactions = PaymentTransaction.objects.filter(
            user=user
        ).order_by('-created_at')[:10]
        
        # Get credit balance
        try:
            credit_balance = user.credits
        except UserCredit.DoesNotExist:
            credit_balance = None
        
        # Get user's properties
        user_properties = Property.objects.filter(owner=user).order_by('-created_at')[:5]
        
        context.update({
            'subscription': subscription,
            'analytics': analytics,
            'recent_transactions': recent_transactions,
            'credit_balance': credit_balance,
            'user_properties': user_properties,
            'current_plan': subscription.plan if subscription else None,
            'upgrade_plans': MembershipService.get_available_plans(user),
        })
        
        return context

# SellerRequiredMixin, LoginRequiredMixin,
class SubscriptionUpgradeView( FormView):
    """Upgrade subscription view"""
    template_name = 'membership/upgrade.html'
    form_class = SubscriptionUpgradeForm
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get current subscription
        try:
            current_subscription = self.request.user.subscription
            context['current_subscription'] = current_subscription
        except UserSubscription.DoesNotExist:
            pass
        
        # Get available upgrade plans
        context['upgrade_plans'] = MembershipService.get_available_plans(self.request.user)
        
        return context
    
    def form_valid(self, form):
        """Process upgrade"""
        user = self.request.user
        new_plan = form.cleaned_data['plan']
        duration = form.cleaned_data['duration']
        prorate = form.cleaned_data.get('prorate', True)
        
        try:
            current_subscription = user.subscription
            
            # Calculate prorated amount
            prorated_amount = 0
            if prorate:
                prorated_amount = form.calculate_prorated_amount(current_subscription)
            
            # Create Razorpay order for upgrade
            razorpay_service = RazorpayService()
            
            # Calculate amount to pay
            new_amount = new_plan.get_price_for_duration(duration)
            amount_to_pay = max(0, new_amount - prorated_amount)
            
            if amount_to_pay > 0:
                # Create order for immediate payment
                order = razorpay_service.create_order(
                    amount=Decimal(amount_to_pay),
                    notes={
                        'user_id': str(user.id),
                        'plan_id': str(new_plan.id),
                        'type': 'upgrade',
                        'current_plan_id': str(current_subscription.plan.id),
                        'prorated_amount': str(prorated_amount),
                    }
                )
                
                # Store upgrade data in session
                self.request.session['upgrade_data'] = {
                    'order_id': order['id'],
                    'plan_id': new_plan.id,
                    'duration': duration,
                    'amount': float(amount_to_pay),
                    'prorated_amount': float(prorated_amount),
                }
                
                # Redirect to payment page
                return redirect('membership_upgrade_payment')
            
            else:
                # No payment needed, upgrade immediately
                current_subscription.upgrade_plan(new_plan, duration)
                
                messages.success(
                    self.request,
                    f'Successfully upgraded to {new_plan.name}! '
                    f'Your prorated credit covered the full amount.'
                )
                
                return redirect('subscription_dashboard')
            
        except Exception as e:
            logger.error(f"Error processing upgrade: {e}", exc_info=True)
            messages.error(
                self.request,
                'An error occurred while processing your upgrade. '
                'Please try again or contact support.'
            )
            return self.form_invalid(form)


class UpgradePaymentView( TemplateView):
    """Payment view for upgrades"""
    template_name = 'membership/upgrade_payment.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Check if upgrade data exists in session
        if 'upgrade_data' not in request.session:
            messages.warning(request, 'Please select an upgrade plan first.')
            return redirect('upgrade')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        upgrade_data = self.request.session['upgrade_data']
        
        try:
            plan = MembershipPlan.objects.get(id=upgrade_data['plan_id'])
        except MembershipPlan.DoesNotExist:
            messages.error(self.request, 'Invalid plan selected.')
            return redirect('membership_upgrade')
        
        context.update({
            'plan': plan,
            'upgrade_data': upgrade_data,
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'order_id': upgrade_data['order_id'],
            'amount': upgrade_data['amount'],
            'currency': 'INR',
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle upgrade payment verification"""
        razorpay_service = RazorpayService()
        
        try:
            # Get payment data
            razorpay_payment_id = request.POST.get('razorpay_payment_id')
            razorpay_order_id = request.POST.get('razorpay_order_id')
            razorpay_signature = request.POST.get('razorpay_signature')
            
            # Verify payment signature
            is_valid = razorpay_service.verify_payment_signature(
                razorpay_order_id,
                razorpay_payment_id,
                razorpay_signature
            )
            
            if not is_valid:
                messages.error(request, 'Payment verification failed.')
                return redirect('membership_upgrade_payment')
            
            # Get upgrade data from session
            upgrade_data = request.session.get('upgrade_data', {})
            
            # Update subscription
            subscription = request.user.subscription
            plan = MembershipPlan.objects.get(id=upgrade_data['plan_id'])
            
            subscription.upgrade_plan(plan, upgrade_data['duration'])
            
            # Create payment transaction
            PaymentTransaction.objects.create(
                user=request.user,
                subscription=subscription,
                plan=plan,
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                razorpay_signature=razorpay_signature,
                amount=Decimal(upgrade_data['amount']),
                status='captured',
                paid_at=timezone.now(),
                description=f"Upgrade to {plan.name} ({upgrade_data['duration']})"
            )
            
            # Clear session data
            if 'upgrade_data' in request.session:
                del request.session['upgrade_data']
            
            messages.success(
                request,
                f'Successfully upgraded to {plan.name}! '
                f'Your new features are now active.'
            )
            
            return redirect('subscription_dashboard')
            
        except Exception as e:
            logger.error(f"Error processing upgrade payment: {e}", exc_info=True)
            messages.error(
                request,
                'An error occurred while processing your payment. '
                'Please contact support if the amount was deducted.'
            )
            return redirect('membership_upgrade_payment')

# SellerRequiredMixin, LoginRequiredMixin,
class SubscriptionCancelView( FormView):
    """Cancel subscription view"""
    template_name = 'membership/cancel.html'
    form_class = SubscriptionCancellationForm
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['subscription'] = self.request.user.subscription
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['subscription'] = self.request.user.subscription
        return context
    
    def form_valid(self, form):
        """Process cancellation"""
        subscription = self.request.user.subscription
        
        try:
            # Get cancellation reason
            reason = form.get_cancellation_reason()
            cancel_at_period_end = form.cleaned_data.get('cancel_at_period_end', True)
            
            # Add feedback to notes
            feedback = form.cleaned_data.get('feedback', '')
            if feedback:
                subscription.notes = f"Feedback: {feedback}\n{subscription.notes or ''}"
            
            # Cancel subscription
            subscription.cancel(reason, cancel_at_period_end)
            
            # Send cancellation confirmation
            self._send_cancellation_email(self.request.user, subscription, reason)
            
            messages.success(
                self.request,
                'Your subscription has been cancelled. '
                'You will have access until the end of your billing period.'
            )
            
            return redirect('subscription_dashboard')
            
        except Exception as e:
            logger.error(f"Error cancelling subscription: {e}", exc_info=True)
            messages.error(
                self.request,
                'An error occurred while cancelling your subscription. '
                'Please contact support.'
            )
            return self.form_invalid(form)
    
    def _send_cancellation_email(self, user, subscription, reason):
        """Send cancellation confirmation email"""
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        
        try:
            subject = f"Subscription Cancelled - {settings.SITE_NAME}"
            
            context = {
                'user': user,
                'subscription': subscription,
                'reason': reason,
                'site_name': settings.SITE_NAME,
                'cancellation_date': timezone.now(),
                'access_until': subscription.end_date if subscription.end_date else 'Immediately',
            }
            
            html_content = render_to_string(
                'membership/email/cancellation_confirmation.html',
                context
            )
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=html_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
                cc=[settings.ADMIN_EMAIL] if hasattr(settings, 'ADMIN_EMAIL') else None
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=True)
            
            logger.info(f"Sent cancellation confirmation to {user.email}")
            
        except Exception as e:
            logger.error(f"Error sending cancellation email: {e}")


class BillingHistoryView(LoginRequiredMixin, ListView):
    """Billing history view"""
    template_name = 'membership/billing_history.html'
    context_object_name = 'transactions'
    paginate_by = 20
    
    def get_queryset(self):
        return PaymentTransaction.objects.filter(
            user=self.request.user
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add summary statistics
        transactions = self.get_queryset()
        
        total_paid = sum(t.amount for t in transactions if t.is_successful)
        total_refunded = sum(t.amount_refunded for t in transactions)
        
        context.update({
            'total_paid': total_paid,
            'total_refunded': total_refunded,
            'net_paid': total_paid - total_refunded,
            'subscription': getattr(self.request.user, 'subscription', None),
        })
        
        return context

# SellerRequiredMixin, LoginRequiredMixin,
class CreditPurchaseView( FormView):
    """Purchase credits view"""
    template_name = 'membership/credit_purchase.html'
    form_class = CreditPurchaseForm
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['credit_packages'] = CreditPackage.objects.filter(is_active=True)
        return context
    
    def form_valid(self, form):
        """Process credit purchase"""
        package = form.cleaned_data['package']
        
        # Create Razorpay order
        razorpay_service = RazorpayService()
        
        try:
            order = razorpay_service.create_order(
                amount=package.price,
                notes={
                    'user_id': str(self.request.user.id),
                    'package_id': str(package.id),
                    'type': 'credit_purchase',
                    'featured_credits': str(package.featured_listing_credits),
                    'bump_up_credits': str(package.bump_up_credits),
                    'highlight_credits': str(package.highlight_credits),
                }
            )
            
            # Store credit purchase data in session
            self.request.session['credit_purchase_data'] = {
                'order_id': order['id'],
                'package_id': package.id,
                'amount': float(package.price),
            }
            
            return redirect('credit_purchase_payment')
            
        except Exception as e:
            logger.error(f"Error creating credit purchase order: {e}")
            messages.error(
                self.request,
                'An error occurred while processing your purchase. '
                'Please try again.'
            )
            return self.form_invalid(form)

# SellerRequiredMixin, LoginRequiredMixin,
class CreditPurchasePaymentView( TemplateView):
    """Payment view for credit purchase"""
    template_name = 'membership/credit_payment.html'
    
    def dispatch(self, request, *args, **kwargs):
        if 'credit_purchase_data' not in request.session:
            messages.warning(request, 'Please select a credit package first.')
            return redirect('credit_purchase')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        purchase_data = self.request.session['credit_purchase_data']
        
        try:
            package = CreditPackage.objects.get(id=purchase_data['package_id'])
        except CreditPackage.DoesNotExist:
            messages.error(self.request, 'Invalid package selected.')
            return redirect('credit_purchase')
        
        context.update({
            'package': package,
            'purchase_data': purchase_data,
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'order_id': purchase_data['order_id'],
            'amount': purchase_data['amount'],
            'currency': 'INR',
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle credit purchase payment"""
        razorpay_service = RazorpayService()
        
        try:
            # Get payment data
            razorpay_payment_id = request.POST.get('razorpay_payment_id')
            razorpay_order_id = request.POST.get('razorpay_order_id')
            razorpay_signature = request.POST.get('razorpay_signature')
            
            # Verify payment signature
            is_valid = razorpay_service.verify_payment_signature(
                razorpay_order_id,
                razorpay_payment_id,
                razorpay_signature
            )
            
            if not is_valid:
                messages.error(request, 'Payment verification failed.')
                return redirect('credit_purchase_payment')
            
            # Get purchase data from session
            purchase_data = request.session.get('credit_purchase_data', {})
            
            # Get package
            package = CreditPackage.objects.get(id=purchase_data['package_id'])
            
            # Update user credits
            user_credit, created = UserCredit.objects.get_or_create(
                user=request.user,
                defaults={
                    'featured_listing_credits': 0,
                    'bump_up_credits': 0,
                    'highlight_credits': 0,
                }
            )
            
            user_credit.add_credits(package)
            
            # Create payment transaction
            PaymentTransaction.objects.create(
                user=request.user,
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                razorpay_signature=razorpay_signature,
                amount=Decimal(purchase_data['amount']),
                status='captured',
                paid_at=timezone.now(),
                description=f"Credit purchase: {package.name}"
            )
            
            # Clear session data
            if 'credit_purchase_data' in request.session:
                del request.session['credit_purchase_data']
            
            messages.success(
                request,
                f'Successfully purchased {package.name}! '
                f'Your credits have been added to your account.'
            )
            
            return redirect('subscription_dashboard')
            
        except Exception as e:
            logger.error(f"Error processing credit purchase: {e}", exc_info=True)
            messages.error(
                request,
                'An error occurred while processing your purchase. '
                'Please contact support if the amount was deducted.'
            )
            return redirect('credit_purchase_payment')


# ===========================================================================
#  Webhook Handler
# ===========================================================================

@csrf_exempt
@require_POST
def razorpay_webhook_view(request):
    """Handle Razorpay webhook events"""
    razorpay_service = RazorpayService()
    
    try:
        # Get webhook signature
        signature = request.headers.get('X-Razorpay-Signature', '')
        
        # Verify webhook signature
        if not razorpay_service.verify_webhook_signature(request.body, signature):
            return HttpResponseBadRequest('Invalid signature')
        
        # Parse webhook data
        event = json.loads(request.body.decode('utf-8'))
        
        # Process webhook event
        success = razorpay_service.process_webhook(event)
        
        if success:
            return HttpResponse('Webhook processed successfully')
        else:
            return HttpResponseBadRequest('Failed to process webhook')
        
    except json.JSONDecodeError:
        logger.error('Invalid JSON in webhook payload')
        return HttpResponseBadRequest('Invalid JSON')
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return HttpResponseServerError('Internal server error')


# ===========================================================================
#  AJAX Views
# ===========================================================================

@login_required
@require_GET
def get_subscription_details_view(request):
    """Get subscription details (AJAX)"""
    try:
        subscription = request.user.subscription
        plan = subscription.plan
        
        data = {
            'plan_name': plan.name,
            'tier': plan.tier,
            'status': subscription.status,
            'is_active': subscription.is_active,
            'days_remaining': subscription.days_remaining,
            'listings_used': subscription.listings_used,
            'listings_limit': plan.max_active_listings,
            'featured_used': subscription.featured_used_this_month,
            'featured_limit': plan.max_featured_listings,
            'next_payment_date': (
                subscription.next_payment_date.isoformat()
                if subscription.next_payment_date else None
            ),
            'end_date': (
                subscription.end_date.isoformat()
                if subscription.end_date else None
            ),
        }
        
        return JsonResponse({'success': True, 'data': data})
        
    except UserSubscription.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'No subscription found'})
    except Exception as e:
        logger.error(f"Error getting subscription details: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_GET
def check_listing_limit_view(request):
    """Check if user can list more properties (AJAX)"""
    try:
        subscription = request.user.subscription
        
        can_list = subscription.can_list_property
        listings_remaining = subscription.listings_remaining
        
        return JsonResponse({
            'success': True,
            'can_list': can_list,
            'listings_remaining': listings_remaining,
            'listings_used': subscription.listings_used,
            'listings_limit': subscription.plan.max_active_listings,
        })
        
    except UserSubscription.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'No active subscription',
            'can_list': False,
        })
    except Exception as e:
        logger.error(f"Error checking listing limit: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def activate_trial_view(request, plan_slug):
    """Activate trial for a plan (AJAX)"""
    try:
        plan = get_object_or_404(MembershipPlan, slug=plan_slug, is_active=True)
        
        success, message = MembershipService.activate_trial(request.user, plan)
        
        if success:
            return JsonResponse({'success': True, 'message': message})
        else:
            return JsonResponse({'success': False, 'error': message})
        
    except Exception as e:
        logger.error(f"Error activating trial: {e}")
        return JsonResponse({'success': False, 'error': str(e)})