from datetime import datetime
import os
from django.db import IntegrityError
from django.http import FileResponse
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from ORG.models import Organisation
from .forms import CreateAccountForm, ApplicationAnswerForm, ApplicationFileAnswerForm
from FWMsg.decorators import required_role
from .models import ApplicationQuestion, ApplicationAnswer, ApplicationText, Bewerber, ApplicationAnswerFile, ApplicationFileQuestion
from django.contrib import messages
# Create your views here.
@login_required
@required_role('B')
def home(request):
    application_text = ApplicationText.objects.filter(org=request.user.org).first()
    
    total_questions = ApplicationQuestion.objects.filter(org=request.user.org).count()
    answered_questions = ApplicationAnswer.objects.filter(user=request.user).exclude(answer='').count()
    
    total_file_questions = ApplicationFileQuestion.objects.filter(org=request.user.org).count()
    answered_file_questions = ApplicationAnswerFile.objects.filter(user=request.user).exclude(file='').count()
    
    context = {
        'application_text': application_text,
        'total_questions': total_questions,
        'answered_questions': answered_questions,
        'answered_questions_percentage': int(answered_questions / total_questions * 100) if total_questions > 0 else 0,
        'open_questions': total_questions - answered_questions,
        
        'total_file_questions': total_file_questions,
        'answered_file_questions': answered_file_questions,
        'answered_file_questions_percentage': int(answered_file_questions / total_file_questions * 100) if total_file_questions > 0 else 0,
        'open_file_questions': total_file_questions - answered_file_questions
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
    
    file_questions = ApplicationFileQuestion.objects.filter(org=request.user.org).order_by('order')
    file_answers = ApplicationAnswerFile.objects.filter(user=request.user, file_question__in=file_questions)
    
    answers_dict = {answer.question.id: answer for answer in answers}
    file_answers_dict = {answer.file_question.id: answer for answer in file_answers}
    
    context = {
        'questions': questions,
        'answers': answers_dict,
        'file_answers': file_answers_dict
    }
    
    return render(request, 'bw_application_questions_list.html', context)

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

@login_required
@required_role('B')
def bw_application_files_list(request):
    file_questions = ApplicationFileQuestion.objects.filter(org=request.user.org).order_by('order')
    file_answers = ApplicationAnswerFile.objects.filter(user=request.user, file_question__in=file_questions)
    
    # Create a dictionary with question IDs as keys and answers as values
    answers_dict = {answer.file_question.id: answer for answer in file_answers}
    
    context = {
        'file_questions': file_questions,
        'file_answers': answers_dict
    }
    
    return render(request, 'bw_application_files_list.html', context)

@login_required
# @required_role('B')
def bw_application_file_answer(request, file_question_id):
    file_question = ApplicationFileQuestion.objects.get(org=request.user.org, id=file_question_id)
    answer = ApplicationAnswerFile.objects.filter(user=request.user, file_question=file_question).first()
    if len(request.FILES) == 1:
        form = ApplicationFileAnswerForm(request.POST or None, request.FILES or None, user=request.user, file_question=file_question, instance=answer)
    else:
        form = ApplicationFileAnswerForm(request.POST or None, user=request.user, file_question=file_question, instance=answer)

    if request.method == 'POST' and form.is_valid() and len(request.FILES) == 1:
        form.save()
        return redirect('bw_application_files_list')
    elif request.method == 'POST' and form.is_valid() and len(request.FILES) == 0:
        return redirect('bw_application_files_list')
    
    return render(request, 'bw_application_file_answer.html', {'form': form, 'file_question': file_question, 'answer': answer})

@login_required
# @required_role('B')
def bw_application_file_answer_download(request, file_answer_id):
    try:
        file_answer = ApplicationAnswerFile.objects.get(id=file_answer_id, user=request.user)
    except ApplicationAnswerFile.DoesNotExist:
        messages.error(request, 'Datei nicht gefunden')
        return redirect('bw_application_files_list')
    
    if file_answer.file and os.path.exists(file_answer.file.path):
        response = FileResponse(file_answer.file)
        response['Content-Disposition'] = f'attachment; filename="{file_answer.file.name}"'
        return response
    else:
        messages.error(request, 'Datei nicht gefunden')
        return redirect('bw_application_files_list')

@login_required
# @required_role('B')
def bw_application_file_answer_delete(request, file_answer_id):
    file_answer = ApplicationAnswerFile.objects.get(id=file_answer_id, user=request.user)
    file_answer.delete()
    messages.success(request, 'Datei wurde erfolgreich gelöscht')
    return redirect('bw_application_files_list')
