import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from ORG.forms import AddAttributeForm, AddUserForm
from ORG.models import Organisation
from ORG.tables import PersonClusterTable, build_person_cluster_filter, get_customuser_filter

from .forms import AddPostForm
from .models import Attribute, CustomUser, Ordner2, PersonCluster, Post2


class ActivePersonClusterTests(TestCase):
    def setUp(self):
        with patch('ORG.tasks.send_register_email_task'):
            self.org = Organisation.objects.create(
                name='Active cluster test org',
                email='org@example.com',
            )

        self.admin = User.objects.get(customuser__org=self.org)
        self.admin.set_password('test-password')
        self.admin.save()
        self.admin_cluster = self.admin.person_cluster
        self.admin_cluster.dokumente = True
        self.admin_cluster.save()
        self.active_cluster = PersonCluster.objects.create(
            org=self.org,
            name='Active',
            view='F',
            active=True,
        )
        self.inactive_cluster = PersonCluster.objects.create(
            org=self.org,
            name='Inactive',
            view='F',
            active=False,
        )
        self.request = SimpleNamespace(user=self.admin, GET={}, COOKIES={})

    def test_selectable_for_org_excludes_inactive_and_other_org(self):
        with patch('ORG.tasks.send_register_email_task'):
            other_org = Organisation.objects.create(
                name='Other active cluster test org',
                email='other@example.com',
            )
        other_cluster = PersonCluster.objects.create(
            org=other_org,
            name='Other active',
            active=True,
        )

        result = PersonCluster.selectable_for_org(self.org)

        self.assertIn(self.active_cluster, result)
        self.assertNotIn(self.inactive_cluster, result)
        self.assertNotIn(other_cluster, result)

    def test_m2m_form_hides_but_preserves_existing_inactive_cluster(self):
        attribute = Attribute.objects.create(
            org=self.org,
            name='Test attribute',
            type='T',
        )
        attribute.person_cluster.add(self.inactive_cluster)
        form = AddAttributeForm(
            data={
                'name': 'Updated attribute',
                'type': 'T',
                'person_cluster': [self.active_cluster.pk],
                'visible_in_profile': True,
            },
            instance=attribute,
            request=self.request,
        )

        self.assertNotIn(
            self.inactive_cluster,
            form.fields['person_cluster'].queryset,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertSetEqual(
            set(attribute.person_cluster.all()),
            {self.active_cluster, self.inactive_cluster},
        )

    def test_fk_form_hides_but_preserves_current_inactive_cluster(self):
        self.admin.customuser.person_cluster = self.inactive_cluster
        self.admin.customuser.save()
        form = AddUserForm(
            data={
                'username': self.admin.username,
                'first_name': 'Updated',
                'last_name': 'Admin',
                'email': self.admin.email,
                'person_cluster': '',
                'geburtsdatum': '',
                'einmalpasswort': '',
                'mail_notifications': False,
            },
            instance=self.admin.customuser,
            request=self.request,
        )

        self.assertNotIn(
            self.inactive_cluster,
            form.fields['person_cluster'].queryset,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.admin.customuser.refresh_from_db()
        self.assertEqual(
            self.admin.customuser.person_cluster,
            self.inactive_cluster,
        )

    def test_post_form_hides_but_preserves_existing_inactive_cluster(self):
        with patch('Global.tasks.send_new_post_email_task'):
            post = Post2.objects.create(
                org=self.org,
                user=self.admin,
                title='Original',
            )
        post.person_cluster.add(self.inactive_cluster)
        with patch('Global.forms.get_current_request', return_value=self.request):
            form = AddPostForm(
                data={
                    'title': 'Updated',
                    'text': '',
                    'person_cluster': [self.active_cluster.pk],
                },
                instance=post,
            )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertSetEqual(
            set(post.person_cluster.all()),
            {self.active_cluster, self.inactive_cluster},
        )

    def test_shared_filters_hide_inactive_except_user_table(self):
        regular_filter, _ = build_person_cluster_filter(
            self.request,
            self.org,
            min_clusters=1,
        )
        regular_values = {
            option['value'] for option in regular_filter['options']
        }
        self.assertNotIn(str(self.inactive_cluster.pk), regular_values)

        _, user_filters = get_customuser_filter(
            self.request,
            self.org,
            CustomUser.objects.filter(org=self.org),
        )
        user_values = {
            option['value']
            for option in user_filters[0]['options']
        }
        self.assertIn(str(self.inactive_cluster.pk), user_values)

        table_ids = {record.pk for record in PersonClusterTable(
            PersonCluster.objects.filter(org=self.org)
        ).data}
        self.assertIn(self.inactive_cluster.pk, table_ids)

    def test_folder_edit_preserves_hidden_inactive_cluster(self):
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT_NAME=media_root):
                folder = Ordner2.objects.create(
                    org=self.org,
                    ordner_name='Test folder',
                )
                folder.typ.add(self.inactive_cluster)
                self.client.force_login(self.admin)

                response = self.client.post(reverse('add_ordner'), {
                    'ordner_id': folder.pk,
                    'ordner_name': 'Updated folder',
                    'ordner_person_cluster': [self.active_cluster.pk],
                    'color': '',
                })

        self.assertEqual(response.status_code, 302)
        self.assertSetEqual(
            set(folder.typ.all()),
            {self.active_cluster, self.inactive_cluster},
        )

    def test_inactive_cluster_own_signin_token_is_rejected(self):
        self.inactive_cluster.create_own_signin_token()

        response = self.client.get(
            reverse('own_signin', args=[self.inactive_cluster.own_signin_token])
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('index_home'))
