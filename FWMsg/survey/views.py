import os
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse, Http404, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.vary import vary_on_headers
from django.views.decorators.http import require_http_methods
from Global.views import check_organization_context
from FWMsg.decorators import required_role


from .models import Survey, SurveyQuestion, SurveyQuestionOption, SurveyResponse, SurveyAnswer
from .forms import (
    SurveyForm, SurveyQuestionForm, SurveyQuestionOptionForm, 
    SurveyParticipationForm, SurveyQuestionOptionFormSet
)
from .pdf_utils import generate_survey_response_pdf, create_pdf_response


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def check_survey_access(request, survey):
    """Check if user has access to manage this survey"""
    if request.user.is_authenticated and survey.org != request.user.org:
        raise Http404("Survey not found")
    return True


# Public Views (accessible without login if survey allows anonymous)

@never_cache
@vary_on_headers('User-Agent')
def survey_detail(request, survey_key):
    """Display survey for participation"""
    survey = get_object_or_404(Survey, survey_key=survey_key)
    
    # Check if survey is accessible
    if not survey.is_accessible():
        messages.error(request, _('This survey is not currently available.'))
        return render(request, 'survey/survey_not_available.html', {'survey': survey})
    
    # Check if user needs to be logged in
    if not survey.allow_anonymous and not request.user.is_authenticated:
        messages.warning(request, _('You need to be logged in to participate in this survey.'))
        
        #add next url to login url as parameter
        next_url = reverse('survey:survey_detail', kwargs={'survey_key': survey_key})
        return redirect(reverse('login') + '?next=' + next_url)
    
    # Check if user has already participated (skip this check for anonymous surveys)
    if not survey.responses_are_anonymous:
        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key if not user else None
        
        existing_response = SurveyResponse.objects.filter(
            survey=survey,
            respondent=user,
            session_key=session_key
        ).first()
        
        if existing_response:
            return render(request, 'survey/survey_already_completed.html', {
                'survey': survey,
                'response': existing_response
            })
    else:
        user = None
    
    if request.method == 'POST':
        form = SurveyParticipationForm(survey, request.POST)
        if form.is_valid():
            # Ensure session exists for anonymous users
            if not user and not request.session.session_key:
                request.session.create()
            
            response = form.save_response(
                survey=survey,
                user=user,
                session_key=request.session.session_key if not user else None,
                ip_address=get_client_ip(request)
            )
            
            return redirect('survey:survey_thank_you', survey_key=survey_key)
    else:
        form = SurveyParticipationForm(survey)
    
    context = check_organization_context(request)
    context['survey'] = survey
    context['form'] = form
    return render(request, 'survey/survey_detail.html', context)


def survey_thank_you(request, survey_key):
    """Thank you page after survey completion"""
    survey = get_object_or_404(Survey, survey_key=survey_key)
    context = check_organization_context(request)
    context['survey'] = survey
    return render(request, 'survey/survey_thank_you.html', context)


# Management Views (require login and permissions)

@method_decorator(login_required, name='dispatch')
@method_decorator(required_role('O'), name='dispatch')
class SurveyListView(ListView):
    """List all surveys for the logged-in user"""
    model = Survey
    template_name = 'survey/survey_list.html'
    context_object_name = 'surveys'
    paginate_by = 10
    
    def get_queryset(self):
        qs = Survey.objects.all()
        if self.request.user.is_authenticated:
            qs = qs.filter(org=self.request.user.org)
        return qs
        # return qs.filter(created_by=self.request.user).annotate(
        #     response_count=Count('responses')
        # )


@method_decorator(login_required, name='dispatch')
@method_decorator(required_role('O'), name='dispatch')
class SurveyCreateView(CreateView):
    """Create a new survey"""
    model = Survey
    form_class = SurveyForm
    template_name = 'survey/survey_create.html'
    success_url = reverse_lazy('survey:survey_list')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        if self.request.user.is_authenticated:
            form.instance.org = self.request.user.org
        else:
            form.instance.org = None
        messages.success(self.request, _('Survey created successfully!'))
        survey = form.save()
        return redirect('survey:survey_manage', pk=survey.pk)


@method_decorator(login_required, name='dispatch')
@method_decorator(required_role('O'), name='dispatch')
class SurveyUpdateView(UpdateView):
    """Update an existing survey"""
    model = Survey
    form_class = SurveyForm
    template_name = 'survey/survey_update.html'
    context_object_name = 'survey'
    
    def get_queryset(self):
        return Survey.objects.filter(org=self.request.user.org)
    
    def get_success_url(self):
        return reverse('survey:survey_manage', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, _('Survey updated successfully!'))
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
@method_decorator(required_role('O'), name='dispatch')
class SurveyDeleteView(DeleteView):
    """Delete a survey"""
    model = Survey
    template_name = 'survey/survey_delete.html'
    context_object_name = 'survey'
    success_url = reverse_lazy('survey:survey_list')
    
    def get_queryset(self):
        return Survey.objects.filter(org=self.request.user.org)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, _('Survey deleted successfully!'))
        context = check_organization_context(request)
        context['survey'] = self.object
        return render(request, 'survey/survey_delete.html', context)


@login_required
@required_role('O')
def survey_manage(request, pk):
    """Manage survey questions and view responses"""
    survey = get_object_or_404(Survey, pk=pk)
    check_survey_access(request, survey)
    
    questions = survey.questions.all().prefetch_related('options')
    responses = survey.responses.filter(is_complete=True)
    
    context = check_organization_context(request)
    context['survey'] = survey
    context['questions'] = questions
    context['responses'] = responses
    context['response_count'] = responses.count()
    return render(request, 'survey/survey_manage.html', context)


@login_required
@required_role('O')
def add_question(request, survey_pk):
    """Add a question to a survey"""
    survey = get_object_or_404(Survey, pk=survey_pk)
    check_survey_access(request, survey)
    
    if request.method == 'POST':
        form = SurveyQuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.survey = survey
            question.org = survey.org
            question.save()
            messages.success(request, _('Question added successfully!'))
            if question.question_type in ['select', 'radio', 'checkbox']:
                return redirect('survey:edit_question', survey_pk=survey.pk, question_pk=question.pk)
            else:
                return redirect('survey:survey_manage', pk=survey.pk)
    else:
        form = SurveyQuestionForm()
    
    context = check_organization_context(request)
    context['survey'] = survey
    context['form'] = form
    return render(request, 'survey/add_question.html', context)


@login_required
@required_role('O')
def edit_question(request, survey_pk, question_pk):
    """Edit a survey question and its options"""
    survey = get_object_or_404(Survey, pk=survey_pk)
    check_survey_access(request, survey)
    question = get_object_or_404(SurveyQuestion, pk=question_pk, survey=survey)
    
    if request.method == 'POST':
        form = SurveyQuestionForm(request.POST, instance=question)
        formset = SurveyQuestionOptionFormSet(request.POST, instance=question, prefix='options')
        
        if form.is_valid():
            # Save the question first
            form.save()
            
            if formset.is_valid():
                # Save the options, ensuring org is set
                option_forms = formset.save(commit=False)
                for option in option_forms:
                    option.org = question.org
                    option.save()
                # Delete any removed options
                for obj in formset.deleted_objects:
                    obj.delete()
            messages.success(request, _('Question updated successfully!'))
            return redirect('survey:survey_manage', pk=survey.pk)
        else:
            # Add form errors to messages
            if form.errors:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"Question {field}: {error}")
    else:
        form = SurveyQuestionForm(instance=question)
        formset = SurveyQuestionOptionFormSet(instance=question, prefix='options')
    
    context = check_organization_context(request)
    context['survey'] = survey
    context['question'] = question
    context['form'] = form
    context['formset'] = formset
    return render(request, 'survey/edit_question.html', context)


@login_required
@required_role('O')
def delete_question(request, survey_pk, question_pk):
    """Delete a survey question"""
    survey = get_object_or_404(Survey, pk=survey_pk)
    question = get_object_or_404(SurveyQuestion, pk=question_pk, survey=survey)
    
    if request.method == 'POST':
        question.delete()
        messages.success(request, _('Question deleted successfully!'))
        return redirect('survey:survey_manage', pk=survey.pk)
    
    context = check_organization_context(request)
    context['survey'] = survey
    context['question'] = question
    return render(request, 'survey/delete_question.html', context)


@login_required
@required_role('O')
def survey_results(request, pk):
    """View detailed survey results"""
    survey = get_object_or_404(Survey, pk=pk)
    check_survey_access(request, survey)
    
    responses = survey.responses.filter(is_complete=True).prefetch_related(
        'answers__question',
        'answers__selected_options'
    )
    
    # Prepare results data
    results_data = {}
    for question in survey.questions.all():
        question_results = {
            'question': question,
            'answers': [],
            'stats': {}
        }
        
        answers = SurveyAnswer.objects.filter(
            response__in=responses,
            question=question
        )
        
        if question.question_type in ['select', 'radio', 'checkbox']:
            # Count option selections
            option_counts = {}
            for answer in answers:
                for option in answer.selected_options.all():
                    option_counts[option.option_text] = option_counts.get(option.option_text, 0) + 1
            question_results['stats'] = option_counts
        
        elif question.question_type == 'rating':
            # Calculate rating statistics
            ratings = [int(answer.text_answer) for answer in answers if answer.text_answer.isdigit()]
            if ratings:
                question_results['stats'] = {
                    'average': sum(ratings) / len(ratings),
                    'count': len(ratings),
                    'distribution': {str(i): ratings.count(i) for i in range(1, 6)}
                }
        
        else:
            # Text answers
            question_results['answers'] = [answer.text_answer for answer in answers if answer.text_answer]
        
        results_data[question.id] = question_results
    
    context = check_organization_context(request)
    context['survey'] = survey
    context['responses'] = responses
    context['results_data'] = results_data
    context['total_responses'] = responses.count()
    return render(request, 'survey/survey_results.html', context)


# AJAX Views for dynamic form handling

@login_required
@require_http_methods(["GET"])
def get_question_form(request):
    """AJAX view to get question form HTML"""
    question_type = request.GET.get('type', 'text')
    
    # Return appropriate form HTML based on question type
    needs_options = question_type in ['select', 'radio', 'checkbox']
    
    context = check_organization_context(request)
    context['question_type'] = question_type
    context['needs_options'] = needs_options
    
    return JsonResponse({
        'needs_options': needs_options,
        'html': render(request, 'survey/partials/question_form.html', context).content.decode('utf-8')
    })


# Staff Views (for site administration)

@staff_member_required
def admin_survey_list(request):
    """Admin view to list all surveys"""
    if request.user.is_authenticated:
        surveys = Survey.objects.filter(org=request.user.org).annotate(
            response_count=Count('responses')
        ).order_by('-created_at')
    else:
        surveys = Survey.objects.all().annotate(
            response_count=Count('responses')
        ).order_by('-created_at')
    
    paginator = Paginator(surveys, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = check_organization_context(request)
    context['page_obj'] = page_obj
    context['surveys'] = page_obj
    return render(request, 'survey/admin_survey_list.html', context)


# PDF Export Views

@login_required
@required_role('O')
def export_response_pdf(request, response_id):
    """Export a single survey response as PDF"""
    response = get_object_or_404(SurveyResponse, id=response_id, is_complete=True)
    check_survey_access(request, response.survey)
    
    # Generate PDF
    pdf_content = generate_survey_response_pdf(response)
    
    # Create filename
    if response.survey.responses_are_anonymous:
        respondent_name = f"Response_{response.id}"
    else:
        respondent_name = "Anonymous" if not response.respondent else response.respondent.username
    filename = f"survey_response_{response.survey.title}_{respondent_name}.pdf"
    # Clean filename for filesystem compatibility
    filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
    filename = filename.replace(' ', '_')
    
    return create_pdf_response(pdf_content, filename)


@login_required
@required_role('O')
def export_survey_responses_pdf(request, survey_id):
    """Export all responses for a survey as individual PDFs in a ZIP file"""
    import zipfile
    import tempfile
    
    survey = get_object_or_404(Survey, id=survey_id)
    check_survey_access(request, survey)
    
    responses = survey.responses.filter(is_complete=True).select_related('respondent')
    
    if not responses.exists():
        messages.warning(request, _('No completed responses found for this survey.'))
        return redirect('survey:survey_results', pk=survey.id)
    
    # Create a temporary file for the ZIP
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    
    try:
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for response in responses:
                # Generate PDF for each response
                pdf_content = generate_survey_response_pdf(response)
                
                # Create filename for this response
                if survey.responses_are_anonymous:
                    respondent_name = f"Response_{response.id}"
                else:
                    respondent_name = "Anonymous" if not response.respondent else response.respondent.username
                pdf_filename = f"response_{respondent_name}.pdf"
                pdf_filename = "".join(c for c in pdf_filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
                pdf_filename = pdf_filename.replace(' ', '_')
                
                # Add PDF to ZIP
                zip_file.writestr(pdf_filename, pdf_content)
        
        # Read the ZIP file content
        with open(temp_zip.name, 'rb') as zip_content:
            response_content = zip_content.read()
        
        # Clean up temporary file
        os.unlink(temp_zip.name)
        
        # Create response
        zip_filename = f"survey_responses_{survey.title}_{survey.id}.zip"
        zip_filename = "".join(c for c in zip_filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
        zip_filename = zip_filename.replace(' ', '_')
        
        response = HttpResponse(response_content, content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
        return response
        
    except Exception as e:
        # Clean up on error
        if os.path.exists(temp_zip.name):
            os.unlink(temp_zip.name)
        messages.error(request, _('Error generating PDF export: %(error)s') % {'error': str(e)})
        return redirect('survey:survey_results', pk=survey.id)
