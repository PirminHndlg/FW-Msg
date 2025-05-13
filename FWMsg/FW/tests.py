from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, date
from FW.models import Freiwilliger
from ORG.models import Organisation
from Global.models import (
    Aufgabe2, UserAufgaben, PersonCluster, CustomUser,
    Post2, Einsatzland2, Einsatzstelle2
)
from TEAM.models import Team
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile

class FWHomeTests(TestCase):
    def setUp(self):
        """Set up test data for home view tests"""
        self._create_organization()
        self._create_person_clusters()
        self._create_test_users()
        self._create_test_tasks()
        self._create_test_posts()
        
        # Login as volunteer by default
        self.client.login(username='volunteer', password='testpass123')

    def _create_organization(self):
        """Create test organization"""
        image = Image.new('RGB', (1, 1), color='red')
        image_io = BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        logo_img = SimpleUploadedFile(
            name='test_logo.png',
            content=image_io.read(),
            content_type='image/png'
        )
        self.org = Organisation.objects.create(
            name='Test Org',
            email='test@test.com',
            logo=logo_img
        )

    def _create_person_clusters(self):
        """Create person clusters for organization and volunteers"""
        self.person_cluster_fw = PersonCluster.objects.create(
            org=self.org,
            name='Test Person Cluster FW',
            view='F',
            aufgaben=True,
            calendar=True,
            dokumente=True,
            ampel=True,
            notfallkontakt=True,
            bilder=True
        )

    def _create_test_users(self):
        """Create test users and volunteers"""
        # Create volunteer user
        self.volunteer_user = get_user_model().objects.create_user(
            username='volunteer',
            password='testpass123',
            first_name='Test',
            last_name='Volunteer'
        )
        
        # Create volunteer
        self.freiwilliger = Freiwilliger.objects.create(
            org=self.org,
            user=self.volunteer_user,
            start_geplant=date.today() + timedelta(days=30)
        )
        
        # Create CustomUser for volunteer
        self.custom_user = CustomUser.objects.create(
            org=self.org,
            user=self.volunteer_user,
            person_cluster=self.person_cluster_fw
        )

    def _create_test_tasks(self):
        """Create test tasks"""
        self.aufgabe = Aufgabe2.objects.create(
            org=self.org,
            name='Test Aufgabe',
            beschreibung='Test Beschreibung'
        )
        self.aufgabe.person_cluster.add(self.person_cluster_fw)

        # Create completed task
        self.completed_task = UserAufgaben.objects.create(
            org=self.org,
            user=self.volunteer_user,
            aufgabe=self.aufgabe,
            erledigt=True,
            erledigt_am=timezone.now()
        )

        # Create pending task
        self.pending_task = UserAufgaben.objects.create(
            org=self.org,
            user=self.volunteer_user,
            aufgabe=self.aufgabe,
            pending=True
        )

        # Create open task
        self.open_task = UserAufgaben.objects.create(
            org=self.org,
            user=self.volunteer_user,
            aufgabe=self.aufgabe
        )

    def _create_test_posts(self):
        """Create test posts"""
        self.post = Post2.objects.create(
            org=self.org,
            user=self.volunteer_user,
            title='Test Post',
            text='Test Content',
            date=timezone.now()
        )
        self.post.person_cluster.add(self.person_cluster_fw)

    def test_home_view(self):
        """Test that the home view loads correctly"""
        response = self.client.get(reverse('fw_home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'homeFw.html')

    def test_home_view_task_statistics(self):
        """Test task statistics in home view"""
        response = self.client.get(reverse('fw_home'))
        self.assertEqual(response.status_code, 200)
        
        # Check task statistics
        self.assertIn('aufgaben', response.context)
        aufgaben = response.context['aufgaben']
        
        # Verify task counts
        self.assertEqual(len(aufgaben['erledigt']), 1)  # One completed task
        self.assertEqual(len(aufgaben['pending']), 1)   # One pending task
        self.assertEqual(len(aufgaben['offen']), 1)     # One open task
        
        # Verify percentages
        self.assertEqual(aufgaben['erledigt_prozent'], 33)  # 1/3 tasks completed
        self.assertEqual(aufgaben['pending_prozent'], 33)   # 1/3 tasks pending
        self.assertEqual(aufgaben['offen_prozent'], 33)     # 1/3 tasks open

    def test_home_view_days_until_start(self):
        """Test days until start calculation"""
        response = self.client.get(reverse('fw_home'))
        self.assertEqual(response.status_code, 200)
        
        # Check days until start
        self.assertIn('days_until_start', response.context)
        self.assertEqual(response.context['days_until_start'], 30)  # Set in _create_test_users

    def test_home_view_posts(self):
        """Test posts display in home view"""
        response = self.client.get(reverse('fw_home'))
        self.assertEqual(response.status_code, 200)
        
        # Check posts
        self.assertIn('posts', response.context)
        self.assertEqual(len(response.context['posts']), 1)  # One test post


class FWLaenderinfoTests(TestCase):
    def setUp(self):
        """Set up test data for laenderinfo view tests"""
        self._create_organization()
        self._create_person_clusters()
        self._create_test_users()
        self._create_test_country_data()
        
        # Login as volunteer by default
        self.client.login(username='volunteer', password='testpass123')

    def _create_organization(self):
        """Create test organization"""
        self.org = Organisation.objects.create(
            name='Test Org',
            email='test@test.com',
            telefon='+1234567890',
            website='https://test.org'
        )

    def _create_person_clusters(self):
        """Create person clusters for organization and volunteers"""
        self.person_cluster_fw = PersonCluster.objects.create(
            org=self.org,
            name='Test Person Cluster FW',
            view='F',
            aufgaben=True,
            calendar=True,
            dokumente=True,
            ampel=True,
            notfallkontakt=True,
            bilder=True
        )

    def _create_test_users(self):
        """Create test users and volunteers"""
        # Create volunteer user
        self.volunteer_user = get_user_model().objects.create_user(
            username='volunteer',
            password='testpass123',
            first_name='Test',
            last_name='Volunteer'
        )
        
        # Create referent user
        self.referent_user = get_user_model().objects.create_user(
            username='referent',
            password='testpass123',
            first_name='Test',
            last_name='Referent',
            email='referent@test.com'
        )
        
        # Create volunteer
        self.freiwilliger = Freiwilliger.objects.create(
            org=self.org,
            user=self.volunteer_user
        )
        
        # Create CustomUser for volunteer
        self.custom_user = CustomUser.objects.create(
            org=self.org,
            user=self.volunteer_user,
            person_cluster=self.person_cluster_fw
        )

    def _create_test_country_data(self):
        """Create test country and location data"""
        # Create country
        self.land = Einsatzland2.objects.create(
            org=self.org,
            name='Test Country',
            notfallnummern='Emergency: 112',
            arztpraxen='Test Doctor: +1234567890',
            apotheken='Test Pharmacy: +1234567890',
            informationen='Test Information'
        )
        
        # Create location
        self.einsatzstelle = Einsatzstelle2.objects.create(
            org=self.org,
            name='Test Location',
            botschaft='Test Embassy: +1234567890',
            konsulat='Test Consulate: +1234567890',
            arbeitsvorgesetzter='Test Supervisor: +1234567890',
            partnerorganisation='Test Partner Org',
            mentor='Test Mentor: +1234567890'
        )
        
        # Update volunteer with country and location
        self.freiwilliger.einsatzland2 = self.land
        self.freiwilliger.einsatzstelle2 = self.einsatzstelle
        self.freiwilliger.save()
        
        # Create referent
        self.referent = Team.objects.create(
            org=self.org,
            user=self.referent_user
        )
        self.referent.land.add(self.land)

    def test_laenderinfo_view(self):
        """Test that the laenderinfo view loads correctly"""
        response = self.client.get(reverse('laenderinfo'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'laenderinfo.html')

    def test_laenderinfo_org_cards(self):
        """Test organization cards in laenderinfo view"""
        response = self.client.get(reverse('laenderinfo'))
        self.assertEqual(response.status_code, 200)
        
        # Check organization cards
        self.assertIn('org_cards', response.context)
        org_cards = response.context['org_cards']
        
        # Verify organization card content
        self.assertEqual(len(org_cards), 2)  # Org card + referent card
        self.assertEqual(org_cards[0]['title'], 'Test Org')
        self.assertEqual(org_cards[1]['title'], 'Ansprechpartner:in Test Referent')

    def test_laenderinfo_country_cards(self):
        """Test country cards in laenderinfo view"""
        response = self.client.get(reverse('laenderinfo'))
        self.assertEqual(response.status_code, 200)
        
        # Check country cards
        self.assertIn('country_cards', response.context)
        country_cards = response.context['country_cards']
        
        # Verify country card content
        self.assertTrue(any(card['title'] == 'Reisehinweise' for card in country_cards))
        self.assertTrue(any(card['title'] == 'Notfallnummern' for card in country_cards))
        self.assertTrue(any(card['title'] == 'Botschaft' for card in country_cards))
        self.assertTrue(any(card['title'] == 'Konsulat' for card in country_cards))

    def test_laenderinfo_location_cards(self):
        """Test location cards in laenderinfo view"""
        response = self.client.get(reverse('laenderinfo'))
        self.assertEqual(response.status_code, 200)
        
        # Check location cards
        self.assertIn('location_cards', response.context)
        location_cards = response.context['location_cards']
        
        # Verify location card content
        self.assertTrue(any(card['title'] == 'Arbeitsvorgesetzte:r' for card in location_cards))
        self.assertTrue(any(card['title'] == 'Partnerorganisation' for card in location_cards))
        self.assertTrue(any(card['title'] == 'Mentor:in' for card in location_cards))

    def test_laenderinfo_general_cards(self):
        """Test general cards in laenderinfo view"""
        response = self.client.get(reverse('laenderinfo'))
        self.assertEqual(response.status_code, 200)
        
        # Check general cards
        self.assertIn('general_cards', response.context)
        general_cards = response.context['general_cards']
        
        # Verify general card content
        self.assertTrue(any(card['title'] == 'Arztpraxen' for card in general_cards))
        self.assertTrue(any(card['title'] == 'Apotheken' for card in general_cards))
        self.assertTrue(any(card['title'] == 'Weitere Informationen' for card in general_cards))
