"""
Tests for membership functionality, particularly the plan selection form fix.
"""
import time
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal

from estate_app.models import MembershipPlan, UserSubscription
from estate_app.membership.services import MembershipService
from estate_app.forms import MembershipPlanSelectionForm

User = get_user_model()


class MembershipTests(TestCase):
    """Test membership functionality"""

    def setUp(self):
        """Set up test data"""
        # Create test users with unique emails
        timestamp = str(int(time.time()))

        self.buyer_user = User.objects.create_user(
            email=f'frontend_buyer_{timestamp}@test.com',
            password='testpass123',
            user_type='buyer',
            first_name='John',
            last_name='Buyer'
        )

        self.seller_user = User.objects.create_user(
            email=f'frontend_seller_{timestamp}@test.com',
            password='testpass123',
            user_type='seller',
            first_name='Jane',
            last_name='Seller'
        )

        # Create membership plans
        self.basic_plan = MembershipPlan.objects.create(
            name='Basic Plan',
            slug='basic-plan',
            tier='basic',
            monthly_price=Decimal('29.99'),
            annual_price=Decimal('299.99'),
            max_active_listings=5,
            max_featured_listings=1,
            is_active=True,
            display_order=1
        )

        self.professional_plan = MembershipPlan.objects.create(
            name='Professional Plan',
            slug='professional-plan',
            tier='professional',
            monthly_price=Decimal('59.99'),
            annual_price=Decimal('599.99'),
            max_active_listings=15,
            max_featured_listings=5,
            is_active=True,
            display_order=2
        )

        self.enterprise_plan = MembershipPlan.objects.create(
            name='Enterprise Plan',
            slug='enterprise-plan',
            tier='enterprise',
            monthly_price=Decimal('99.99'),
            annual_price=Decimal('999.99'),
            max_active_listings=50,
            max_featured_listings=20,
            is_active=True,
            display_order=3
        )

        # Create subscription for seller (basic plan)
        self.subscription = UserSubscription.objects.create(
            user=self.seller_user,
            plan=self.basic_plan,
            status='active',
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=30),
            listings_used=0,
            featured_used_this_month=0
        )

    def test_membership_service_get_available_plans_returns_queryset(self):
        """Test that get_available_plans returns a QuerySet, not a list"""
        # Test for new user (no subscription)
        plans = MembershipService.get_available_plans(self.buyer_user)
        self.assertIsNotNone(plans)
        # Should be a QuerySet
        self.assertTrue(hasattr(plans, 'filter'))
        self.assertTrue(hasattr(plans, 'all'))
        # Should contain all active plans
        self.assertEqual(plans.count(), 3)

        # Test for user with subscription (should filter out lower tier plans)
        plans = MembershipService.get_available_plans(self.seller_user)
        self.assertIsNotNone(plans)
        self.assertTrue(hasattr(plans, 'filter'))
        # Should only show professional and enterprise plans (higher tiers)
        plan_ids = list(plans.values_list('id', flat=True))
        self.assertIn(self.professional_plan.id, plan_ids)
        self.assertIn(self.enterprise_plan.id, plan_ids)
        self.assertNotIn(self.basic_plan.id, plan_ids)

    def test_membership_plan_selection_form_initialization(self):
        """Test that MembershipPlanSelectionForm initializes correctly with QuerySet"""
        # Test form initialization for new user
        form = MembershipPlanSelectionForm(user=self.buyer_user)
        self.assertIsNotNone(form.fields['plan'].queryset)
        self.assertTrue(hasattr(form.fields['plan'].queryset, 'all'))
        # Should have all plans available
        self.assertEqual(form.fields['plan'].queryset.count(), 3)

        # Test form initialization for user with subscription
        form = MembershipPlanSelectionForm(user=self.seller_user)
        self.assertIsNotNone(form.fields['plan'].queryset)
        self.assertTrue(hasattr(form.fields['plan'].queryset, 'all'))
        # Should have only higher tier plans available
        self.assertEqual(form.fields['plan'].queryset.count(), 2)
        plan_ids = list(form.fields['plan'].queryset.values_list('id', flat=True))
        self.assertIn(self.professional_plan.id, plan_ids)
        self.assertIn(self.enterprise_plan.id, plan_ids)
        self.assertNotIn(self.basic_plan.id, plan_ids)

    def test_plan_selection_view_get(self):
        """Test that plan selection view loads without errors"""
        client = Client()

        # Test for unauthenticated user - should redirect to login or show plans
        response = client.get(reverse('plan_selection'))
        # Depending on your view logic, it might redirect or show plans
        self.assertIn(response.status_code, [200, 302])

        # Test for authenticated user without subscription
        client.login(email=self.buyer_user.email, password='testpass123')
        response = client.get(reverse('plan_selection'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose Your Plan')
        # Should show all plans
        self.assertContains(response, 'Basic Plan')
        self.assertContains(response, 'Professional Plan')
        self.assertContains(response, 'Enterprise Plan')

        # Test for authenticated user with subscription
        client.logout()
        client.login(email=self.seller_user.email, password='testpass123')
        response = client.get(reverse('plan_selection'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose Your Plan')
        # Should show only higher tier plans
        self.assertNotContains(response, 'Basic Plan')
        self.assertContains(response, 'Professional Plan')
        self.assertContains(response, 'Enterprise Plan')

    def test_plan_selection_form_validation(self):
        """Test form validation with valid and invalid data"""
        # Test valid form submission for new user
        form = MembershipPlanSelectionForm(
            user=self.buyer_user,
            data={'plan': self.basic_plan.id, 'duration': 'monthly'}
        )
        self.assertTrue(form.is_valid())

        # Test valid form submission for user with subscription (higher tier)
        form = MembershipPlanSelectionForm(
            user=self.seller_user,
            data={'plan': self.professional_plan.id, 'duration': 'monthly'}
        )
        self.assertTrue(form.is_valid())

        # Test invalid form submission (lower tier for user with subscription)
        form = MembershipPlanSelectionForm(
            user=self.seller_user,
            data={'plan': self.basic_plan.id, 'duration': 'monthly'}
        )
        self.assertFalse(form.is_valid())
        self.assertIn('plan', form.errors)

    def test_membership_service_user_current_plan(self):
        """Test getting user's current plan"""
        # Test user with active subscription
        current_plan = MembershipService.get_user_current_plan(self.seller_user)
        self.assertEqual(current_plan, self.basic_plan)

        # Test user without subscription
        current_plan = MembershipService.get_user_current_plan(self.buyer_user)
        self.assertIsNone(current_plan)

    def test_membership_service_can_user_upgrade(self):
        """Test upgrade eligibility checking"""
        # Test upgrade from basic to professional
        can_upgrade, message = MembershipService.can_user_upgrade(self.seller_user, self.professional_plan)
        self.assertTrue(can_upgrade)
        self.assertEqual(message, "")

        # Test upgrade from basic to enterprise
        can_upgrade, message = MembershipService.can_user_upgrade(self.seller_user, self.enterprise_plan)
        self.assertTrue(can_upgrade)
        self.assertEqual(message, "")

        # Test downgrade attempt (should fail)
        can_upgrade, message = MembershipService.can_user_upgrade(self.seller_user, self.basic_plan)
        self.assertFalse(can_upgrade)
        self.assertIn("higher tier plan", message)

        # Test same plan (should fail)
        can_upgrade, message = MembershipService.can_user_upgrade(self.seller_user, self.basic_plan)
        self.assertFalse(can_upgrade)
        self.assertIn("already on this plan", message)

    def test_plan_selection_view_post_valid(self):
        """Test valid form submission to plan selection view"""
        client = Client()
        client.login(email=self.buyer_user.email, password='testpass123')

        response = client.post(
            reverse('plan_selection'),
            {'plan': self.basic_plan.id, 'duration': 'monthly'}
        )
        # Should redirect to checkout
        self.assertEqual(response.status_code, 302)
        self.assertIn('checkout', response.url)

    def test_plan_selection_view_post_invalid(self):
        """Test invalid form submission to plan selection view"""
        client = Client()
        client.login(email=self.seller_user.email, password='testpass123')

        # Try to select lower tier plan (should fail)
        response = client.post(
            reverse('plan_selection'),
            {'plan': self.basic_plan.id, 'duration': 'monthly'}
        )
        # Should stay on same page with errors
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select Your Plan')
        self.assertContains(response, 'error')  # Should contain error messages
