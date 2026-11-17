from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from BW.models import Bewerber
from FW.models import Freiwilliger
from Global.models import CustomUser, PersonCluster
from ORG.models import Organisation


class MissingRoleObjectFilterTests(TestCase):
    """CustomUser admin filter listing users whose role object (Bewerber, Freiwilliger, ...) is missing."""

    def setUp(self):
        self.addCleanup(patch.stopall)
        patch('celery.app.task.Task.apply_async').start()
        patch('Global.send_email.send_mail', return_value=1).start()

        self.org = Organisation.objects.create(name='Filter Org', email='filter@test.de')
        self.clusters = {
            view: PersonCluster.objects.create(name=f'Gruppe {view}', org=self.org, view=view)
            for view in ('B', 'F', 'E', 'T')
        }

        # Consistent users: the CustomUser post_save signal creates the role object.
        self.ok_bw = self.make_user('ok_bw', 'B')
        self.ok_fw = self.make_user('ok_fw', 'F')

        # Broken users: role object removed without signals.
        self.broken_bw = self.make_user('broken_bw', 'B')
        Bewerber.objects.filter(user=self.broken_bw.user)._raw_delete(using='default')
        self.broken_fw = self.make_user('broken_fw', 'F')
        Freiwilliger.objects.filter(user=self.broken_fw.user)._raw_delete(using='default')

        admin_user = User.objects.create_superuser('admin_filter', 'admin@test.de', 'pass')
        self.client.force_login(admin_user)

    def make_user(self, username, view):
        user = User.objects.create_user(username=username, password='pass1234')
        return CustomUser.objects.create(user=user, org=self.org, person_cluster=self.clusters[view])

    def filtered_ids(self, value):
        response = self.client.get(
            reverse('admin:Global_customuser_changelist'), {'missing_role_object': value}
        )
        self.assertEqual(response.status_code, 200)
        return set(response.context['cl'].queryset.values_list('id', flat=True))

    def test_filter_bewerber(self):
        self.assertEqual(self.filtered_ids('B'), {self.broken_bw.id})

    def test_filter_freiwillige(self):
        self.assertEqual(self.filtered_ids('F'), {self.broken_fw.id})

    def test_filter_any(self):
        self.assertEqual(self.filtered_ids('any'), {self.broken_bw.id, self.broken_fw.id})

    def test_role_object_of_other_type_does_not_count(self):
        # A Bewerber object does not satisfy a user in a Freiwilligen group.
        Bewerber.objects.create(user=self.broken_fw.user, org=self.org)
        self.assertIn(self.broken_fw.id, self.filtered_ids('F'))


class HasCustomUserFilterTests(TestCase):
    """User admin filter for users with/without a CustomUser."""

    def setUp(self):
        self.addCleanup(patch.stopall)
        patch('celery.app.task.Task.apply_async').start()
        patch('Global.send_email.send_mail', return_value=1).start()

        org = Organisation.objects.create(name='User Filter Org', email='userfilter@test.de')
        cluster = PersonCluster.objects.create(name='FW', org=org, view='F')
        self.with_cu = User.objects.create_user('with_cu', password='pass1234')
        CustomUser.objects.create(user=self.with_cu, org=org, person_cluster=cluster)
        self.without_cu = User.objects.create_user('without_cu', password='pass1234')

        self.admin_user = User.objects.create_superuser('admin_userfilter', 'a@test.de', 'pass')
        self.client.force_login(self.admin_user)

    def filtered_ids(self, value):
        response = self.client.get(reverse('admin:auth_user_changelist'), {'has_customuser': value})
        self.assertEqual(response.status_code, 200)
        return set(response.context['cl'].queryset.values_list('id', flat=True))

    def test_without_customuser(self):
        ids = self.filtered_ids('no')
        self.assertIn(self.without_cu.id, ids)
        self.assertNotIn(self.with_cu.id, ids)

    def test_with_customuser(self):
        ids = self.filtered_ids('yes')
        self.assertIn(self.with_cu.id, ids)
        self.assertNotIn(self.without_cu.id, ids)
