from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from Global.models import CustomUser, Einsatzland2, Einsatzstelle2, PersonCluster, UserAttribute, Attribute
from FW.models import Freiwilliger
from TEAM.models import Team
from django.utils import timezone
import datetime
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from ORG.models import Organisation

class TeamViewsTest(TestCase):
    def setUp(self):
        image = Image.new('RGB', (1, 1), color='red')
        image_io = BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        logo_img = SimpleUploadedFile(
            name='test_logo.png',
            content=image_io.read(),
            content_type='image/png'
        )
        # Create organization
        self.org = Organisation.objects.create(
            name='Test Org',
            email='test@example.com',
            logo=logo_img
        )
        # Create person cluster
        self.person_cluster_team = PersonCluster.objects.create(
            org=self.org,
            name='Test Team',
            view='T'
        )
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        # Create custom user
        self.customuser = CustomUser.objects.create(
            user=self.user,
            org=self.org,
            person_cluster=self.person_cluster_team
        )
        
        # Create test country
        self.land = Einsatzland2.objects.create(
            org=self.org,
            name='Test Country',
            notfallnummern='Emergency: 123',
            arztpraxen='Doctors: 456',
            apotheken='Pharmacies: 789',
            informationen='Test information'
        )
        
        # Create test placement location
        self.einsatzstelle = Einsatzstelle2.objects.create(
            org=self.org,
            name='Test Placement',
            land=self.land,
            partnerorganisation='Test Org',
            arbeitsvorgesetzter='Test Boss',
            mentor='Test Mentor',
            botschaft='Test Embassy',
            konsulat='Test Consulate',
            informationen='Test info'
        )
        
        # Create team member
        self.team = Team.objects.get_or_create(org=self.org, user=self.user)[0]
        self.team.land.add(self.land)
        
        # Create test volunteer
        self.freiwilliger = Freiwilliger.objects.get_or_create(
            org=self.org,
            user=self.user,
            einsatzland2=self.land
        )[0]
        
        # Create test attributes
        self.phone_attr = Attribute.objects.create(
            org=self.org,
            name='Phone',
            type='P'
        )
        self.email_attr = Attribute.objects.create(
            org=self.org,
            name='Email',
            type='E'
        )
        
        # Add attributes to user
        UserAttribute.objects.create(
            org=self.org,
            user=self.user,
            attribute=self.phone_attr,
            value='+1234567890'
        )
        UserAttribute.objects.create(
            org=self.org,
            user=self.user,
            attribute=self.email_attr,
            value='test@example.com'
        )
        
        # Setup client
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

    def test_home_view(self):
        """Test the home view"""
        response = self.client.get(reverse('team_home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'teamHome.html')

    def test_contacts_view(self):
        """Test the contacts view"""
        response = self.client.get(reverse('team_contacts'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'teamContacts.html')
        
        # Check if volunteer data is in context
        self.assertIn('freiwillige', response.context)
        self.assertIn('fw_cards', response.context)
        
        # Verify contact information
        fw_cards = response.context['fw_cards']
        self.assertEqual(len(fw_cards), 1)
        self.assertEqual(fw_cards[0]['title'], 'Test User')
        self.assertTrue(any(item['type'] == 'phone' for item in fw_cards[0]['items']))
        self.assertTrue(any(item['type'] == 'email' for item in fw_cards[0]['items']))

    def test_ampelmeldung_view(self):
        """Test the ampelmeldung view"""
        response = self.client.get(reverse('list_ampel'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'list_ampel.html')
        
        # Check if required context data is present
        self.assertIn('ampel_matrix', response.context)
        self.assertIn('months', response.context)
        self.assertIn('current_month', response.context)


    def test_unauthorized_access(self):
        """Test unauthorized access to team views"""
        # Create a non-team user
        non_team_user = User.objects.create_user(
            username='nonteam',
            password='testpass123'
        )
        self.client.login(username='nonteam', password='testpass123')
        
        # Try to access team views
        views = [
            'team_home',
            'team_contacts',
            'list_ampel',
        ]
        
        for view_name in views:
            response = self.client.get(reverse(view_name))
            self.assertEqual(response.status_code, 403)  # Forbidden
