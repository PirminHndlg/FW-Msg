from datetime import datetime
from django.shortcuts import redirect
from .models import ApplicationText
from seminar.models import Seminar

def application_or_seminar_is_open(view_func):
    def wrapper(request, *args, **kwargs):
        current_date = datetime.now()
    
        current_seminar = Seminar.objects.filter(org=request.user.org, deadline_start__lte=current_date, deadline_end__gte=current_date).first()
        if current_seminar:
            return redirect('seminar_land')
        
        current_application_text = ApplicationText.objects.filter(org=request.user.org, deadline__gte=current_date).exists()
        if not current_application_text:
            return redirect('bw_no_application')
        return view_func(request, *args, **kwargs)
    return wrapper