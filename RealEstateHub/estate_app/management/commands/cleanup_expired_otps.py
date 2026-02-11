from django.core.management.base import BaseCommand
from django.utils import timezone
from estate_app.models import OTPVerification

class Command(BaseCommand):
    help = 'Clean up expired OTPs'
    
    def handle(self, *args, **options):
        expired_otps = OTPVerification.objects.filter(
            expires_at__lt=timezone.now()
        )
        count = expired_otps.count()
        expired_otps.delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully deleted {count} expired OTPs')
        )