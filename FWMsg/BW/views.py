from datetime import datetime
from django.db import IntegrityError
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from ORG.models import Organisation
from .forms import CreateAccountForm, ApplicationAnswerForm
from FWMsg.decorators import required_role
from .models import ApplicationQuestion, ApplicationAnswer, ApplicationText, Bewerber

# Create your views here.
@login_required
@required_role('B')
def home(request):
    application_text = ApplicationText.objects.filter(org=request.user.org).first()
    
    total_questions = ApplicationQuestion.objects.filter(org=request.user.org).count()
    answered_questions = ApplicationAnswer.objects.filter(user=request.user).exclude(answer='').count()
    
    context = {
        'application_text': application_text,
        'total_questions': total_questions,
        'answered_questions': answered_questions,
        'answered_questions_percentage': int(answered_questions / total_questions * 100) if total_questions > 0 else 0,
        'open_questions': total_questions - answered_questions
    }
    
    return render(request, 'homeBw.html', context)

def create_account(request, org_id):
    try:
        org = Organisation.objects.get(id=org_id)
    except Organisation.DoesNotExist:
        return redirect('bw_home')
    
    form = CreateAccountForm(request.POST or None, org=org)
    
    if request.method == 'POST' and form.is_valid():
        try:
            user = form.save()
            if user:
                login(request, user)
                return redirect('bw_home')
            else:
                form.add_error('email', 'User already exists')
        except IntegrityError:
            form.add_error('email', 'User already exists')
    
    context = {
        'form': form,
        'org': org
    }
    return render(request, 'bw_create_account.html', context)

@login_required
# @required_role('B')
def bw_application_questions_list(request):
    questions = ApplicationQuestion.objects.filter(org=request.user.org).order_by('order')
    answers = ApplicationAnswer.objects.filter(user=request.user, question__in=questions).exclude(answer='')
    answers_dict = {answer.question.id: answer for answer in answers}
    return render(request, 'bw_application_questions_list.html', {'questions': questions, 'answers': answers_dict})

@login_required
# @required_role('B')
def bw_application_answer(request, question_id):
    question = ApplicationQuestion.objects.get(org=request.user.org, id=question_id)
    answer = ApplicationAnswer.objects.filter(user=request.user, question=question).first()
    form = ApplicationAnswerForm(request.POST or None, user=request.user, question=question, instance=answer)
    
    if request.method == 'POST' and form.is_valid():
        bewerber = Bewerber.objects.get(user=request.user)
        
        if bewerber.abgeschlossen == True:
            messages.error(request, 'Sie haben bereits Ihre Bewerbung abgeschlossen.')
            return redirect('bw_application_complete')
        
        answer = form.save()
        if answer.answer == '':
            answer.delete()
            
        return redirect('bw_application_questions_list')
    
    return render(request, 'bw_application_answer.html', {'form': form, 'question': question, 'answer': answer})

@login_required
# @required_role('B')
def bw_application_answers_list(request):
    answers = ApplicationAnswer.objects.filter(org=request.user.org)
    return render(request, 'bw_application_answers_list.html', {'answers': answers})


@login_required
# @required_role('B')
def bw_application_complete(request):
    bewerber = Bewerber.objects.get(user=request.user)
    bewerber.abgeschlossen = True
    bewerber.abgeschlossen_am = datetime.now()
    bewerber.save()
    return redirect('bw_home')