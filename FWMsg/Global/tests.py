from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core import signing
from datetime import datetime, timedelta
from .models import CustomUser, UserAufgaben, Aufgabe2, KalenderEvent, PersonCluster, Bilder2, BilderGallery2, Dokument2, Ordner2, DokumentColor2
from ORG.models import Organisation
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.base import ContentFile
import os
import tempfile
from PIL import Image
import io


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


class FileServingViewsTests(TestCase):
    """Tests for file serving views: serve_bilder, serve_small_bilder, serve_dokument"""
    
    def setUp(self):
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
        # Create a test PDF document
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
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

    def test_serve_dokument_pdf_download(self):
        """Test that PDFs can be downloaded with download parameter"""
        # Create a test PDF document
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
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


