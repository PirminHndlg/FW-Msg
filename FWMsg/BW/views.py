from datetime import datetime
import hashlib
import os
import secrets
import time
from celery import uuid
from django.db import IntegrityError
from django.http import FileResponse
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from BW.tasks import send_account_created_email, send_application_complete_email
from ORG.models import Organisation
from .forms import CreateAccountForm, ApplicationAnswerForm, ApplicationFileAnswerForm
from FWMsg.decorators import required_role
from .models import ApplicationQuestion, ApplicationAnswer, ApplicationText, Bewerber, ApplicationAnswerFile, ApplicationFileQuestion
from django.contrib import messages

base_template = 'baseBw.html'

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
        'open_file_questions': total_file_questions - answered_file_questions,
        'now': datetime.now().date()
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
            user, bewerber = form.save()
            if user:
                # Create a SHA-256 hash of this value
                unique_value = f"{user.id}_{time.time()}_{secrets.token_hex(16)}"
                hash_obj = hashlib.sha256(unique_value.encode())
                verification_token = hash_obj.hexdigest()
                
                bewerber.verification_token = verification_token
                bewerber.save()
                
                user.is_active = False
                user.save()
                
                send_account_created_email.s(bewerber.id).apply_async(countdown=2)
                return redirect('account_created')
            else:
                form.add_error('email', 'User already exists')
        except IntegrityError:
            form.add_error('email', 'User already exists')
    
    context = {
        'form': form,
        'org': org
    }
    return render(request, 'bw_create_account.html', context)

def account_created(request):
    return render(request, 'bw_account_created.html')

def verify_account(request, token):
    try:
        bewerber = Bewerber.objects.get(verification_token=token)
        bewerber.user.is_active = True
        bewerber.user.save()
        login(request, bewerber.user)
        return redirect('bw_home')
    except Bewerber.DoesNotExist:
        return redirect('bw_home')


@login_required
@required_role('B')
def bw_application_answer(request, question_id=None):
    all_questions = ApplicationQuestion.objects.filter(org=request.user.org).order_by('order')
    try:
        question = all_questions.get(id=question_id)
    except ApplicationQuestion.DoesNotExist:
        question = all_questions.first()
    
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
            
        next_question = all_questions.filter(order__gt=question.order).first()
        if next_question:
            return redirect('bw_application_answer', question_id=next_question.id)
        else:
            return redirect('bw_application_complete')
        
    answered_questions_ids = ApplicationAnswer.objects.filter(user=request.user).values_list('question_id', flat=True)
    print(answered_questions_ids)
    
    context = {
        'form': form,
        'question': question,
        'all_questions': all_questions,
        'answer': answer,
        'answered_questions_ids': answered_questions_ids
    }
    
    return render(request, 'bw_application_answer.html', context)

@login_required
@required_role('B')
def bw_application_answers_list(request):
    answers = ApplicationAnswer.objects.filter(org=request.user.org, user=request.user).order_by('question__order')
    file_answers = ApplicationAnswerFile.objects.filter(org=request.user.org, user=request.user).order_by('file_question__order')
    
    context = {
        'answers': answers,
        'file_answers': file_answers
    }
    return render(request, 'bw_application_answers_list.html', context)


@login_required
@required_role('B')
def bw_application_complete(request):
    try:
        application_text = ApplicationText.objects.filter(org=request.user.org).first()
        if application_text.deadline and application_text.deadline < datetime.now().date():
            messages.error(request, 'Die Abgabefrist ist abgelaufen.')
            return redirect('bw_home')
    except ApplicationText.DoesNotExist:
        pass
    
    bewerber = Bewerber.objects.get(user=request.user)
    bewerber.abgeschlossen = True
    bewerber.abgeschlossen_am = datetime.now()
    bewerber.save()
    send_application_complete_email.s(bewerber.id).apply_async(countdown=2)
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
@required_role('B')
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
@required_role('BO')
def bw_application_file_answer_download(request, file_answer_id):
    try:
        if request.user.customuser.person_cluster.view == 'B':
            file_answer = ApplicationAnswerFile.objects.get(id=file_answer_id, user=request.user)
        elif request.user.customuser.person_cluster.view == 'O':
            file_answer = ApplicationAnswerFile.objects.get(id=file_answer_id, file_question__org=request.user.org)
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
@required_role('BO')
def bw_application_file_answer_delete(request, file_answer_id):
    file_answer = ApplicationAnswerFile.objects.get(id=file_answer_id, user=request.user)
    file_answer.delete()
    messages.success(request, 'Datei wurde erfolgreich gelöscht')
    return redirect('bw_application_files_list')
