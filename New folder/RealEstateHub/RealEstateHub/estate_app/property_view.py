# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.db import transaction
from django.utils import timezone
from django.core.paginator import Paginator
from django.urls import reverse
from django.views.generic import CreateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django import forms
import json
import logging

from .models import Property, PropertyCategory, PropertySubCategory, Amenity, PropertyImage
from .forms import (
    DynamicPropertyForm, LocationForm, ContactForm, 
    AmenityForm, PropertyImageFormSet, LegalForm, PublishForm
)

logger = logging.getLogger(__name__)


@login_required
def create_property_wizard(request):
    """99acres style step-by-step property creation wizard"""
    step = request.GET.get('step', '1')
    property_id = request.GET.get('property_id')
    
    context = {
        'current_step': step,
        'total_steps': 7,
    }
    
    # Helper function to get property with validation
    def get_property_obj(property_id):
        if not property_id:
            return None
        try:
            return Property.objects.get(id=property_id, owner=request.user)
        except Property.DoesNotExist:
            messages.error(request, 'Property not found or you do not have permission.')
            return None
    
    # Step 1: Basic Information
    if step == '1':
        if request.method == 'POST':
            form = DynamicPropertyForm(request.POST, user=request.user)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        property_obj = form.save(commit=False)
                        property_obj.owner = request.user
                        property_obj.created_by = request.user
                        property_obj.last_modified_by = request.user
                        property_obj.save()
                        
                        messages.success(request, 'Basic information saved successfully!')
                        return redirect(f'{reverse("create_property_wizard")}?step=2&property_id={property_obj.id}')
                except Exception as e:
                    logger.error(f"Error saving property: {e}")
                    messages.error(request, 'Error saving property. Please try again.')
            else:
                messages.error(request, 'Please correct the errors below.')
        else:
            form = DynamicPropertyForm(user=request.user)
        
        context['form'] = form
        context['categories'] = PropertyCategory.objects.filter(is_active=True)
        context['step_title'] = 'Basic Information'
        context['step_description'] = 'Tell us about your property'
    
    # Step 2: Location Details
    elif step == '2':
        property_obj = get_property_obj(property_id)
        if not property_obj:
            return redirect(f'{reverse("create_property_wizard")}?step=1')
        
        if request.method == 'POST':
            form = LocationForm(request.POST, instance=property_obj)
            if form.is_valid():
                try:
                    form.save()
                    messages.success(request, 'Location details saved successfully!')
                    return redirect(f'{reverse("create_property_wizard")}?step=3&property_id={property_obj.id}')
                except Exception as e:
                    logger.error(f"Error saving location: {e}")
                    messages.error(request, 'Error saving location. Please try again.')
            else:
                messages.error(request, 'Please correct the errors below.')
        else:
            form = LocationForm(instance=property_obj)
        
        context['form'] = form
        context['property'] = property_obj
        context['step_title'] = 'Location Details'
        context['step_description'] = 'Where is your property located?'
    
    # Step 3: Property Details
    elif step == '3':
        property_obj = get_property_obj(property_id)
        if not property_obj:
            return redirect(f'{reverse("create_property_wizard")}?step=1')
        
        if request.method == 'POST':
            try:
                # Update property with POST data
                if property_obj.category:
                    # Update fields based on category configuration
                    if property_obj.category.has_bedrooms:
                        if 'bedrooms' in request.POST and request.POST['bedrooms']:
                            property_obj.bedrooms = int(request.POST['bedrooms'])
                        if 'bathrooms' in request.POST and request.POST['bathrooms']:
                            property_obj.bathrooms = int(request.POST['bathrooms'])
                        if 'balconies' in request.POST and request.POST['balconies']:
                            property_obj.balconies = int(request.POST['balconies'])
                    
                    if property_obj.category.has_floor:
                        if 'floor_number' in request.POST and request.POST['floor_number']:
                            property_obj.floor_number = int(request.POST['floor_number'])
                        if 'total_floors' in request.POST and request.POST['total_floors']:
                            property_obj.total_floors = int(request.POST['total_floors'])
                    
                    if property_obj.category.has_furnishing and 'furnishing' in request.POST:
                        property_obj.furnishing = request.POST['furnishing']
                    
                    if property_obj.category.has_age:
                        if 'age_of_property' in request.POST:
                            property_obj.age_of_property = request.POST['age_of_property']
                        if 'possession_status' in request.POST:
                            property_obj.possession_status = request.POST['possession_status']
                    
                    if property_obj.category.has_facing and 'facing' in request.POST:
                        property_obj.facing = request.POST['facing']
                    
                    if property_obj.category.has_pantry:
                        property_obj.pantry = 'pantry' in request.POST
                        property_obj.conference_room = 'conference_room' in request.POST
                    
                    if property_obj.category.has_washrooms and 'washrooms' in request.POST and request.POST['washrooms']:
                        property_obj.washrooms = int(request.POST['washrooms'])
                    
                    if property_obj.category.has_power_backup and 'power_backup' in request.POST:
                        property_obj.power_backup = request.POST['power_backup']
                    
                    if property_obj.category.has_clear_height and 'clear_height' in request.POST and request.POST['clear_height']:
                        property_obj.clear_height = float(request.POST['clear_height'])
                    
                    if property_obj.category.has_floor_loading and 'floor_loading' in request.POST and request.POST['floor_loading']:
                        property_obj.floor_loading = float(request.POST['floor_loading'])
                    
                    if property_obj.category.has_dimensions:
                        if 'plot_length' in request.POST and request.POST['plot_length']:
                            property_obj.plot_length = float(request.POST['plot_length'])
                        if 'plot_breadth' in request.POST and request.POST['plot_breadth']:
                            property_obj.plot_breadth = float(request.POST['plot_breadth'])
                        if 'plot_type' in request.POST:
                            property_obj.plot_type = request.POST['plot_type']
                    
                    if property_obj.category.has_soil_type and 'soil_type' in request.POST:
                        property_obj.soil_type = request.POST['soil_type']
                
                property_obj.save()
                messages.success(request, 'Property details saved successfully!')
                return redirect(f'{reverse("create_property_wizard")}?step=4&property_id={property_obj.id}')
                
            except ValueError as e:
                logger.error(f"Value error: {e}")
                messages.error(request, 'Invalid data entered. Please check the values.')
            except Exception as e:
                logger.error(f"Error saving property details: {e}")
                messages.error(request, 'Error saving property details. Please try again.')
        
        context['property'] = property_obj
        context['step_title'] = 'Property Details'
        context['step_description'] = 'Specifications and measurements'
    
    # Step 4: Amenities
    elif step == '4':
        property_obj = get_property_obj(property_id)
        if not property_obj:
            return redirect(f'{reverse("create_property_wizard")}?step=1')
        
        if request.method == 'POST':
            try:
                # Get selected amenities
                amenity_ids = request.POST.getlist('amenities')
                if amenity_ids:
                    # Convert to integers and filter valid amenities
                    amenity_ids = [int(id) for id in amenity_ids if id.isdigit()]
                    amenities = Amenity.objects.filter(id__in=amenity_ids, is_active=True)
                    property_obj.amenities.set(amenities)
                else:
                    property_obj.amenities.clear()
                
                messages.success(request, 'Amenities saved successfully!')
                return redirect(f'{reverse("create_property_wizard")}?step=5&property_id={property_obj.id}')
                
            except Exception as e:
                logger.error(f"Error saving amenities: {e}")
                messages.error(request, 'Error saving amenities. Please try again.')
        
        # Get amenities based on property category
        amenities = Amenity.objects.filter(is_active=True)
        if property_obj.category:
            # Get all amenities applicable to this property type or 'all'
            property_type = property_obj.category.property_type
            amenities = amenities.filter(
                Q(applicable_to=property_type) | Q(applicable_to='all')
            ).order_by('category', 'display_order')
        
        # Group amenities by category and mark selected ones
        amenity_categories = {}
        for amenity in amenities:
            category = amenity.get_category_display()
            if category not in amenity_categories:
                amenity_categories[category] = []
            
            amenity_categories[category].append({
                'id': amenity.id,
                'name': amenity.name,
                'icon': amenity.icon,
                'selected': property_obj.amenities.filter(id=amenity.id).exists()
            })
        
        context['amenity_categories'] = amenity_categories
        context['property'] = property_obj
        context['step_title'] = 'Amenities & Facilities'
        context['step_description'] = 'Select all available amenities'
    
    # Step 5: Photos
    elif step == '5':
        property_obj = get_property_obj(property_id)
        if not property_obj:
            return redirect(f'{reverse("create_property_wizard")}?step=1')
        
        if request.method == 'POST':
            formset = PropertyImageFormSet(request.POST, request.FILES, instance=property_obj)
            if formset.is_valid():
                try:
                    formset.save()
                    
                    # Ensure at least one primary image
                    if not property_obj.images.filter(is_primary=True).exists():
                        first_image = property_obj.images.first()
                        if first_image:
                            first_image.is_primary = True
                            first_image.save()
                    
                    messages.success(request, 'Photos saved successfully!')
                    return redirect(f'{reverse("create_property_wizard")}?step=6&property_id={property_obj.id}')
                    
                except Exception as e:
                    logger.error(f"Error saving photos: {e}")
                    messages.error(request, 'Error saving photos. Please try again.')
            else:
                messages.error(request, 'Please correct the errors in the photos form.')
        else:
            formset = PropertyImageFormSet(instance=property_obj)
        
        context['formset'] = formset
        context['property'] = property_obj
        context['existing_images'] = property_obj.images.all().order_by('order', 'uploaded_at')
        context['step_title'] = 'Property Photos'
        context['step_description'] = 'Upload high-quality images'
    
    # Step 6: Contact & Legal
    elif step == '6':
        property_obj = get_property_obj(property_id)
        if not property_obj:
            return redirect(f'{reverse("create_property_wizard")}?step=1')
        
        if request.method == 'POST':
            # Handle both forms in one POST
            contact_form = ContactForm(request.POST, instance=property_obj)
            legal_form = LegalForm(request.POST, instance=property_obj)
            
            contact_valid = contact_form.is_valid()
            legal_valid = legal_form.is_valid()
            
            if contact_valid and legal_valid:
                try:
                    with transaction.atomic():
                        contact_form.save()
                        legal_form.save()
                    
                    messages.success(request, 'Contact and legal details saved successfully!')
                    return redirect(f'{reverse("create_property_wizard")}?step=7&property_id={property_obj.id}')
                    
                except Exception as e:
                    logger.error(f"Error saving contact/legal: {e}")
                    messages.error(request, 'Error saving details. Please try again.')
            else:
                if not contact_valid:
                    messages.error(request, 'Please correct errors in contact information.')
                if not legal_valid:
                    messages.error(request, 'Please correct errors in legal information.')
        else:
            contact_form = ContactForm(instance=property_obj)
            legal_form = LegalForm(instance=property_obj)
        
        context['contact_form'] = contact_form
        context['legal_form'] = legal_form
        context['property'] = property_obj
        context['step_title'] = 'Contact & Legal Details'
        context['step_description'] = 'Your contact information and property verification'
    
    # Step 7: Preview & Publish
    elif step == '7':
        property_obj = get_property_obj(property_id)
        if not property_obj:
            return redirect(f'{reverse("create_property_wizard")}?step=1')
        
        if request.method == 'POST':
            publish_form = PublishForm(request.POST)
            if publish_form.is_valid():
                publish_option = publish_form.cleaned_data['publish_option']
                schedule_date = publish_form.cleaned_data.get('schedule_date')
                
                try:
                    # Handle publish options
                    if publish_option == 'publish':
                        property_obj.status = 'active'
                        property_obj.is_active = True
                        property_obj.published_at = timezone.now()
                        messages.success(request, 'Property published successfully!')
                    
                    elif publish_option == 'premium':
                        property_obj.status = 'active'
                        property_obj.is_active = True
                        property_obj.is_premium = True
                        property_obj.published_at = timezone.now()
                        messages.success(request, 'Premium property published successfully!')
                    
                    elif publish_option == 'schedule':
                        property_obj.status = 'pending'
                        property_obj.is_active = False
                        property_obj.published_at = schedule_date
                        messages.success(request, f'Property scheduled for {schedule_date.strftime("%b %d, %Y %I:%M %p")}')
                    
                    else:  # draft
                        property_obj.status = 'draft'
                        property_obj.is_active = False
                        messages.success(request, 'Property saved as draft.')
                    
                    property_obj.save()
                    
                    # Redirect to property detail page
                    return redirect('property_detail', slug=property_obj.slug)
                    
                except Exception as e:
                    logger.error(f"Error publishing property: {e}")
                    messages.error(request, 'Error publishing property. Please try again.')
            else:
                messages.error(request, 'Please correct the errors below.')
        else:
            publish_form = PublishForm()
        
        context['publish_form'] = publish_form
        context['property'] = property_obj
        context['step_title'] = 'Preview & Publish'
        context['step_description'] = 'Review your listing and publish'
    
    # Invalid step
    else:
        messages.error(request, 'Invalid step. Starting from the beginning.')
        return redirect(f'{reverse("create_property_wizard")}?step=1')
    
    return render(request, 'dashboard/seller/property_create_wizard.html', context)


@require_GET
@login_required
def get_subcategories(request):
    """AJAX endpoint to get subcategories"""
    category_id = request.GET.get('category_id')
    
    if not category_id:
        return JsonResponse({'error': 'Category ID required'}, status=400)
    
    try:
        subcategories = PropertySubCategory.objects.filter(
            category_id=category_id,
            is_active=True
        ).order_by('display_order').values('id', 'name', 'icon')
        
        return JsonResponse({
            'success': True,
            'subcategories': list(subcategories)
        })
    except Exception as e:
        logger.error(f"Error getting subcategories: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
@login_required
def get_category_fields(request):
    """AJAX endpoint to get required fields for a category"""
    category_id = request.GET.get('category_id')
    
    if not category_id:
        return JsonResponse({'error': 'Category ID required'}, status=400)
    
    try:
        category = PropertyCategory.objects.get(id=category_id)
        
        # Get field configuration
        fields = {
            'has_bedrooms': category.has_bedrooms,
            'has_bathrooms': category.has_bathrooms,
            'has_balconies': category.has_balconies,
            'has_floor': category.has_floor,
            'has_furnishing': category.has_furnishing,
            'has_age': category.has_age,
            'has_facing': category.has_facing,
            'has_pantry': category.has_pantry,
            'has_conference_room': category.has_conference_room,
            'has_washrooms': category.has_washrooms,
            'has_power_backup': category.has_power_backup,
            'has_clear_height': category.has_clear_height,
            'has_floor_loading': category.has_floor_loading,
            'has_dimensions': category.has_dimensions,
            'has_soil_type': category.has_soil_type,
            'has_irrigation': category.has_irrigation,
            'has_crops': category.has_crops,
        }
        
        # Get recommended fields based on property type
        recommended_fields = []
        if category.property_type == 'residential':
            recommended_fields = ['bedrooms', 'bathrooms', 'furnishing', 'floor_number']
        elif category.property_type == 'commercial':
            recommended_fields = ['washrooms', 'power_backup', 'pantry', 'conference_room']
        elif category.property_type == 'land':
            recommended_fields = ['plot_length', 'plot_breadth', 'plot_type', 'facing_road_width']
        elif category.property_type == 'agricultural':
            recommended_fields = ['soil_type', 'irrigation_facilities', 'crops_grown', 'water_source']
        
        return JsonResponse({
            'success': True,
            'fields': fields,
            'recommended_fields': recommended_fields,
            'property_type': category.property_type,
            'category_name': category.name
        })
    except PropertyCategory.DoesNotExist:
        return JsonResponse({'error': 'Category not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting category fields: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
@login_required
@csrf_exempt
def save_property_step(request):
    """Save property data for each step (AJAX endpoint)"""
    try:
        data = json.loads(request.body)
        step = data.get('step')
        property_id = data.get('property_id')
        form_data = data.get('form_data', {})
        
        # Get or create property
        if property_id:
            try:
                property_obj = Property.objects.get(id=property_id, owner=request.user)
            except Property.DoesNotExist:
                return JsonResponse({'error': 'Property not found'}, status=404)
        else:
            property_obj = Property(owner=request.user)
        
        # Update property based on step
        with transaction.atomic():
            if step == 'basic':
                # Basic information
                property_obj.title = form_data.get('title', '')
                property_obj.description = form_data.get('description', '')
                property_obj.listing_type = form_data.get('listing_type', 'sale')
                
                # Category
                category_id = form_data.get('category')
                if category_id:
                    property_obj.category_id = category_id
                
                # Subcategory
                subcategory_id = form_data.get('subcategory')
                if subcategory_id:
                    property_obj.subcategory_id = subcategory_id
                
                # Price
                price = form_data.get('price')
                if price:
                    property_obj.price = price
                    property_obj.price_negotiable = form_data.get('price_negotiable', False)
                
                # Area
                super_area = form_data.get('super_area')
                if super_area:
                    property_obj.super_area = super_area
                    carpet_area = form_data.get('carpet_area')
                    if carpet_area:
                        property_obj.carpet_area = carpet_area
                    plot_area = form_data.get('plot_area')
                    if plot_area:
                        property_obj.plot_area = plot_area
                    property_obj.area_unit = form_data.get('area_unit', 'sqft')
                
                property_obj.save()
                
                # Save amenities if provided
                amenities = form_data.get('amenities', [])
                if amenities:
                    property_obj.amenities.set(amenities)
            
            elif step == 'location':
                # Location details
                property_obj.address = form_data.get('address', '')
                property_obj.city = form_data.get('city', '')
                property_obj.locality = form_data.get('locality', '')
                property_obj.landmark = form_data.get('landmark', '')
                property_obj.pincode = form_data.get('pincode', '')
                property_obj.state = form_data.get('state', '')
                property_obj.country = form_data.get('country', 'India')
                latitude = form_data.get('latitude')
                if latitude:
                    property_obj.latitude = latitude
                longitude = form_data.get('longitude')
                if longitude:
                    property_obj.longitude = longitude
            
            elif step == 'details':
                # Update dynamic fields based on category
                if property_obj.category:
                    if property_obj.category.has_bedrooms:
                        bedrooms = form_data.get('bedrooms')
                        if bedrooms:
                            property_obj.bedrooms = int(bedrooms)
                        bathrooms = form_data.get('bathrooms')
                        if bathrooms:
                            property_obj.bathrooms = int(bathrooms)
                        balconies = form_data.get('balconies')
                        if balconies:
                            property_obj.balconies = int(balconies)
                    
                    if property_obj.category.has_floor:
                        floor_number = form_data.get('floor_number')
                        if floor_number:
                            property_obj.floor_number = int(floor_number)
                        total_floors = form_data.get('total_floors')
                        if total_floors:
                            property_obj.total_floors = int(total_floors)
                    
                    if property_obj.category.has_furnishing:
                        furnishing = form_data.get('furnishing')
                        if furnishing:
                            property_obj.furnishing = furnishing
                    
                    if property_obj.category.has_age:
                        age_of_property = form_data.get('age_of_property')
                        if age_of_property:
                            property_obj.age_of_property = age_of_property
                        possession_status = form_data.get('possession_status')
                        if possession_status:
                            property_obj.possession_status = possession_status
                    
                    if property_obj.category.has_facing:
                        facing = form_data.get('facing')
                        if facing:
                            property_obj.facing = facing
                    
                    if property_obj.category.has_pantry:
                        property_obj.pantry = form_data.get('pantry', False)
                        property_obj.conference_room = form_data.get('conference_room', False)
                    
                    if property_obj.category.has_washrooms:
                        washrooms = form_data.get('washrooms')
                        if washrooms:
                            property_obj.washrooms = int(washrooms)
                    
                    if property_obj.category.has_power_backup:
                        power_backup = form_data.get('power_backup')
                        if power_backup:
                            property_obj.power_backup = power_backup
                    
                    if property_obj.category.has_clear_height:
                        clear_height = form_data.get('clear_height')
                        if clear_height:
                            property_obj.clear_height = float(clear_height)
                    
                    if property_obj.category.has_floor_loading:
                        floor_loading = form_data.get('floor_loading')
                        if floor_loading:
                            property_obj.floor_loading = float(floor_loading)
                    
                    if property_obj.category.has_dimensions:
                        plot_length = form_data.get('plot_length')
                        if plot_length:
                            property_obj.plot_length = float(plot_length)
                        plot_breadth = form_data.get('plot_breadth')
                        if plot_breadth:
                            property_obj.plot_breadth = float(plot_breadth)
                        plot_type = form_data.get('plot_type')
                        if plot_type:
                            property_obj.plot_type = plot_type
                        facing_road_width = form_data.get('facing_road_width')
                        if facing_road_width:
                            property_obj.facing_road_width = float(facing_road_width)
                    
                    if property_obj.category.has_soil_type:
                        soil_type = form_data.get('soil_type')
                        if soil_type:
                            property_obj.soil_type = soil_type
                        irrigation_facilities = form_data.get('irrigation_facilities')
                        if irrigation_facilities:
                            property_obj.irrigation_facilities = irrigation_facilities
                        crops_grown = form_data.get('crops_grown')
                        if crops_grown:
                            property_obj.crops_grown = crops_grown
                        water_source = form_data.get('water_source')
                        if water_source:
                            property_obj.water_source = water_source
                        electricity_connection = form_data.get('electricity_connection', False)
                        property_obj.electricity_connection = electricity_connection
                        farm_house = form_data.get('farm_house', False)
                        property_obj.farm_house = farm_house
            
            elif step == 'contact':
                # Contact details
                property_obj.contact_person = form_data.get('contact_person', '')
                property_obj.contact_email = form_data.get('contact_email', '')
                property_obj.contact_phone = form_data.get('contact_phone', '')
                property_obj.alternate_phone = form_data.get('alternate_phone', '')
                property_obj.whatsapp_enabled = form_data.get('whatsapp_enabled', True)
                property_obj.preferred_contact_time = form_data.get('preferred_contact_time', '')
                property_obj.preferred_tenants = form_data.get('preferred_tenants')
                available_from = form_data.get('available_from')
                if available_from:
                    property_obj.available_from = available_from
                
                # Legal details
                property_obj.rera_registered = form_data.get('rera_registered', False)
                property_obj.rera_number = form_data.get('rera_number', '')
                property_obj.legal_documents = form_data.get('legal_documents', '')
                property_obj.ownership_type = form_data.get('ownership_type')
            
            property_obj.last_modified_by = request.user
            property_obj.save()
        
        return JsonResponse({
            'success': True,
            'property_id': property_obj.id,
            'message': 'Step saved successfully'
        })
        
    except ValueError as e:
        logger.error(f"Value error in save_property_step: {e}")
        return JsonResponse({'error': 'Invalid data format'}, status=400)
    except Exception as e:
        logger.error(f"Error saving property step: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
@login_required
def upload_property_images(request):
    """Upload property images"""
    property_id = request.POST.get('property_id')
    
    if not property_id:
        return JsonResponse({'error': 'Property ID required'}, status=400)
    
    try:
        property_obj = Property.objects.get(id=property_id, owner=request.user)
        
        images = request.FILES.getlist('images')
        uploaded_images = []
        
        for i, image_file in enumerate(images):
            # Validate image size (max 10MB)
            if image_file.size > 10 * 1024 * 1024:
                continue
            
            # Validate file type
            import os
            ext = os.path.splitext(image_file.name)[1].lower()
            valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
            if ext not in valid_extensions:
                continue
            
            # Create PropertyImage
            property_image = PropertyImage(
                property=property_obj,
                image=image_file,
                order=i,
                caption=request.POST.get(f'caption_{i}', ''),
                is_primary=(i == 0 and not property_obj.images.filter(is_primary=True).exists())
            )
            property_image.save()
            uploaded_images.append({
                'id': property_image.id,
                'url': property_image.image.url,
                'thumbnail': property_image.thumbnail.url if property_image.thumbnail else property_image.image.url,
                'caption': property_image.caption,
                'is_primary': property_image.is_primary
            })
        
        return JsonResponse({
            'success': True,
            'images': uploaded_images,
            'message': f'{len(uploaded_images)} images uploaded successfully'
        })
        
    except Property.DoesNotExist:
        return JsonResponse({'error': 'Property not found'}, status=404)
    except Exception as e:
        logger.error(f"Error uploading images: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
@login_required
def delete_property_image(request):
    """Delete property image"""
    image_id = request.POST.get('image_id')
    
    if not image_id:
        return JsonResponse({'error': 'Image ID required'}, status=400)
    
    try:
        image = PropertyImage.objects.get(id=image_id, property__owner=request.user)
        image.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Image deleted successfully'
        })
        
    except PropertyImage.DoesNotExist:
        return JsonResponse({'error': 'Image not found'}, status=404)
    except Exception as e:
        logger.error(f"Error deleting image: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
@login_required
def set_primary_image(request):
    """Set image as primary"""
    image_id = request.POST.get('image_id')
    
    if not image_id:
        return JsonResponse({'error': 'Image ID required'}, status=400)
    
    try:
        image = PropertyImage.objects.get(id=image_id, property__owner=request.user)
        
        # Remove primary from all images
        PropertyImage.objects.filter(property=image.property).update(is_primary=False)
        
        # Set new primary
        image.is_primary = True
        image.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Primary image updated'
        })
        
    except PropertyImage.DoesNotExist:
        return JsonResponse({'error': 'Image not found'}, status=404)
    except Exception as e:
        logger.error(f"Error setting primary image: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
@login_required
def get_price_suggestions(request):
    """Get price suggestions based on location and property type"""
    city = request.GET.get('city')
    locality = request.GET.get('locality')
    category_id = request.GET.get('category_id')
    area = request.GET.get('area')
    listing_type = request.GET.get('listing_type', 'sale')
    
    if not city or not area:
        return JsonResponse({'error': 'City and area required'}, status=400)
    
    try:
        area = float(area)
        
        # Get average price per sqft for similar properties
        similar_properties = Property.objects.filter(
            city__iexact=city,
            is_active=True,
            status='active',
            super_area__gt=0,
            listing_type=listing_type
        ).exclude(price__isnull=True).exclude(super_area__isnull=True)
        
        if locality:
            similar_properties = similar_properties.filter(locality__icontains=locality)
        
        if category_id:
            similar_properties = similar_properties.filter(category_id=category_id)
        
        # Calculate average price per sqft
        avg_price_per_sqft = 0
        sample_count = 0
        
        if similar_properties.exists():
            valid_properties = []
            for prop in similar_properties:
                if prop.super_area and prop.super_area > 0:
                    valid_properties.append(prop)
            
            if valid_properties:
                total_price = sum(p.price for p in valid_properties)
                total_area = sum(p.super_area for p in valid_properties)
                if total_area > 0:
                    avg_price_per_sqft = total_price / total_area
                sample_count = len(valid_properties)
        
        # Calculate suggested price range
        suggested_price = area * avg_price_per_sqft if avg_price_per_sqft > 0 else 0
        
        # Price range (±20%)
        min_price = suggested_price * 0.8
        max_price = suggested_price * 1.2
        
        return JsonResponse({
            'success': True,
            'suggested_price': round(suggested_price, 2),
            'min_price': round(min_price, 2),
            'max_price': round(max_price, 2),
            'price_per_sqft': round(avg_price_per_sqft, 2),
            'sample_size': sample_count,
            'currency': '₹'
        })
        
    except ValueError:
        return JsonResponse({'error': 'Invalid area value'}, status=400)
    except Exception as e:
        logger.error(f"Error getting price suggestions: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_subcategories(request):
    """Get subcategories for a given category via AJAX"""
    category_id = request.GET.get('category_id')
    if not category_id:
        return JsonResponse({'success': False, 'error': 'Category ID required'})

    try:
        subcategories = PropertySubCategory.objects.filter(
            category_id=category_id,
            is_active=True
        ).values('id', 'name')
        return JsonResponse({
            'success': True,
            'subcategories': list(subcategories)
        })
    except Exception as e:
        logger.error(f"Error getting subcategories for category {category_id}: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
@login_required
@csrf_exempt
def save_property_ajax(request):
    """AJAX endpoint for saving property with validation"""
    try:
        data = json.loads(request.body)
        step = data.get('step')
        property_id = data.get('property_id')
        
        if not step:
            return JsonResponse({'success': False, 'error': 'Step not specified'})
        
        # Handle different steps
        if step == '1':
            form = DynamicPropertyForm(data, user=request.user)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        property_obj = form.save(commit=False)
                        property_obj.owner = request.user
                        property_obj.created_by = request.user
                        property_obj.last_modified_by = request.user
                        property_obj.save()
                    
                    return JsonResponse({
                        'success': True,
                        'property_id': property_obj.id,
                        'redirect_url': reverse('create_property_wizard') + f'?step=2&property_id={property_obj.id}',
                        'message': 'Basic information saved successfully!'
                    })
                except Exception as e:
                    logger.error(f"Error saving property: {e}")
                    return JsonResponse({
                        'success': False,
                        'errors': [{'field': 'general', 'message': 'Error saving property. Please try again.'}]
                    })
            else:
                # Return form errors in structured format
                errors = []
                for field, error_list in form.errors.items():
                    for error in error_list:
                        errors.append({
                            'field': field,
                            'message': str(error)
                        })
                
                return JsonResponse({
                    'success': False,
                    'errors': errors
                })
        
        else:
            return JsonResponse({
                'success': False,
                'error': f'Step {step} not implemented for AJAX'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception as e:
        logger.error(f"Error in save_property_ajax: {e}")
        return JsonResponse({'success': False, 'error': 'Internal server error'})

@login_required
def property_preview(request, property_id):
    """Preview property before publishing"""
    try:
        property_obj = Property.objects.get(id=property_id, owner=request.user)

        context = {
            'property': property_obj,
            'amenities': property_obj.amenities.all(),
            'images': property_obj.images.all(),
            'can_publish': property_obj.can_publish(),
        }

        return render(request, 'dashboard/seller/property_preview.html', context)

    except Property.DoesNotExist:
        messages.error(request, 'Property not found.')
        return redirect('seller_properties')
