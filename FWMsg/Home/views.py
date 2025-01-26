from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.models import User
def index(request):
    # Redirect if user is already authenticated
    if request.path != '/index':
        if request.user.is_authenticated and hasattr(request.user, 'customuser'):
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

def first_login(request):
    if request.method == 'POST':
        user_name = request.POST['username']
        password = request.POST['password']
        password_repeat = request.POST['password_repeat']
        einmalpasswort = request.POST['einmalpasswort']

        user = User.objects.get(username=user_name)

        if password != password_repeat:
            messages.error(request, _('Passwörter stimmen nicht überein.'))
            return redirect('first_login')
        
        if user.customuser.einmalpasswort == einmalpasswort:
            user.customuser.einmalpasswort = None
            user.customuser.save()

            user.set_password(password)
            user.save()

            # Re-authenticate with new password
            user = authenticate(username=user_name, password=password)
            if user is not None:
                login(request, user)
                return redirect('index_home')
            else:
                messages.error(request, _('Fehler beim Login. Bitte versuchen Sie es erneut.'))
                return redirect('first_login')
        else:
            messages.error(request, _('Ungültiges Einmalpasswort.'))
            return redirect('first_login')

    return render(request, 'first_login.html')
