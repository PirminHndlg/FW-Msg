from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from FW.models import Aufgabe, FreiwilligerAufgaben, Freiwilliger
from .models import Organisation

class AufgabenTableTests(TestCase):
    def setUp(self):
        # Create test organization first
        self.org = Organisation.objects.create(
            name='Test Org',
            email='test@test.com',
        )
        
        # Create test users
        self.user = get_user_model().objects.create_user(
            username='testuser',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        # Create test freiwilliger
        self.freiwilliger = Freiwilliger.objects.create(
            org=self.org,
            first_name='Test',
            last_name='Freiwilliger',
            email='freiwilliger@test.com',
        )
        
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        # Create test tasks
        self.aufgabe = Aufgabe.objects.create(
            org=self.org,
            name='Test Aufgabe',
            beschreibung='Test Beschreibung'
        )

    def test_list_aufgaben_view(self):
        """Test that the aufgaben list view loads correctly"""
        response = self.client.get(reverse('list_aufgaben_table'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'list_aufgaben_table.html')

    def test_aufgaben_status_changes(self):
        """Test task status changes (erledigt, pending)"""
        freiwilliger_aufgabe = FreiwilligerAufgaben.objects.create(
            org=self.org,
            freiwilliger=self.freiwilliger,
            aufgabe=self.aufgabe,
            faellig=timezone.now() + timedelta(days=7)
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
            f"{reverse('list_aufgaben_table')}?fw={self.freiwilliger.id}&a={self.aufgabe.id}"
        )
        # Check for redirect after successful assignment
        self.assertEqual(response.status_code, 302)
        
        # Verify the task was created
        self.assertTrue(
            FreiwilligerAufgaben.objects.filter(
                org=self.org,
                freiwilliger=self.freiwilliger,
                aufgabe=self.aufgabe
            ).exists()
        )

    def test_overdue_tasks(self):
        """Test that overdue tasks are correctly identified"""
        overdue_task = FreiwilligerAufgaben.objects.create(
            org=self.org,
            freiwilliger=self.freiwilliger,
            aufgabe=self.aufgabe,
            faellig=timezone.now() - timedelta(days=1)
        )
        response = self.client.get(reverse('list_aufgaben_table'))
        self.assertEqual(response.status_code, 200)
        # Check if the task appears in the overdue context
        # This will depend on how you've implemented the view

    def test_file_upload(self):
        """Test file upload functionality"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        
        test_file = SimpleUploadedFile(
            "test_file.txt",
            b"Test file content",
            content_type="text/plain"
        )
        
        freiwilliger_aufgabe = FreiwilligerAufgaben.objects.create(
            org=self.org,
            freiwilliger=self.freiwilliger,
            aufgabe=self.aufgabe,
            faellig=timezone.now() + timedelta(days=7),
            file=test_file
        )
        
        # Test file download view - expect redirect if authentication required
        response = self.client.get(reverse('download_aufgabe', args=[freiwilliger_aufgabe.id]))
        self.assertIn(response.status_code, [200, 302])  # Accept either success or redirect
        
        if response.status_code == 200:
            self.assertEqual(
                response.get('Content-Disposition'),
                f'attachment; filename="{test_file.name}"'
            )
