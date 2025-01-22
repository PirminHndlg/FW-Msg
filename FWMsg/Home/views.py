from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.utils.translation import gettext as _

def index(request):
    # Redirect if user is already authenticated
    if request.path != '/index':
        if request.user.is_authenticated:
            if request.user.customuser.role == 'O':
                return redirect('org_home')
            return redirect('fw_home')

    # Handle login form
    form = AuthenticationForm()
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                # Redirect based on user type
                if hasattr(user, 'org'):
                    return redirect('org_home')
                return redirect('fw_home')
            else:
                messages.error(request, _('Ungültiger Benutzername oder Passwort.'))
        else:
            messages.error(request, _('Ungültiger Benutzername oder Passwort.'))

    return render(request, 'index.html', {'form': form})
