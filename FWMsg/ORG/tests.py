from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from FW.models import Freiwilliger
from .models import Organisation
from Global.models import (
    Aufgabe2, Bilder2, BilderGallery2, UserAufgaben, PersonCluster, CustomUser,
    UserAttribute, Attribute
)
import json
from PIL import Image
from io import BytesIO

class AufgabenTableTests(TestCase):
    def setUp(self):
        """Set up test data that will be used across all tests"""
        self._create_organization()
        self._create_person_clusters()
        self._create_test_users()
        self._create_test_tasks(self.person_cluster_fw)
        self._create_admin_user()
        
        # Login as admin by default
        self.client.login(username='admin', password='adminpass123')

    def _create_organization(self):
        """Create test organization"""
        self.org = Organisation.objects.create(
            name='Test Org',
            email='test@test.com',
        )

    def _create_person_clusters(self):
        """Create person clusters for organization and volunteers"""
        self.person_cluster_org = PersonCluster.objects.create(
            org=self.org,
            name='Test Person Cluster Org',
            view='O',
            aufgaben=True,
            calendar=True,
            dokumente=True,
            ampel=True,
            notfallkontakt=True,
            bilder=True
        )
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
        # Create regular user
        self.user = get_user_model().objects.create_user(
            username='testuser',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        # Create volunteer
        self.freiwilliger = Freiwilliger.objects.create(
            org=self.org,
            user=self.user
        )
        
        # Create CustomUser for volunteer
        self.custom_user = CustomUser.objects.create(
            org=self.org,
            user=self.user,
            person_cluster=self.person_cluster_fw
        )

    def _create_test_tasks(self, person_cluster=None):
        """Create test tasks"""
        self.aufgabe = Aufgabe2.objects.create(
            org=self.org,
            name='Test Aufgabe',
            beschreibung='Test Beschreibung'
        )
        if person_cluster:
            self.aufgabe.person_cluster.add(person_cluster)

    def _create_admin_user(self):
        """Create admin user"""
        self.admin_user = get_user_model().objects.create_user(
            username='admin',
            password='adminpass123',
            first_name='Admin',
            last_name='User',
        )
        self.admin_custom_user = CustomUser.objects.create(
            org=self.org,
            user=self.admin_user,
            person_cluster=self.person_cluster_org
        )
        
    def _create_additional_volunteer(self):
        """Helper method to create an additional volunteer"""
        user = get_user_model().objects.create_user(
            username='testuser2',
            password='testpass123',
            first_name='Test2',
            last_name='User2'
        )
        freiwilliger = Freiwilliger.objects.create(
            org=self.org,
            user=user
        )
        CustomUser.objects.create(
            org=self.org,
            user=user,
            person_cluster=self.person_cluster_fw
        )
        return user, freiwilliger

    def _create_task_assignment(self, user, aufgabe, days_until_due=7):
        """Helper method to create a task assignment"""
        return UserAufgaben.objects.create(
            org=self.org,
            user=user,
            aufgabe=aufgabe,
            faellig=timezone.now() + timedelta(days=days_until_due)
        )

    def test_list_aufgaben_view(self):
        """Test that the aufgaben list view loads correctly"""
        response = self.client.get(reverse('list_aufgaben_table'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'list_aufgaben_table.html')

    def test_aufgaben_status_changes(self):
        """Test task status changes (erledigt, pending)"""
        freiwilliger_aufgabe = self._create_task_assignment(
            self.freiwilliger.user,
            self.aufgabe
        )

        # Test marking as completed
        response = self.client.post(reverse('list_aufgaben_table'), {
            'aufgabe_id': freiwilliger_aufgabe.id,
            'erledigt': 'True',
            'pending': 'False'
        })
        
        freiwilliger_aufgabe.refresh_from_db()
        self.assertTrue(freiwilliger_aufgabe.erledigt)
        self.assertFalse(freiwilliger_aufgabe.pending)

        # Test marking as pending
        response = self.client.post(reverse('list_aufgaben_table'), {
            'aufgabe_id': freiwilliger_aufgabe.id,
            'erledigt': 'False',
            'pending': 'True'
        })
        
        freiwilliger_aufgabe.refresh_from_db()
        self.assertFalse(freiwilliger_aufgabe.erledigt)
        self.assertTrue(freiwilliger_aufgabe.pending)

    def test_task_assignment(self):
        """Test assigning tasks to volunteers"""
        response = self.client.get(
            f"{reverse('list_aufgaben_table')}?u={self.freiwilliger.user.id}&a={self.aufgabe.id}"
        )
        self.assertEqual(response.status_code, 302)
        
        self.assertTrue(
            UserAufgaben.objects.filter(
                org=self.org,
                user=self.freiwilliger.user,
                aufgabe=self.aufgabe
            ).exists()
        )
        
    def test_task_assignment_all(self):
        """Test assigning tasks to all volunteers"""
        # Create a new task
        new_aufgabe = Aufgabe2.objects.create(
            org=self.org,
            name='Test Aufgabe 2',
            beschreibung='Test Beschreibung 2'
        )
        new_aufgabe.person_cluster.add(self.person_cluster_fw)
        
        # Create another volunteer
        user2, freiwilliger2 = self._create_additional_volunteer()
        
        response = self.client.get(
            f"{reverse('list_aufgaben_table')}?u=all&a={new_aufgabe.id}"
        )
        self.assertEqual(response.status_code, 302)
        
        # Verify assignments
        self.assertEqual(
            UserAufgaben.objects.filter(
                org=self.org,
                aufgabe=new_aufgabe
            ).count(),
            Freiwilliger.objects.filter(org=self.org).count()
        )
        
        # Verify specific assignments
        for user in [self.freiwilliger.user, user2]:
            self.assertTrue(
                UserAufgaben.objects.filter(
                    org=self.org,
                    user=user,
                    aufgabe=new_aufgabe
                ).exists()
            )
        
    def test_task_deletion(self):
        """Test deleting tasks"""
        freiwilliger_aufgabe = self._create_task_assignment(
            self.freiwilliger.user,
            self.aufgabe
        )
        response = self.client.get(
            f"{reverse('delete_object', args=['useraufgaben', freiwilliger_aufgabe.id])}"
        )
        self.assertEqual(response.status_code, 302)
        
        self.assertFalse(
            UserAufgaben.objects.filter(
                org=self.org,
                aufgabe=self.aufgabe,
                user=self.freiwilliger.user
            ).exists()
        )
        
    def test_overdue_tasks(self):
        """Test that overdue tasks are correctly identified"""
        overdue_task = self._create_task_assignment(
            self.freiwilliger.user,
            self.aufgabe,
            days_until_due=-1  # Make it overdue
        )
        
        response = self.client.get(reverse('list_aufgaben_table'))
        self.assertEqual(response.status_code, 200)
        
        self.assertTrue(
            UserAufgaben.objects.filter(
                org=self.org,
                user=self.freiwilliger.user,
                aufgabe=self.aufgabe,
                faellig__lt=timezone.now()
            ).exists()
        )

    def test_file_upload(self):
        """Test file upload functionality"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        test_file = SimpleUploadedFile(
            "test_file.txt",
            b"Test file content",
            content_type="text/plain"
        )
        
        freiwilliger_aufgabe = self._create_task_assignment(
            self.freiwilliger.user,
            self.aufgabe
        )
        freiwilliger_aufgabe.file = test_file
        freiwilliger_aufgabe.save()
        
        response = self.client.get(reverse('download_aufgabe', args=[freiwilliger_aufgabe.id]))
        self.assertIn(response.status_code, [200, 302])
        
        if response.status_code == 200:
            import re
            self.assertTrue(
                re.match(
                    r'^attachment; filename="uploads/test_file.*\.txt"$',
                    response.get('Content-Disposition', '')
                )
            )

class AmpelTests(TestCase):
    def setUp(self):
        """Set up test data for ampel tests"""
        self._create_organization()
        self._create_person_clusters()
        self._create_test_users()
        self._create_admin_user()
        
        # Login as admin by default
        self.client.login(username='admin', password='adminpass123')

    def _create_organization(self):
        """Create test organization"""
        self.org = Organisation.objects.create(
            name='Test Org',
            email='test@test.com',
        )

    def _create_person_clusters(self):
        """Create person clusters for organization and volunteers"""
        self.person_cluster_org = PersonCluster.objects.create(
            org=self.org,
            name='Test Person Cluster Org',
            view='O',
            aufgaben=True,
            calendar=True,
            dokumente=True,
            ampel=True,
            notfallkontakt=True,
            bilder=True
        )
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
        # Create regular user
        self.user = get_user_model().objects.create_user(
            username='testuser',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        # Create volunteer
        self.freiwilliger = Freiwilliger.objects.create(
            org=self.org,
            user=self.user,
            start_geplant=timezone.now().date()
        )
        
        # Create CustomUser for volunteer
        self.custom_user = CustomUser.objects.create(
            org=self.org,
            user=self.user,
            person_cluster=self.person_cluster_fw
        )

    def _create_admin_user(self):
        """Create admin user"""
        self.admin_user = get_user_model().objects.create_user(
            username='admin',
            password='adminpass123',
            first_name='Admin',
            last_name='User',
        )
        self.admin_custom_user = CustomUser.objects.create(
            org=self.org,
            user=self.admin_user,
            person_cluster=self.person_cluster_org
        )

    def test_list_ampel_view(self):
        """Test that the ampel list view loads correctly"""
        response = self.client.get(reverse('list_ampel'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'list_ampel.html')

    def test_list_ampel_with_person_cluster(self):
        """Test ampel view with person cluster filter"""
        # Set person cluster cookie
        self.client.cookies['selectedPersonCluster'] = str(self.person_cluster_fw.id)
        
        response = self.client.get(reverse('list_ampel'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'list_ampel.html')
        
        # Verify context contains expected data
        self.assertIn('ampel_matrix', response.context)
        self.assertIn('months', response.context)

    def test_list_ampel_without_ampel_permission(self):
        """Test ampel view when person cluster doesn't have ampel permission"""
        # Create person cluster without ampel permission
        no_ampel_cluster = PersonCluster.objects.create(
            org=self.org,
            name='No Ampel Cluster',
            view='F',
            ampel=False
        )
        
        # Set person cluster cookie
        self.client.cookies['selectedPersonCluster'] = str(no_ampel_cluster.id)
        
        response = self.client.get(reverse('list_ampel'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('error', response.context)
        self.assertIn('keine Ampel-Funktion aktiviert', response.context['error'])

class StatistikTests(TestCase):
    def setUp(self):
        """Set up test data for statistics tests"""
        self._create_organization()
        self._create_person_clusters()
        self._create_test_users()
        self._create_admin_user()
        
        # Login as admin by default
        self.client.login(username='admin', password='adminpass123')

    def _create_organization(self):
        """Create test organization"""
        self.org = Organisation.objects.create(
            name='Test Org',
            email='test@test.com',
        )

    def _create_person_clusters(self):
        """Create person clusters for organization and volunteers"""
        self.person_cluster_org = PersonCluster.objects.create(
            org=self.org,
            name='Test Person Cluster Org',
            view='O',
            aufgaben=True,
            calendar=True,
            dokumente=True,
            ampel=True,
            notfallkontakt=True,
            bilder=True
        )
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
        # Create regular user
        self.user = get_user_model().objects.create_user(
            username='testuser',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        # Create volunteer
        self.freiwilliger = Freiwilliger.objects.create(
            org=self.org,
            user=self.user
        )
        
        # Create CustomUser for volunteer
        self.custom_user = CustomUser.objects.create(
            org=self.org,
            user=self.user,
            person_cluster=self.person_cluster_fw
        )

        # Create attributes for statistics
        self.geschlecht_attr = Attribute.objects.create(
            org=self.org,
            name='Geschlecht',
            type='T',
        )
        self.geschlecht_attr.person_cluster.add(self.person_cluster_fw)
        self.ort_attr = Attribute.objects.create(
            org=self.org,
            name='Ort',
            type='T',
        )
        self.ort_attr.person_cluster.add(self.person_cluster_fw)

        # Create user attributes
        UserAttribute.objects.create(
            org=self.org,
            user=self.user,
            attribute=self.geschlecht_attr,
            value='M'
        )
        UserAttribute.objects.create(
            org=self.org,
            user=self.user,
            attribute=self.ort_attr,
            value='Test City'
        )

    def _create_admin_user(self):
        """Create admin user"""
        self.admin_user = get_user_model().objects.create_user(
            username='admin',
            password='adminpass123',
            first_name='Admin',
            last_name='User',
        )
        self.admin_custom_user = CustomUser.objects.create(
            org=self.org,
            user=self.admin_user,
            person_cluster=self.person_cluster_org
        )

    def test_statistik_view(self):
        """Test that the statistics view loads correctly"""
        response = self.client.get(reverse('statistik'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'statistik.html')

    def test_statistik_field_data(self):
        """Test statistics data for specific fields"""
        # Test gender statistics
        response = self.client.get(reverse('statistik') + '?field=Geschlecht')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('M', data)
        self.assertEqual(data['M'], 1)

        # Test city statistics
        response = self.client.get(reverse('statistik') + '?field=Ort')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('Test City', data)
        self.assertEqual(data['Test City'], 1)

    def test_statistik_with_person_cluster(self):
        """Test statistics with person cluster filter"""
        # Set person cluster cookie
        self.client.cookies['selectedPersonCluster'] = str(self.person_cluster_fw.id)
        
        response = self.client.get(reverse('statistik'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'statistik.html')
        
        # Verify context contains expected data
        self.assertIn('freiwillige', response.context)
        self.assertIn('fields', response.context)

class DownloadTests(TestCase):
    def setUp(self):
        """Set up test data for download tests"""
        self._create_organization()
        self._create_person_clusters()
        self._create_test_users()
        self._create_admin_user()
        self._create_test_files()
        
        # Login as admin by default
        self.client.login(username='admin', password='adminpass123')

    def _create_organization(self):
        """Create test organization"""
        self.org = Organisation.objects.create(
            name='Test Org',
            email='test@test.com',
        )

    def _create_person_clusters(self):
        """Create person clusters for organization and volunteers"""
        self.person_cluster_org = PersonCluster.objects.create(
            org=self.org,
            name='Test Person Cluster Org',
            view='O',
            aufgaben=True,
            calendar=True,
            dokumente=True,
            ampel=True,
            notfallkontakt=True,
            bilder=True
        )
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
        # Create regular user
        self.user = get_user_model().objects.create_user(
            username='testuser',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        # Create volunteer
        self.freiwilliger = Freiwilliger.objects.create(
            org=self.org,
            user=self.user
        )
        
        # Create CustomUser for volunteer
        self.custom_user = CustomUser.objects.create(
            org=self.org,
            user=self.user,
            person_cluster=self.person_cluster_fw
        )

    def _create_admin_user(self):
        """Create admin user"""
        self.admin_user = get_user_model().objects.create_user(
            username='admin',
            password='adminpass123',
            first_name='Admin',
            last_name='User',
        )
        self.admin_custom_user = CustomUser.objects.create(
            org=self.org,
            user=self.admin_user,
            person_cluster=self.person_cluster_org
        )

    def _create_test_files(self):
        """Create test files for download tests"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        # Create test task with file
        self.aufgabe = Aufgabe2.objects.create(
            org=self.org,
            name='Test Aufgabe',
            beschreibung='Test Beschreibung'
        )
        
        test_file = SimpleUploadedFile(
            "test_file.txt",
            b"Test file content",
            content_type="text/plain"
        )
        
        # Create test task assignment with file
        self.user_aufgabe = UserAufgaben.objects.create(
            org=self.org,
            user=self.user,
            aufgabe=self.aufgabe,
            file=test_file
        )
        
        # Create test image
        self.bild = Bilder2.objects.create(
            org=self.org,
            user=self.user,
            titel='Test Bild'
        )
        
        # Create a small valid JPEG image
        image = Image.new('RGB', (1, 1), color='red')
        image_io = BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        test_image = SimpleUploadedFile(
            "test_image.jpg",
            image_io.read(),
            content_type="image/jpeg"
        )
        
        # Create test image gallery
        self.bild_gallery = BilderGallery2.objects.create(
            org=self.org,
            bilder=self.bild,
            image=test_image
        )

    def test_download_aufgabe(self):
        """Test downloading a task file"""
        response = self.client.get(reverse('download_aufgabe', args=[self.user_aufgabe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/octet-stream')

    def test_download_aufgabe_no_file(self):
        """Test downloading a task with no file"""
        self.user_aufgabe.file = None
        self.user_aufgabe.save()
        response = self.client.get(reverse('download_aufgabe', args=[self.user_aufgabe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), 'Keine Datei gefunden')

    def test_download_bild_as_zip(self):
        """Test downloading images as zip"""
        response = self.client.get(reverse('download_bild_as_zip', args=[self.bild.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertIn('attachment; filename=', response['Content-Disposition'])

    def test_download_unauthorized(self):
        """Test downloading with unauthorized access"""
        # Create another organization
        other_org = Organisation.objects.create(
            name='Other Org',
            email='other@test.com'
        )
        
        # Create task in other organization
        other_aufgabe = UserAufgaben.objects.create(
            org=other_org,
            user=self.user,
            aufgabe=self.aufgabe
        )
        
        response = self.client.get(reverse('download_aufgabe', args=[other_aufgabe.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), 'Nicht erlaubt')

