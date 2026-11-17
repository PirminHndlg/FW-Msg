from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from Global.models import Maintenance


class MaintenancePageTests(TestCase):
    def test_start_page_redirects_to_maintenance_page(self):
        now = timezone.now()
        Maintenance.objects.create(
            maintenance_start_time=now - timedelta(hours=1),
            maintenance_end_time=now + timedelta(hours=1),
        )
        response = self.client.get(reverse('index_home'))
        self.assertRedirects(response, reverse('maintenance'), fetch_redirect_response=False)

        response = self.client.get(reverse('maintenance'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'bootstrap.min')

    def test_maintenance_page_without_maintenance_redirects(self):
        response = self.client.get(reverse('maintenance'))
        self.assertRedirects(response, reverse('index_home'), fetch_redirect_response=False)
