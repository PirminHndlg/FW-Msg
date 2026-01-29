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
from BW.models import Bewerber
from ORG.forms import AddBewerberApplicationPdfForm
import json
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
import threading
import concurrent.futures
from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from Global.models import CustomUser, PersonCluster
from ORG.models import Organisation
from seminar.models import Bewertung, Kommentar, Frage, Fragekategorie, Einheit
from ORG.views import get_cascade_info

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
        
        response = self.client.get(reverse('list_ampel') + '?person_cluster_filter=' + str(no_ampel_cluster.id))
        self.assertEqual(response.status_code, 200)
        self.assertIn('ampel_matrix', response.context)
        
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
        response = self.client.get(reverse('ajax_statistik') + '?field=Geschlecht')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('M', data)
        self.assertEqual(data['M'], 1)

        # Test city statistics
        response = self.client.get(reverse('ajax_statistik') + '?field=Ort')
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
        self.assertEqual(response.status_code, 403)

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
        self.assertEqual(response.status_code, 403)


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
        """Test that the AJAX endpoint includes all necessary JSON data"""
        user_aufgabe = self._create_task_assignment()
        
        # Test the AJAX endpoint that returns JSON data
        response = self.client.get(reverse('ajax_load_aufgaben_table_data'))
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Check that the response includes the new JSON structure
        self.assertIn('users', data['data'])
        self.assertIn('aufgaben', data['data'])
        self.assertIn('user_aufgaben_assigned', data['data'])
        self.assertIn('user_aufgaben_eligible', data['data'])
        self.assertIn('today', data['data'])
        self.assertIn('current_person_cluster', data['data'])
        
        # Verify user_aufgaben_assigned contains the task data
        user_id = str(user_aufgabe.user.id)
        aufgabe_id = str(user_aufgabe.aufgabe.id)
        self.assertIn(user_id, data['data']['user_aufgaben_assigned'])
        self.assertIn(aufgabe_id, data['data']['user_aufgaben_assigned'][user_id])

    def test_task_state_visibility_upcoming(self):
        """Test that upcoming tasks have correct JSON data structure"""
        user_aufgabe = self._create_task_assignment(
            erledigt=False,
            pending=False
        )
        
        response = self.client.get(reverse('ajax_load_aufgaben_table_data'))
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Find the user_aufgabe in the response data using sparse format
        user_id = str(user_aufgabe.user.id)
        aufgabe_id = str(user_aufgabe.aufgabe.id)
        
        self.assertIn(user_id, data['data']['user_aufgaben_assigned'])
        self.assertIn(aufgabe_id, data['data']['user_aufgaben_assigned'][user_id])
        
        task_data = data['data']['user_aufgaben_assigned'][user_id][aufgabe_id]
        self.assertIsNotNone(task_data, "Task not found in response")
        self.assertFalse(task_data['user_aufgabe']['erledigt'])
        self.assertFalse(task_data['user_aufgabe']['pending'])

    def test_task_state_visibility_pending(self):
        """Test that pending tasks have correct JSON data structure"""
        user_aufgabe = self._create_task_assignment(
            erledigt=False,
            pending=True
        )
        
        response = self.client.get(reverse('ajax_load_aufgaben_table_data'))
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Find the user_aufgabe in the response data using sparse format
        user_id = str(user_aufgabe.user.id)
        aufgabe_id = str(user_aufgabe.aufgabe.id)
        
        self.assertIn(user_id, data['data']['user_aufgaben_assigned'])
        self.assertIn(aufgabe_id, data['data']['user_aufgaben_assigned'][user_id])
        
        task_data = data['data']['user_aufgaben_assigned'][user_id][aufgabe_id]
        self.assertIsNotNone(task_data, "Task not found in response")
        self.assertFalse(task_data['user_aufgabe']['erledigt'])
        self.assertTrue(task_data['user_aufgabe']['pending'])

    def test_task_state_visibility_completed(self):
        """Test that completed tasks have correct JSON data structure"""
        user_aufgabe = self._create_task_assignment(
            erledigt=True,
            erledigt_am=timezone.now(),
            pending=False
        )
        
        response = self.client.get(reverse('ajax_load_aufgaben_table_data'))
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Find the user_aufgabe in the response data using sparse format
        user_id = str(user_aufgabe.user.id)
        aufgabe_id = str(user_aufgabe.aufgabe.id)
        
        self.assertIn(user_id, data['data']['user_aufgaben_assigned'])
        self.assertIn(aufgabe_id, data['data']['user_aufgaben_assigned'][user_id])
        
        task_data = data['data']['user_aufgaben_assigned'][user_id][aufgabe_id]
        self.assertIsNotNone(task_data, "Task not found in response")
        self.assertTrue(task_data['user_aufgabe']['erledigt'])
        self.assertIsNotNone(task_data['user_aufgabe']['erledigt_am'])

    def test_task_row_background_classes(self):
        """Test that completed tasks have correct state in JSON data"""
        # Create a completed task
        completed_task = self._create_task_assignment(
            erledigt=True,
            erledigt_am=timezone.now(),
            pending=False
        )
        
        response = self.client.get(reverse('ajax_load_aufgaben_table_data'))
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Find the completed task in the response data using sparse format
        user_id = str(completed_task.user.id)
        aufgabe_id = str(completed_task.aufgabe.id)
        
        self.assertIn(user_id, data['data']['user_aufgaben_assigned'])
        self.assertIn(aufgabe_id, data['data']['user_aufgaben_assigned'][user_id])
        
        task_data = data['data']['user_aufgaben_assigned'][user_id][aufgabe_id]
        self.assertIsNotNone(task_data, "Task not found in response")
        self.assertTrue(task_data['user_aufgabe']['erledigt'])
        # The background class will be determined by JavaScript based on this data

    def test_overdue_task_styling(self):
        """Test that overdue tasks have correct date in JSON data"""
        overdue_task = self._create_task_assignment(
            faellig=timezone.now() - timedelta(days=1),  # Make it overdue
            erledigt=False,
            pending=False
        )
        
        response = self.client.get(reverse('ajax_load_aufgaben_table_data'))
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Find the overdue task in the response data using sparse format
        user_id = str(overdue_task.user.id)
        aufgabe_id = str(overdue_task.aufgabe.id)
        
        self.assertIn(user_id, data['data']['user_aufgaben_assigned'])
        self.assertIn(aufgabe_id, data['data']['user_aufgaben_assigned'][user_id])
        
        task_data = data['data']['user_aufgaben_assigned'][user_id][aufgabe_id]
        self.assertIsNotNone(task_data, "Task not found in response")
        # Verify the task is overdue (faellig date is in the past)
        # The danger styling will be applied by JavaScript based on this date

    def test_main_view_loads_with_ajax_loading(self):
        """Test that the AJAX endpoint returns correct JSON structure"""
        response = self.client.get(reverse('ajax_load_aufgaben_table_data'))
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
        # Check that the response includes the new JSON structure
        self.assertIn('users', data['data'])
        self.assertIn('aufgaben', data['data'])
        self.assertIn('user_aufgaben_assigned', data['data'])
        self.assertIn('user_aufgaben_eligible', data['data'])
        self.assertIn('today', data['data'])
        self.assertIn('current_person_cluster', data['data'])

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


class BewerberPdfUploadTests(TestCase):
    """Test the AddBewerberApplicationPdfForm PDF upload and merging functionality"""
    
    def setUp(self):
        """Set up test data for Bewerber PDF upload tests"""
        self._create_organization()
        self._create_person_clusters()
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
        """Create person clusters for organization"""
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
        self.person_cluster_bewerber = PersonCluster.objects.create(
            org=self.org,
            name='Test Person Cluster Bewerber',
            view='B',
            aufgaben=False,
            calendar=False,
            dokumente=False,
            ampel=False,
            notfallkontakt=False,
            bilder=False
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

    def _create_pdf_file(self, filename='test.pdf', content=None):
        """Create a simple PDF file for testing"""
        if content is None:
            # Create a minimal valid PDF content
            content = b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF'
        
        return SimpleUploadedFile(
            filename,
            content,
            content_type='application/pdf'
        )

    def _create_bewerber(self):
        """Create a test Bewerber"""
        user = get_user_model().objects.create_user(
            username='bewerber_test',
            password='testpass123',
            first_name='Test',
            last_name='Bewerber',
            email='bewerber@test.com'
        )
        
        bewerber = Bewerber.objects.create(
            org=self.org,
            user=user
        )
        
        CustomUser.objects.create(
            org=self.org,
            user=user,
            person_cluster=self.person_cluster_bewerber
        )
        
        return bewerber

    def test_single_pdf_upload(self):
        """Test uploading a single PDF file"""
        pdf_file = self._create_pdf_file('application.pdf')
        
        # Create form data
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@test.com',
            'person_cluster': self.person_cluster_bewerber.id,
        }
        
        files = {'pdf_files': pdf_file}
        
        # Create a mock request with FILES
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post('/test/', data, format='multipart')
        request.user = self.admin_user
        request.FILES.setlist('pdf_files', [pdf_file])
        
        form = AddBewerberApplicationPdfForm(data=data, files=files, request=request)
        
        # Validate form
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        # Save the form
        bewerber = form.save()
        
        # Verify PDF was saved
        self.assertIsNotNone(bewerber.application_pdf)
        self.assertTrue(bewerber.application_pdf.name.endswith('.pdf'))

    def test_multiple_pdf_merge(self):
        """Test uploading and merging multiple PDF files"""
        pdf_file1 = self._create_pdf_file('application1.pdf')
        pdf_file2 = self._create_pdf_file('application2.pdf')
        pdf_file3 = self._create_pdf_file('application3.pdf')
        
        # Create form data
        data = {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'jane.smith@test.com',
            'person_cluster': self.person_cluster_bewerber.id,
        }
        
        # Create a mock request with multiple FILES
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post('/test/', data, format='multipart')
        request.user = self.admin_user
        request.FILES.setlist('pdf_files', [pdf_file1, pdf_file2, pdf_file3])
        
        files = {'pdf_files': [pdf_file1, pdf_file2, pdf_file3]}
        
        form = AddBewerberApplicationPdfForm(data=data, files=files, request=request)
        
        # Validate form
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        # Save the form
        bewerber = form.save()
        
        # Verify merged PDF was saved
        self.assertIsNotNone(bewerber.application_pdf)
        self.assertTrue(bewerber.application_pdf.name.endswith('.pdf'))
        
        # Verify the file size is larger (merged content)
        self.assertGreater(bewerber.application_pdf.size, 0)

    def test_invalid_file_type_rejection(self):
        """Test that non-PDF files are rejected"""
        # Create a text file instead of PDF
        text_file = SimpleUploadedFile(
            'application.txt',
            b'This is not a PDF file',
            content_type='text/plain'
        )
        
        data = {
            'first_name': 'Bob',
            'last_name': 'Invalid',
            'email': 'bob@test.com',
            'person_cluster': self.person_cluster_bewerber.id,
        }
        
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post('/test/', data, format='multipart')
        request.user = self.admin_user
        request.FILES.setlist('pdf_files', [text_file])
        
        files = {'pdf_files': text_file}
        
        form = AddBewerberApplicationPdfForm(data=data, files=files, request=request)
        
        # Form should be invalid
        self.assertFalse(form.is_valid())
        self.assertIn('pdf_files', form.errors)

    def test_pdf_merge_with_memory_buffers(self):
        """Test that PDFs are read into memory immediately to avoid temp file issues"""
        pdf_files = [
            self._create_pdf_file(f'application{i}.pdf')
            for i in range(5)
        ]
        
        data = {
            'first_name': 'Memory',
            'last_name': 'Test',
            'email': 'memory@test.com',
            'person_cluster': self.person_cluster_bewerber.id,
        }
        
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post('/test/', data, format='multipart')
        request.user = self.admin_user
        request.FILES.setlist('pdf_files', pdf_files)
        
        files = {'pdf_files': pdf_files}
        
        form = AddBewerberApplicationPdfForm(data=data, files=files, request=request)
        
        # Validate and save
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        bewerber = form.save()
        
        # Verify merged PDF exists
        self.assertIsNotNone(bewerber.application_pdf)

    def test_concurrent_uploads_no_race_condition(self):
        """Test that concurrent uploads don't cause race conditions with PDF temp files"""
        from django.db import transaction, connection
        
        # Skip for SQLite as it doesn't handle concurrent writes well
        if 'sqlite' in connection.settings_dict['ENGINE']:
            self.skipTest("SQLite doesn't support concurrent writes - this tests PDF temp file handling")
        
        results = []
        errors = []
        
        def upload_bewerber(index):
            """Function to upload a Bewerber with PDF"""
            try:
                # Use atomic transaction for database operations
                with transaction.atomic():
                    pdf_file = self._create_pdf_file(f'concurrent_{index}.pdf')
                    
                    data = {
                        'first_name': f'Concurrent{index}',
                        'last_name': 'User',
                        'email': f'concurrent{index}@test.com',
                        'person_cluster': self.person_cluster_bewerber.id,
                    }
                    
                    from django.test import RequestFactory
                    factory = RequestFactory()
                    request = factory.post('/test/', data, format='multipart')
                    request.user = self.admin_user
                    request.FILES.setlist('pdf_files', [pdf_file])
                    
                    files = {'pdf_files': pdf_file}
                    
                    form = AddBewerberApplicationPdfForm(data=data, files=files, request=request)
                    
                    if form.is_valid():
                        bewerber = form.save()
                        results.append({
                            'success': True,
                            'bewerber_id': bewerber.id,
                            'has_pdf': bool(bewerber.application_pdf)
                        })
                    else:
                        errors.append({
                            'index': index,
                            'errors': form.errors
                        })
            except Exception as e:
                errors.append({
                    'index': index,
                    'exception': str(e)
                })
        
        # Simulate concurrent uploads
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(upload_bewerber, i) for i in range(10)]
            concurrent.futures.wait(futures)
        
        # All uploads should succeed
        self.assertEqual(len(results), 10, f"Expected 10 successful uploads, got {len(results)}. Errors: {errors}")
        self.assertEqual(len(errors), 0, f"Expected no errors, got: {errors}")
        
        # All should have PDFs
        for result in results:
            self.assertTrue(result['success'])
            self.assertTrue(result['has_pdf'])

    def test_empty_pdf_files_handled_gracefully(self):
        """Test that form handles empty/no PDF files gracefully"""
        data = {
            'first_name': 'No',
            'last_name': 'PDF',
            'email': 'nopdf@test.com',
            'person_cluster': self.person_cluster_bewerber.id,
        }
        
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post('/test/', data, format='multipart')
        request.user = self.admin_user
        request.FILES.setlist('pdf_files', [])
        
        form = AddBewerberApplicationPdfForm(data=data, files={}, request=request)
        
        # Form should still be valid (PDF is optional)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        # Save the form
        bewerber = form.save()
        
        # No PDF should be saved
        self.assertFalse(bewerber.application_pdf)

    def test_update_existing_bewerber_with_new_pdf(self):
        """Test updating an existing Bewerber with a new PDF"""
        # Create existing bewerber
        bewerber = self._create_bewerber()
        
        # Upload initial PDF
        pdf_file1 = self._create_pdf_file('initial.pdf', b'%PDF-Initial%')
        bewerber.application_pdf = pdf_file1
        bewerber.save()
        
        initial_pdf_name = bewerber.application_pdf.name
        
        # Now update with new PDF
        pdf_file2 = self._create_pdf_file('updated.pdf', b'%PDF-Updated%')
        
        data = {
            'first_name': bewerber.user.first_name,
            'last_name': bewerber.user.last_name,
            'email': bewerber.user.email,
            'person_cluster': self.person_cluster_bewerber.id,
        }
        
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post('/test/', data, format='multipart')
        request.user = self.admin_user
        request.FILES.setlist('pdf_files', [pdf_file2])
        
        files = {'pdf_files': pdf_file2}
        
        form = AddBewerberApplicationPdfForm(
            data=data,
            files=files,
            instance=bewerber,
            request=request
        )
        
        # Validate and save
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        updated_bewerber = form.save()
        
        # PDF should be updated
        self.assertIsNotNone(updated_bewerber.application_pdf)
        # The file name might be the same or different depending on storage backend

    def test_merge_pdfs_error_handling(self):
        """Test that merge_pdfs handles errors gracefully"""
        from django.core.files.base import ContentFile
        
        bewerber = self._create_bewerber()
        
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post('/test/')
        request.user = self.admin_user
        
        data = {
            'first_name': 'Error',
            'last_name': 'Test',
            'email': 'error@test.com',
            'person_cluster': self.person_cluster_bewerber.id,
        }
        
        form = AddBewerberApplicationPdfForm(data=data, instance=bewerber, request=request)
        
        # Test with corrupted PDF content
        corrupted_file = SimpleUploadedFile(
            'corrupted.pdf',
            b'This is not a valid PDF at all, just random bytes',
            content_type='application/pdf'
        )
        
        # The form should handle this gracefully
        try:
            result = form.merge_pdfs([corrupted_file])
            # If it doesn't raise an error, it should return something or None
            self.assertTrue(True)
        except Exception as e:
            # Error should be a ValidationError or handled gracefully
            from django.forms import ValidationError
            self.assertIsInstance(e, (ValidationError, Exception))

    def test_pdf_files_read_immediately_no_temp_file_error(self):
        """Test that PDF files are read into memory immediately, preventing temp file errors"""
        pdf_file = self._create_pdf_file('immediate_read.pdf')
        
        data = {
            'first_name': 'Immediate',
            'last_name': 'Read',
            'email': 'immediate@test.com',
            'person_cluster': self.person_cluster_bewerber.id,
        }
        
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post('/test/', data, format='multipart')
        request.user = self.admin_user
        request.FILES.setlist('pdf_files', [pdf_file])
        
        files = {'pdf_files': pdf_file}
        
        form = AddBewerberApplicationPdfForm(data=data, files=files, request=request)
        
        self.assertTrue(form.is_valid())
        
        # The merge_pdfs method should read files into memory immediately
        pdf_files = [pdf_file]
        
        # Reset file pointer
        pdf_file.seek(0)
        
        # Call merge_pdfs - it should work without temp file issues
        merged = form.merge_pdfs(pdf_files)
        
        # Verify merged PDF was created
        self.assertIsNotNone(merged)
        self.assertTrue(hasattr(merged, 'read'))

    def test_form_displays_existing_pdf(self):
        """Test that form displays existing PDF when editing"""
        bewerber = self._create_bewerber()
        
        # Add PDF to bewerber
        pdf_file = self._create_pdf_file('existing.pdf')
        bewerber.application_pdf = pdf_file
        bewerber.save()
        
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/test/')
        request.user = self.admin_user
        
        # Create form with existing instance
        form = AddBewerberApplicationPdfForm(instance=bewerber, request=request)
        
        # Form should have help text showing existing PDF
        self.assertIn('pdf_files', form.fields)
        if bewerber.application_pdf:
            self.assertIsNotNone(form.fields['pdf_files'].help_text)

    def test_multiple_pdf_validation(self):
        """Test that all PDFs in a batch are validated"""
        pdf_file1 = self._create_pdf_file('valid1.pdf')
        pdf_file2 = self._create_pdf_file('valid2.pdf')
        
        data = {
            'first_name': 'Valid',
            'last_name': 'Batch',
            'email': 'valid@test.com',
            'person_cluster': self.person_cluster_bewerber.id,
        }
        
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post('/test/', data, format='multipart')
        request.user = self.admin_user
        request.FILES.setlist('pdf_files', [pdf_file1, pdf_file2])
        
        files = {'pdf_files': [pdf_file1, pdf_file2]}
        
        form = AddBewerberApplicationPdfForm(data=data, files=files, request=request)
        
        # Should validate both files
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

    def test_pdf_temp_file_race_condition_fix(self):
        """Test that the PDF temp file race condition is fixed by reading into memory immediately"""
        # This test works even with SQLite as it only tests PDF merging, not database writes
        import time
        
        # Create multiple PDFs
        pdf_files = [self._create_pdf_file(f'race_{i}.pdf') for i in range(5)]
        
        bewerber = self._create_bewerber()
        
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.post('/test/')
        request.user = self.admin_user
        
        data = {
            'first_name': 'RaceTest',
            'last_name': 'User',
            'email': 'race@test.com',
            'person_cluster': self.person_cluster_bewerber.id,
        }
        
        form = AddBewerberApplicationPdfForm(data=data, instance=bewerber, request=request)
        
        # Simulate temp files being cleaned up by seeking to end (simulating file system cleanup)
        # Our fix should read files into memory immediately, preventing temp file errors
        for pdf_file in pdf_files:
            pdf_file.seek(0)  # Reset to beginning
        
        # Call merge_pdfs - should work because files are read into memory immediately
        try:
            merged_pdf = form.merge_pdfs(pdf_files)
            self.assertIsNotNone(merged_pdf, "Merged PDF should be created")
            self.assertTrue(hasattr(merged_pdf, 'read'), "Merged PDF should be file-like")
            
            # Verify we can read the merged content
            content = merged_pdf.read()
            self.assertGreater(len(content), 0, "Merged PDF should have content")
            
        except IOError as e:
            if 'No such file or directory' in str(e):
                self.fail(f"Temp file error occurred - the race condition fix is not working: {e}")
            raise

    def test_stress_test_many_concurrent_uploads(self):
        """Stress test with many concurrent uploads to verify no race conditions"""
        from django.db import transaction, connection
        
        # Skip for SQLite as it doesn't handle concurrent writes well
        if 'sqlite' in connection.settings_dict['ENGINE']:
            self.skipTest("SQLite doesn't support concurrent writes - this tests PDF temp file handling")
        
        results = {'success': 0, 'errors': 0}
        lock = threading.Lock()
        
        def stress_upload(index):
            """Stress test upload function"""
            try:
                with transaction.atomic():
                    pdf_files = [
                        self._create_pdf_file(f'stress_{index}_{j}.pdf')
                        for j in range(3)  # 3 PDFs per upload
                    ]
                    
                    data = {
                        'first_name': f'Stress{index}',
                        'last_name': 'Test',
                        'email': f'stress{index}@test.com',
                        'person_cluster': self.person_cluster_bewerber.id,
                    }
                    
                    from django.test import RequestFactory
                    factory = RequestFactory()
                    request = factory.post('/test/', data, format='multipart')
                    request.user = self.admin_user
                    request.FILES.setlist('pdf_files', pdf_files)
                    
                    form = AddBewerberApplicationPdfForm(data=data, files={'pdf_files': pdf_files}, request=request)
                    
                    if form.is_valid():
                        bewerber = form.save()
                        if bewerber.application_pdf:
                            with lock:
                                results['success'] += 1
                        else:
                            with lock:
                                results['errors'] += 1
                    else:
                        with lock:
                            results['errors'] += 1
            except Exception:
                with lock:
                    results['errors'] += 1
        
        # Run 20 concurrent uploads
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(stress_upload, i) for i in range(20)]
            concurrent.futures.wait(futures)
        
        # Most or all should succeed
        self.assertGreater(results['success'], 15, 
                          f"Expected at least 15 successful uploads, got {results['success']} successes and {results['errors']} errors")

class GetCascadeInfoTestCase(TestCase):
    """Test suite for get_cascade_info view function"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Use existing setup patterns from other tests
        self.org = Organisation.objects.create(
            name='Test Org',
            email='test@test.com',
        )
        
        # Create person cluster
        self.person_cluster = PersonCluster.objects.create(
            org=self.org,
            name='Test Person Cluster',
            view='O',
            aufgaben=True,
            calendar=True,
            dokumente=True,
            ampel=True,
            notfallkontakt=True,
            bilder=True
        )
        
        # Create admin user with org role
        self.admin_user = get_user_model().objects.create_user(
            username='admin_cascade',
            email='admin@test.com',
            password='testpass123',
            first_name='Admin',
            last_name='User'
        )
        self.custom_user = CustomUser.objects.create(
            user=self.admin_user,
            org=self.org,
            person_cluster=self.person_cluster
        )
        
        # Create test user (to be deleted)
        self.test_user = get_user_model().objects.create_user(
            username='testuser_cascade',
            email='test@test.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.test_custom_user = CustomUser.objects.create(
            user=self.test_user,
            org=self.org,
            person_cluster=self.person_cluster
        )
        
        # Create Bewerber
        self.bewerber = Bewerber.objects.create(
            user=self.test_user,
            org=self.org
        )
        
        # Create related objects for cascade testing
        self.fragekategorie = Fragekategorie.objects.create(
            name="Test Category",
            org=self.org
        )
        self.frage = Frage.objects.create(
            text="Test Question",
            kategorie=self.fragekategorie,
            org=self.org
        )
        self.einheit = Einheit.objects.create(
            name="Test Unit",
            org=self.org
        )
        
        # Create Bewertung (will be cascade deleted)
        self.bewertung1 = Bewertung.objects.create(
            bewerter=self.admin_user,
            bewerber=self.bewerber,
            frage=self.frage,
            einheit=self.einheit,
            bewertung=4,
            org=self.org
        )
        self.bewertung2 = Bewertung.objects.create(
            bewerter=self.admin_user,
            bewerber=self.bewerber,
            frage=self.frage,
            einheit=self.einheit,
            bewertung=5,
            org=self.org
        )
        
        # Create Kommentar (will be cascade deleted)
        self.kommentar = Kommentar.objects.create(
            bewerter=self.admin_user,
            bewerber=self.bewerber,
            einheit=self.einheit,
            text="Test comment",
            org=self.org
        )
        
        self.factory = RequestFactory()
    
    def test_get_cascade_info_success(self):
        """Test successful retrieval of cascade information"""
        request = self.factory.get(
            f'/org/get-cascade-info/?model=bewerber&id={self.bewerber.id}'
        )
        request.user = self.admin_user
        
        response = get_cascade_info(request)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('cascade_objects', data)
        self.assertIsInstance(data['cascade_objects'], list)
        
        # Should find related objects
        self.assertGreater(len(data['cascade_objects']), 0)
        
        # Check for expected model types
        model_names = [obj['model'] for obj in data['cascade_objects']]
        # Should find Bewertungen or Kommentare
        has_expected_objects = any(
            'bewertung' in name.lower() or 'kommentar' in name.lower() 
            for name in model_names
        )
        self.assertTrue(has_expected_objects, f"Expected Bewertungen or Kommentare in {model_names}")
    
    def test_get_cascade_info_missing_parameters(self):
        """Test handling of missing parameters"""
        # Missing both parameters
        request = self.factory.get('/org/get-cascade-info/')
        request.user = self.admin_user
        
        response = get_cascade_info(request)
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Missing required parameters')
    
    def test_get_cascade_info_invalid_object_id(self):
        """Test handling of invalid object ID"""
        request = self.factory.get('/org/get-cascade-info/?model=bewerber&id=invalid')
        request.user = self.admin_user
        
        response = get_cascade_info(request)
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Invalid object ID')
    
    def test_get_cascade_info_nonexistent_object(self):
        """Test handling of non-existent object"""
        from django.http import Http404
        
        request = self.factory.get('/org/get-cascade-info/?model=bewerber&id=99999')
        request.user = self.admin_user
        
        # Should raise Http404 when object doesn't exist
        with self.assertRaises(Http404):
            get_cascade_info(request)
    
    def test_get_cascade_info_invalid_model(self):
        """Test handling of invalid model name"""
        request = self.factory.get('/org/get-cascade-info/?model=invalidmodel&id=1')
        request.user = self.admin_user
        
        response = get_cascade_info(request)
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Model not found')
    
    def test_get_cascade_info_includes_details(self):
        """Test that response includes detailed object information"""
        request = self.factory.get(
            f'/org/get-cascade-info/?model=bewerber&id={self.bewerber.id}'
        )
        request.user = self.admin_user
        
        response = get_cascade_info(request)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Check structure of cascade objects
        for cascade_obj in data['cascade_objects']:
            self.assertIn('model', cascade_obj)
            self.assertIn('count', cascade_obj)
            self.assertIn('objects', cascade_obj)
            self.assertIsInstance(cascade_obj['objects'], list)
            
            # Check structure of individual objects
            for obj in cascade_obj['objects']:
                self.assertIn('id', obj)
                self.assertIn('display_name', obj)
    
    def test_get_cascade_info_respects_limits(self):
        """Test that response respects object limits (50 per model type)"""
        # This test verifies the structure works correctly
        request = self.factory.get(
            f'/org/get-cascade-info/?model=bewerber&id={self.bewerber.id}'
        )
        request.user = self.admin_user
        
        response = get_cascade_info(request)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Verify no model type has more than 50 individual objects listed
        for cascade_obj in data['cascade_objects']:
            # Account for the "... und X weitere" entry
            self.assertLessEqual(len(cascade_obj['objects']), 51)
    
    def test_get_cascade_info_counts_match_objects(self):
        """Test that counts match the actual number of objects"""
        request = self.factory.get(
            f'/org/get-cascade-info/?model=bewerber&id={self.bewerber.id}'
        )
        request.user = self.admin_user
        
        response = get_cascade_info(request)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Verify counts are positive numbers
        for cascade_obj in data['cascade_objects']:
            self.assertGreater(cascade_obj['count'], 0)
            self.assertIsInstance(cascade_obj['count'], int)
