from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.messages import get_messages

from .models import Survey, SurveyQuestion, SurveyQuestionOption, SurveyResponse, SurveyAnswer
from ORG.models import Organisation
from Global.models import CustomUser, PersonCluster


class SurveyViewsTestCase(TestCase):
    def setUp(self):
        """Set up test data"""
        self._create_organizations()
        self._create_person_clusters()
        self._create_users()
        self._create_surveys()
        self.client = Client()

    def _create_organizations(self):
        """Create test organizations"""
        # Create test image for logo
        image = Image.new('RGB', (1, 1), color='red')
        image_io = BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        logo_img = SimpleUploadedFile(
            name='test_logo.png',
            content=image_io.read(),
            content_type='image/png'
        )
        
        self.org1 = Organisation.objects.create(
            name='Test Org 1',
            email='test1@example.com',
            logo=logo_img
        )
        
        self.org2 = Organisation.objects.create(
            name='Test Org 2', 
            email='test2@example.com'
        )

    def _create_person_clusters(self):
        """Create person clusters"""
        self.person_cluster1 = PersonCluster.objects.create(
            org=self.org1,
            name='Test Cluster 1',
            view='O'
        )
        
        self.person_cluster2 = PersonCluster.objects.create(
            org=self.org2,
            name='Test Cluster 2',
            view='O'
        )

    def _create_users(self):
        """Create test users"""
        # User from org1
        self.user1 = get_user_model().objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            first_name='User',
            last_name='One'
        )
        self.custom_user1 = CustomUser.objects.create(
            user=self.user1,
            org=self.org1,
            person_cluster=self.person_cluster1
        )
        
        # User from org2
        self.user2 = get_user_model().objects.create_user(
            username='user2',
            email='user2@example.com', 
            password='testpass123',
            first_name='User',
            last_name='Two'
        )
        self.custom_user2 = CustomUser.objects.create(
            user=self.user2,
            org=self.org2,
            person_cluster=self.person_cluster2
        )
        
        # Staff user
        self.staff_user = get_user_model().objects.create_user(
            username='staff',
            email='staff@example.com',
            password='testpass123',
            is_staff=True
        )
        self.custom_staff = CustomUser.objects.create(
            user=self.staff_user,
            org=self.org1,
            person_cluster=self.person_cluster1
        )

    def _create_surveys(self):
        """Create test surveys"""
        # Active survey for org1 (allows anonymous)
        self.survey1 = Survey.objects.create(
            title='Test Survey 1',
            description='Test description 1',
            org=self.org1,
            created_by=self.user1,
            is_active=True,
            allow_anonymous=True,
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=30)
        )
        
        # Active survey for org1 (requires login)
        self.survey2 = Survey.objects.create(
            title='Test Survey 2',
            description='Test description 2',
            org=self.org1,
            created_by=self.user1,
            is_active=True,
            allow_anonymous=False,
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=30)
        )
        
        # Inactive survey for org1
        self.survey3 = Survey.objects.create(
            title='Test Survey 3',
            description='Test description 3',
            org=self.org1,
            created_by=self.user1,
            is_active=False,
            allow_anonymous=True
        )
        
        # Survey for org2
        self.survey4 = Survey.objects.create(
            title='Test Survey 4',
            description='Test description 4',
            org=self.org2,
            created_by=self.user2,
            is_active=True,
            allow_anonymous=True
        )
        
        # Survey with date restrictions
        self.survey5 = Survey.objects.create(
            title='Test Survey 5',
            description='Test description 5',
            org=self.org1,
            created_by=self.user1,
            is_active=True,
            allow_anonymous=True,
            start_date=date.today() + timedelta(days=1),  # Starts tomorrow
            end_date=date.today() + timedelta(days=30)
        )
        
        # Create questions for testing
        self.question1 = SurveyQuestion.objects.create(
            survey=self.survey1,
            org=self.org1,
            question_text='What is your name?',
            question_type='text',
            order=1,
            is_required=True
        )
        
        self.question2 = SurveyQuestion.objects.create(
            survey=self.survey1,
            org=self.org1,
            question_text='How do you rate our service?',
            question_type='radio',
            order=2,
            is_required=False
        )
        
        # Create options for radio question
        self.option1 = SurveyQuestionOption.objects.create(
            question=self.question2,
            org=self.org1,
            option_text='Excellent'
        )
        
        self.option2 = SurveyQuestionOption.objects.create(
            question=self.question2,
            org=self.org1,
            option_text='Good'
        )


class SurveyPublicViewsTests(SurveyViewsTestCase):
    """Test public survey views (accessible without login if anonymous allowed)"""
    
    def test_survey_detail_anonymous_allowed(self):
        """Test survey detail view for anonymous users when allowed"""
        response = self.client.get(reverse('survey:survey_detail', 
                                         kwargs={'survey_key': self.survey1.survey_key}))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.survey1.title)
        self.assertContains(response, self.question1.question_text)
        self.assertContains(response, self.question2.question_text)
    
    def test_survey_detail_anonymous_not_allowed(self):
        """Test survey detail view for anonymous users when not allowed"""
        response = self.client.get(reverse('survey:survey_detail', 
                                         kwargs={'survey_key': self.survey2.survey_key}))
        
        self.assertEqual(response.status_code, 302)  # Redirect to login
        self.assertIn('login', response.url)
        self.assertIn('next=', response.url)
    
    def test_survey_detail_authenticated_user(self):
        """Test survey detail view for authenticated users"""
        self.client.login(username='user1', password='testpass123')
        response = self.client.get(reverse('survey:survey_detail', 
                                         kwargs={'survey_key': self.survey2.survey_key}))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.survey2.title)
    
    def test_survey_detail_inactive_survey(self):
        """Test survey detail view for inactive survey"""
        response = self.client.get(reverse('survey:survey_detail', 
                                         kwargs={'survey_key': self.survey3.survey_key}))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'not currently available')
    
    def test_survey_detail_future_start_date(self):
        """Test survey detail view for survey with future start date"""
        response = self.client.get(reverse('survey:survey_detail', 
                                         kwargs={'survey_key': self.survey5.survey_key}))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'not currently available')
    
    def test_survey_detail_invalid_key(self):
        """Test survey detail view with invalid survey key"""
        response = self.client.get(reverse('survey:survey_detail', 
                                         kwargs={'survey_key': 'invalid-key'}))
        
        self.assertEqual(response.status_code, 404)
    
    def test_survey_submission_anonymous(self):
        """Test survey submission by anonymous user"""
        post_data = {
            f'question_{self.question1.id}': 'John Doe',
            f'question_{self.question2.id}': str(self.option1.id)  # Use option ID for radio button
        }
        
        response = self.client.post(reverse('survey:survey_detail', 
                                          kwargs={'survey_key': self.survey1.survey_key}),
                                  data=post_data)
        
        self.assertEqual(response.status_code, 302)  # Redirect to thank you
        self.assertIn('thanks', response.url)
        
        # Check that response was created
        survey_response = SurveyResponse.objects.filter(survey=self.survey1).first()
        self.assertIsNotNone(survey_response)
        self.assertIsNone(survey_response.respondent)  # Anonymous
        self.assertIsNotNone(survey_response.session_key)
        
        # Check answers
        answers = SurveyAnswer.objects.filter(response=survey_response)
        self.assertEqual(answers.count(), 2)
    
    def test_survey_submission_authenticated(self):
        """Test survey submission by authenticated user"""
        self.client.login(username='user1', password='testpass123')
        
        post_data = {
            f'question_{self.question1.id}': 'Jane Doe',
            f'question_{self.question2.id}': str(self.option2.id)  # Use option ID for radio button
        }
        
        response = self.client.post(reverse('survey:survey_detail', 
                                          kwargs={'survey_key': self.survey2.survey_key}),
                                  data=post_data)
        
        self.assertEqual(response.status_code, 302)  # Redirect to thank you
        
        # Check that response was created
        survey_response = SurveyResponse.objects.filter(
            survey=self.survey2, 
            respondent=self.user1
        ).first()
        self.assertIsNotNone(survey_response)
        self.assertEqual(survey_response.respondent, self.user1)
    
    def test_survey_already_completed(self):
        """Test that user can't submit survey twice"""
        # Create existing response
        SurveyResponse.objects.create(
            survey=self.survey2,
            org=self.survey2.org,
            respondent=self.user1,
            is_complete=True
        )
        
        self.client.login(username='user1', password='testpass123')
        response = self.client.get(reverse('survey:survey_detail', 
                                         kwargs={'survey_key': self.survey2.survey_key}))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Already Completed')
    
    def test_survey_thank_you_page(self):
        """Test survey thank you page"""
        response = self.client.get(reverse('survey:survey_thank_you', 
                                         kwargs={'survey_key': self.survey1.survey_key}))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Thank you')
        self.assertContains(response, self.survey1.title)


class SurveyManagementViewsTests(SurveyViewsTestCase):
    """Test survey management views (requires login)"""
    
    def test_survey_list_unauthenticated(self):
        """Test survey list requires login"""
        response = self.client.get(reverse('survey:survey_list'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_survey_list_authenticated(self):
        """Test survey list for authenticated user"""
        self.client.login(username='user1', password='testpass123')
        response = self.client.get(reverse('survey:survey_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.survey1.title)
        self.assertContains(response, self.survey2.title)
        self.assertContains(response, self.survey3.title)
        # Should not contain surveys from other organizations
        self.assertNotContains(response, self.survey4.title)
    
    def test_survey_create_unauthenticated(self):
        """Test survey create requires login"""
        response = self.client.get(reverse('survey:survey_create'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_survey_create_get(self):
        """Test survey create form display"""
        self.client.login(username='user1', password='testpass123')
        response = self.client.get(reverse('survey:survey_create'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create Survey')
    
    def test_survey_create_post(self):
        """Test survey creation"""
        self.client.login(username='user1', password='testpass123')
        
        post_data = {
            'title': 'New Test Survey',
            'description': 'New test description',
            'allow_anonymous': True,
            'start_date': date.today().strftime('%Y-%m-%d'),
            'end_date': (date.today() + timedelta(days=30)).strftime('%Y-%m-%d')
        }
        
        response = self.client.post(reverse('survey:survey_create'), data=post_data)
        
        # Should redirect to survey list
        self.assertEqual(response.status_code, 302)
        
        # Check survey was created
        new_survey = Survey.objects.filter(title='New Test Survey').first()
        self.assertIsNotNone(new_survey)
        self.assertEqual(new_survey.created_by, self.user1)
        self.assertEqual(new_survey.org, self.org1)
    
    def test_survey_update_own_survey(self):
        """Test updating own survey"""
        self.client.login(username='user1', password='testpass123')
        
        post_data = {
            'title': 'Updated Survey Title',
            'description': self.survey1.description,
            'allow_anonymous': self.survey1.allow_anonymous,
        }
        
        response = self.client.post(
            reverse('survey:survey_update', kwargs={'pk': self.survey1.pk}),
            data=post_data
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Check survey was updated
        self.survey1.refresh_from_db()
        self.assertEqual(self.survey1.title, 'Updated Survey Title')
    
    def test_survey_update_other_user_survey(self):
        """Test that user cannot update another user's survey"""
        self.client.login(username='user2', password='testpass123')
        
        response = self.client.get(
            reverse('survey:survey_update', kwargs={'pk': self.survey1.pk})
        )
        
        self.assertEqual(response.status_code, 404)
    
    def test_survey_delete_own_survey(self):
        """Test deleting own survey"""
        self.client.login(username='user1', password='testpass123')
        
        response = self.client.post(
            reverse('survey:survey_delete', kwargs={'pk': self.survey1.pk})
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Check survey was deleted
        self.assertFalse(Survey.objects.filter(pk=self.survey1.pk).exists())
    
    def test_survey_manage_view(self):
        """Test survey management dashboard"""
        self.client.login(username='user1', password='testpass123')
        
        response = self.client.get(
            reverse('survey:survey_manage', kwargs={'pk': self.survey1.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.survey1.title)
        self.assertContains(response, self.question1.question_text)
        self.assertContains(response, self.question2.question_text)
    
    def test_survey_results_view(self):
        """Test survey results view"""
        # Create some responses for testing
        response1 = SurveyResponse.objects.create(
            survey=self.survey1,
            org=self.survey1.org,
            respondent=self.user1,
            is_complete=True
        )
        
        SurveyAnswer.objects.create(
            response=response1,
            org=self.survey1.org,
            question=self.question1,
            text_answer='Test Answer'
        )
        
        self.client.login(username='user1', password='testpass123')
        
        response = self.client.get(
            reverse('survey:survey_results', kwargs={'pk': self.survey1.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Survey Results')
        self.assertContains(response, self.survey1.title)


class SurveyQuestionManagementTests(SurveyViewsTestCase):
    """Test survey question management views"""
    
    def test_add_question_get(self):
        """Test add question form display"""
        self.client.login(username='user1', password='testpass123')
        
        response = self.client.get(
            reverse('survey:add_question', kwargs={'survey_pk': self.survey1.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add Question')
    
    def test_add_question_post(self):
        """Test adding a new question"""
        self.client.login(username='user1', password='testpass123')
        
        post_data = {
            'question_text': 'New test question?',
            'question_type': 'text',
            'is_required': True,
            'order': 10
        }
        
        response = self.client.post(
            reverse('survey:add_question', kwargs={'survey_pk': self.survey1.pk}),
            data=post_data
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Check question was created
        new_question = SurveyQuestion.objects.filter(question_text='New test question?').first()
        self.assertIsNotNone(new_question)
        self.assertEqual(new_question.survey, self.survey1)
        self.assertEqual(new_question.org, self.survey1.org)
    
    def test_edit_question_get(self):
        """Test edit question form display"""
        self.client.login(username='user1', password='testpass123')
        
        response = self.client.get(
            reverse('survey:edit_question', kwargs={
                'survey_pk': self.survey1.pk,
                'question_pk': self.question2.pk
            })
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edit Question')
        self.assertContains(response, self.question2.question_text)
    
    def test_edit_question_post(self):
        """Test updating a question"""
        self.client.login(username='user1', password='testpass123')
        
        post_data = {
            'question_text': 'Updated question text?',
            'question_type': 'radio',
            'is_required': True,
            'order': self.question2.order,
            # Formset management form data
            'options-TOTAL_FORMS': '2',
            'options-INITIAL_FORMS': '2',
            'options-MIN_NUM_FORMS': '0',
            'options-MAX_NUM_FORMS': '1000',
            # Existing options
            f'options-0-id': self.option1.id,
            'options-0-option_text': 'Updated Excellent',
            f'options-1-id': self.option2.id,
            'options-1-option_text': 'Updated Good',
        }
        
        response = self.client.post(
            reverse('survey:edit_question', kwargs={
                'survey_pk': self.survey1.pk,
                'question_pk': self.question2.pk
            }),
            data=post_data
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Check question was updated
        self.question2.refresh_from_db()
        self.assertEqual(self.question2.question_text, 'Updated question text?')
    
    def test_delete_question(self):
        """Test deleting a question"""
        self.client.login(username='user1', password='testpass123')
        
        response = self.client.post(
            reverse('survey:delete_question', kwargs={
                'survey_pk': self.survey1.pk,
                'question_pk': self.question1.pk
            })
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Check question was deleted
        self.assertFalse(SurveyQuestion.objects.filter(pk=self.question1.pk).exists())
    
    def test_question_access_other_org(self):
        """Test that users cannot access questions from other organizations"""
        self.client.login(username='user2', password='testpass123')
        
        response = self.client.get(
            reverse('survey:edit_question', kwargs={
                'survey_pk': self.survey1.pk,
                'question_pk': self.question1.pk
            })
        )
        
        self.assertEqual(response.status_code, 404)


class SurveyAdminViewsTests(SurveyViewsTestCase):
    """Test admin-only survey views"""
    
    def test_admin_survey_list_unauthenticated(self):
        """Test admin survey list requires login"""
        response = self.client.get(reverse('survey:admin_survey_list'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_admin_survey_list_non_staff(self):
        """Test admin survey list requires staff permissions"""
        self.client.login(username='user1', password='testpass123')
        response = self.client.get(reverse('survey:admin_survey_list'))
        self.assertEqual(response.status_code, 302)  # Redirect
    
    def test_admin_survey_list_staff(self):
        """Test admin survey list for staff users"""
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(reverse('survey:admin_survey_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'All Surveys')
        # Staff user should only see surveys from their organization
        self.assertContains(response, self.survey1.title)
        self.assertNotContains(response, self.survey4.title)


class SurveyModelTests(TestCase):
    """Test survey model methods and properties"""
    
    def setUp(self):
        self.org = Organisation.objects.create(name='Test Org')
        self.user = get_user_model().objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_survey_key_generation(self):
        """Test that survey keys are generated automatically"""
        survey = Survey.objects.create(
            title='Test Survey',
            org=self.org,
            created_by=self.user
        )
        
        self.assertIsNotNone(survey.survey_key)
        self.assertGreater(len(survey.survey_key), 20)  # Should be long enough
    
    def test_survey_is_accessible_active(self):
        """Test survey accessibility when active"""
        survey = Survey.objects.create(
            title='Test Survey',
            org=self.org,
            created_by=self.user,
            is_active=True
        )
        
        self.assertTrue(survey.is_accessible())
    
    def test_survey_is_accessible_inactive(self):
        """Test survey accessibility when inactive"""
        survey = Survey.objects.create(
            title='Test Survey',
            org=self.org,
            created_by=self.user,
            is_active=False
        )
        
        self.assertFalse(survey.is_accessible())
    
    def test_survey_is_accessible_future_start(self):
        """Test survey accessibility with future start date"""
        survey = Survey.objects.create(
            title='Test Survey',
            org=self.org,
            created_by=self.user,
            is_active=True,
            start_date=date.today() + timedelta(days=1)
        )
        
        self.assertFalse(survey.is_accessible())
    
    def test_survey_is_accessible_past_end(self):
        """Test survey accessibility with past end date"""
        survey = Survey.objects.create(
            title='Test Survey',
            org=self.org,
            created_by=self.user,
            is_active=True,
            end_date=date.today() - timedelta(days=1)
        )
        
        self.assertFalse(survey.is_accessible())
    
    def test_survey_response_count(self):
        """Test survey response count calculation"""
        survey = Survey.objects.create(
            title='Test Survey',
            org=self.org,
            created_by=self.user
        )
        
        # Create some responses
        SurveyResponse.objects.create(
            survey=survey,
            org=self.org,
            is_complete=True
        )
        SurveyResponse.objects.create(
            survey=survey,
            org=self.org,
            is_complete=True
        )
        # This one shouldn't count (incomplete)
        SurveyResponse.objects.create(
            survey=survey,
            org=self.org,
            is_complete=False
        )
        
        self.assertEqual(survey.response_count(), 2)
    
    def test_survey_max_responses_limit(self):
        """Test survey accessibility with max responses limit"""
        survey = Survey.objects.create(
            title='Test Survey',
            org=self.org,
            created_by=self.user,
            is_active=True,
            max_responses=2
        )
        
        # Should be accessible initially
        self.assertTrue(survey.is_accessible())
        
        # Add responses up to limit
        SurveyResponse.objects.create(
            survey=survey,
            org=self.org,
            is_complete=True
        )
        SurveyResponse.objects.create(
            survey=survey,
            org=self.org,
            is_complete=True
        )
        
        # Should no longer be accessible
        self.assertFalse(survey.is_accessible())
