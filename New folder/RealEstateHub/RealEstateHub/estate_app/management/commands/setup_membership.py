"""
Setup initial membership plans and configurations
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from estate_app.models import MembershipPlan, CreditPackage
from estate_app.membership.services import RazorpayService


class Command(BaseCommand):
    help = 'Setup initial membership plans and credit packages'
    
    def handle(self, *args, **options):
        self.stdout.write('Setting up membership system...')
        
        # Create or update membership plans
        plans = [
            {
                'name': 'Basic',
                'slug': 'basic',
                'tier': 'basic',
                'description': 'Perfect for individual property owners',
                'monthly_price': 0,
                'annual_price': 0,
                'max_active_listings': 1,
                'max_featured_listings': 0,
                'max_images_per_listing': 5,
                'has_priority_ranking': False,
                'has_advanced_analytics': False,
                'has_dedicated_support': False,
                'can_use_virtual_tour': False,
                'can_use_video': False,
                'has_agency_profile': False,
                'has_bulk_upload': False,
                'badge_text': None,
                'display_order': 1,
                'is_popular': False,
                'is_active': True,
                'has_trial': False,
                'trial_days': 0,
            },
            {
                'name': 'Professional',
                'slug': 'professional',
                'tier': 'professional',
                'description': 'For real estate agents and small agencies',
                'monthly_price': 299,
                'annual_price': 299 * 12 * 0.8,  # 20% discount
                'max_active_listings': 10,
                'max_featured_listings': 2,
                'max_images_per_listing': 10,
                'has_priority_ranking': True,
                'has_advanced_analytics': True,
                'has_dedicated_support': False,
                'can_use_virtual_tour': True,
                'can_use_video': True,
                'has_agency_profile': True,
                'has_bulk_upload': False,
                'badge_text': 'Verified Agent',
                'badge_color': 'success',
                'display_order': 2,
                'is_popular': True,
                'is_active': True,
                'has_trial': True,
                'trial_days': 14,
            },
            {
                'name': 'Enterprise',
                'slug': 'enterprise',
                'tier': 'enterprise',
                'description': 'For large agencies and property developers',
                'monthly_price': 999,
                'annual_price': 999 * 12 * 0.75,  # 25% discount
                'max_active_listings': 0,  # Unlimited
                'max_featured_listings': 10,
                'max_images_per_listing': 15,
                'has_priority_ranking': True,
                'has_advanced_analytics': True,
                'has_dedicated_support': True,
                'can_use_virtual_tour': True,
                'can_use_video': True,
                'has_agency_profile': True,
                'has_bulk_upload': True,
                'badge_text': 'Premium Partner',
                'badge_color': 'warning',
                'display_order': 3,
                'is_popular': False,
                'is_active': True,
                'has_trial': True,
                'trial_days': 14,
            }
        ]
        
        for plan_data in plans:
            plan, created = MembershipPlan.objects.update_or_create(
                slug=plan_data['slug'],
                defaults=plan_data
            )
            
            if created:
                self.stdout.write(f"Created plan: {plan.name}")
            else:
                self.stdout.write(f"Updated plan: {plan.name}")
            
            # Sync with Razorpay if live mode
            from django.conf import settings
            if settings.RAZORPAY_LIVE_MODE:
                razorpay_service = RazorpayService()
                razorpay_service.sync_plan_to_razorpay(plan)
                self.stdout.write(f"  Synced with Razorpay")
        
        # Create credit packages
        credit_packages = [
            {
                'name': 'Starter Credits',
                'slug': 'starter-credits',
                'featured_listing_credits': 5,
                'bump_up_credits': 3,
                'highlight_credits': 2,
                'price': 499,
                'original_price': 699,
                'validity_days': 180,
                'is_active': True,
            },
            {
                'name': 'Professional Credits',
                'slug': 'professional-credits',
                'featured_listing_credits': 15,
                'bump_up_credits': 10,
                'highlight_credits': 5,
                'price': 1299,
                'original_price': 1999,
                'validity_days': 365,
                'is_active': True,
            },
            {
                'name': 'Agency Credits',
                'slug': 'agency-credits',
                'featured_listing_credits': 50,
                'bump_up_credits': 25,
                'highlight_credits': 15,
                'price': 3999,
                'original_price': 5999,
                'validity_days': 365,
                'is_active': True,
            }
        ]
        
        for package_data in credit_packages:
            package, created = CreditPackage.objects.update_or_create(
                slug=package_data['slug'],
                defaults=package_data
            )
            
            if created:
                self.stdout.write(f"Created credit package: {package.name}")
            else:
                self.stdout.write(f"Updated credit package: {package.name}")
        
        self.stdout.write(self.style.SUCCESS('Membership setup completed successfully!'))