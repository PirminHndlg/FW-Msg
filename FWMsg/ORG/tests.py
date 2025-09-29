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
        """Test task status changes (erledigt, pending) via AJAX"""
        freiwilliger_aufgabe = self._create_task_assignment(
            self.freiwilliger.user,
            self.aufgabe
        )

        # Test marking as completed via AJAX
        response = self.client.post(
            reverse('ajax_update_task_status'),
            data=json.dumps({
                'aufgabe_id': freiwilliger_aufgabe.id,
                'erledigt': True,
                'pending': False
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        freiwilliger_aufgabe.refresh_from_db()
        self.assertTrue(freiwilliger_aufgabe.erledigt)
        self.assertFalse(freiwilliger_aufgabe.pending)

        # Test marking as pending via AJAX
        response = self.client.post(
            reverse('ajax_update_task_status'),
            data=json.dumps({
                'aufgabe_id': freiwilliger_aufgabe.id,
                'erledigt': False,
                'pending': True
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        freiwilliger_aufgabe.refresh_from_db()
        self.assertFalse(freiwilliger_aufgabe.erledigt)
        self.assertTrue(freiwilliger_aufgabe.pending)

    def test_task_assignment(self):
        """Test assigning tasks to volunteers via AJAX"""
        response = self.client.post(
            reverse('ajax_assign_task'),
            data=json.dumps({
                'user_id': self.freiwilliger.user.id,
                'aufgabe_id': self.aufgabe.id
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        self.assertTrue(
            UserAufgaben.objects.filter(
                org=self.org,
                user=self.freiwilliger.user,
                aufgabe=self.aufgabe
            ).exists()
        )
        
    def test_task_assignment_all(self):
        """Test assigning tasks to all volunteers via AJAX"""
        # Create a new task
        new_aufgabe = Aufgabe2.objects.create(
            org=self.org,
            name='Test Aufgabe 2',
            beschreibung='Test Beschreibung 2'
        )
        new_aufgabe.person_cluster.add(self.person_cluster_fw)
        
        # Create another volunteer
        user2, freiwilliger2 = self._create_additional_volunteer()
        
        response = self.client.post(
            reverse('ajax_assign_task_to_all'),
            data=json.dumps({
                'aufgabe_id': new_aufgabe.id
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
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


class AjaxTaskOperationsTests(TestCase):
    def setUp(self):
        """Set up test data for AJAX task operations tests"""
        self._create_organization()
        self._create_person_clusters()
        self._create_test_users()
        self._create_test_tasks()
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

        # Create second user for testing
        self.user2 = get_user_model().objects.create_user(
            username='testuser2',
            password='testpass123',
            first_name='Test2',
            last_name='User2'
        )
        
        self.freiwilliger2 = Freiwilliger.objects.create(
            org=self.org,
            user=self.user2
        )
        
        self.custom_user2 = CustomUser.objects.create(
            org=self.org,
            user=self.user2,
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

        self.aufgabe2 = Aufgabe2.objects.create(
            org=self.org,
            name='Test Aufgabe 2',
            beschreibung='Test Beschreibung 2'
        )
        self.aufgabe2.person_cluster.add(self.person_cluster_fw)

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

    def _create_task_assignment(self, user=None, aufgabe=None):
        """Helper method to create a task assignment"""
        if user is None:
            user = self.user
        if aufgabe is None:
            aufgabe = self.aufgabe
            
        return UserAufgaben.objects.create(
            org=self.org,
            user=user,
            aufgabe=aufgabe,
            faellig=timezone.now() + timedelta(days=7)
        )

    def test_ajax_update_task_status_mark_done(self):
        """Test marking a task as done via AJAX"""
        user_aufgabe = self._create_task_assignment()
        
        response = self.client.post(
            reverse('ajax_update_task_status'),
            data=json.dumps({
                'aufgabe_id': user_aufgabe.id,
                'pending': False,
                'erledigt': True
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'Task status updated successfully')
        self.assertTrue(data['new_status']['erledigt'])
        self.assertFalse(data['new_status']['pending'])
        self.assertIn('erledigt_am', data['new_status'])
        
        # Verify database update
        user_aufgabe.refresh_from_db()
        self.assertTrue(user_aufgabe.erledigt)
        self.assertFalse(user_aufgabe.pending)
        self.assertIsNotNone(user_aufgabe.erledigt_am)

    def test_ajax_update_task_status_mark_pending(self):
        """Test marking a task as pending via AJAX"""
        user_aufgabe = self._create_task_assignment()
        
        response = self.client.post(
            reverse('ajax_update_task_status'),
            data=json.dumps({
                'aufgabe_id': user_aufgabe.id,
                'pending': True,
                'erledigt': False
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertTrue(data['new_status']['pending'])
        self.assertFalse(data['new_status']['erledigt'])
        
        # Verify database update
        user_aufgabe.refresh_from_db()
        self.assertTrue(user_aufgabe.pending)
        self.assertFalse(user_aufgabe.erledigt)

    def test_ajax_update_task_status_invalid_json(self):
        """Test AJAX update with invalid JSON"""
        response = self.client.post(
            reverse('ajax_update_task_status'),
            data='invalid json',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Invalid JSON')

    def test_ajax_update_task_status_task_not_found(self):
        """Test AJAX update with non-existent task"""
        response = self.client.post(
            reverse('ajax_update_task_status'),
            data=json.dumps({
                'aufgabe_id': 99999,
                'pending': False,
                'erledigt': True
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Task not found')

    def test_ajax_delete_task_file(self):
        """Test deleting task file via AJAX"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        user_aufgabe = self._create_task_assignment()
        test_file = SimpleUploadedFile(
            "test_file.txt",
            b"Test file content",
            content_type="text/plain"
        )
        user_aufgabe.file = test_file
        user_aufgabe.save()
        
        response = self.client.post(
            reverse('ajax_delete_task_file'),
            data=json.dumps({
                'aufgabe_id': user_aufgabe.id
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'File deleted successfully')
        
        # Verify file was deleted
        user_aufgabe.refresh_from_db()
        self.assertFalse(user_aufgabe.file)

    def test_ajax_delete_task_file_no_file(self):
        """Test deleting file when no file exists"""
        user_aufgabe = self._create_task_assignment()
        
        response = self.client.post(
            reverse('ajax_delete_task_file'),
            data=json.dumps({
                'aufgabe_id': user_aufgabe.id
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'No file to delete')

    def test_ajax_assign_task(self):
        """Test assigning a task to a specific user via AJAX"""
        response = self.client.post(
            reverse('ajax_assign_task'),
            data=json.dumps({
                'user_id': self.user.id,
                'aufgabe_id': self.aufgabe.id
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'Task assigned successfully')
        self.assertTrue(data['created'])
        
        # Verify task assignment was created
        self.assertTrue(
            UserAufgaben.objects.filter(
                org=self.org,
                user=self.user,
                aufgabe=self.aufgabe
            ).exists()
        )

    def test_ajax_assign_task_already_assigned(self):
        """Test assigning a task that's already assigned"""
        # Create existing assignment
        self._create_task_assignment(self.user, self.aufgabe)
        
        response = self.client.post(
            reverse('ajax_assign_task'),
            data=json.dumps({
                'user_id': self.user.id,
                'aufgabe_id': self.aufgabe.id
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'Task was already assigned')
        self.assertFalse(data['created'])

    def test_ajax_assign_task_permission_denied(self):
        """Test assigning task when user doesn't have permission"""
        # Create a task for a different person cluster
        restricted_cluster = PersonCluster.objects.create(
            org=self.org,
            name='Restricted Cluster',
            view='F',
            aufgaben=True
        )
        
        restricted_task = Aufgabe2.objects.create(
            org=self.org,
            name='Restricted Task',
            beschreibung='Restricted Description'
        )
        restricted_task.person_cluster.add(restricted_cluster)
        
        response = self.client.post(
            reverse('ajax_assign_task'),
            data=json.dumps({
                'user_id': self.user.id,
                'aufgabe_id': restricted_task.id
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('has no access to task', data['error'])

    def test_ajax_assign_task_to_all(self):
        """Test assigning a task to all eligible users via AJAX"""
        response = self.client.post(
            reverse('ajax_assign_task_to_all'),
            data=json.dumps({
                'aufgabe_id': self.aufgabe.id
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'Task assigned to 2 users')
        self.assertEqual(data['assigned_count'], 2)
        
        # Verify both users got the task
        self.assertTrue(
            UserAufgaben.objects.filter(
                org=self.org,
                user=self.user,
                aufgabe=self.aufgabe
            ).exists()
        )
        self.assertTrue(
            UserAufgaben.objects.filter(
                org=self.org,
                user=self.user2,
                aufgabe=self.aufgabe
            ).exists()
        )

    def test_ajax_assign_task_to_all_with_existing_assignments(self):
        """Test assigning to all when some users already have the task"""
        # Pre-assign to one user
        self._create_task_assignment(self.user, self.aufgabe)
        
        response = self.client.post(
            reverse('ajax_assign_task_to_all'),
            data=json.dumps({
                'aufgabe_id': self.aufgabe.id
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['assigned_count'], 1)  # Only one new assignment
        
        # Verify both users have the task
        self.assertEqual(
            UserAufgaben.objects.filter(
                org=self.org,
                aufgabe=self.aufgabe
            ).count(),
            2
        )

    def test_ajax_assign_tasks_by_country(self):
        """Test assigning tasks by country via AJAX"""
        from Global.models import Einsatzland2
        
        # Create a country
        country = Einsatzland2.objects.create(
            org=self.org,
            name='Test Country'
        )
        
        # Assign country to freiwilliger
        self.freiwilliger.einsatzland2 = country
        self.freiwilliger.save()
        
        response = self.client.post(
            reverse('ajax_assign_tasks_by_country'),
            data=json.dumps({
                'aufgabe_id': self.aufgabe.id,
                'country_id': country.id
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('Tasks assigned to', data['message'])
        self.assertGreaterEqual(data['assigned_count'], 0)

    def test_ajax_unauthorized_access(self):
        """Test AJAX endpoints with unauthorized access"""
        # Create another organization
        other_org = Organisation.objects.create(
            name='Other Org',
            email='other@test.com'
        )
        
        # Create task in other organization
        other_aufgabe = Aufgabe2.objects.create(
            org=other_org,
            name='Other Task',
            beschreibung='Other Description'
        )
        
        other_user_aufgabe = UserAufgaben.objects.create(
            org=other_org,
            user=self.user,
            aufgabe=other_aufgabe
        )
        
        # Test update task status with unauthorized task
        response = self.client.post(
            reverse('ajax_update_task_status'),
            data=json.dumps({
                'aufgabe_id': other_user_aufgabe.id,
                'pending': False,
                'erledigt': True
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Task not found')

    def test_ajax_endpoints_require_login(self):
        """Test that AJAX endpoints require login"""
        self.client.logout()
        
        endpoints = [
            'ajax_update_task_status',
            'ajax_delete_task_file',
            'ajax_assign_task',
            'ajax_assign_task_to_all',
            'ajax_assign_tasks_by_country'
        ]
        
        for endpoint in endpoints:
            response = self.client.post(
                reverse(endpoint),
                data=json.dumps({'test': 'data'}),
                content_type='application/json'
            )
            # Should redirect to login or return 403/401
            self.assertIn(response.status_code, [302, 401, 403])

    def test_ajax_endpoints_require_org_role(self):
        """Test that AJAX endpoints require organization role"""
        # Create user without organization role
        non_org_user = get_user_model().objects.create_user(
            username='nonorguser',
            password='testpass123'
        )
        
        # Create CustomUser without org role
        CustomUser.objects.create(
            org=self.org,
            user=non_org_user,
            person_cluster=self.person_cluster_fw
        )
        
        self.client.login(username='nonorguser', password='testpass123')
        
        user_aufgabe = self._create_task_assignment()
        
        response = self.client.post(
            reverse('ajax_update_task_status'),
            data=json.dumps({
                'aufgabe_id': user_aufgabe.id,
                'pending': False,
                'erledigt': True
            }),
            content_type='application/json'
        )
        
        # Should be forbidden due to role requirement
        self.assertIn(response.status_code, [302, 403])

    def test_ajax_endpoints_only_accept_post(self):
        """Test that AJAX endpoints only accept POST requests"""
        user_aufgabe = self._create_task_assignment()
        
        endpoints = [
            'ajax_update_task_status',
            'ajax_delete_task_file',
            'ajax_assign_task',
            'ajax_assign_task_to_all',
            'ajax_assign_tasks_by_country'
        ]
        
        for endpoint in endpoints:
            # Test GET request
            response = self.client.get(reverse(endpoint))
            self.assertEqual(response.status_code, 405)  # Method not allowed
            
            # Test PUT request
            response = self.client.put(
                reverse(endpoint),
                data=json.dumps({'test': 'data'}),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 405)  # Method not allowed


    def test_ajax_update_task_status_reset_to_upcoming(self):
        """Test resetting a task to upcoming (not pending, not done) via AJAX"""
        user_aufgabe = self._create_task_assignment()
        
        # First mark as done
        user_aufgabe.erledigt = True
        user_aufgabe.erledigt_am = timezone.now()
        user_aufgabe.save()
        
        # Then reset to upcoming
        response = self.client.post(
            reverse('ajax_update_task_status'),
            data=json.dumps({
                'aufgabe_id': user_aufgabe.id,
                'pending': False,
                'erledigt': False
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertFalse(data['new_status']['erledigt'])
        self.assertFalse(data['new_status']['pending'])
        
        # Verify database update
        user_aufgabe.refresh_from_db()
        self.assertFalse(user_aufgabe.erledigt)
        self.assertFalse(user_aufgabe.pending)
        self.assertIsNone(user_aufgabe.erledigt_am)


class TaskTemplateStateTests(TestCase):
    """Test the new template-based state switching approach"""
    
    def setUp(self):
        """Set up test data for template state tests"""
        self._create_organization()
        self._create_person_clusters()
        self._create_test_users()
        self._create_test_tasks()
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
            person_cluster=self.person_cluster_fw,
            mail_notifications=True  # Enable notifications for testing
        )

    def _create_test_tasks(self):
        """Create test tasks"""
        self.aufgabe = Aufgabe2.objects.create(
            org=self.org,
            name='Test Aufgabe',
            beschreibung='Test Beschreibung'
        )
        self.aufgabe.person_cluster.add(self.person_cluster_fw)

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

    def _create_task_assignment(self, user=None, aufgabe=None, **kwargs):
        """Helper method to create a task assignment"""
        if user is None:
            user = self.user
        if aufgabe is None:
            aufgabe = self.aufgabe
            
        defaults = {
            'org': self.org,
            'user': user,
            'aufgabe': aufgabe,
            'faellig': timezone.now() + timedelta(days=7)
        }
        defaults.update(kwargs)
        
        return UserAufgaben.objects.create(**defaults)

    def test_task_template_states_in_response(self):
        """Test that the task table view includes all template states"""
        user_aufgabe = self._create_task_assignment()
        
        response = self.client.get(reverse('list_aufgaben_table'))
        self.assertEqual(response.status_code, 200)
        
        # Check that all template IDs are present in the HTML
        content = response.content.decode()
        self.assertIn(f'id="completed-task-template-{user_aufgabe.id}"', content)
        self.assertIn(f'id="pending-task-template-{user_aufgabe.id}"', content)
        self.assertIn(f'id="upcoming-task-template-{user_aufgabe.id}"', content)
        self.assertIn(f'id="task-table-row-{user_aufgabe.id}"', content)

    def test_task_state_visibility_upcoming(self):
        """Test that upcoming tasks show the correct template"""
        user_aufgabe = self._create_task_assignment(
            erledigt=False,
            pending=False
        )
        
        response = self.client.get(reverse('list_aufgaben_table'))
        content = response.content.decode()
        
        # Upcoming template should be visible (no d-none class)
        self.assertNotIn(f'id="upcoming-task-template-{user_aufgabe.id}" class="d-none"', content)
        # Other templates should be hidden
        self.assertIn(f'id="completed-task-template-{user_aufgabe.id}" class="d-none"', content)
        self.assertIn(f'id="pending-task-template-{user_aufgabe.id}" class="d-none"', content)

    def test_task_state_visibility_pending(self):
        """Test that pending tasks show the correct template"""
        user_aufgabe = self._create_task_assignment(
            erledigt=False,
            pending=True
        )
        
        response = self.client.get(reverse('list_aufgaben_table'))
        content = response.content.decode()
        
        # Pending template should be visible
        self.assertNotIn(f'id="pending-task-template-{user_aufgabe.id}" class="d-none"', content)
        # Other templates should be hidden
        self.assertIn(f'id="completed-task-template-{user_aufgabe.id}" class="d-none"', content)
        self.assertIn(f'id="upcoming-task-template-{user_aufgabe.id}" class="d-none"', content)

    def test_task_state_visibility_completed(self):
        """Test that completed tasks show the correct template"""
        user_aufgabe = self._create_task_assignment(
            erledigt=True,
            erledigt_am=timezone.now(),
            pending=False
        )
        
        response = self.client.get(reverse('list_aufgaben_table'))
        content = response.content.decode()
        
        # Completed template should be visible
        self.assertNotIn(f'id="completed-task-template-{user_aufgabe.id}" class="d-none"', content)
        # Other templates should be hidden
        self.assertIn(f'id="pending-task-template-{user_aufgabe.id}" class="d-none"', content)
        self.assertIn(f'id="upcoming-task-template-{user_aufgabe.id}" class="d-none"', content)

    def test_task_row_background_classes(self):
        """Test that task rows have correct background classes based on state"""
        # Create a completed task
        completed_task = self._create_task_assignment(
            erledigt=True,
            erledigt_am=timezone.now(),
            pending=False
        )
        
        response = self.client.get(reverse('list_aufgaben_table'))
        content = response.content.decode()
        
        # Check that completed task has success background
        self.assertIn('bg-success bg-opacity-25', content)
        
        # Check that the task row ID is present
        self.assertIn(f'id="task-table-row-{completed_task.id}"', content)

    def test_overdue_task_styling(self):
        """Test that overdue tasks have danger background"""
        overdue_task = self._create_task_assignment(
            faellig=timezone.now() - timedelta(days=1),  # Make it overdue
            erledigt=False,
            pending=False
        )
        
        response = self.client.get(reverse('list_aufgaben_table'))
        content = response.content.decode()
        
        # Should have danger background for overdue
        self.assertIn('bg-danger bg-opacity-25', content)

    def test_ajax_state_change_response_format(self):
        """Test that AJAX responses include all necessary data for state switching"""
        user_aufgabe = self._create_task_assignment()
        
        # Test marking as done
        response = self.client.post(
            reverse('ajax_update_task_status'),
            data=json.dumps({
                'aufgabe_id': user_aufgabe.id,
                'pending': False,
                'erledigt': True
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Check response includes all necessary fields for JavaScript state switching
        self.assertTrue(data['success'])
        self.assertIn('new_status', data)
        self.assertIn('erledigt', data['new_status'])
        self.assertIn('pending', data['new_status'])
        self.assertIn('erledigt_am', data['new_status'])
        
        # Test marking as pending
        response = self.client.post(
            reverse('ajax_update_task_status'),
            data=json.dumps({
                'aufgabe_id': user_aufgabe.id,
                'pending': True,
                'erledigt': False
            }),
            content_type='application/json'
        )
        
        data = json.loads(response.content)
        self.assertTrue(data['new_status']['pending'])
        self.assertFalse(data['new_status']['erledigt'])

    def test_task_assignment_creates_proper_state(self):
        """Test that newly assigned tasks are in the correct initial state"""
        response = self.client.post(
            reverse('ajax_assign_task'),
            data=json.dumps({
                'user_id': self.user.id,
                'aufgabe_id': self.aufgabe.id
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertTrue(data['created'])
        self.assertIn('task_id', data)
        
        # Verify the created task is in upcoming state
        created_task = UserAufgaben.objects.get(id=data['task_id'])
        self.assertFalse(created_task.erledigt)
        self.assertFalse(created_task.pending)

    def test_task_file_operations(self):
        """Test file upload and deletion with the new template system"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        user_aufgabe = self._create_task_assignment()
        
        # Add file to task
        test_file = SimpleUploadedFile(
            "test_file.txt",
            b"Test file content",
            content_type="text/plain"
        )
        user_aufgabe.file = test_file
        user_aufgabe.save()
        
        # Test file deletion
        response = self.client.post(
            reverse('ajax_delete_task_file'),
            data=json.dumps({
                'aufgabe_id': user_aufgabe.id
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Verify file was deleted
        user_aufgabe.refresh_from_db()
        self.assertFalse(user_aufgabe.file)

    def test_multiple_state_transitions(self):
        """Test multiple state transitions work correctly"""
        user_aufgabe = self._create_task_assignment()
        
        # 1. Start as upcoming -> Mark as pending
        response = self.client.post(
            reverse('ajax_update_task_status'),
            data=json.dumps({
                'aufgabe_id': user_aufgabe.id,
                'pending': True,
                'erledigt': False
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        user_aufgabe.refresh_from_db()
        self.assertTrue(user_aufgabe.pending)
        self.assertFalse(user_aufgabe.erledigt)
        
        # 2. Pending -> Mark as done
        response = self.client.post(
            reverse('ajax_update_task_status'),
            data=json.dumps({
                'aufgabe_id': user_aufgabe.id,
                'pending': False,
                'erledigt': True
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        user_aufgabe.refresh_from_db()
        self.assertFalse(user_aufgabe.pending)
        self.assertTrue(user_aufgabe.erledigt)
        self.assertIsNotNone(user_aufgabe.erledigt_am)
        
        # 3. Done -> Back to upcoming
        response = self.client.post(
            reverse('ajax_update_task_status'),
            data=json.dumps({
                'aufgabe_id': user_aufgabe.id,
                'pending': False,
                'erledigt': False
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        user_aufgabe.refresh_from_db()
        self.assertFalse(user_aufgabe.pending)
        self.assertFalse(user_aufgabe.erledigt)
        self.assertIsNone(user_aufgabe.erledigt_am)

    def test_concurrent_task_operations(self):
        """Test that concurrent operations on the same task work correctly"""
        user_aufgabe = self._create_task_assignment()
        
        # Simulate concurrent requests (though they'll be processed sequentially in tests)
        responses = []
        
        # Multiple status updates
        for i in range(3):
            response = self.client.post(
                reverse('ajax_update_task_status'),
                data=json.dumps({
                    'aufgabe_id': user_aufgabe.id,
                    'pending': i % 2 == 0,  # Alternate between pending and not
                    'erledigt': False
                }),
                content_type='application/json'
            )
            responses.append(response)
        
        # All requests should succeed
        for response in responses:
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.content)
            self.assertTrue(data['success'])
        
        # Final state should match the last request
        user_aufgabe.refresh_from_db()
        self.assertTrue(user_aufgabe.pending)  # Last request had pending=True
        self.assertFalse(user_aufgabe.erledigt)

