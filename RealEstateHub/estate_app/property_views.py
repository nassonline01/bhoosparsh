# """
# Enhanced Property Views for Seller Dashboard
# """
# import logging
# from typing import Dict, List, Optional, Any
# from django.shortcuts import render, redirect, get_object_or_404
# from django.contrib.auth.decorators import login_required
# from django.contrib import messages
# from django.views.decorators.http import require_http_methods, require_GET, require_POST
# from django.db import transaction
# from django.db.models import Count, Q, Prefetch, Avg
# from django.core.paginator import Paginator
# from django.http import JsonResponse, HttpResponseBadRequest
# from django.utils import timezone
# from django.views import View
# from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
# from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
# from django.urls import reverse_lazy
# from django.urls import reverse
# from django.conf import settings
# from django.views.decorators.csrf import csrf_exempt


# from .seller_dashboard import get_seller_context


# from django.db import models


# logger = logging.getLogger(__name__)


# # ======================================================================
# #  Property Views for Seller Dashboard
# # ======================================================================

# # class SellerPropertyCreateView(LoginRequiredMixin, CreateView):
# #     """Create property view for seller dashboard"""
# #     model = Property
# #     form_class = PropertyCreationForm
# #     template_name = 'dashboard/seller/property_create.html'
    
# #     def get_form_kwargs(self):
# #         """Pass request and user to form"""
# #         kwargs = super().get_form_kwargs()
# #         kwargs['user'] = self.request.user
# #         kwargs['request'] = self.request
# #         return kwargs
    
# #     def get_context_data(self, **kwargs):
# #         """Add additional context for seller dashboard"""
# #         context = super().get_context_data(**kwargs)
        
# #         # Get seller context
# #         seller_context = get_seller_context(self.request.user, 'properties')
# #         context.update(seller_context)
        
# #         # Get categories and amenities
# #         context['categories'] = PropertyCategory.objects.filter(is_active=True)
# #         context['amenities'] = Amenity.objects.filter(is_active=True)
        
# #         # Get membership info
# #         try:
# #             membership = self.request.user.membership
# #             context['membership'] = membership
# #             context['listings_remaining'] = (
# #                 membership.plan.max_active_listings - membership.listings_used
# #                 if not membership.plan.is_unlimited else 'Unlimited'
# #             )
# #         except UserMembership.DoesNotExist:
# #             context['membership'] = None
# #             context['listings_remaining'] = 0
        
# #         # Add current year for validation
# #         from django.utils import timezone
# #         context['current_year'] = timezone.now().year
        
# #         # Add current date for schedule field
# #         context['current_date'] = timezone.now().strftime('%Y-%m-%dT%H:%M')
        
# #         # Add page title
# #         context['page_title'] = 'Post New Property'
        
# #         # Add location data for dropdowns
# #         # Get states and cities from existing properties
# #         existing_states = Property.objects.filter(state__isnull=False).values_list('state', flat=True).distinct().order_by('state')
# #         existing_cities = Property.objects.filter(city__isnull=False).values_list('city', flat=True).distinct().order_by('city')

# #         # Default Indian states if no existing data
# #         default_states = [
# #             'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
# #             'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka',
# #             'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram',
# #             'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu',
# #             'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
# #             'Delhi', 'Jammu and Kashmir', 'Ladakh', 'Puducherry', 'Chandigarh',
# #             'Andaman and Nicobar Islands', 'Dadra and Nagar Haveli and Daman and Diu',
# #             'Lakshadweep'
# #         ]

# #         # Default major cities if no existing data
# #         default_cities = [
# #             'Mumbai', 'Delhi', 'Bangalore', 'Hyderabad', 'Ahmedabad', 'Chennai', 'Kolkata',
# #             'Surat', 'Pune', 'Jaipur', 'Lucknow', 'Kanpur', 'Nagpur', 'Indore', 'Thane',
# #             'Bhopal', 'Visakhapatnam', 'Pimpri-Chinchwad', 'Patna', 'Vadodara', 'Ghaziabad',
# #             'Ludhiana', 'Agra', 'Nashik', 'Faridabad', 'Meerut', 'Rajkot', 'Kalyan-Dombivli',
# #             'Vasai-Virar', 'Varanasi', 'Srinagar', 'Aurangabad', 'Dhanbad', 'Amritsar',
# #             'Navi Mumbai', 'Allahabad', 'Howrah', 'Ranchi', 'Gwalior', 'Jabalpur', 'Coimbatore',
# #             'Vijayawada', 'Jodhpur', 'Madurai', 'Raipur', 'Kota', 'Guwahati', 'Chandigarh',
# #             'Solapur', 'Hubballi-Dharwad', 'Tiruchirappalli', 'Bareilly', 'Moradabad', 'Mysore',
# #             'Tiruppur', 'Gurgaon', 'Aligarh', 'Jalandhar', 'Bhubaneswar', 'Salem', 'Warangal',
# #             'Guntur', 'Bhiwandi', 'Saharanpur', 'Gorakhpur', 'Bikaner', 'Amravati', 'Noida',
# #             'Jamshedpur', 'Bhilai', 'Cuttack', 'Firozabad', 'Kochi', 'Nellore', 'Bhavnagar',
# #             'Dehradun', 'Durgapur', 'Asansol', 'Rourkela', 'Nanded', 'Kolhapur', 'Ajmer',
# #             'Akola', 'Gulbarga', 'Jamnagar', 'Ujjain', 'Loni', 'Siliguri', 'Jhansi',
# #             'Ulhasnagar', 'Jammu', 'Sangli-Miraj & Kupwad', 'Mangalore', 'Erode', 'Belgaum',
# #             'Ambattur', 'Tirunelveli', 'Malegaon', 'Gaya', 'Tiruppur', 'Davanagere', 'Kozhikode',
# #             'Akola', 'Kurnool', 'Rajpur Sonarpur', 'Bokaro', 'South Dumdum', 'Bellary',
# #             'Patiala', 'Gopalpur', 'Agartala', 'Bhagalpur', 'Muzaffarnagar', 'Bhatpara',
# #             'Panihati', 'Latur', 'Dhule', 'Tirupati', 'Rohtak', 'Korba', 'Bhilwara', 'Berhampur',
# #             'Muzaffarpur', 'Ahmednagar', 'Mathura', 'Kollam', 'Avadi', 'Kadapa', 'Kamarhati',
# #             'Sambalpur', 'Bilaspur', 'Shahjahanpur', 'Satara', 'Bijapur', 'Rampur', 'Shorapur',
# #             'Chandrapur', 'Junagadh', 'Thrissur', 'Alwar', 'Bardhaman', 'Kulti', 'Kakinada',
# #             'Nizamabad', 'Parbhani', 'Tumkur', 'Khammam', 'Ozhukarai', 'Bihar Sharif',
# #             'Panipat', 'Darbhanga', 'Bally', 'Aizawl', 'Dewas', 'Ichalkaranji', 'Karnal',
# #             'Bathinda', 'Jalna', 'Eluru', 'Kirari Suleman Nagar', 'Barasat', 'Purnia',
# #             'Satna', 'Mau', 'Sonipat', 'Farrukhabad', 'Sagar', 'Rourkela', 'Durg', 'Imphal',
# #             'Ratlam', 'Hapur', 'Arrah', 'Karimnagar', 'Anantapur', 'Etawah', 'Ambernath',
# #             'North Dumdum', 'Bharatpur', 'Begusarai', 'New Delhi', 'Gandhidham', 'Baranagar',
# #             'Tiruvottiyur', 'Pondicherry', 'Sikar', 'Thoothukudi', 'Rewa', 'Mirzapur', 'Raichur',
# #             'Pali', 'Ramagundam', 'Haridwar', 'Vijayanagaram', 'Katihar', 'Hardwar', 'Sri Ganganagar',
# #             'Karawal Nagar', 'Nagercoil', 'Mango', 'Thanjavur', 'Bulandshahr', 'Uluberia',
# #             'Murwara', 'Sambhal', 'Singrauli', 'Nadiad', 'Secunderabad', 'Naihati', 'Yamunanagar',
# #             'Bidhan Nagar', 'Pallavaram', 'Bidar', 'Munger', 'Panchkula', 'Burhanpur', 'Raurkela',
# #             'Kharagpur', 'Dindigul', 'Gandhinagar', 'Hospet', 'Nangloi Jat', 'Malda', 'Ongole',
# #             'Deoghar', 'Chapra', 'Haldia', 'Khandwa', 'Nandyal', 'Morena', 'Amroha', 'Anand',
# #             'Bhind', 'Bhalswa Jahangir Pur', 'Madhyamgram', 'Bhiwani', 'Visnagar', 'Ajmer',
# #             'Bahraich', 'Ambala', 'Avadi', 'Fatehpur', 'Bhusawal', 'Orai', 'Bahadurgarh',
# #             'Vellore', 'Mehsana', 'Raiganj', 'Sirsa', 'Danapur', 'Serampore', 'Sultan Pur Majra',
# #             'Guna', 'Jaunpur', 'Panvel', 'Shivpuri', 'Surendranagar Dudhrej', 'Unnao', 'Chinsurah',
# #             'Alappuzha', 'Kottayam', 'Machilipatnam', 'Shimla', 'Adoni', 'Udupi', 'Tenali',
# #             'Proddatur', 'Saharsa', 'Hindupur', 'Sasaram', 'Hajipur', 'Bhimavaram', 'Kishangarh',
# #             'Dehri', 'Moradabad', 'Adilabad', 'Connaught Place', 'Rajahmundry', 'Tadepalligudem',
# #             'Rajpur Sonarpur', 'Godhra', 'Hazaribagh', 'Bhimavaram', 'Mothihari', 'Suratgarh',
# #             'Port Blair', 'Ballia', 'Amla', 'Phusro', 'Navsari', 'Bahadurgarh', 'Silchar',
# #             'Shahdol', 'Beawar', 'Budaun', 'Chittoor', 'Fatehabad', 'Washim', 'Raipur', 'Palghar'
# #         ]

# #         # Combine existing and default data
# #         context['states'] = sorted(list(set(list(existing_states) + default_states)))
# #         context['cities'] = sorted(list(set(list(existing_cities) + default_cities)))
        
# #         return context
    
# #     def form_valid(self, form):
# #         """Handle successful form submission"""
# #         try:
# #             with transaction.atomic():
# #                 # Validate images BEFORE saving property
# #                 images = self.request.FILES.getlist('images')
                
# #                 if len(images) < 3:
# #                     messages.error(self.request, 'Please upload at least 3 images.')
# #                     return self.form_invalid(form)
                
# #                 if len(images) > 20:
# #                     messages.error(self.request, 'Maximum 20 images allowed.')
# #                     return self.form_invalid(form)
                
# #                 # Validate each image
# #                 for image in images:
# #                     # Check file size
# #                     if image.size > 10 * 1024 * 1024:  # 10MB
# #                         messages.error(self.request, f'Image "{image.name}" is too large. Maximum size is 10MB.')
# #                         return self.form_invalid(form)
                    
# #                     # Check file extension
# #                     import os
# #                     ext = os.path.splitext(image.name)[1].lower()
# #                     valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
# #                     if ext not in valid_extensions:
# #                         messages.error(self.request, f'Invalid file type for "{image.name}". Allowed: JPG, JPEG, PNG, WebP, GIF.')
# #                         return self.form_invalid(form)
                    
# #                     # Check if file is actually an image (optional)
# #                     try:
# #                         from PIL import Image
# #                         import io
                        
# #                         # Try to open the image
# #                         img_data = image.read()
# #                         img = Image.open(io.BytesIO(img_data))
# #                         img.verify()  # Verify it's a valid image
                        
# #                         # Reset file pointer
# #                         image.seek(0)
                        
# #                         # Check dimensions
# #                         img = Image.open(io.BytesIO(img_data))
# #                         width, height = img.size
# #                         if width < 400 or height < 300:
# #                             messages.warning(self.request, f'Image "{image.name}" dimensions are small. Minimum 400x300 pixels recommended.')
                        
# #                         # Reset file pointer again
# #                         image.seek(0)
                        
# #                     except ImportError:
# #                         # PIL not installed, skip image validation
# #                         pass
# #                     except Exception as e:
# #                         messages.error(self.request, f'Invalid image file: "{image.name}". Please upload a valid image.')
# #                         return self.form_invalid(form)
                
# #                 # Save property
# #                 self.object = form.save(commit=False)
# #                 self.object.owner = self.request.user
# #                 self.object.created_by = self.request.user
# #                 self.object.last_modified_by = self.request.user
                
# #                 # Set initial status based on publish option
# #                 publish_option = self.request.POST.get('publish_option', 'draft')
# #                 publish_schedule = self.request.POST.get('publish_schedule')
                
# #                 if publish_option == 'publish':
# #                     self.object.status = 'for_sale' if 'sale' in self.request.POST.get('status', '') else 'for_rent'
# #                     self.object.is_active = True
# #                     self.object.published_at = timezone.now()
# #                     self.object.expires_at = timezone.now() + timezone.timedelta(days=90)
# #                 elif publish_option == 'schedule' and publish_schedule:
# #                     self.object.status = 'for_sale' if 'sale' in self.request.POST.get('status', '') else 'for_rent'
# #                     self.object.is_active = False
# #                     self.object.published_at = publish_schedule
# #                     self.object.expires_at = publish_schedule + timezone.timedelta(days=90)
# #                 else:
# #                     self.object.status = 'draft'
# #                     self.object.is_active = False
                
# #                 # Set premium options
# #                 self.object.is_featured = self.request.POST.get('is_featured') == 'true'
# #                 self.object.is_premium = self.request.POST.get('is_highlighted') == 'true'
                
# #                 # Generate ref_id if not present
# #                 if not self.object.ref_id:
# #                     import random
# #                     import string
# #                     prefix = "PROP"
# #                     timestamp = timezone.now().strftime('%y%m%d')
# #                     random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
# #                     self.object.ref_id = f"{prefix}{timestamp}{random_str}"
                
# #                 self.object.save()
                
# #                 # Save amenities
# #                 amenities = self.request.POST.getlist('amenities')
# #                 if amenities:
# #                     self.object.amenities.set(amenities)
                
# #                 # Handle image uploads - Save PropertyImage instances
# #                 primary_set = False
                
# #                 for i, image_file in enumerate(images):
# #                     if image_file and image_file.size > 0:
# #                         # Create PropertyImage instance
# #                         property_image = PropertyImage(
# #                             property=self.object,
# #                             image=image_file,
# #                             order=i,
# #                             is_primary=not primary_set,
# #                             caption=f"Property Image {i+1}"
# #                         )
# #                         property_image.save()
                        
# #                         if property_image.is_primary:
# #                             primary_set = True
                
# #                 # Update membership usage if property is active
# #                 if self.object.is_active:
# #                     try:
# #                         membership = self.request.user.membership
# #                         if membership.listings_used < membership.plan.max_active_listings:
# #                             membership.listings_used += 1
# #                             membership.save(update_fields=['listings_used'])
# #                     except (UserMembership.DoesNotExist, AttributeError):
# #                         pass
                
# #                 # Send success message
# #                 success_message = f'Property "{self.object.title}" created successfully! '
# #                 if publish_option == 'publish':
# #                     success_message += 'It is now live on the website.'
# #                 elif publish_option == 'schedule':
# #                     success_message += f'It is scheduled to publish on {publish_schedule}.'
# #                 else:
# #                     success_message += 'You can publish it from your dashboard.'
                
# #                 messages.success(self.request, success_message)
                
# #                 # Handle AJAX request
# #                 if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
# #                     return JsonResponse({
# #                         'success': True,
# #                         'message': 'Property created successfully!',
# #                         'redirect_url': reverse('seller_property_detail', kwargs={'slug': self.object.slug}),
# #                         'property_id': self.object.id
# #                     })
                
# #                 # Redirect to property detail
# #                 return redirect('seller_property_detail', slug=self.object.slug)
                
# #         except Exception as e:
# #             logger.error(f"Error creating property: {e}", exc_info=True)
            
# #             # Handle AJAX request
# #             if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
# #                 return JsonResponse({
# #                     'success': False,
# #                     'error': 'Unable to create property. Please check all fields and try again.',
# #                     'detail': str(e) if settings.DEBUG else ''
# #                 }, status=500)
            
# #             messages.error(
# #                 self.request,
# #                 'An error occurred while creating the property. Please try again.'
# #             )
# #             return self.form_invalid(form)
    
# #     def form_invalid(self, form):
# #         """Handle invalid form submission"""
# #         # Log form errors
# #         logger.error(f"Form errors: {form.errors}")
        
# #         # Add form errors to messages
# #         for field, errors in form.errors.items():
# #             for error in errors:
# #                 messages.error(self.request, f"{field}: {error}")
        
# #         return super().form_invalid(form)


# # class SellerPropertyUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
# #     """Update property view for seller dashboard"""
# #     model = Property
# #     form_class = PropertyUpdateForm
# #     template_name = 'dashboard/seller/property_edit.html'
# #     slug_field = 'slug'
# #     slug_url_kwarg = 'slug'
    
# #     def test_func(self):
# #         """Verify that current user owns the property"""
# #         property_obj = self.get_object()
# #         return property_obj.owner == self.request.user or self.request.user.is_staff
    
# #     def handle_no_permission(self):
# #         messages.error(self.request, "You don't have permission to edit this property.")
# #         return redirect('seller_properties')
    
# #     def get_form_kwargs(self):
# #         """Pass request and user to form"""
# #         kwargs = super().get_form_kwargs()
# #         kwargs['user'] = self.request.user
# #         kwargs['request'] = self.request
# #         return kwargs
    
# #     def get_context_data(self, **kwargs):
# #         """Add additional context"""
# #         from .seller_dashboard import get_seller_context
# #         context = super().get_context_data(**kwargs)
        
# #         # Get seller context
# #         seller_context = get_seller_context(self.request.user, 'properties')
# #         context.update(seller_context)
        
# #         # Get existing images
# #         context['existing_images'] = self.object.images.all().order_by('order')
        
# #         # Get categories and amenities
# #         context['categories'] = PropertyCategory.objects.filter(is_active=True)
# #         context['amenities'] = Amenity.objects.filter(is_active=True)
# #         context['selected_amenities'] = self.object.amenities.all()
        
# #         # Add page title
# #         context['page_title'] = f'Edit {self.object.title}'
        
# #         return context
    
# #     def form_valid(self, form):
# #         """Handle successful form update"""
# #         try:
# #             with transaction.atomic():
# #                 # Save property updates
# #                 self.object = form.save(commit=False)
# #                 self.object.last_modified_by = self.request.user
# #                 self.object.save()
                
# #                 # Save amenities
# #                 amenities = form.cleaned_data.get('amenities', [])
# #                 self.object.amenities.set(amenities)
                
# #                 # Handle new image uploads
# #                 new_images = self.request.FILES.getlist('new_images')
# #                 if new_images:
# #                     for image_file in new_images:
# #                         PropertyImage.objects.create(
# #                             property=self.object,
# #                             image=image_file
# #                         )
                
# #                 # Handle image deletions
# #                 delete_images = self.request.POST.getlist('delete_images')
# #                 if delete_images:
# #                     PropertyImage.objects.filter(
# #                         id__in=delete_images,
# #                         property=self.object
# #                     ).delete()
                
# #                 # Handle image ordering
# #                 order_data = self.request.POST.get('image_order')
# #                 if order_data:
# #                     self._update_image_order(order_data)
                
# #                 messages.success(self.request, 'Property updated successfully!')
# #                 return redirect('seller_property_detail', slug=self.object.slug)
                
# #         except Exception as e:
# #             logger.error(f"Error updating property {self.object.id}: {e}", exc_info=True)
# #             messages.error(self.request, 'An error occurred while updating the property.')
# #             return self.form_invalid(form)
    
# #     def _update_image_order(self, order_data: str):
# #         """Update image ordering"""
# #         try:
# #             order_mapping = {}
# #             for item in order_data.split(','):
# #                 if ':' in item:
# #                     img_id, order = item.split(':')
# #                     order_mapping[int(img_id)] = int(order)
            
# #             for image in self.object.images.all():
# #                 if image.id in order_mapping:
# #                     image.order = order_mapping[image.id]
# #                     image.save(update_fields=['order'])
# #         except Exception as e:
# #             logger.warning(f"Error updating image order: {e}")


# @login_required
# @require_POST
# def seller_delete_property(request, slug):
#     """Soft delete property from seller dashboard"""
#     property_obj = get_object_or_404(Property, slug=slug, owner=request.user)
    
#     try:
#         # Soft delete by marking as archived
#         property_obj.status = 'archived'
#         property_obj.is_active = False
#         property_obj.save(update_fields=['status', 'is_active', 'updated_at'])
        
#         # Decrement user's listing count
#         try:
#             request.user.membership.decrement_listing_count()
#         except UserMembership.DoesNotExist:
#             pass
        
#         messages.success(request, f'Property "{property_obj.title}" has been archived.')
#         logger.info(f"Property archived: {property_obj.id} by user: {request.user.id}")
        
#     except Exception as e:
#         logger.error(f"Error deleting property {property_obj.id}: {e}", exc_info=True)
#         messages.error(request, 'An error occurred while deleting the property.')
    
#     return redirect('seller_properties')


# @login_required
# @require_POST
# def seller_toggle_featured(request, slug):
#     """Toggle featured status for property from seller dashboard"""
#     property_obj = get_object_or_404(Property, slug=slug, owner=request.user)
    
#     try:
#         # Check if user can feature property
#         membership = request.user.membership
#         if not membership.can_feature_property:
#             messages.error(
#                 request,
#                 f'You have used all your featured listings for this month. '
#                 f'Limit: {membership.plan.max_featured_listings} per month.'
#             )
#             return redirect('seller_properties')
        
#         # Toggle featured status
#         property_obj.is_featured = not property_obj.is_featured
        
#         if property_obj.is_featured:
#             # Set featured expiry (30 days)
#             property_obj.featured_until = timezone.now() + timezone.timedelta(days=30)
#             membership.increment_featured_count()
#             message = 'Property marked as featured!'
#         else:
#             property_obj.featured_until = None
#             message = 'Property removed from featured listings.'
        
#         property_obj.save()
        
#         messages.success(request, message)
        
#     except UserMembership.DoesNotExist:
#         messages.error(request, 'You need an active membership to feature properties.')
#     except AttributeError:
#         messages.error(request, 'You need an active membership to feature properties.')
#     except Exception as e:
#         logger.error(f"Error toggling featured status for property {property_obj.id}: {e}")
#         messages.error(request, 'An error occurred. Please try again.')
    
#     return redirect('seller_properties')




# @login_required
# @require_POST
# def seller_publish_property(request, slug):
#     """Publish draft property"""
#     property_obj = get_object_or_404(Property, slug=slug, owner=request.user)
    
#     try:
#         # Check if property can be published
#         if property_obj.status != 'draft':
#             messages.error(request, 'Only draft properties can be published.')
#             return redirect('seller_property_detail', slug=slug)
        
#         # Check membership limits
#         membership = request.user.membership
#         if not membership.can_list_property:
#             messages.error(
#                 request,
#                 'You have reached your listing limit. Please upgrade your membership.'
#             )
#             return redirect('seller_packages')
        
#         # Publish property
#         property_obj.status = 'for_sale' if 'sale' in property_obj.status else 'for_rent'
#         property_obj.is_active = True
#         property_obj.published_at = timezone.now()
#         property_obj.expires_at = timezone.now() + timezone.timedelta(days=90)
#         property_obj.save()
        
#         messages.success(request, 'Property published successfully! It is now live on the website.')
        
#     except UserMembership.DoesNotExist:
#         messages.error(request, 'You need an active membership to publish properties.')
#     except Exception as e:
#         logger.error(f"Error publishing property {property_obj.id}: {e}")
#         messages.error(request, 'An error occurred while publishing the property.')
    
#     return redirect('seller_property_detail', slug=slug)


# @login_required
# @require_POST
# def seller_pause_property(request, slug):
#     """Pause active property"""
#     property_obj = get_object_or_404(Property, slug=slug, owner=request.user)
    
#     try:
#         if property_obj.is_active:
#             property_obj.is_active = False
#             property_obj.save()
#             messages.success(request, 'Property paused successfully.')
#         else:
#             messages.info(request, 'Property is already paused.')
        
#     except Exception as e:
#         logger.error(f"Error pausing property {property_obj.id}: {e}")
#         messages.error(request, 'An error occurred while pausing the property.')
    
#     return redirect('seller_property_detail', slug=slug)


# @login_required
# @require_POST
# def seller_unpause_property(request, slug):
#     """Unpause paused property"""
#     property_obj = get_object_or_404(Property, slug=slug, owner=request.user)
    
#     try:
#         if not property_obj.is_active and property_obj.status not in ['expired', 'archived']:
#             property_obj.is_active = True
#             property_obj.save()
#             messages.success(request, 'Property activated successfully.')
#         else:
#             messages.info(request, 'Property cannot be activated.')
        
#     except Exception as e:
#         logger.error(f"Error activating property {property_obj.id}: {e}")
#         messages.error(request, 'An error occurred while activating the property.')
    
#     return redirect('seller_property_detail', slug=slug)


# @login_required
# def seller_property_quick_actions(request, slug, action):
#     """Handle quick actions for property"""
#     property_obj = get_object_or_404(Property, slug=slug, owner=request.user)
    
#     try:
#         if action == 'boost':
#             # This would trigger boost modal
#             pass
#         elif action == 'share':
#             # Generate shareable link
#             pass
#         elif action == 'renew':
#             property_obj.renew(request.user)
#             messages.success(request, 'Property renewed successfully.')
#         elif action == 'duplicate':
#             # Duplicate property
#             new_property = property_obj.duplicate(request.user)
#             messages.success(request, f'Property duplicated as "{new_property.title}".')
#             return redirect('seller_property_detail', slug=new_property.slug)
        
#     except Exception as e:
#         logger.error(f"Error performing action {action} on property {property_obj.id}: {e}")
#         messages.error(request, f'Error performing {action} action.')
    
#     return redirect('seller_property_detail', slug=slug)


# # ======================================================================
# #  AJAX Property Views
# # ======================================================================

# @login_required
# @require_GET
# def ajax_get_subcategories(request):
#     """AJAX endpoint for getting subcategories"""
#     category_id = request.GET.get('category')

#     if not category_id:
#         return JsonResponse({'error': 'Category ID required'}, status=400)

#     try:
#         subcategories = PropertySubCategory.objects.filter(
#             category_id=category_id,
#             is_active=True
#         ).values('id', 'name')

#         return JsonResponse({
#             'success': True,
#             'subcategories': list(subcategories)
#         })
#     except Exception as e:
#         logger.error(f"Error getting subcategories: {e}")
#         return JsonResponse({'success': False, 'error': 'Internal server error'}, status=500)


# @login_required
# @require_POST
# def ajax_delete_property_image(request, image_id):
#     """Delete property image via AJAX"""
#     try:
#         image = PropertyImage.objects.get(id=image_id, property__owner=request.user)
#         image.delete()
        
#         return JsonResponse({
#             'success': True,
#             'message': 'Image deleted successfully'
#         })
        
#     except PropertyImage.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'error': 'Image not found or permission denied'
#         }, status=404)
#     except Exception as e:
#         logger.error(f"Error deleting property image: {e}")
#         return JsonResponse({
#             'success': False,
#             'error': 'Internal server error'
#         }, status=500)


# @login_required
# @require_POST
# def ajax_set_primary_image(request, image_id):
#     """Set property image as primary via AJAX"""
#     try:
#         image = PropertyImage.objects.get(id=image_id, property__owner=request.user)
        
#         # Unset current primary
#         PropertyImage.objects.filter(
#             property=image.property,
#             is_primary=True
#         ).update(is_primary=False)
        
#         # Set new primary
#         image.is_primary = True
#         image.save()
        
#         return JsonResponse({
#             'success': True,
#             'message': 'Primary image updated successfully'
#         })
        
#     except PropertyImage.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'error': 'Image not found or permission denied'
#         }, status=404)
#     except Exception as e:
#         logger.error(f"Error setting primary image: {e}")
#         return JsonResponse({
#             'success': False,
#             'error': 'Internal server error'
#         }, status=500)


# @login_required
# @require_GET
# def ajax_check_listing_limit(request):
#     """Check if user can list more properties"""
#     try:
#         membership = request.user.membership
#         can_list = membership.can_list_property
#         remaining = membership.listings_remaining

#         return JsonResponse({
#             'success': True,
#             'can_list': can_list,
#             'remaining': remaining if remaining != 'Unlimited' else -1,
#             'message': f'You can list {remaining} more properties.' if can_list else 'Listing limit reached.'
#         })

#     except UserMembership.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'can_list': False,
#             'message': 'No active membership found.'
#         })
#     except Exception as e:
#         logger.error(f"Error checking listing limit: {e}")
#         return JsonResponse({
#             'success': False,
#             'error': 'Internal server error'
#         }, status=500)
        
# @require_GET
# @csrf_exempt
# def ajax_get_average_price(request):
#     """Get average price for a city - AJAX endpoint"""
#     city = request.GET.get('city', '').strip()
    
#     if not city:
#         return JsonResponse({
#             'success': False,
#             'error': 'City parameter is required'
#         })
    
#     try:
#         # Get average price for the city
#         avg_price_data = Property.objects.filter(
#             city__iexact=city,
#             is_active=True,
#             area__gt=0,
#             price__gt=0
#         ).exclude(
#             Q(status='draft') | Q(status='expired') | Q(status='archived')
#         ).aggregate(
#             avg_price=Avg('price'),
#             avg_area=Avg('area'),
#             count=models.Count('id')
#         )
        
#         avg_price = avg_price_data['avg_price']
#         avg_area = avg_price_data['avg_area'] or 1000  # Default 1000 sqft
#         count = avg_price_data['count']
        
#         if avg_price and avg_area > 0:
#             avg_price_per_sqft = avg_price / avg_area
#         else:
#             # Return default averages if no data
#             avg_price_per_sqft = None
        
#         # Get price range for the city
#         price_range = Property.objects.filter(
#             city__iexact=city,
#             is_active=True,
#             price__gt=0
#         ).exclude(
#             Q(status='draft') | Q(status='expired') | Q(status='archived')
#         ).aggregate(
#             min_price=models.Min('price'),
#             max_price=models.Max('price')
#         )
        
#         return JsonResponse({
#             'success': True,
#             'city': city,
#             'average_price': float(avg_price) if avg_price else None,
#             'average_price_per_sqft': float(avg_price_per_sqft) if avg_price_per_sqft else None,
#             'property_count': count,
#             'min_price': float(price_range['min_price']) if price_range['min_price'] else None,
#             'max_price': float(price_range['max_price']) if price_range['max_price'] else None,
#             'suggested_price_per_sqft': get_suggested_price_range(city) if avg_price_per_sqft else None
#         })
        
#     except Exception as e:
#         logger.error(f"Error getting average price for city {city}: {e}")
#         return JsonResponse({
#             'success': False,
#             'error': str(e)
#         })


# def get_suggested_price_range(city):
#     """Get suggested price range for a city"""
#     # You can customize this based on your business logic
#     # For now, return some default ranges
#     city_lower = city.lower()
    
#     # Default price ranges per sqft based on Indian cities
#     price_ranges = {
#         'mumbai': {'min': 15000, 'max': 45000},
#         'delhi': {'min': 8000, 'max': 25000},
#         'bangalore': {'min': 6000, 'max': 15000},
#         'chennai': {'min': 5000, 'max': 12000},
#         'hyderabad': {'min': 4500, 'max': 10000},
#         'pune': {'min': 5000, 'max': 12000},
#         'kolkata': {'min': 4000, 'max': 9000},
#         'ahmedabad': {'min': 3000, 'max': 8000},
#     }
    
#     # Check for partial matches
#     for key, value in price_ranges.items():
#         if key in city_lower:
#             return value
    
#     # Default range for other cities
#     return {'min': 3000, 'max': 8000}        