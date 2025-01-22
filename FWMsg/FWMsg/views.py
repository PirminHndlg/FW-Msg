from django.contrib import messages
from django.contrib.auth import logout
from django.http import HttpResponseRedirect


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return HttpResponseRedirect('/')
