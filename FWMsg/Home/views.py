from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.models import User
from .forms import PasswordResetForm

def index(request):
    # Redirect if user is already authenticated
    if request.path != '/index':
        if request.user.is_authenticated and hasattr(request.user, 'customuser'):
            if request.user.customuser.role == 'O':
                return redirect('org_home')
            elif request.user.customuser.role == 'T':
                return redirect('team_home')
            return redirect('fw_home')

    # Handle login form
    form = AuthenticationForm()
    if request.method == 'POST':
        form_login = AuthenticationForm(request, data=request.POST)
        if form_login.is_valid():
            username = form_login.cleaned_data.get('username')
            password = form_login.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                # Redirect based on user type
                if hasattr(user, 'org'):
                    return redirect('org_home')
                return redirect('fw_home')
            else:
                messages.error(request, _('Ungültiger Benutzername oder Passwort.'))

    return render(request, 'index.html', {'form': form})

def first_login(request):
    if request.method == 'POST':
        user_name = request.POST['username']
        password = request.POST['password']
        password_repeat = request.POST['password_repeat']
        einmalpasswort = request.POST['einmalpasswort']

        user_exists = User.objects.filter(username=user_name).exists()

        if not user_exists:
            messages.error(request, _('Benutzername nicht gefunden.'))
            return redirect('first_login')
        else:
            user = User.objects.get(username=user_name)
        
        if not user.customuser:
            messages.error(request, _('Interner Fehler: Benutzer nicht gefunden. Kontaktiere den Administrator.'))
            return redirect('first_login')
        
        if password != password_repeat:
            messages.error(request, _('Passwörter stimmen nicht überein.'))
            return redirect('first_login')
        
        if not user.customuser.einmalpasswort:
            messages.error(request, _('Einmalpasswort bereits verwendet.'))
            return redirect('first_login')
        
        if user.customuser.einmalpasswort != einmalpasswort:
            messages.error(request, _('Ungültiges Einmalpasswort.'))
            return redirect('first_login')
        
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

    return render(request, 'first_login.html')

def password_reset(request):
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(username=username)
                print(user.email, email)
                if user.email != email:
                    messages.error(request, 'Der Benutzer hat eine andere E-Mail-Adresse.')
                    return redirect('password_reset')
                else:
                    messages.success(request, 'Eine E-Mail mit einem Link zum Zurücksetzen des Passworts wurde an die angegebene E-Mail-Adresse gesendet.')
                    user.customuser.send_registration_email()
                    return redirect('first_login')
            except User.DoesNotExist:
                messages.error(request, 'Es gibt keinen Benutzer mit diesem Benutzernamen.')
                return redirect('password_reset')
    else:
        form = PasswordResetForm()
    return render(request, 'password_reset.html', {'form': form})