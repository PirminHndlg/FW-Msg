from functools import wraps
from datetime import datetime
from django.shortcuts import redirect
from .models import ApplicationText
from seminar.models import Seminar
from BW.models import Bewerber

def application_or_seminar_is_open(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            bewerber = Bewerber.objects.get(user=request.user)
        except Bewerber.DoesNotExist:
            # If bewerber doesn't exist, redirect to no_application
            return redirect('bw_no_application')
        
        current_datetime = datetime.now()
        current_date = current_datetime.date()
        
        # Check if there's an active seminar for this bewerber
        # Seminar.bewerber is a ManyToManyField, so we need to use bewerber__in
        current_seminar = Seminar.objects.filter(
            org=bewerber.org,
            deadline_start__lte=current_datetime,
            deadline_end__gte=current_datetime,
            bewerber__in=[bewerber]
        )
        if current_seminar.exists():
            return redirect('seminar_home')
        
        # Check if there's an active application text (deadline is a DateField)
        current_application_text = ApplicationText.objects.filter(
            org=bewerber.org,
            deadline__gte=current_date
        ).exists()
        if not current_application_text:
            return redirect('bw_no_application')
        
        return view_func(request, *args, **kwargs)
    return wrapper