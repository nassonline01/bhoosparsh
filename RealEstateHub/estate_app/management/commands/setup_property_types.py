# management/commands/setup_property_types.py
from django.core.management.base import BaseCommand
from estate_app.models import PropertyCategory, PropertyType
from django.utils.text import slugify

class Command(BaseCommand):
    help = 'Setup default property types for each category'
    
    # Define property types for each category
    PROPERTY_TYPES = {
        'residential': [
            'Apartment',
            'Independent House/Villa',
            'Builder Floor',
            'Farm House',
            'Studio Apartment',
            'Service Apartment',
            'Penthouse',
            'Duplex',
            'Triplex',
            'Row House',
            'Bungalow',
            'Villa',
            'Housing Society',
            'Residential Land',
            '1 RK/1 BHK',
            '2 BHK',
            '3 BHK',
            '4 BHK',
            '5 BHK',
            '5+ BHK',
            'Other'
        ],
        'commercial': [
            'Office Space',
            'Shop/Retail',
            'Showroom',
            'Commercial Land',
            'Warehouse/Godown',
            'Industrial Building',
            'Industrial Shed',
            'Co-working Space',
            'Business Centre',
            'Hotel/Resort',
            'Restaurant/Cafe',
            'Fuel Station',
            'Educational Institute',
            'Hospital/Clinic',
            'Banquet Hall',
            'Cold Storage',
            'Factory',
            'Mining Land',
            'Agricultural Land',
            'Other'
        ],
        'industrial': [
            'Manufacturing Unit',
            'Warehouse',
            'Factory',
            'Industrial Shed',
            'Cold Storage',
            'Industrial Land',
            'Godown',
            'Workshop',
            'Logistics Park',
            'Industrial Plot',
            'SEZ Unit',
            'IT Park',
            'Textile Unit',
            'Chemical Plant',
            'Other'
        ],
        'plot-land': [
            'Residential Plot',
            'Commercial Plot',
            'Industrial Plot',
            'Agricultural Land',
            'Plot File',
            'Plot Form',
            'NA Plot',
            'Gram Panchayat Plot',
            'Society Plot',
            'Farm Land',
            'Orchard',
            'Barren Land',
            'Beach Front Land',
            'Hill View Land',
            'Lake View Land',
            'Gated Community Plot',
            'Corner Plot',
            'Main Road Plot',
            'Other'
        ],
        'agricultural': [
            'Agricultural Land',
            'Farm House',
            'Farm Land',
            'Orchard',
            'Plantation',
            'Vineyard',
            'Dairy Farm',
            'Poultry Farm',
            'Fishery',
            'Green House',
            'Nursery',
            'Agricultural Shed',
            'Irrigated Land',
            'Non-irrigated Land',
            'Cultivable Land',
            'Barren Land',
            'Other'
        ],
        'pg-hostel': [
            'PG (Girls)',
            'PG (Boys)',
            'PG (Co-ed)',
            'Hostel (Girls)',
            'Hostel (Boys)',
            'Hostel (Co-ed)',
            'Student Accommodation',
            'Working Professional PG',
            'Family PG',
            'Single Room PG',
            'Double Sharing PG',
            'Triple Sharing PG',
            'Dormitory',
            'Serviced Apartment',
            'Guest House',
            'Other'
        ],
        'rural': [
            'Village House',
            'Farm House',
            'Rural Land',
            'Traditional House',
            'Country House',
            'Rural Farm',
            'Village Plot',
            'Rural Commercial',
            'Rural Industrial',
            'Other'
        ],
        'other': [
            'Mixed Use',
            'Institutional',
            'Religious',
            'Charitable',
            'Government',
            'Public Utility',
            'Special Purpose',
            'Leasehold',
            'Freehold',
            'Other'
        ]
    }

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Setting up property types...'))
        
        total_created = 0
        total_updated = 0
        
        # Get all categories
        categories = PropertyCategory.objects.filter(is_active=True)
        
        for category in categories:
            category_slug = category.slug
            
            if category_slug in self.PROPERTY_TYPES:
                self.stdout.write(f'\n{category.name} category:')
                
                type_names = self.PROPERTY_TYPES[category_slug]
                
                for type_name in type_names:
                    slug = slugify(f"{category_slug}-{type_name}")
                    
                    property_type, created = PropertyType.objects.update_or_create(
                        slug=slug,
                        defaults={
                            'category': category,
                            'name': type_name,
                            'description': f'{type_name} under {category.name}',
                            'is_active': True
                        }
                    )
                    
                    if created:
                        total_created += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Created: {type_name}')
                        )
                    else:
                        total_updated += 1
                        self.stdout.write(
                            self.style.WARNING(f'  ↻ Updated: {type_name}')
                        )
        
        # Summary
        self.stdout.write(self.style.SUCCESS(
            f'\n\nSuccessfully setup property types:'
        ))
        self.stdout.write(f'  - Total created: {total_created}')
        self.stdout.write(f'  - Total updated: {total_updated}')
        
        # Display count by category
        self.stdout.write('\nProperty types by category:')
        for category in categories:
            count = PropertyType.objects.filter(category=category, is_active=True).count()
            self.stdout.write(f'  - {category.name}: {count} types')
        
        total_types = PropertyType.objects.filter(is_active=True).count()
        self.stdout.write(f'\nTotal active property types: {total_types}')