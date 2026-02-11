# management/commands/setup_property_categories.py
from django.core.management.base import BaseCommand
from estate_app.models import PropertyCategory
from django.utils.text import slugify

class Command(BaseCommand):
    help = 'Setup default property categories'
    
    # Define all property categories with icons
    CATEGORIES = [
        {
            'name': 'Residential',
            'slug': 'residential',
            'icon': 'fas fa-home',
            'description': 'Residential properties including apartments, houses, villas',
            'display_order': 1
        },
        {
            'name': 'Commercial',
            'slug': 'commercial',
            'icon': 'fas fa-building',
            'description': 'Commercial properties including offices, shops, retail spaces',
            'display_order': 2
        },
        {
            'name': 'Industrial',
            'slug': 'industrial',
            'icon': 'fas fa-industry',
            'description': 'Industrial properties including factories, warehouses, manufacturing units',
            'display_order': 3
        },
        {
            'name': 'Plot/Land',
            'slug': 'plot-land',
            'icon': 'fas fa-map-marker-alt',
            'description': 'Land and plot properties for development',
            'display_order': 4
        },
        {
            'name': 'Agricultural',
            'slug': 'agricultural',
            'icon': 'fas fa-tractor',
            'description': 'Agricultural land and farmhouses',
            'display_order': 5
        },
        {
            'name': 'PG/Hostel',
            'slug': 'pg-hostel',
            'icon': 'fas fa-bed',
            'description': 'PG accommodations, hostels, and paying guest facilities',
            'display_order': 6
        },
        {
            'name': 'Rural',
            'slug': 'rural',
            'icon': 'fas fa-tree',
            'description': 'Rural properties and village homes',
            'display_order': 7
        },
        {
            'name': 'Other',
            'slug': 'other',
            'icon': 'fas fa-ellipsis-h',
            'description': 'Other types of properties',
            'display_order': 8
        }
    ]

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Setting up property categories...'))
        
        created_count = 0
        updated_count = 0
        
        for category_data in self.CATEGORIES:
            category, created = PropertyCategory.objects.update_or_create(
                slug=category_data['slug'],
                defaults={
                    'name': category_data['name'],
                    'icon': category_data['icon'],
                    'description': category_data['description'],
                    'display_order': category_data['display_order'],
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created: {category.name}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'↻ Updated: {category.name}')
                )
        
        self.stdout.write(self.style.SUCCESS(
            f'\nSuccessfully setup {created_count + updated_count} property categories:'
        ))
        self.stdout.write(f'  - Created: {created_count}')
        self.stdout.write(f'  - Updated: {updated_count}')
        
        # Display all categories
        categories = PropertyCategory.objects.all().order_by('display_order')
        self.stdout.write('\nAvailable categories:')
        for category in categories:
            self.stdout.write(f'  - {category.name} ({category.slug})')