#!/usr/bin/env python
"""
Test script for property_form.html template functionality
Tests the multi-step form, JavaScript functions, and form validation
"""

import os
import sys
import django
from django.conf import settings
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from bs4 import BeautifulSoup
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RealEstateHub.settings')
django.setup()

from estate_app.models import PropertyCategory, PropertyType, CustomUser, UserMembership, MembershipPlan

class PropertyFormTest(TestCase):
    def setUp(self):
        """Set up test data"""
        self.client = Client()

        # Create test user
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            phone='1234567890'
        )

        # Create membership
        basic_plan = MembershipPlan.objects.create(
            name='Basic',
            slug='basic',
            price=0,
            max_listings=5,
            max_featured=1
        )

        self.membership = UserMembership.objects.create(
            user=self.user,
            plan=basic_plan
        )

        # Create property categories and types
        self.category = PropertyCategory.objects.create(
            name='Residential',
            slug='residential',
            is_active=True
        )

        self.property_type = PropertyType.objects.create(
            name='Apartment',
            slug='apartment',
            category=self.category,
            is_active=True
        )

    def test_property_form_access(self):
        """Test that property form is accessible"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('seller_property_create'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/seller/property_form.html')

        # Check that form contains expected elements
        content = response.content.decode()
        self.assertIn('propertyForm', content)
        self.assertIn('step1', content)
        self.assertIn('step2', content)
        self.assertIn('step3', content)
        self.assertIn('step4', content)

    def test_form_context_data(self):
        """Test that form has required context data"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('seller_property_create'))

        # Check context data
        self.assertIn('categories', response.context)
        self.assertIn('property_types', response.context)
        self.assertIn('amenities_list', response.context)
        self.assertIn('user', response.context)

        # Check that categories and types are populated
        self.assertTrue(len(response.context['categories']) > 0)
        self.assertTrue(len(response.context['property_types']) > 0)

    def test_form_html_structure(self):
        """Test HTML structure of the form"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('seller_property_create'))

        soup = BeautifulSoup(response.content, 'html.parser')

        # Check form exists
        form = soup.find('form', {'id': 'propertyForm'})
        self.assertIsNotNone(form)

        # Check steps exist
        steps = soup.find_all('div', {'class': 'form-step'})
        self.assertEqual(len(steps), 4)

        # Check step indicators
        indicators = soup.find_all('div', {'class': 'step-indicator'})
        self.assertEqual(len(indicators), 4)

        # Check navigation buttons
        next_buttons = soup.find_all('button', {'onclick': 'nextStep()'})
        prev_buttons = soup.find_all('button', {'onclick': 'prevStep()'})
        self.assertTrue(len(next_buttons) > 0)
        self.assertTrue(len(prev_buttons) > 0)

    def test_javascript_functions_present(self):
        """Test that JavaScript functions are present in template"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('seller_property_create'))

        content = response.content.decode()

        # Check JavaScript functions
        js_functions = [
            'nextStep()',
            'prevStep()',
            'goToStep(',
            'validateStep(',
            'updateDynamicSections(',
            'previewPrimaryImage(',
            'previewAdditionalImages(',
            'openMapPicker()',
            'saveAsDraft()'
        ]

        for func in js_functions:
            self.assertIn(func, content, f"JavaScript function {func} not found")

    def test_form_validation_fields(self):
        """Test that required fields have proper validation"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('seller_property_create'))

        soup = BeautifulSoup(response.content, 'html.parser')

        # Check required fields
        required_fields = [
            'id_title',
            'id_description',
            'id_category',
            'id_property_type',
            'id_address',
            'id_city',
            'id_state',
            'id_pincode',
            'id_price',
            'id_carpet_area',
            'id_contact_person',
            'id_contact_phone',
            'id_primary_image'
        ]

        for field_id in required_fields:
            field = soup.find(attrs={'id': field_id})
            if field:
                self.assertTrue(field.get('required') or 'required-field' in field.get('class', []),
                              f"Field {field_id} should be required")

    def test_form_submission_empty(self):
        """Test form submission with empty data"""
        self.client.login(username='testuser', password='testpass123')

        # Submit empty form
        response = self.client.post(reverse('seller_property_create'), {})

        # Should redirect back with errors
        self.assertEqual(response.status_code, 200)
        self.assertIn('errors', response.context)
        self.assertTrue(len(response.context['errors']) > 0)

    def test_form_submission_valid_data(self):
        """Test form submission with valid data"""
        self.client.login(username='testuser', password='testpass123')

        # Create a test image file
        from django.core.files.uploadedfile import SimpleUploadedFile
        image = SimpleUploadedFile(
            "test_image.jpg",
            b"file_content",
            content_type="image/jpeg"
        )

        form_data = {
            'title': 'Test Property',
            'description': 'Test description for property',
            'category': str(self.category.id),
            'property_type': str(self.property_type.id),
            'property_for': 'sale',
            'listing_type': 'basic',
            'address': '123 Test Street',
            'city': 'Test City',
            'state': 'Test State',
            'pincode': '123456',
            'price': '1000000',
            'carpet_area': '1000',
            'contact_person': 'Test Person',
            'contact_phone': '1234567890',
            'primary_image': image,
            'terms': 'on'
        }

        response = self.client.post(reverse('seller_property_create'), form_data)

        # Should redirect to properties list on success
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('seller_properties'))

    def test_step_navigation_javascript(self):
        """Test that step navigation JavaScript variables are set"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('seller_property_create'))

        content = response.content.decode()

        # Check JavaScript variables
        self.assertIn('let currentStep = 1;', content)
        self.assertIn('const totalSteps = 4;', content)

    def test_dynamic_sections(self):
        """Test that dynamic sections are present"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('seller_property_create'))

        soup = BeautifulSoup(response.content, 'html.parser')

        # Check for residential section
        residential_section = soup.find('div', {'id': 'residentialSection'})
        self.assertIsNotNone(residential_section)

        # Check amenities section
        amenities_section = soup.find('div', {'class': 'grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3'})
        self.assertIsNotNone(amenities_section)

    def test_image_upload_fields(self):
        """Test that image upload fields are present"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('seller_property_create'))

        soup = BeautifulSoup(response.content, 'html.parser')

        # Check primary image input
        primary_image = soup.find('input', {'id': 'id_primary_image'})
        self.assertIsNotNone(primary_image)
        self.assertEqual(primary_image.get('type'), 'file')
        self.assertEqual(primary_image.get('accept'), 'image/*')

        # Check additional images input
        additional_images = soup.find('input', {'id': 'id_additional_images'})
        self.assertIsNotNone(additional_images)
        self.assertEqual(additional_images.get('type'), 'file')
        self.assertTrue(additional_images.get('multiple'))

    def test_map_picker_modal(self):
        """Test that map picker modal is present"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('seller_property_create'))

        soup = BeautifulSoup(response.content, 'html.parser')

        # Check map modal
        map_modal = soup.find('div', {'id': 'mapModal'})
        self.assertIsNotNone(map_modal)

        # Check map picker button
        map_button = soup.find('button', {'onclick': 'openMapPicker()'})
        self.assertIsNotNone(map_button)

    def test_form_progress_indicators(self):
        """Test that progress indicators are working"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('seller_property_create'))

        soup = BeautifulSoup(response.content, 'html.parser')

        # Check step indicators
        active_indicator = soup.find('div', {'class': 'step-indicator active'})
        self.assertIsNotNone(active_indicator)

        # Check step connectors
        connectors = soup.find_all('div', {'class': 'step-connector'})
        self.assertEqual(len(connectors), 3)  # 3 connectors for 4 steps

    def run_all_tests(self):
        """Run all tests and report results"""
        import unittest

        # Create test suite
        suite = unittest.TestLoader().loadTestsFromTestCase(PropertyFormTest)

        # Run tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

        # Report results
        print(f"\n{'='*50}")
        print("PROPERTY FORM TEST RESULTS")
        print(f"{'='*50}")

        if result.wasSuccessful():
            print("✅ ALL TESTS PASSED")
            print("The property form is working correctly!")
        else:
            print("❌ SOME TESTS FAILED")
            print(f"Failed tests: {len(result.failures)}")
            print(f"Errors: {len(result.errors)}")

            if result.failures:
                print("\nFAILURES:")
                for test, traceback in result.failures:
                    print(f"- {test}: {traceback}")

            if result.errors:
                print("\nERRORS:")
                for test, traceback in result.errors:
                    print(f"- {test}: {traceback}")

        return result.wasSuccessful()

if __name__ == '__main__':
    # Run the tests
    test_instance = PropertyFormTest()
    test_instance.setUp()

    success = test_instance.run_all_tests()

    if success:
        print("\n🎉 Property form testing completed successfully!")
        print("All functionality appears to be working correctly.")
    else:
        print("\n⚠️  Property form testing found issues that need attention.")
        sys.exit(1)
