from django.core.management.base import BaseCommand
from django.utils import timezone
from estate_app.models import MembershipPlan

class Command(BaseCommand):
    help = 'Setup default membership plans'

    def handle(self, *args, **kwargs):
        # Essential Plan (Free)
        essential_plan, created = MembershipPlan.objects.get_or_create(
            slug='essential',
            defaults={
                'name': 'Essential',
                'description': 'Perfect for new sellers with basic needs',
                'plan_type': 'free',
                'price': 0,
                'max_listings': 5,
                'max_featured': 2,
                'max_active_listings': 5,
                'show_contact_details': False,
                'whatsapp_notifications': False,
                'sms_notifications': False,
                'priority_support': False,
                'dedicated_manager': False,
                'analytics_dashboard': False,
                'is_active': True,
                'is_popular': False,
                'is_unlimited': False,
                'display_order': 1,
            }
        )

        # Professional Plan (Most Popular)
        professional_plan, created = MembershipPlan.objects.get_or_create(
            slug='professional',
            defaults={
                'name': 'Professional',
                'description': 'Most popular choice for serious sellers',
                'plan_type': 'professional',
                'price': 2499,
                'max_listings': 15,
                'max_featured': 5,
                'max_active_listings': 15,
                'show_contact_details': True,
                'whatsapp_notifications': True,
                'sms_notifications': False,
                'priority_support': True,
                'dedicated_manager': False,
                'analytics_dashboard': True,
                'is_active': True,
                'is_popular': True,
                'is_unlimited': False,
                'display_order': 2,
            }
        )

        # Enterprise Plan
        enterprise_plan, created = MembershipPlan.objects.get_or_create(
            slug='enterprise',
            defaults={
                'name': 'Enterprise',
                'description': 'For brokers and large agencies',
                'plan_type': 'enterprise',
                'price': 4999,
                'max_listings': 999,
                'max_featured': 15,
                'max_active_listings': 50,
                'show_contact_details': True,
                'whatsapp_notifications': True,
                'sms_notifications': True,
                'priority_support': True,
                'dedicated_manager': True,
                'analytics_dashboard': True,
                'is_active': True,
                'is_popular': False,
                'is_unlimited': True,
                'display_order': 3,
            }
        )

        self.stdout.write(
            self.style.SUCCESS('Successfully setup membership plans:')
        )
        self.stdout.write(
            f'  - {essential_plan.name}: ₹{essential_plan.price}/month'
        )
        self.stdout.write(
            f'  - {professional_plan.name}: ₹{professional_plan.price}/month'
        )
        self.stdout.write(
            f'  - {enterprise_plan.name}: ₹{enterprise_plan.price}/month'
        )