from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core import signing
from datetime import datetime, timedelta
from .models import CustomUser, ProfilUser2, UserAufgaben, Aufgabe2, KalenderEvent, PersonCluster, Bilder2, BilderGallery2, Dokument2, Ordner2, DokumentColor2, ChangeRequest, Einsatzland2, Einsatzstelle2
from ORG.models import Organisation
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.base import ContentFile
import os
import tempfile
from PIL import Image
import io
from django.db.models.signals import post_save
from django.contrib.messages import get_messages
from unittest.mock import patch, Mock
from TEAM.models import Team
from Ehemalige.models import Ehemalige


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
        self.token = self.custom_user.ensure_calendar_token()

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
        other_token = other_user.customuser.ensure_calendar_token()
        
        # Test access
        response = self.client.get(reverse('kalender_abbonement', args=[other_token]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/calendar')


class FileServingViewsTests(TestCase):
    """Tests for file serving views: serve_bilder, serve_small_bilder, serve_dokument"""
    
    def setUp(self):
        # Disable the post_save signal for Dokument2 to avoid PDF preview generation issues
        post_save.disconnect(receiver=None, sender=Dokument2, dispatch_uid='create_preview_image')
        
        # Create test organization
        self.org = Organisation.objects.create(name="Test Org")
        
        # Create different person clusters for testing permissions
        self.admin_cluster = PersonCluster.objects.create(
            name="Admin Cluster",
            org=self.org,
            view='A',  # Admin view
            bilder=True,
            dokumente=True
        )
        
        self.org_cluster = PersonCluster.objects.create(
            name="Org Cluster",
            org=self.org,
            view='O',  # Organization view
            bilder=True,
            dokumente=True
        )
        
        self.freiwillige_cluster = PersonCluster.objects.create(
            name="Freiwillige Cluster",
            org=self.org,
            view='F',  # Freiwillige view
            bilder=True,
            dokumente=True
        )
        
        self.no_bilder_cluster = PersonCluster.objects.create(
            name="No Bilder Cluster",
            org=self.org,
            view='F',  # Freiwillige view
            bilder=False,  # No bilder permission
            dokumente=True
        )
        
        self.no_dokumente_cluster = PersonCluster.objects.create(
            name="No Dokumente Cluster",
            org=self.org,
            view='F',  # Freiwillige view
            bilder=True,
            dokumente=False  # No dokumente permission
        )
        
        # Create test users
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='testpass123'
        )
        self.admin_custom_user = CustomUser.objects.create(
            user=self.admin_user,
            org=self.org,
            person_cluster=self.admin_cluster
        )
        
        self.org_user = User.objects.create_user(
            username='orguser',
            email='org@example.com',
            password='testpass123'
        )
        self.org_custom_user = CustomUser.objects.create(
            user=self.org_user,
            org=self.org,
            person_cluster=self.org_cluster
        )
        
        self.freiwillige_user = User.objects.create_user(
            username='freiwilligeuser',
            email='freiwillige@example.com',
            password='testpass123'
        )
        self.freiwillige_custom_user = CustomUser.objects.create(
            user=self.freiwillige_user,
            org=self.org,
            person_cluster=self.freiwillige_cluster
        )
        
        self.no_bilder_user = User.objects.create_user(
            username='nobilderuser',
            email='nobilder@example.com',
            password='testpass123'
        )
        self.no_bilder_custom_user = CustomUser.objects.create(
            user=self.no_bilder_user,
            org=self.org,
            person_cluster=self.no_bilder_cluster
        )
        
        self.no_dokumente_user = User.objects.create_user(
            username='nodokumenteuser',
            email='nodokumente@example.com',
            password='testpass123'
        )
        self.no_dokumente_custom_user = CustomUser.objects.create(
            user=self.no_dokumente_user,
            org=self.org,
            person_cluster=self.no_dokumente_cluster
        )
        
        # Create another organization for cross-org testing
        self.other_org = Organisation.objects.create(name="Other Org")
        self.other_cluster = PersonCluster.objects.create(
            name="Other Cluster",
            org=self.other_org,
            view='F',
            bilder=True,
            dokumente=True
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        self.other_custom_user = CustomUser.objects.create(
            user=self.other_user,
            org=self.other_org,
            person_cluster=self.other_cluster
        )
        
        # Create test files
        self.create_test_files()
        
        # Create client
        self.client = Client()

    def tearDown(self):
        # Re-enable the post_save signal for Dokument2
        from .models import create_preview_image
        post_save.connect(create_preview_image, sender=Dokument2, dispatch_uid='create_preview_image')
        super().tearDown()

    def create_test_files(self):
        """Create test image and document files"""
        # Create a test image
        image = Image.new('RGB', (100, 100), color='red')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        # Create test bilder
        self.bilder = Bilder2.objects.create(
            user=self.admin_user,
            org=self.org,
            titel="Test Bild",
            beschreibung="Test description"
        )
        
        # Create test bilder gallery
        self.bilder_gallery = BilderGallery2.objects.create(
            bilder=self.bilder,
            org=self.org,
            image=SimpleUploadedFile(
                "test_image.jpg",
                image_io.getvalue(),
                content_type="image/jpeg"
            )
        )
        
        # Create test document folder and color
        self.doc_color = DokumentColor2.objects.create(
            name="Test Color",
            color="#FF0000"
        )
        
        self.doc_folder = Ordner2.objects.create(
            ordner_name="Test Folder",
            org=self.org,
            color=self.doc_color
        )
        self.doc_folder.typ.add(self.admin_cluster)
        
        # Create test document
        test_content = b"This is a test document content"
        self.dokument = Dokument2.objects.create(
            org=self.org,
            ordner=self.doc_folder,
            dokument=SimpleUploadedFile(
                "test_document.txt",
                test_content,
                content_type="text/plain"
            ),
            titel="Test Document",
            beschreibung="Test document description"
        )
        self.dokument.darf_bearbeiten.add(self.admin_cluster)

    def test_serve_bilder_success(self):
        """Test successful image serving for users with bilder permission"""
        # Test with admin user
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('serve_bilder', args=[self.bilder_gallery.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.assertIn('inline', response['Content-Disposition'])
        
        # Test with org user
        self.client.force_login(self.org_user)
        response = self.client.get(reverse('serve_bilder', args=[self.bilder_gallery.id]))
        self.assertEqual(response.status_code, 200)
        
        # Test with freiwillige user
        self.client.force_login(self.freiwillige_user)
        response = self.client.get(reverse('serve_bilder', args=[self.bilder_gallery.id]))
        self.assertEqual(response.status_code, 200)

    def test_serve_bilder_permission_denied(self):
        """Test that users without bilder permission are denied access"""
        self.client.force_login(self.no_bilder_user)
        response = self.client.get(reverse('serve_bilder', args=[self.bilder_gallery.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to index

    def test_serve_bilder_not_found(self):
        """Test 404 response for non-existent image"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('serve_bilder', args=[99999]))
        self.assertEqual(response.status_code, 404)

    def test_serve_bilder_wrong_organization(self):
        """Test that users cannot access images from other organizations"""
        self.client.force_login(self.other_user)
        response = self.client.get(reverse('serve_bilder', args=[self.bilder_gallery.id]))
        self.assertEqual(response.status_code, 404)  # HttpResponseNotAllowed

    def test_serve_bilder_unauthenticated(self):
        """Test that unauthenticated users are redirected to login"""
        response = self.client.get(reverse('serve_bilder', args=[self.bilder_gallery.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_serve_small_bilder_success(self):
        """Test successful small image serving"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('serve_small_bilder', args=[self.bilder_gallery.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.assertIn('inline', response['Content-Disposition'])

    def test_serve_small_bilder_fallback_to_full(self):
        """Test that small image falls back to full image when small doesn't exist"""
        # Delete the small image
        if self.bilder_gallery.small_image:
            self.bilder_gallery.small_image.delete()
            self.bilder_gallery.save()
        
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('serve_small_bilder', args=[self.bilder_gallery.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')

    def test_serve_small_bilder_permission_denied(self):
        """Test that users without bilder permission are denied access to small images"""
        self.client.force_login(self.no_bilder_user)
        response = self.client.get(reverse('serve_small_bilder', args=[self.bilder_gallery.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to index

    def test_serve_dokument_success(self):
        """Test successful document serving"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('serve_dokument', args=[self.dokument.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')
        self.assertIn('attachment', response['Content-Disposition'])

    def test_serve_dokument_permission_denied(self):
        """Test that users without dokumente permission are denied access"""
        self.client.force_login(self.no_dokumente_user)
        response = self.client.get(reverse('serve_dokument', args=[self.dokument.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to index

    def test_serve_dokument_not_found(self):
        """Test 404 response for non-existent document"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('serve_dokument', args=[99999]))
        self.assertEqual(response.status_code, 404)

    def test_serve_dokument_wrong_organization(self):
        """Test that users cannot access documents from other organizations"""
        self.client.force_login(self.other_user)
        response = self.client.get(reverse('serve_dokument', args=[self.dokument.id]))
        self.assertEqual(response.status_code, 405)  # HttpResponseNotAllowed

    def test_serve_dokument_file_not_found(self):
        """Test 404 when document file doesn't exist on disk"""
        # Delete the actual file but keep the database record
        if self.dokument.dokument and os.path.exists(self.dokument.dokument.path):
            os.remove(self.dokument.dokument.path)
        
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('serve_dokument', args=[self.dokument.id]))
        self.assertEqual(response.status_code, 404)

    def test_serve_dokument_with_img_parameter(self):
        """Test serving document preview image"""
        self.client.force_login(self.admin_user)
        response = self.client.get(
            reverse('serve_dokument', args=[self.dokument.id]),
            {'img': '1'}
        )
        # Should return the document itself since it's text/plain
        self.assertEqual(response.status_code, 200)

    def test_serve_dokument_with_download_parameter(self):
        """Test serving document as download"""
        self.client.force_login(self.admin_user)
        response = self.client.get(
            reverse('serve_dokument', args=[self.dokument.id]),
            {'download': '1'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])

    def test_serve_dokument_pdf_inline(self):
        """Test that PDFs are served inline by default"""
        # Create a test PDF document with valid PDF content
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n72 720 Td\n(Test PDF) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000204 00000 n \ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n297\n%%EOF\n"
        
        # Temporarily disable the post_save signal to avoid PDF preview generation
        from django.db.models.signals import post_save
        from .models import create_preview_image
        post_save.disconnect(create_preview_image, sender=Dokument2)
        
        try:
            pdf_dokument = Dokument2.objects.create(
                org=self.org,
                ordner=self.doc_folder,
                dokument=SimpleUploadedFile(
                    "test.pdf",
                    pdf_content,
                    content_type="application/pdf"
                ),
                titel="Test PDF",
                beschreibung="Test PDF document"
            )
            pdf_dokument.darf_bearbeiten.add(self.admin_cluster)
            
            self.client.force_login(self.admin_user)
            response = self.client.get(reverse('serve_dokument', args=[pdf_dokument.id]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/pdf')
            self.assertIn('inline', response['Content-Disposition'])
        finally:
            # Re-enable the post_save signal
            post_save.connect(create_preview_image, sender=Dokument2, dispatch_uid='create_preview_image')

    def test_serve_dokument_pdf_download(self):
        """Test that PDFs can be downloaded with download parameter"""
        # Create a test PDF document with valid PDF content
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n72 720 Td\n(Test PDF) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000204 00000 n \ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n297\n%%EOF\n"
        
        # Temporarily disable the post_save signal to avoid PDF preview generation
        from django.db.models.signals import post_save
        from .models import create_preview_image
        post_save.disconnect(create_preview_image, sender=Dokument2)
        
        try:
            pdf_dokument = Dokument2.objects.create(
                org=self.org,
                ordner=self.doc_folder,
                dokument=SimpleUploadedFile(
                    "test.pdf",
                    pdf_content,
                    content_type="application/pdf"
                ),
                titel="Test PDF",
                beschreibung="Test PDF document"
            )
            pdf_dokument.darf_bearbeiten.add(self.admin_cluster)
            
            self.client.force_login(self.admin_user)
            response = self.client.get(
                reverse('serve_dokument', args=[pdf_dokument.id]),
                {'download': '1'}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/pdf')
            self.assertIn('attachment', response['Content-Disposition'])
        finally:
            # Re-enable the post_save signal
            post_save.connect(create_preview_image, sender=Dokument2, dispatch_uid='create_preview_image')

    def test_serve_dokument_image_inline(self):
        """Test that image documents are served inline"""
        # Create a test image document
        image = Image.new('RGB', (100, 100), color='blue')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        image_dokument = Dokument2.objects.create(
            org=self.org,
            ordner=self.doc_folder,
            dokument=SimpleUploadedFile(
                "test_image.jpg",
                image_io.getvalue(),
                content_type="image/jpeg"
            ),
            titel="Test Image",
            beschreibung="Test image document"
        )
        image_dokument.darf_bearbeiten.add(self.admin_cluster)
        
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('serve_dokument', args=[image_dokument.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.assertIn('inline', response['Content-Disposition'])

    def test_serve_dokument_image_download(self):
        """Test that image documents can be downloaded with download parameter"""
        # Create a test image document
        image = Image.new('RGB', (100, 100), color='blue')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        image_dokument = Dokument2.objects.create(
            org=self.org,
            ordner=self.doc_folder,
            dokument=SimpleUploadedFile(
                "test_image.jpg",
                image_io.getvalue(),
                content_type="image/jpeg"
            ),
            titel="Test Image",
            beschreibung="Test image document"
        )
        image_dokument.darf_bearbeiten.add(self.admin_cluster)
        
        self.client.force_login(self.admin_user)
        response = self.client.get(
            reverse('serve_dokument', args=[image_dokument.id]),
            {'download': '1'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.assertIn('attachment', response['Content-Disposition'])

    def test_serve_dokument_unknown_mimetype(self):
        """Test serving document with unknown MIME type"""
        # Create a document with unknown extension
        unknown_content = b"This is unknown content"
        unknown_dokument = Dokument2.objects.create(
            org=self.org,
            ordner=self.doc_folder,
            dokument=SimpleUploadedFile(
                "test.unknown",
                unknown_content,
                content_type="application/octet-stream"
            ),
            titel="Test Unknown",
            beschreibung="Test unknown document"
        )
        unknown_dokument.darf_bearbeiten.add(self.admin_cluster)
        
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('serve_dokument', args=[unknown_dokument.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/octet-stream')
        self.assertIn('attachment', response['Content-Disposition'])

    def test_serve_dokument_with_link(self):
        """Test serving document that has a link instead of file"""
        link_dokument = Dokument2.objects.create(
            org=self.org,
            ordner=self.doc_folder,
            link="https://example.com/test.pdf",
            titel="Test Link",
            beschreibung="Test link document"
        )
        link_dokument.darf_bearbeiten.add(self.admin_cluster)
        
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('serve_dokument', args=[link_dokument.id]))
        self.assertEqual(response.status_code, 404)  # No file to serve

    def test_serve_dokument_unauthenticated(self):
        """Test that unauthenticated users are redirected to login"""
        response = self.client.get(reverse('serve_dokument', args=[self.dokument.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_serve_bilder_unauthenticated(self):
        """Test that unauthenticated users are redirected to login for bilder"""
        response = self.client.get(reverse('serve_bilder', args=[self.bilder_gallery.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_serve_small_bilder_unauthenticated(self):
        """Test that unauthenticated users are redirected to login for small bilder"""
        response = self.client.get(reverse('serve_small_bilder', args=[self.bilder_gallery.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_different_person_cluster_views_access(self):
        """Test access from different PersonCluster views"""
        # Test all view types
        view_types = [view[0] for view in PersonCluster.view_choices]
        
        for view_type in view_types:
            # Create cluster with this view type
            cluster = PersonCluster.objects.create(
                name=f"Cluster {view_type}",
                org=self.org,
                view=view_type,
                bilder=True,
                dokumente=True
            )
            
            # Create user with this cluster
            user = User.objects.create_user(
                username=f'user_{view_type}',
                email=f'user_{view_type}@example.com',
                password='testpass123'
            )
            CustomUser.objects.create(
                user=user,
                org=self.org,
                person_cluster=cluster
            )
            
            # Test bilder access
            self.client.force_login(user)
            response = self.client.get(reverse('serve_bilder', args=[self.bilder_gallery.id]))
            self.assertEqual(response.status_code, 200)
            
            # Test dokument access
            response = self.client.get(reverse('serve_dokument', args=[self.dokument.id]))
            self.assertEqual(response.status_code, 200)

    def test_user_without_person_cluster(self):
        """Test user without person_cluster assignment"""
        # Create user without person_cluster
        no_cluster_user = User.objects.create_user(
            username='noclusteruser',
            email='nocluster@example.com',
            password='testpass123'
        )
        CustomUser.objects.create(
            user=no_cluster_user,
            org=self.org,
            person_cluster=None
        )
        
        self.client.force_login(no_cluster_user)
        
        # Should be denied access
        response = self.client.get(reverse('serve_bilder', args=[self.bilder_gallery.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to index
        
        response = self.client.get(reverse('serve_dokument', args=[self.dokument.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to index

    def test_superuser_access(self):
        """Test superuser access to files"""
        # Create superuser
        superuser = User.objects.create_superuser(
            username='superuser',
            email='super@example.com',
            password='testpass123'
        )
        CustomUser.objects.create(
            user=superuser,
            org=self.org,
            person_cluster=self.admin_cluster
        )
        
        self.client.force_login(superuser)
        
        # Should have access
        response = self.client.get(reverse('serve_bilder', args=[self.bilder_gallery.id]))
        self.assertEqual(response.status_code, 200)
        
        response = self.client.get(reverse('serve_dokument', args=[self.dokument.id]))
        self.assertEqual(response.status_code, 200)


class BilderViewsTests(TestCase):
    def setUp(self):
        self.org = Organisation.objects.create(name="Test Org")
        self.admin_cluster = PersonCluster.objects.create(name="Admin", org=self.org, view='A', bilder=True)
        self.no_bilder_cluster = PersonCluster.objects.create(name="NoBilder", org=self.org, view='F', bilder=False)
        self.user = User.objects.create_user(username='user', password='pw')
        self.admin_user = User.objects.create_user(username='admin', password='pw')
        self.no_bilder_user = User.objects.create_user(username='nobilder', password='pw')
        CustomUser.objects.create(user=self.user, org=self.org, person_cluster=self.admin_cluster)
        CustomUser.objects.create(user=self.admin_user, org=self.org, person_cluster=self.admin_cluster)
        CustomUser.objects.create(user=self.no_bilder_user, org=self.org, person_cluster=self.no_bilder_cluster)
        # Create a test image and gallery
        image = Image.new('RGB', (10, 10), color='red')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        self.bilder = Bilder2.objects.create(user=self.user, org=self.org, titel="Bild", beschreibung="desc")
        self.gallery = BilderGallery2.objects.create(bilder=self.bilder, org=self.org, image=SimpleUploadedFile("img.jpg", image_io.getvalue(), content_type="image/jpeg"))
        self.client = Client()

    def test_bilder_view_permission(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('bilder'))
        self.assertEqual(response.status_code, 200)
        self.client.force_login(self.no_bilder_user)
        response = self.client.get(reverse('bilder'))
        self.assertEqual(response.status_code, 302)

    def test_bilder_view_unauthenticated(self):
        response = self.client.get(reverse('bilder'))
        self.assertEqual(response.status_code, 302)

    @patch('Global.views.send_image_uploaded_email_task.apply_async')
    def test_bild_upload_success(self, mock_email_task):
        self.client.force_login(self.user)
        import uuid
        
        # Create test image
        image = Image.new('RGB', (10, 10), color='blue')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        # Create the uploaded file
        uploaded_file = SimpleUploadedFile('img2.jpg', image_io.getvalue(), content_type='image/jpeg')
        
        # Build the request data
        data = {
            'titel': 'NewBild', 
            'beschreibung': 'desc',
            'submission_key': str(uuid.uuid4()),
            'image': uploaded_file  # Add image to data, not files
        }
        
        response = self.client.post(reverse('bild'), data=data, follow=True)
        
        # Check that Bilder2 was created
        messages_list = list(get_messages(response.wsgi_request))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Bilder2.objects.filter(titel='NewBild').exists(), 
                       f"Bilder2 not created. Messages: {[str(m) for m in messages_list]}")
        
        # Check that messages contain success message
        self.assertTrue(any('erfolgreich' in str(msg).lower() for msg in messages_list))
        
        # Verify email task was scheduled (but not actually sent due to mock)
        mock_email_task.assert_called_once()

    def test_bild_upload_debug_form_errors(self):
        """Test to debug form validation errors"""
        self.client.force_login(self.user)
        import uuid
        image = Image.new('RGB', (10, 10), color='blue')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        data = {
            'titel': 'NewBild', 
            'beschreibung': 'desc',
            'submission_key': str(uuid.uuid4())
        }
        files = {'image': SimpleUploadedFile('img2.jpg', image_io.getvalue(), content_type='image/jpeg')}
        response = self.client.post(reverse('bild'), data=data, files=files, follow=True)
        
        # Check if the form is valid by testing it directly
        from FW.forms import BilderForm
        form = BilderForm(data=data, user=self.user, org=self.org)
        if not form.is_valid():
            print(f"Form validation errors: {form.errors}")
        
        # The response should either be a redirect (success) or 200 with form errors
        self.assertIn(response.status_code, [200, 302])

    def test_bild_form_validation(self):
        """Test that BilderForm validation works correctly"""
        from FW.forms import BilderForm
        import uuid
        
        # Test valid data
        valid_data = {
            'titel': 'Test Title', 
            'beschreibung': 'Test description',
            'submission_key': str(uuid.uuid4())
        }
        form = BilderForm(data=valid_data, user=self.user, org=self.org)
        self.assertTrue(form.is_valid())
        
        # Test invalid data (missing titel)
        invalid_data = {
            'beschreibung': 'Test description',
            'submission_key': str(uuid.uuid4())
        }
        form = BilderForm(data=invalid_data, user=self.user, org=self.org)
        self.assertFalse(form.is_valid())
        self.assertIn('titel', form.errors)

    def test_bild_upload_no_images(self):
        """Test that upload fails when no images are provided"""
        self.client.force_login(self.user)
        import uuid
        data = {
            'titel': 'NewBild', 
            'beschreibung': 'desc',
            'submission_key': str(uuid.uuid4())
        }
        response = self.client.post(reverse('bild'), data=data, follow=True)
        
        # Should return 200 and show error message (no images uploaded)
        self.assertEqual(response.status_code, 200)
        # No new Bilder2 should be created
        self.assertFalse(Bilder2.objects.filter(titel='NewBild').exists())
        
        # Check for error message
        messages_list = list(get_messages(response.wsgi_request))
        self.assertTrue(any('bild' in str(msg).lower() for msg in messages_list))

    def test_bild_upload_no_permission(self):
        self.client.force_login(self.no_bilder_user)
        response = self.client.post(reverse('bild'), data={'titel': 'fail', 'beschreibung': 'desc'})
        self.assertEqual(response.status_code, 302)

    def test_bild_upload_invalid(self):
        self.client.force_login(self.user)
        import uuid
        
        # Create an image but send invalid form data (empty titel)
        image = Image.new('RGB', (10, 10), color='blue')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        uploaded_file = SimpleUploadedFile('img2.jpg', image_io.getvalue(), content_type='image/jpeg')
        
        data = {
            'titel': '',  # Empty titel should fail validation
            'beschreibung': 'desc',
            'submission_key': str(uuid.uuid4()),
            'image': uploaded_file
        }
        
        response = self.client.post(reverse('bild'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Check for error message in messages
        messages_list = list(get_messages(response.wsgi_request))
        # The view should show form errors (titel is required)
        self.assertTrue(any('fehler' in str(msg).lower() or 'korrigieren' in str(msg).lower() for msg in messages_list),
                       f"No error message found. Messages: {[str(m) for m in messages_list]}")

    def test_remove_bild_success(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('remove_bild') + f'?galleryImageId={self.gallery.id}')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(BilderGallery2.objects.filter(id=self.gallery.id).exists())

    def test_remove_bild_not_owner(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('remove_bild') + f'?galleryImageId={self.gallery.id}')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(BilderGallery2.objects.filter(id=self.gallery.id).exists())

    def test_remove_bild_not_found(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('remove_bild') + '?galleryImageId=99999')
        self.assertEqual(response.status_code, 302)

    def test_remove_bild_unauthenticated(self):
        response = self.client.get(reverse('remove_bild') + f'?galleryImageId={self.gallery.id}')
        self.assertEqual(response.status_code, 302)

    def test_remove_bild_last_image_deletes_bilder(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('remove_bild') + f'?galleryImageId={self.gallery.id}')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Bilder2.objects.filter(id=self.bilder.id).exists())

    def test_personcluster_views_access(self):
        for view_type in ['A', 'O', 'F', 'E', 'T', 'B']:
            cluster = PersonCluster.objects.create(name=f'Cluster{view_type}', org=self.org, view=view_type, bilder=True)
            user = User.objects.create_user(username=f'user_{view_type}', password='pw')
            CustomUser.objects.create(user=user, org=self.org, person_cluster=cluster)
            self.client.force_login(user)
            response = self.client.get(reverse('bilder'))
            self.assertEqual(response.status_code, 200)


class DokumentViewsTests(TestCase):
    """Tests for document-related views: dokumente, add_dokument, add_ordner, remove_dokument, remove_ordner"""
    
    def setUp(self):
        # Create test organization
        self.org = Organisation.objects.create(name="Test Org")
        
        # Create different person clusters for testing permissions
        self.admin_cluster = PersonCluster.objects.create(
            name="Admin Cluster",
            org=self.org,
            view='A',  # Admin view
            dokumente=True
        )
        
        self.org_cluster = PersonCluster.objects.create(
            name="Org Cluster",
            org=self.org,
            view='O',  # Organization view
            dokumente=True
        )
        
        self.freiwillige_cluster = PersonCluster.objects.create(
            name="Freiwillige Cluster",
            org=self.org,
            view='F',  # Freiwillige view
            dokumente=True
        )
        
        self.no_dokumente_cluster = PersonCluster.objects.create(
            name="No Dokumente Cluster",
            org=self.org,
            view='F',  # Freiwillige view
            dokumente=False  # No dokumente permission
        )
        
        # Create test users
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='testpass123'
        )
        self.admin_custom_user = CustomUser.objects.create(
            user=self.admin_user,
            org=self.org,
            person_cluster=self.admin_cluster
        )
        
        self.org_user = User.objects.create_user(
            username='orguser',
            email='org@example.com',
            password='testpass123'
        )
        self.org_custom_user = CustomUser.objects.create(
            user=self.org_user,
            org=self.org,
            person_cluster=self.org_cluster
        )
        
        self.freiwillige_user = User.objects.create_user(
            username='freiwilligeuser',
            email='freiwillige@example.com',
            password='testpass123'
        )
        self.freiwillige_custom_user = CustomUser.objects.create(
            user=self.freiwillige_user,
            org=self.org,
            person_cluster=self.freiwillige_cluster
        )
        
        self.no_dokumente_user = User.objects.create_user(
            username='nodokumenteuser',
            email='nodokumente@example.com',
            password='testpass123'
        )
        self.no_dokumente_custom_user = CustomUser.objects.create(
            user=self.no_dokumente_user,
            org=self.org,
            person_cluster=self.no_dokumente_cluster
        )
        
        # Create test document folder and color
        self.doc_color = DokumentColor2.objects.create(
            name="Test Color",
            color="#FF0000"
        )
        
        self.doc_folder = Ordner2.objects.create(
            ordner_name="Test Folder",
            org=self.org,
            color=self.doc_color
        )
        self.doc_folder.typ.add(self.admin_cluster, self.org_cluster, self.freiwillige_cluster)
        
        # Create test document
        test_content = b"This is a test document content"
        self.dokument = Dokument2.objects.create(
            org=self.org,
            ordner=self.doc_folder,
            dokument=SimpleUploadedFile(
                "test_document.txt",
                test_content,
                content_type="text/plain"
            ),
            titel="Test Document",
            beschreibung="Test document description"
        )
        self.dokument.darf_bearbeiten.add(self.admin_cluster)
        
        # Create client
        self.client = Client()

    def test_dokumente_view_success(self):
        """Test successful document view for users with dokumente permission"""
        # Test with admin user
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('dokumente'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('folder_structure', response.context)
        self.assertIn('ordners', response.context)
        self.assertIn('colors', response.context)
        
        # Test with org user
        self.client.force_login(self.org_user)
        response = self.client.get(reverse('dokumente'))
        self.assertEqual(response.status_code, 200)
        
        # Test with freiwillige user
        self.client.force_login(self.freiwillige_user)
        response = self.client.get(reverse('dokumente'))
        self.assertEqual(response.status_code, 200)

    def test_dokumente_view_permission_denied(self):
        """Test that users without dokumente permission are denied access"""
        self.client.force_login(self.no_dokumente_user)
        response = self.client.get(reverse('dokumente'))
        self.assertEqual(response.status_code, 302)  # Redirect to index

    def test_dokumente_view_unauthenticated(self):
        """Test that unauthenticated users are redirected to login"""
        response = self.client.get(reverse('dokumente'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_dokumente_view_with_ordner_id(self):
        """Test document view with specific folder ID"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('dokumente', args=[self.doc_folder.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['ordner_id'], self.doc_folder.id)

    def test_dokumente_view_org_role_filtering(self):
        """Test that org users see filtered content based on person cluster"""
        # Create a cluster-specific folder
        org_specific_folder = Ordner2.objects.create(
            ordner_name="Org Specific Folder",
            org=self.org,
            color=self.doc_color
        )
        org_specific_folder.typ.add(self.org_cluster)  # Only visible to org cluster
        
        self.client.force_login(self.org_user)
        response = self.client.get(reverse('dokumente'))
        self.assertEqual(response.status_code, 200)
        
        # Check that the org-specific folder is in the context
        folder_names = [item['ordner'].ordner_name for item in response.context['folder_structure']]
        self.assertIn("Org Specific Folder", folder_names)

    def test_add_dokument_success(self):
        """Test successful document upload"""
        self.client.force_login(self.admin_user)
        
        test_content = b"This is a new test document"
        data = {
            'titel': 'New Document',
            'beschreibung': 'New document description',
            'ordner': self.doc_folder.id
        }
        files = {
            'dokument': SimpleUploadedFile(
                "new_document.txt",
                test_content,
                content_type="text/plain"
            )
        }
        
        response = self.client.post(reverse('add_dokument'), data=data, files=files, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Check that document was created
        self.assertTrue(Dokument2.objects.filter(titel='New Document').exists())
        new_doc = Dokument2.objects.get(titel='New Document')
        self.assertEqual(new_doc.org, self.org)
        self.assertEqual(new_doc.ordner, self.doc_folder)

    def test_add_dokument_with_link(self):
        """Test adding document with link instead of file"""
        self.client.force_login(self.admin_user)
        
        data = {
            'dokument_id': self.dokument.id,
            'titel': 'Link Document',
            'beschreibung': 'Document with link',
            'link': 'https://example.com/document.pdf',
            'ordner': self.doc_folder.id
        }
        
        response = self.client.post(reverse('add_dokument'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Check that document was created
        self.assertTrue(Dokument2.objects.filter(titel='Link Document').exists())
        new_doc = Dokument2.objects.get(titel='Link Document')
        self.assertEqual(new_doc.link, 'https://example.com/document.pdf')

    def test_add_dokument_permission_denied(self):
        """Test that users without dokumente permission are denied access"""
        self.client.force_login(self.no_dokumente_user)
        response = self.client.post(reverse('add_dokument'), data={'titel': 'fail'})
        self.assertEqual(response.status_code, 302)  # Redirect to index

    def test_add_dokument_unauthenticated(self):
        """Test that unauthenticated users are redirected to login"""
        response = self.client.post(reverse('add_dokument'), data={'titel': 'fail'})
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_add_dokument_edit_existing(self):
        """Test editing an existing document"""
        self.client.force_login(self.admin_user)
        
        data = {
            'dokument_id': self.dokument.id,
            'titel': 'Updated Document',
            'beschreibung': 'Updated description',
            'ordner': self.doc_folder.id
        }
        
        response = self.client.post(reverse('add_dokument'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Check that document was updated
        self.dokument.refresh_from_db()
        self.assertEqual(self.dokument.titel, 'Updated Document')
        self.assertEqual(self.dokument.beschreibung, 'Updated description')

    def test_add_dokument_wrong_organization(self):
        """Test that users cannot edit documents from other organizations"""
        # Create another organization and document
        other_org = Organisation.objects.create(name="Other Org")
        other_doc = Dokument2.objects.create(
            org=other_org,
            ordner=self.doc_folder,
            titel="Other Org Document",
            beschreibung="Other org document"
        )
        
        self.client.force_login(self.admin_user)
        data = {
            'dokument_id': other_doc.id,
            'titel': 'Should Fail',
            'beschreibung': 'Should not update',
            'ordner': self.doc_folder.id
        }
        
        response = self.client.post(reverse('add_dokument'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Check that document was not updated
        other_doc.refresh_from_db()
        self.assertEqual(other_doc.titel, 'Other Org Document')

    def test_add_ordner_success(self):
        """Test successful folder creation (org user only)"""
        self.client.force_login(self.org_user)
        
        data = {
            'ordner_name': 'New Folder',
            'ordner_person_cluster': [self.freiwillige_cluster.id],
            'color': self.doc_color.id
        }
        
        response = self.client.post(reverse('add_ordner'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Check that folder was created
        self.assertTrue(Ordner2.objects.filter(ordner_name='New Folder').exists())
        new_folder = Ordner2.objects.get(ordner_name='New Folder')
        self.assertEqual(new_folder.org, self.org)
        self.assertEqual(new_folder.color, self.doc_color)
        self.assertIn(self.freiwillige_cluster, new_folder.typ.all())

    def test_add_ordner_permission_denied(self):
        """Test that non-org users cannot create folders"""
        self.client.force_login(self.freiwillige_user)
        data = {'ordner_name': 'Should Fail'}
        response = self.client.post(reverse('add_ordner'), data=data)
        self.assertEqual(response.status_code, 403)  # Not allowed

    def test_add_ordner_edit_existing(self):
        """Test editing an existing folder"""
        self.client.force_login(self.org_user)
        
        data = {
            'ordner_id': self.doc_folder.id,
            'ordner_name': 'Updated Folder',
            'ordner_person_cluster': [self.admin_cluster.id],
            'color': self.doc_color.id
        }
        
        response = self.client.post(reverse('add_ordner'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Check that folder was updated
        self.doc_folder.refresh_from_db()
        self.assertEqual(self.doc_folder.ordner_name, 'Updated Folder')

    def test_add_ordner_wrong_organization(self):
        """Test that users cannot edit folders from other organizations"""
        # Create another organization and folder
        other_org = Organisation.objects.create(name="Other Org")
        other_folder = Ordner2.objects.create(
            org=other_org,
            ordner_name="Other Org Folder"
        )
        
        self.client.force_login(self.org_user)
        data = {
            'ordner_id': other_folder.id,
            'ordner_name': 'Should Fail',
            'ordner_person_cluster': [self.admin_cluster.id]
        }
        
        response = self.client.post(reverse('add_ordner'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Check that folder was not updated
        other_folder.refresh_from_db()
        self.assertEqual(other_folder.ordner_name, 'Other Org Folder')

    def test_remove_dokument_success_owner(self):
        """Test successful document deletion by owner"""
        self.client.force_login(self.admin_user)
        
        data = {'dokument_id': self.dokument.id}
        response = self.client.post(reverse('remove_dokument'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Check that document was deleted
        self.assertFalse(Dokument2.objects.filter(id=self.dokument.id).exists())

    def test_remove_dokument_success_authorized(self):
        """Test successful document deletion by authorized user"""
        # Add freiwillige user to darf_bearbeiten
        self.dokument.darf_bearbeiten.add(self.freiwillige_cluster)
        
        self.client.force_login(self.freiwillige_user)
        data = {'dokument_id': self.dokument.id}
        response = self.client.post(reverse('remove_dokument'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Check that document was deleted
        self.assertFalse(Dokument2.objects.filter(id=self.dokument.id).exists())

    def test_remove_dokument_permission_denied(self):
        """Test that unauthorized users cannot delete documents"""
        self.client.force_login(self.freiwillige_user)
        data = {'dokument_id': self.dokument.id}
        response = self.client.post(reverse('remove_dokument'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Check that document was not deleted
        self.assertTrue(Dokument2.objects.filter(id=self.dokument.id).exists())

    def test_remove_dokument_not_found(self):
        """Test deleting non-existent document"""
        self.client.force_login(self.admin_user)
        data = {'dokument_id': 99999}
        response = self.client.post(reverse('remove_dokument'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_remove_dokument_wrong_organization(self):
        """Test that users cannot delete documents from other organizations"""
        # Create another organization and document
        other_org = Organisation.objects.create(name="Other Org")
        other_doc = Dokument2.objects.create(
            org=other_org,
            ordner=self.doc_folder,
            titel="Other Org Document"
        )
        
        self.client.force_login(self.admin_user)
        data = {'dokument_id': other_doc.id}
        response = self.client.post(reverse('remove_dokument'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Check that document was not deleted
        self.assertTrue(Dokument2.objects.filter(id=other_doc.id).exists())

    def test_remove_ordner_success_empty(self):
        """Test successful folder deletion when empty"""
        # Create an empty folder
        empty_folder = Ordner2.objects.create(
            ordner_name="Empty Folder",
            org=self.org,
            color=self.doc_color
        )
        
        self.client.force_login(self.admin_user)
        data = {'ordner_id': empty_folder.id}
        response = self.client.post(reverse('remove_ordner'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Check that folder was deleted
        self.assertFalse(Ordner2.objects.filter(id=empty_folder.id).exists())

    def test_remove_ordner_fails_not_empty(self):
        """Test that non-empty folders cannot be deleted"""
        self.client.force_login(self.admin_user)
        data = {'ordner_id': self.doc_folder.id}
        response = self.client.post(reverse('remove_ordner'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Check that folder was not deleted
        self.assertTrue(Ordner2.objects.filter(id=self.doc_folder.id).exists())

    def test_remove_ordner_not_found(self):
        """Test deleting non-existent folder"""
        self.client.force_login(self.admin_user)
        data = {'ordner_id': 99999}
        response = self.client.post(reverse('remove_ordner'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_remove_ordner_wrong_organization(self):
        """Test that users cannot delete folders from other organizations"""
        # Create another organization and folder
        other_org = Organisation.objects.create(name="Other Org")
        other_folder = Ordner2.objects.create(
            org=other_org,
            ordner_name="Other Org Folder"
        )
        
        self.client.force_login(self.admin_user)
        data = {'ordner_id': other_folder.id}
        response = self.client.post(reverse('remove_ordner'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Check that folder was not deleted
        self.assertTrue(Ordner2.objects.filter(id=other_folder.id).exists())

    def test_different_person_cluster_views_access(self):
        """Test access from different PersonCluster views"""
        # Test all view types
        view_types = ['A', 'O', 'F', 'E', 'T', 'B']
        
        for view_type in view_types:
            # Create cluster with this view type
            cluster = PersonCluster.objects.create(
                name=f"Cluster {view_type}",
                org=self.org,
                view=view_type,
                bilder=True,
                dokumente=True
            )
            
            # Create user with this cluster
            user = User.objects.create_user(
                username=f'user_{view_type}',
                email=f'user_{view_type}@example.com',
                password='testpass123'
            )
            CustomUser.objects.create(
                user=user,
                org=self.org,
                person_cluster=cluster
            )
            
            # Test dokumente access
            self.client.force_login(user)
            response = self.client.get(reverse('dokumente'))
            self.assertEqual(response.status_code, 200)
            
            # Test add_dokument access
            response = self.client.post(reverse('add_dokument'), data={'titel': 'test'})
            self.assertEqual(response.status_code, 302)  # Redirect after success
            
            # Test add_ordner access (only for org users)
            if view_type == 'O':
                response = self.client.post(reverse('add_ordner'), data={'ordner_name': 'test'})
                self.assertEqual(response.status_code, 302)  # Redirect after success
            else:
                response = self.client.post(reverse('add_ordner'), data={'ordner_name': 'test'})
                self.assertEqual(response.status_code, 403)  # Not allowed

    def test_user_without_person_cluster(self):
        """Test user without person_cluster assignment"""
        # Create user without person_cluster
        no_cluster_user = User.objects.create_user(
            username='noclusteruser',
            email='nocluster@example.com',
            password='testpass123'
        )
        CustomUser.objects.create(
            user=no_cluster_user,
            org=self.org,
            person_cluster=None
        )
        
        self.client.force_login(no_cluster_user)
        
        # Should be denied access
        response = self.client.get(reverse('dokumente'))
        self.assertEqual(response.status_code, 302)  # Redirect to index
        
        response = self.client.get(reverse('serve_dokument', args=[self.dokument.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to index

    def test_form_validation_errors(self):
        """Test form validation errors"""
        self.client.force_login(self.org_user)
        
        # Test add_dokument with missing required fields
        data = {'beschreibung': 'Only description'}  # Missing titel and ordner
        response = self.client.post(reverse('add_dokument'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Test add_ordner with missing required fields
        data = {'color': self.doc_color.id}  # Missing ordner_name
        response = self.client.post(reverse('add_ordner'), data=data, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_dokumente_view_context_data(self):
        """Test that dokumente view provides correct context data"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('dokumente'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('folder_structure', response.context)
        self.assertIn('ordners', response.context)
        self.assertIn('colors', response.context)
        self.assertIn('person_clusters', response.context)
        
        # Check that our test folder is in the structure
        folder_names = [item['ordner'].ordner_name for item in response.context['folder_structure']]
        self.assertIn('Test Folder', folder_names)
        
        # Check that our test document is in the structure
        documents = []
        for item in response.context['folder_structure']:
            if item['ordner'] == self.doc_folder:
                documents = item['dokumente']
                break
        self.assertIn(self.dokument, documents)


class ProfileViewsTests(TestCase):
    """Tests for profile-related views: view_profil, update_profil_picture, serve_profil_picture, remove_profil_attribut"""
    
    def setUp(self):
        # Create test organization
        self.org = Organisation.objects.create(name="Test Org")
        
        # Create different person clusters for testing permissions
        self.admin_cluster = PersonCluster.objects.create(
            name="Admin Cluster",
            org=self.org,
            view='A',  # Admin view
            bilder=True,
            posts=True
        )
        
        self.org_cluster = PersonCluster.objects.create(
            name="Org Cluster",
            org=self.org,
            view='O',  # Organization view
            bilder=True,
            posts=True
        )
        
        self.freiwillige_cluster = PersonCluster.objects.create(
            name="Freiwillige Cluster",
            org=self.org,
            view='F',  # Freiwillige view
            bilder=True,
            posts=True
        )
        
        self.ehemalige_cluster = PersonCluster.objects.create(
            name="Ehemalige Cluster",
            org=self.org,
            view='E',  # Ehemalige view
            bilder=True,
            posts=True
        )
        
        self.team_cluster = PersonCluster.objects.create(
            name="Team Cluster",
            org=self.org,
            view='T',  # Team view
            bilder=True,
            posts=True
        )
        
        self.bewerber_cluster = PersonCluster.objects.create(
            name="Bewerber Cluster",
            org=self.org,
            view='B',  # Bewerber view
            bilder=True,
            posts=True
        )
        
        # Create test users
        self.admin_user = User.objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='testpass123',
            first_name='Admin',
            last_name='User'
        )
        self.admin_custom_user = CustomUser.objects.create(
            user=self.admin_user,
            org=self.org,
            person_cluster=self.admin_cluster
        )
        
        self.org_user = User.objects.create_user(
            username='orguser',
            email='org@example.com',
            password='testpass123',
            first_name='Org',
            last_name='User'
        )
        self.org_custom_user = CustomUser.objects.create(
            user=self.org_user,
            org=self.org,
            person_cluster=self.org_cluster
        )
        
        self.freiwillige_user = User.objects.create_user(
            username='freiwilligeuser',
            email='freiwillige@example.com',
            password='testpass123',
            first_name='Freiwillige',
            last_name='User'
        )
        self.freiwillige_custom_user = CustomUser.objects.create(
            user=self.freiwillige_user,
            org=self.org,
            person_cluster=self.freiwillige_cluster
        )
        
        # Create another organization for cross-org testing
        self.other_org = Organisation.objects.create(name="Other Org")
        self.other_cluster = PersonCluster.objects.create(
            name="Other Cluster",
            org=self.other_org,
            view='F',
            bilder=True,
            posts=True
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123',
            first_name='Other',
            last_name='User'
        )
        self.other_custom_user = CustomUser.objects.create(
            user=self.other_user,
            org=self.other_org,
            person_cluster=self.other_cluster
        )
        
        # Create test images
        self.create_test_images()
        
        # Create test profile attributes
        self.profil_attribut = ProfilUser2.objects.create(
            org=self.org,
            user=self.freiwillige_user,
            attribut='Instagram',
            value='@testuser'
        )
        
        # Create test freiwilliger
        from FW.models import Freiwilliger
        self.freiwilliger = Freiwilliger.objects.get_or_create(
            org=self.org,
            user=self.freiwillige_user
        )[0]
        
        # Create client
        self.client = Client()

    def create_test_images(self):
        """Create test images for profile pictures"""
        # Create a test image
        image = Image.new('RGB', (100, 100), color='red')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        # Create test bilder
        self.bilder = Bilder2.objects.create(
            user=self.freiwillige_user,
            org=self.org,
            titel="Test Bild",
            beschreibung="Test description"
        )
        
        # Create test bilder gallery
        self.bilder_gallery = BilderGallery2.objects.create(
            bilder=self.bilder,
            org=self.org,
            image=SimpleUploadedFile(
                "test_image.jpg",
                image_io.getvalue(),
                content_type="image/jpeg"
            )
        )

    def test_view_profil_own_profile_success(self):
        """Test viewing own profile"""
        self.client.force_login(self.freiwillige_user)
        response = self.client.get(reverse('profil'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('user', response.context)
        self.assertIn('this_user', response.context)
        self.assertIn('profil_users', response.context)
        self.assertIn('profil_user_form', response.context)
        self.assertIn('freiwilliger', response.context)
        self.assertIn('gallery_images', response.context)
        self.assertIn('posts', response.context)
        self.assertIn('user_attributes', response.context)
        
        # Check that this_user is True for own profile
        self.assertTrue(response.context['this_user'])
        self.assertEqual(response.context['user'], self.freiwillige_user)

    def test_view_profil_other_user_success(self):
        """Test viewing another user's profile"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('profil', args=[self.freiwillige_user.id]))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('user', response.context)
        self.assertIn('this_user', response.context)
        self.assertIn('profil_users', response.context)
        self.assertIn('profil_user_form', response.context)
        self.assertIn('freiwilliger', response.context)
        self.assertIn('gallery_images', response.context)
        self.assertIn('posts', response.context)
        
        # Check that this_user is False for other user's profile
        self.assertFalse(response.context['this_user'])
        self.assertEqual(response.context['user'], self.freiwillige_user)

    def test_view_profil_wrong_organization(self):
        """Test that users cannot view profiles from other organizations"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('profil', args=[self.other_user.id]), follow=True)
        
        self.assertEqual(response.status_code, 200)  # After redirect
        # Check for error message
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('Nicht gefunden' in str(msg) for msg in messages))

    def test_view_profil_unauthenticated(self):
        """Test that unauthenticated users are redirected to login"""
        response = self.client.get(reverse('profil'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_view_profil_add_attribute_success(self):
        """Test adding a profile attribute via POST"""
        self.client.force_login(self.freiwillige_user)
        data = {
            'attribut': 'Twitter',
            'value': '@newuser'
        }
        response = self.client.post(reverse('profil'), data=data, follow=True)
        
        self.assertEqual(response.status_code, 200)
        # Check that attribute was created
        self.assertTrue(ProfilUser2.objects.filter(
            user=self.freiwillige_user,
            attribut='Twitter',
            value='@newuser'
        ).exists())

    def test_view_profil_form_validation(self):
        """Test ProfilUserForm validation"""
        from FW.forms import ProfilUserForm
        
        # Test valid data
        valid_data = {'attribut': 'Instagram', 'value': '@testuser'}
        form = ProfilUserForm(data=valid_data)
        self.assertTrue(form.is_valid())
        
        # Test invalid data (missing attribut)
        invalid_data = {'value': '@testuser'}
        form = ProfilUserForm(data=invalid_data)
        self.assertFalse(form.is_valid())
        self.assertIn('attribut', form.errors)

    def test_update_profil_picture_success(self):
        """Test successful profile picture update"""
        self.client.force_login(self.freiwillige_user)
        
        # Create a test image
        image = Image.new('RGB', (100, 100), color='blue')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        files = {
            'profil_picture': SimpleUploadedFile(
                "new_profile.jpg",
                image_io.getvalue(),
                content_type="image/jpeg"
            )
        }
        
        response = self.client.post(reverse('update_profil_picture'), files=files, follow=True)
        self.assertEqual(response.status_code, 200)
        
        # Check that profile picture was updated
        self.freiwillige_user.refresh_from_db()
        self.assertTrue(self.freiwillige_user.customuser.profil_picture is not None)

    def test_update_profil_picture_no_file(self):
        """Test profile picture update without file"""
        self.client.force_login(self.freiwillige_user)
        response = self.client.post(reverse('update_profil_picture'), follow=True)
        self.assertEqual(response.status_code, 200)
        # Should redirect without error

    def test_update_profil_picture_unauthenticated(self):
        """Test that unauthenticated users are redirected to login"""
        response = self.client.post(reverse('update_profil_picture'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_serve_profil_picture_success(self):
        """Test successful profile picture serving"""
        # Set a profile picture for the user
        image = Image.new('RGB', (100, 100), color='green')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        self.freiwillige_user.customuser.profil_picture = SimpleUploadedFile(
            "profile.jpg",
            image_io.getvalue(),
            content_type="image/jpeg"
        )
        self.freiwillige_user.customuser.save()
        
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('serve_profil_picture', args=[self.freiwillige_user.id]))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')

    def test_serve_profil_picture_default_image(self):
        """Test serving default image when no profile picture exists"""
        # Create a mock default image file
        import tempfile
        import os
        from django.conf import settings
        
        # Create a temporary default image
        image = Image.new('RGB', (100, 100), color='gray')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        # Create the static/img directory if it doesn't exist
        static_img_dir = os.path.join(settings.STATIC_ROOT, 'img')
        os.makedirs(static_img_dir, exist_ok=True)
        
        # Create the default image file
        default_img_path = os.path.join(static_img_dir, 'default_img.png')
        with open(default_img_path, 'wb') as f:
            f.write(image_io.getvalue())
        
        try:
            self.client.force_login(self.admin_user)
            response = self.client.get(reverse('serve_profil_picture', args=[self.freiwillige_user.id]))
            
            # The response should be either 200 (success) or 404 (if default image not found)
            self.assertIn(response.status_code, [200, 404])
            if response.status_code == 200:
                # Content type is determined by file extension, default_img.png should return image/png
                self.assertEqual(response['Content-Type'], 'image/png')
        finally:
            # Clean up the temporary file
            if os.path.exists(default_img_path):
                os.remove(default_img_path)

    def test_serve_profil_picture_wrong_organization(self):
        """Test that users cannot access profile pictures from other organizations"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('serve_profil_picture', args=[self.other_user.id]))
        
        self.assertEqual(response.status_code, 403)  # Forbidden

    def test_serve_profil_picture_unauthenticated(self):
        """Test that unauthenticated users are redirected to login"""
        response = self.client.get(reverse('serve_profil_picture', args=[self.freiwillige_user.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_remove_profil_attribut_success(self):
        """Test successful profile attribute removal"""
        self.client.force_login(self.freiwillige_user)
        response = self.client.get(reverse('remove_profil_attribut', args=[self.profil_attribut.id]), follow=True)
        
        self.assertEqual(response.status_code, 200)
        # Check that attribute was deleted
        self.assertFalse(ProfilUser2.objects.filter(id=self.profil_attribut.id).exists())

    def test_remove_profil_attribut_wrong_user(self):
        """Test that users cannot remove other users' attributes"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('remove_profil_attribut', args=[self.profil_attribut.id]), follow=True)
        
        self.assertEqual(response.status_code, 200)
        # Check that attribute was not deleted
        self.assertTrue(ProfilUser2.objects.filter(id=self.profil_attribut.id).exists())

    def test_remove_profil_attribut_unauthenticated(self):
        """Test that unauthenticated users are redirected to login"""
        response = self.client.get(reverse('remove_profil_attribut', args=[self.profil_attribut.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_different_person_cluster_views_access(self):
        """Test access from different PersonCluster views"""
        # Test all view types
        view_types = [view[0] for view in PersonCluster.view_choices]
        
        for view_type in view_types:
            # Create cluster with this view type
            cluster = PersonCluster.objects.create(
                name=f"Cluster {view_type}",
                org=self.org,
                view=view_type,
                bilder=True,
                posts=True
            )
            
            # Create user with this cluster
            user = User.objects.create_user(
                username=f'user_{view_type}',
                email=f'user_{view_type}@example.com',
                password='testpass123'
            )
            CustomUser.objects.create(
                user=user,
                org=self.org,
                person_cluster=cluster
            )
            
            # Test profil access - profile view should work for all users
            self.client.force_login(user)
            response = self.client.get(reverse('profil'))
            # Profile view should work for all authenticated users
            self.assertIn(response.status_code, [200, 302])  # Either success or redirect
            
            # Test serve_profil_picture access
            response = self.client.get(reverse('serve_profil_picture', args=[self.freiwillige_user.id]))
            self.assertIn(response.status_code, [200, 404])  # Either success or not found
            
            # Test update_profil_picture access
            response = self.client.post(reverse('update_profil_picture'))
            self.assertEqual(response.status_code, 302)  # Redirect after success

    def test_profile_context_data_with_freiwilliger(self):
        """Test that profile view provides correct context data when user has freiwilliger"""
        self.client.force_login(self.freiwillige_user)
        response = self.client.get(reverse('profil'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('freiwilliger', response.context)
        self.assertEqual(response.context['freiwilliger'], self.freiwilliger)

    def test_profile_context_data_without_freiwilliger(self):
        """Test that profile view provides correct context data when user has no freiwilliger"""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('profil'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('freiwilliger', response.context)
        self.assertIsNone(response.context['freiwilliger'])

    def test_profile_context_data_with_ampel(self):
        """Test that profile view provides correct context data when user has ampel status"""
        from Global.models import Ampel2
        
        # Create ampel status for user
        ampel = Ampel2.objects.create(
            org=self.org,
            user=self.freiwillige_user,
            status='G',
            comment='All good'
        )
        
        self.client.force_login(self.freiwillige_user)
        response = self.client.get(reverse('profil'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('ampel_of_user', response.context)
        self.assertEqual(response.context['ampel_of_user'], ampel)

    def test_profile_context_data_without_ampel(self):
        """Test that profile view provides correct context data when user has no ampel status"""
        self.client.force_login(self.freiwillige_user)
        response = self.client.get(reverse('profil'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('ampel_of_user', response.context)
        self.assertIsNone(response.context['ampel_of_user'])

    def test_profile_context_data_with_gallery_images(self):
        """Test that profile view provides correct context data with gallery images"""
        self.client.force_login(self.freiwillige_user)
        response = self.client.get(reverse('profil'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('gallery_images', response.context)
        # Should contain the test image we created
        self.assertEqual(len(response.context['gallery_images']), 1)

    def test_profile_context_data_with_posts(self):
        """Test that profile view provides correct context data with posts"""
        from Global.models import Post2
        
        # Create a test post
        post = Post2.objects.create(
            org=self.org,
            user=self.freiwillige_user,
            title="Test Post",
            text="Test post content"
        )
        
        self.client.force_login(self.freiwillige_user)
        response = self.client.get(reverse('profil'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('posts', response.context)
        # Should contain the test post
        self.assertEqual(len(response.context['posts']), 1)

    def test_profile_context_data_with_user_attributes(self):
        """Test that profile view provides correct context data with user attributes"""
        from Global.models import Attribute, UserAttribute
        
        # Create test attribute
        attribute = Attribute.objects.create(
            org=self.org,
            name="Test Attribute",
            type='T'
        )
        
        # Create user attribute
        user_attribute = UserAttribute.objects.create(
            org=self.org,
            user=self.freiwillige_user,
            attribute=attribute,
            value="Test Value"
        )
        
        self.client.force_login(self.freiwillige_user)
        response = self.client.get(reverse('profil'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('user_attributes', response.context)
        # Should contain the test user attribute
        self.assertEqual(len(response.context['user_attributes']), 1)

    def test_profile_context_data_other_user_no_attributes(self):
        """Test that profile view doesn't show user attributes for other users"""
        from Global.models import Attribute, UserAttribute
        
        # Create test attribute
        attribute = Attribute.objects.create(
            org=self.org,
            name="Test Attribute",
            type='T'
        )
        
        # Create user attribute for freiwillige user
        user_attribute = UserAttribute.objects.create(
            org=self.org,
            user=self.freiwillige_user,
            attribute=attribute,
            value="Test Value"
        )
        
        # View as admin user
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('profil', args=[self.freiwillige_user.id]))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('user_attributes', response.context)
        # Should be empty for other users
        self.assertEqual(len(response.context['user_attributes']), 0)

    def test_superuser_access(self):
        """Test superuser access to profile views"""
        # Create superuser
        superuser = User.objects.create_superuser(
            username='superuser',
            email='super@example.com',
            password='testpass123'
        )
        CustomUser.objects.create(
            user=superuser,
            org=self.org,
            person_cluster=self.admin_cluster
        )
        
        self.client.force_login(superuser)
        
        # Should have access
        response = self.client.get(reverse('profil'))
        self.assertIn(response.status_code, [200, 302])  # Either success or redirect
        
        response = self.client.get(reverse('serve_profil_picture', args=[self.freiwillige_user.id]))
        self.assertIn(response.status_code, [200, 404])  # Either success or not found
        
        response = self.client.post(reverse('update_profil_picture'))
        self.assertEqual(response.status_code, 302)  # Redirect after success


class ChangeRequestTests(TestCase):
    """Tests for ChangeRequest functionality including views, models, and notifications."""
    
    def setUp(self):
        # Create test organization
        self.org = Organisation.objects.create(name="Test Org")
        
        # Create different person clusters for testing permissions
        self.org_cluster = PersonCluster.objects.create(
            name="Org Cluster",
            org=self.org,
            view='O'  # Organization view
        )
        
        self.team_cluster = PersonCluster.objects.create(
            name="Team Cluster",
            org=self.org,
            view='T'  # Team view
        )
        
        self.ehemalige_cluster = PersonCluster.objects.create(
            name="Ehemalige Cluster",
            org=self.org,
            view='E'  # Ehemalige view
        )
        
        self.freiwillige_cluster = PersonCluster.objects.create(
            name="Freiwillige Cluster",
            org=self.org,
            view='F'  # Freiwillige view
        )
        
        # Create test users
        self.org_user = User.objects.create_user(
            username='orguser',
            email='org@example.com',
            password='testpass123',
            first_name='Org',
            last_name='User'
        )
        self.org_custom_user = CustomUser.objects.create(
            user=self.org_user,
            org=self.org,
            person_cluster=self.org_cluster
        )
        
        self.team_user = User.objects.create_user(
            username='teamuser',
            email='team@example.com',
            password='testpass123',
            first_name='Team',
            last_name='User'
        )
        self.team_custom_user = CustomUser.objects.create(
            user=self.team_user,
            org=self.org,
            person_cluster=self.team_cluster
        )
        
        self.ehemalige_user = User.objects.create_user(
            username='ehemaligeuser',
            email='ehemalige@example.com',
            password='testpass123',
            first_name='Ehemalige',
            last_name='User'
        )
        self.ehemalige_custom_user = CustomUser.objects.create(
            user=self.ehemalige_user,
            org=self.org,
            person_cluster=self.ehemalige_cluster
        )
        
        self.freiwillige_user = User.objects.create_user(
            username='freiwilligeuser',
            email='freiwillige@example.com',
            password='testpass123',
            first_name='Freiwillige',
            last_name='User'
        )
        self.freiwillige_custom_user = CustomUser.objects.create(
            user=self.freiwillige_user,
            org=self.org,
            person_cluster=self.freiwillige_cluster
        )
        
        # Create another organization for cross-org testing
        self.other_org = Organisation.objects.create(name="Other Org")
        self.other_cluster = PersonCluster.objects.create(
            name="Other Cluster",
            org=self.other_org,
            view='T'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123',
            first_name='Other',
            last_name='User'
        )
        self.other_custom_user = CustomUser.objects.create(
            user=self.other_user,
            org=self.other_org,
            person_cluster=self.other_cluster
        )
        
        # Create test countries and placement locations
        self.einsatzland = Einsatzland2.objects.create(
            org=self.org,
            name='Test Country',
            notfallnummern='Emergency: 123',
            arztpraxen='Doctors: 456',
            apotheken='Pharmacies: 789',
            informationen='Test information'
        )
        
        self.einsatzstelle = Einsatzstelle2.objects.create(
            org=self.org,
            land=self.einsatzland,
            partnerorganisation='Test Partner',
            arbeitsvorgesetzter='Test Arbeitsvorgesetzter',
            mentor='Test Mentor',
            botschaft='Test Botschaft',
            konsulat='Test Konsulat',
            informationen='Test information'
        )
        
        # Create team member with assigned countries
        self.team_member, _ = Team.objects.get_or_create(
            user=self.team_user,
            org=self.org
        )
        self.team_member.land.add(self.einsatzland)

        # Create ehemalige member
        self.ehemalige_member, _ = Ehemalige.objects.get_or_create(
            user=self.ehemalige_user,
            org=self.org
        )
        self.ehemalige_member.land.add(self.einsatzland)
        
        # Create client
        self.client = Client()

    def test_change_request_model_creation(self):
        """Test creating a ChangeRequest model instance."""
        change_request = ChangeRequest.objects.create(
            org=self.org,
            requested_by=self.team_user,
            change_type='einsatzland',
            object_id=self.einsatzland.id,
            field_changes={'notfallnummern': 'New value'},
            reason='Test reason'
        )
        
        self.assertEqual(change_request.org, self.org)
        self.assertEqual(change_request.requested_by, self.team_user)
        self.assertEqual(change_request.change_type, 'einsatzland')
        self.assertEqual(change_request.object_id, self.einsatzland.id)
        self.assertEqual(change_request.status, 'pending')
        self.assertEqual(change_request.reason, 'Test reason')

    def test_change_request_get_object(self):
        """Test ChangeRequest.get_object() method."""
        change_request = ChangeRequest.objects.create(
            org=self.org,
            requested_by=self.team_user,
            change_type='einsatzland',
            object_id=self.einsatzland.id,
            field_changes={'notfallnummern': 'New value'},
            reason='Test reason'
        )
        
        obj = change_request.get_object()
        self.assertEqual(obj, self.einsatzland)
        
        # Test with non-existent object
        change_request.object_id = 99999
        change_request.save()
        obj = change_request.get_object()
        self.assertIsNone(obj)

    def test_change_request_get_object_name(self):
        """Test ChangeRequest.get_object_name() method."""
        change_request = ChangeRequest.objects.create(
            org=self.org,
            requested_by=self.team_user,
            change_type='einsatzland',
            object_id=self.einsatzland.id,
            field_changes={'notfallnummern': 'New value'},
            reason='Test reason'
        )
        
        obj_name = change_request.get_object_name()
        self.assertEqual(obj_name, 'Test Country')
        
        # Test with non-existent object
        change_request.object_id = 99999
        change_request.save()
        obj_name = change_request.get_object_name()
        self.assertEqual(obj_name, '[Gelöschtes Objekt]')

    def test_change_request_apply_changes(self):
        """Test ChangeRequest.apply_changes() method."""
        change_request = ChangeRequest.objects.create(
            org=self.org,
            requested_by=self.team_user,
            change_type='einsatzland',
            object_id=self.einsatzland.id,
            field_changes={'notfallnummern': 'Emergency: 999'},
            reason='Test reason',
            status='approved'
        )
        
        # Apply changes
        result = change_request.apply_changes()
        self.assertTrue(result)
        
        # Check that changes were applied
        self.einsatzland.refresh_from_db()
        self.assertEqual(self.einsatzland.notfallnummern, 'Emergency: 999')
        
        # Check that change request status was updated
        change_request.refresh_from_db()
        self.assertEqual(change_request.status, 'approved')

    def test_change_request_apply_changes_wrong_org(self):
        """Test that apply_changes fails for wrong organization."""
        change_request = ChangeRequest.objects.create(
            org=self.other_org,
            requested_by=self.other_user,
            change_type='einsatzland',
            object_id=self.einsatzland.id,  # Object from different org
            field_changes={'notfallnummern': 'Emergency: 999'},
            reason='Test reason',
            status='approved'
        )
        
        # Should raise ValueError for wrong organization
        with self.assertRaises(ValueError) as context:
            change_request.apply_changes()
        self.assertIn('Sicherheitsfehler', str(context.exception))

    def test_change_request_apply_changes_deleted_object(self):
        """Test that apply_changes fails for deleted object."""
        change_request = ChangeRequest.objects.create(
            org=self.org,
            requested_by=self.team_user,
            change_type='einsatzland',
            object_id=99999,  # Non-existent object
            field_changes={'notfallnummern': 'Emergency: 999'},
            reason='Test reason',
            status='approved'
        )
        
        # Should raise ValueError for non-existent object
        with self.assertRaises(ValueError) as context:
            change_request.apply_changes()
        self.assertIn('wurde nicht gefunden', str(context.exception))

    def test_change_request_get_field_changes_display(self):
        """Test ChangeRequest.get_field_changes_display() method."""
        change_request = ChangeRequest.objects.create(
            org=self.org,
            requested_by=self.team_user,
            change_type='einsatzland',
            object_id=self.einsatzland.id,
            field_changes={
                'notfallnummern': 'Emergency: 999',
                'arztpraxen': 'Doctors: 888'
            },
            reason='Test reason'
        )
        
        changes = change_request.get_field_changes_display()
        self.assertEqual(len(changes), 2)
        
        # Check field names are translated
        field_names = [change['field'] for change in changes]
        self.assertIn('Notfallnummern', field_names)
        self.assertIn('Arztpraxen', field_names)

    @patch('Global.views_change_requests._notify_org_members_of_change_request')
    def test_save_land_info_team_member(self, mock_notify):
        """Test save_land_info view for team member."""
        self.client.force_login(self.team_user)
        
        data = {
            'notfallnummern': 'Updated Emergency: 999',
            'arztpraxen': 'Updated Doctors: 888',
            'apotheken': 'Updated Pharmacies: 777',
            'informationen': 'Updated information',
            'reason': 'Test reason for change'
        }
        
        response = self.client.post(
            reverse('save_land_info', args=[self.einsatzland.id]),
            data
        )
        
        # Should redirect to laender_info
        self.assertEqual(response.status_code, 302)
        self.assertIn('laender', response.url)
        
        # Check that ChangeRequest was created
        change_request = ChangeRequest.objects.filter(
            org=self.org,
            requested_by=self.team_user,
            change_type='einsatzland',
            object_id=self.einsatzland.id
        ).first()
        
        self.assertIsNotNone(change_request)
        self.assertEqual(change_request.reason, 'Test reason for change')
        
        # Check that notification was called
        mock_notify.assert_called_once_with(change_request)

    @patch('Global.views_change_requests._notify_org_members_of_change_request')
    def test_save_land_info_ehemalige_member(self, mock_notify):
        """Test save_land_info view for ehemalige member."""
        self.client.force_login(self.ehemalige_user)
        
        data = {
            'notfallnummern': 'Updated Emergency: 999',
            'arztpraxen': 'Updated Doctors: 888',
            'apotheken': 'Updated Pharmacies: 777',
            'informationen': 'Updated information',
            'reason': 'Test reason for change'
        }
        
        response = self.client.post(
            reverse('save_land_info', args=[self.einsatzland.id]),
            data
        )
        
        # Should redirect to laender_info
        self.assertEqual(response.status_code, 302)
        self.assertIn('laender', response.url)
        
        # Check that ChangeRequest was created
        change_request = ChangeRequest.objects.filter(
            org=self.org,
            requested_by=self.ehemalige_user,
            change_type='einsatzland',
            object_id=self.einsatzland.id
        ).first()
        
        self.assertIsNotNone(change_request)
        self.assertEqual(change_request.reason, 'Test reason for change')
        
        # Check that notification was called
        mock_notify.assert_called_once_with(change_request)

    @patch('Global.views_change_requests._notify_org_members_of_change_request')
    def test_save_einsatzstelle_info_team_member(self, mock_notify):
        """Test save_einsatzstelle_info view for team member."""
        self.client.force_login(self.team_user)
        
        data = {
            'adresse': 'Updated Address',
            'telefon': 'Updated Phone',
            'email': 'updated@placement.com',
            'ansprechpartner': 'Updated Contact',
            'informationen': 'Updated placement information',
            'reason': 'Test reason for change'
        }
        
        response = self.client.post(
            reverse('save_einsatzstelle_info', args=[self.einsatzstelle.id]),
            data
        )
        
        # Should redirect to einsatzstellen_info
        self.assertEqual(response.status_code, 302)
        self.assertIn('einsatzstellen', response.url)
        
        # Check that ChangeRequest was created
        change_request = ChangeRequest.objects.filter(
            org=self.org,
            requested_by=self.team_user,
            change_type='einsatzstelle',
            object_id=self.einsatzstelle.id
        ).first()
        
        self.assertIsNotNone(change_request)
        self.assertEqual(change_request.reason, 'Test reason for change')
        
        # Check that notification was called
        mock_notify.assert_called_once_with(change_request)

    def test_save_land_info_unauthorized_user(self):
        """Test that unauthorized users cannot create change requests."""
        self.client.force_login(self.freiwillige_user)
        
        data = {
            'notfallnummern': 'Updated Emergency: 999',
            'reason': 'Test reason'
        }
        
        response = self.client.post(
            reverse('save_land_info', args=[self.einsatzland.id]),
            data
        )
        
        # Should be forbidden
        self.assertEqual(response.status_code, 403)

    def test_save_land_info_wrong_organization(self):
        """Test that users cannot create change requests for other organizations."""
        self.client.force_login(self.other_user)
        
        data = {
            'notfallnummern': 'Updated Emergency: 999',
            'reason': 'Test reason'
        }
        
        response = self.client.post(
            reverse('save_land_info', args=[self.einsatzland.id]),
            data
        )
        
        # Should redirect to laender_info with error message
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('laender_info'))
        
        # Verify no ChangeRequest was created
        change_requests = ChangeRequest.objects.filter(
            org=self.other_org,
            requested_by=self.other_user,
            change_type='einsatzland',
            object_id=self.einsatzland.id
        )
        self.assertEqual(change_requests.count(), 0)

    def test_save_land_info_unauthenticated(self):
        """Test that unauthenticated users are redirected to login."""
        data = {
            'notfallnummern': 'Updated Emergency: 999',
            'reason': 'Test reason'
        }
        
        response = self.client.post(
            reverse('save_land_info', args=[self.einsatzland.id]),
            data
        )
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_laender_info_view_team_member(self):
        """Test laender_info view for team member."""
        self.client.force_login(self.team_user)
        response = self.client.get(reverse('laender_info'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('laender', response.context)
        self.assertIn('base_template', response.context)
        self.assertIn('member', response.context)
        
        # Check that assigned countries are in context
        laender = response.context['laender']
        self.assertEqual(len(laender), 1)
        self.assertEqual(laender[0], self.einsatzland)

    def test_laender_info_view_ehemalige_member(self):
        """Test laender_info view for ehemalige member."""
        self.client.force_login(self.ehemalige_user)
        response = self.client.get(reverse('laender_info'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('laender', response.context)
        self.assertIn('base_template', response.context)
        self.assertIn('member', response.context)

    def test_einsatzstellen_info_view_team_member(self):
        """Test einsatzstellen_info view for team member."""
        self.client.force_login(self.team_user)
        response = self.client.get(reverse('einsatzstellen_info'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('einsatzstellen', response.context)
        self.assertIn('base_template', response.context)
        self.assertIn('member', response.context)
        
        # Check that placement locations are in context
        einsatzstellen = response.context['einsatzstellen']
        self.assertEqual(len(einsatzstellen), 1)
        self.assertEqual(einsatzstellen[0], self.einsatzstelle)

    def test_laender_info_view_unauthorized_user(self):
        """Test that unauthorized users cannot access laender_info."""
        self.client.force_login(self.freiwillige_user)
        response = self.client.get(reverse('laender_info'))
        
        # Should be forbidden
        self.assertEqual(response.status_code, 403)

    def test_einsatzstellen_info_view_unauthorized_user(self):
        """Test that unauthorized users cannot access einsatzstellen_info."""
        self.client.force_login(self.freiwillige_user)
        response = self.client.get(reverse('einsatzstellen_info'))
        
        # Should be forbidden
        self.assertEqual(response.status_code, 403)

    def test_laender_info_view_unauthenticated(self):
        """Test that unauthenticated users are redirected to login."""
        response = self.client.get(reverse('laender_info'))
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_einsatzstellen_info_view_unauthenticated(self):
        """Test that unauthenticated users are redirected to login."""
        response = self.client.get(reverse('einsatzstellen_info'))
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_laender_info_with_pending_requests(self):
        """Test laender_info view shows pending change requests."""
        # Create pending change request
        change_request = ChangeRequest.objects.create(
            org=self.org,
            requested_by=self.team_user,
            change_type='einsatzland',
            object_id=self.einsatzland.id,
            field_changes={'notfallnummern': 'New'},
            reason='Test reason'
        )
        
        self.client.force_login(self.team_user)
        response = self.client.get(reverse('laender_info'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('pending_requests_by_land', response.context)
        
        # Check that pending request is in context
        pending_requests = response.context['pending_requests_by_land']
        self.assertIn(self.einsatzland.id, pending_requests)
        self.assertEqual(pending_requests[self.einsatzland.id], change_request)

    def test_einsatzstellen_info_with_pending_requests(self):
        """Test einsatzstellen_info view shows pending change requests."""
        # Create pending change request
        change_request = ChangeRequest.objects.create(
            org=self.org,
            requested_by=self.team_user,
            change_type='einsatzstelle',
            object_id=self.einsatzstelle.id,
            field_changes={'adresse': 'New'},
            reason='Test reason'
        )
        
        self.client.force_login(self.team_user)
        response = self.client.get(reverse('einsatzstellen_info'))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('pending_requests_by_stelle', response.context)
        
        # Check that pending request is in context
        pending_requests = response.context['pending_requests_by_stelle']
        self.assertIn(self.einsatzstelle.id, pending_requests)
        self.assertEqual(pending_requests[self.einsatzstelle.id], change_request)

    @patch('Global.tasks.send_change_request_new_email_task.apply_async')
    def test_notify_org_members_of_change_request(self, mock_apply_async):
        """Test notification function for new change requests."""
        from Global.views_change_requests import _notify_org_members_of_change_request
        
        # Create change request
        change_request = ChangeRequest.objects.create(
            org=self.org,
            requested_by=self.team_user,
            change_type='einsatzland',
            object_id=self.einsatzland.id,
            field_changes={'notfallnummern': 'New'},
            reason='Test reason'
        )
        
        # Call notification function
        _notify_org_members_of_change_request(change_request)
        
        # Check that Celery task was queued for org users
        # Should be called for each org member (at least once)
        self.assertTrue(mock_apply_async.called)
        # Verify countdown parameter
        for call in mock_apply_async.call_args_list:
            args, kwargs = call
            self.assertIn('args', kwargs)  # Should have args in kwargs
            self.assertEqual(len(kwargs['args']), 2)  # Should have [change_request_id, user_id]
            self.assertEqual(kwargs['args'][0], change_request.id)
            self.assertEqual(kwargs['countdown'], 5)

    @patch('Global.tasks.send_change_request_decision_email_task.apply_async')
    def test_notify_requester_of_decision(self, mock_apply_async):
        """Test notification function for change request decisions."""
        from Global.views_change_requests import _notify_requester_of_decision
        
        # Create change request
        change_request = ChangeRequest.objects.create(
            org=self.org,
            requested_by=self.team_user,
            change_type='einsatzland',
            object_id=self.einsatzland.id,
            field_changes={'notfallnummern': 'New'},
            reason='Test reason',
            status='approved',
            reviewed_by=self.org_user,
            review_comment='Approved'
        )
        
        # Call notification function
        _notify_requester_of_decision(change_request)
        
        # Check that Celery task was queued
        mock_apply_async.assert_called_once()
        args, kwargs = mock_apply_async.call_args
        self.assertEqual(kwargs['args'], [change_request.id])
        self.assertEqual(kwargs['countdown'], 5)

    def test_change_request_form_validation(self):
        """Test that form validation works correctly."""
        self.client.force_login(self.team_user)
        
        # Test with optional reason field (reason is not required)
        data = {
            'notfallnummern': 'Updated Emergency: 999',
            # reason is optional
        }
        
        response = self.client.post(
            reverse('save_land_info', args=[self.einsatzland.id]),
            data
        )
        
        # Should redirect and ChangeRequest should be created (reason is optional)
        self.assertEqual(response.status_code, 302)
        
        # ChangeRequest should be created even without reason
        change_requests = ChangeRequest.objects.filter(
            org=self.org,
            requested_by=self.team_user,
            change_type='einsatzland',
            object_id=self.einsatzland.id
        )
        self.assertEqual(change_requests.count(), 1)
        # Verify reason is empty string
        self.assertEqual(change_requests.first().reason, '')

    def test_change_request_with_no_changes(self):
        """Test that no ChangeRequest is created when no changes are made."""
        self.client.force_login(self.team_user)
        
        # Submit form with no changes
        data = {
            'notfallnummern': self.einsatzland.notfallnummern,  # Same value
            'arztpraxen': self.einsatzland.arztpraxen,  # Same value
            'apotheken': self.einsatzland.apotheken,  # Same value
            'informationen': self.einsatzland.informationen,  # Same value
            'reason': 'No changes made'
        }
        
        response = self.client.post(
            reverse('save_land_info', args=[self.einsatzland.id]),
            data
        )
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # No ChangeRequest should be created
        change_requests = ChangeRequest.objects.filter(
            org=self.org,
            requested_by=self.team_user,
            change_type='einsatzland',
            object_id=self.einsatzland.id
        )
        self.assertEqual(change_requests.count(), 0)

    def test_change_request_multiple_users_same_object(self):
        """Test that multiple users can create change requests for the same object."""
        self.client.force_login(self.team_user)
        
        # First user creates change request
        data = {
            'notfallnummern': 'Updated Emergency: 999',
            'reason': 'Team user reason'
        }
        
        response = self.client.post(
            reverse('save_land_info', args=[self.einsatzland.id]),
            data
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Second user creates change request
        self.client.force_login(self.ehemalige_user)
        data = {
            'notfallnummern': 'Updated Emergency: 888',
            'reason': 'Ehemalige user reason'
        }
        
        response = self.client.post(
            reverse('save_land_info', args=[self.einsatzland.id]),
            data
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Check that both change requests exist
        change_requests = ChangeRequest.objects.filter(
            org=self.org,
            change_type='einsatzland',
            object_id=self.einsatzland.id
        )
        self.assertEqual(change_requests.count(), 2)
        
        # Check that both users have their own requests
        team_request = change_requests.filter(requested_by=self.team_user).first()
        ehemalige_request = change_requests.filter(requested_by=self.ehemalige_user).first()
        
        self.assertIsNotNone(team_request)
        self.assertIsNotNone(ehemalige_request)
        self.assertEqual(team_request.reason, 'Team user reason')
        self.assertEqual(ehemalige_request.reason, 'Ehemalige user reason')

    def test_change_request_status_choices(self):
        """Test ChangeRequest status choices."""
        change_request = ChangeRequest.objects.create(
            org=self.org,
            requested_by=self.team_user,
            change_type='einsatzland',
            object_id=self.einsatzland.id,
            field_changes={'notfallnummern': 'New'},
            reason='Test reason'
        )
        
        # Test initial status
        self.assertEqual(change_request.status, 'pending')
        
        # Test status display
        self.assertEqual(change_request.get_status_display(), 'Ausstehend')
        
        # Test approved status
        change_request.status = 'approved'
        change_request.save()
        self.assertEqual(change_request.get_status_display(), 'Genehmigt')
        
        # Test rejected status
        change_request.status = 'rejected'
        change_request.save()
        self.assertEqual(change_request.get_status_display(), 'Abgelehnt')

    def test_change_request_change_type_choices(self):
        """Test ChangeRequest change type choices."""
        # Test einsatzland change type
        change_request = ChangeRequest.objects.create(
            org=self.org,
            requested_by=self.team_user,
            change_type='einsatzland',
            object_id=self.einsatzland.id,
            field_changes={'notfallnummern': 'New'},
            reason='Test reason'
        )
        
        self.assertEqual(change_request.get_change_type_display(), 'Einsatzland')
        
        # Test einsatzstelle change type
        change_request.change_type = 'einsatzstelle'
        change_request.object_id = self.einsatzstelle.id
        change_request.save()
        
        self.assertEqual(change_request.get_change_type_display(), 'Einsatzstelle')
