from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core import signing
from datetime import datetime, timedelta
from .models import CustomUser, UserAufgaben, Aufgabe2, KalenderEvent, PersonCluster
from ORG.models import Organisation


class KalenderAbbonementTests(TestCase):
    def setUp(self):
        # Create test organization
        self.org = Organisation.objects.create(name="Test Org")
        
        # Create person cluster
        self.person_cluster = PersonCluster.objects.create(
            name="Test Cluster",
            org=self.org,
            view='O'  # Organization view
        )
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.custom_user = CustomUser.objects.create(
            user=self.user,
            org=self.org,
            person_cluster=self.person_cluster
        )
        
        # Create test task
        self.aufgabe = Aufgabe2.objects.create(
            name="Test Aufgabe",
            org=self.org
        )
        
        # Create user task
        self.user_aufgabe = UserAufgaben.objects.create(
            org=self.org,
            user=self.user,
            aufgabe=self.aufgabe,
            faellig=datetime.now().date() + timedelta(days=1)
        )
        
        # Create calendar event
        self.calendar_event = KalenderEvent.objects.create(
            title="Test Event",
            org=self.org,
            start=datetime.now() + timedelta(days=1),
            end=datetime.now() + timedelta(days=1, hours=2)
        )
        self.calendar_event.user.add(self.user)
        
        # Create client
        self.client = Client()
        
        # Generate token
        self.token = signing.dumps({'user_id': self.user.id})

    def test_invalid_token(self):
        """Test that invalid token returns error"""
        response = self.client.get(reverse('kalender_abbonement', args=['invalid_token']))
        self.assertEqual(response.status_code, 302)  # Redirects to index

    def test_direct_download(self):
        """Test direct download of calendar file"""
        response = self.client.get(reverse('kalender_abbonement', args=[self.token]))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/calendar')
        self.assertTrue('attachment' in response['Content-Disposition'])
        self.assertTrue('.ics' in response['Content-Disposition'])

    def test_calendar_app_request(self):
        """Test calendar app request"""
        headers = {'HTTP_ACCEPT': 'text/calendar'}
        response = self.client.get(
            reverse('kalender_abbonement', args=[self.token]),
            **headers
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/calendar')
        self.assertTrue('inline' in response['Content-Disposition'])
        self.assertTrue('.ics' in response['Content-Disposition'])

    def test_calendar_format_param(self):
        """Test request with format=ical parameter"""
        response = self.client.get(
            reverse('kalender_abbonement', args=[self.token]),
            {'format': 'ical'}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/calendar')
        self.assertTrue('inline' in response['Content-Disposition'])

    def test_calendar_user_agent(self):
        """Test request with calendar in User-Agent"""
        headers = {'HTTP_USER_AGENT': 'Mozilla/5.0 (Calendar App)'}
        response = self.client.get(
            reverse('kalender_abbonement', args=[self.token]),
            **headers
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/calendar')
        self.assertTrue('inline' in response['Content-Disposition'])

    def test_calendar_content(self):
        """Test that calendar content includes both tasks and events"""
        response = self.client.get(reverse('kalender_abbonement', args=[self.token]))
        content = response.content.decode('utf-8')
        
        # Check for task
        self.assertIn(self.aufgabe.name, content)
        
        # Check for calendar event
        self.assertIn(self.calendar_event.title, content)
        
        # Check for URLs
        self.assertIn(reverse('aufgaben_detail', args=[self.user_aufgabe.id]), content)
        self.assertIn(reverse('kalender_event', args=[self.calendar_event.id]), content)

    def test_organization_access(self):
        """Test that organization members can access their calendar"""
        # Create another person cluster for the other user
        other_person_cluster = PersonCluster.objects.create(
            name="Other Cluster",
            org=self.org,
            view='F'  # Freiwillige view
        )
        
        # Create another user in the same organization
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        CustomUser.objects.create(
            user=other_user,
            org=self.org,
            person_cluster=other_person_cluster
        )
        
        # Create token for other user
        other_token = signing.dumps({'user_id': other_user.id})
        
        # Test access
        response = self.client.get(reverse('kalender_abbonement', args=[other_token]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/calendar')
