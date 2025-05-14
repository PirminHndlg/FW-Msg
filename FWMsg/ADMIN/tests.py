from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from Global.models import CustomUser, PersonCluster
from ORG.models import Organisation
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.base import ContentFile

class AdminViewsTest(TestCase):
    def setUp(self):
        # Create test image for logo
        image = Image.new('RGB', (1, 1), color='red')
        image_io = BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        self.logo_img = SimpleUploadedFile(
            name='test_logo.png',
            content=image_io.read(),
            content_type='image/png'
        )
        
        # Create test organisation
        self.org = Organisation.objects.create(
            name='Test Org',
            email='test@example.com',
            website='https://test.com',
            logo=self.logo_img
        )
        
        # Create test person cluster
        self.person_cluster_admin = PersonCluster.objects.create(
            org=self.org,
            name='Test Person Cluster Admin',
            view='A'
        )
        
        # Create User
        self.admin_user = get_user_model().objects.create_user(
            username='admin',
            password='testpass123',
            first_name='Test',
            last_name='Admin'
        )
        
        # Create CustomUser for volunteer
        self.custom_user = CustomUser.objects.create(
            org=self.org,
            user=self.admin_user,
            person_cluster=self.person_cluster_admin
        )
        
        # Login user
        self.client.login(username='admin', password='testpass123')

    def test_admin_home_view(self):
        """Test the admin home view"""
        response = self.client.get(reverse('admin_home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin_home.html')
        self.assertContains(response, 'Test Org')
        self.assertContains(response, 'test@example.com')
        self.assertContains(response, 'https://test.com')

    def test_create_organization(self):
        """Test creating a new organization"""
        # Create new image for new organization
        image = Image.new('RGB', (1, 1), color='blue')
        image_io = BytesIO()
        image.save(image_io, format='PNG')
        image_io.seek(0)
        
        new_logo = SimpleUploadedFile(
            name='new_logo.png',
            content=image_io.read(),
            content_type='image/png'
        )

        # Test POST request to create new organization
        response = self.client.post(
            reverse('admin_org'),
            {
                'name': 'New Org',
                'email': 'new@example.com',
                'website': 'https://new.org',
                'logo': new_logo,
                'farbe': '#007bff',
                'text_color_on_org_color': '#000000'
            },
            format='multipart'
        )
        
        # Print form errors if any
        if response.status_code == 200:
            form = response.context['form']
            print("Form errors:", form.errors)
        
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Verify the organization was created
        new_org = Organisation.objects.get(name='New Org')
        self.assertEqual(new_org.email, 'new@example.com')
        self.assertEqual(new_org.website, 'https://new.org')
        self.assertTrue(new_org.logo)  # Check if logo was uploaded
        self.assertTrue(new_org.logo.name.startswith('logos/'))  # Check if logo is in correct directory

    def test_edit_organization(self):
        """Test editing an existing organization"""
        # Test GET request to edit form
        response = self.client.get(reverse('admin_org_id', args=[self.org.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin_org.html')
        self.assertContains(response, 'Test Org')
        self.assertContains(response, 'test@example.com')
        
        # Test POST request to update organization
        response = self.client.post(
            reverse('admin_org_id', args=[self.org.id]),
            {
                'name': 'Updated Org',
                'email': 'updated@example.com',
                'website': 'https://updated.org',
                'farbe': '#007bff',
                'text_color_on_org_color': '#000000'
            }
        )
        
        # Print form errors if any
        if response.status_code == 200:
            form = response.context['form']
            print("Form errors:", form.errors)
        
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Verify the update
        updated_org = Organisation.objects.get(id=self.org.id)
        self.assertEqual(updated_org.name, 'Updated Org')
        self.assertEqual(updated_org.email, 'updated@example.com')
        self.assertEqual(updated_org.website, 'https://updated.org')

    def test_edit_organization_with_new_logo(self):
        """Test editing an organization with a new logo"""
        # Create new image for logo update
        image = Image.new('RGB', (100, 100), color='green')
        image_io = BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        new_logo = SimpleUploadedFile(
            name='updated_logo.jpg',
            content=image_io.read(),
            content_type='image/jpeg'
        )

        # Test POST request to update organization with new logo
        response = self.client.post(
            reverse('admin_org_id', args=[self.org.id]),
            {
                'name': 'Test Org',
                'email': 'test@example.com',
                'website': 'https://test.com',
                'farbe': '#007bff',
                'text_color_on_org_color': '#000000',
                'logo': new_logo
            }
        )
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Verify the update
        updated_org = Organisation.objects.get(id=self.org.id)
        self.assertNotEqual(updated_org.logo.name, self.org.logo.name)

    def test_unauthorized_access(self):
        """Test unauthorized access to admin views"""
        # Logout the admin user
        self.client.logout()
        
        # Try to access admin home
        response = self.client.get(reverse('admin_home'))
        self.assertEqual(response.status_code, 302)  # Should redirect to login
        
        # Try to access organization edit
        response = self.client.get(reverse('admin_org_id', args=[self.org.id]))
        self.assertEqual(response.status_code, 302)  # Should redirect to login
