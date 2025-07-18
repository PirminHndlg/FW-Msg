from datetime import datetime, timedelta
from django.forms import ValidationError
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.models import User
from .forms import EmailAuthenticationForm, FirstLoginForm
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth import get_user_model
import re
from Global.models import CustomUser, Maintenance
from django.utils import timezone
from django.core import signing
from django.contrib.auth.decorators import login_required

def _is_email(value):
        """
        Check if the given value is an email address.
        
        Args:
            value (str): The string to check
            
        Returns:
            bool: True if the value is an email address, False otherwise
        """
        email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        return bool(re.match(email_pattern, value))

def index(request):
    maintenance = Maintenance.objects.order_by('-id').first()
    
    if maintenance:
        return redirect('maintenance')

    def redirect_to_home(user):
        if user.role == 'O':
            return redirect('org_home')
        elif user.role == 'T':
            return redirect('team_home')
        elif user.role == 'F':
            return redirect('fw_home')
        elif user.role == 'A' or user.is_superuser:
            return redirect('admin_home')
        elif user.role == 'B':
            return redirect('bw_home')
        else:
            messages.error(request, _('Ungültige Personengruppe.'))
            return redirect('index')
         
    # Handle login form
    form = EmailAuthenticationForm()
    if request.method == 'POST':
        form = EmailAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')

            # Try to authenticate with the provided credentials
            user = None
            
            # First check if input is an email
            if _is_email(username):
                try:
                    # Get the user by email
                    email_user = get_user_model().objects.get(email=username)
                    # Then authenticate with the username and password
                    user = authenticate(username=email_user.username, password=password)
                    
                    # Check if user exists but is not active (email not verified)
                    if user is None and email_user is not None and not email_user.is_active:
                        messages.error(request, _('Bitte verifizieren Sie zuerst Ihre E-Mail-Adresse.'))
                        return redirect('index')
                        
                except get_user_model().DoesNotExist:
                    user = None
            else:
                # Standard username authentication
                user = authenticate(username=username, password=password)
                
                # Check if user exists but is not active
                if user is None:
                    try:
                        username_user = get_user_model().objects.get(username=username)
                        if not username_user.is_active:
                            messages.error(request, _('Bitte verifizieren Sie zuerst Ihre E-Mail-Adresse.'))
                            return redirect('index')
                    except get_user_model().DoesNotExist:
                        pass

            if user is not None:
                login(request, user)
                
                from django.contrib.auth.password_validation import validate_password
                try:
                    validate_password(password, user)
                except ValidationError as e:
                    messages.error(request, 'Das Passwort entspricht den Anforderungen nicht, wir empfehlen einen Passwortwechsel.')
                    return redirect('password_change')
                
                return redirect_to_home(user)
            else:
                # Add non-field error if authentication fails
                messages.error(request, _('Ungültiger Benutzername oder Passwort.'))
                return redirect('index')
    
    # Redirect if user is already authenticated
    if request.path != '/index':
        if request.user.is_authenticated and hasattr(request.user, 'customuser'):
            return redirect_to_home(request.user)

    return render(request, 'index.html', {'form': form})

def maintenance(request):
    maintenance = Maintenance.objects.order_by('-id').first()

    if not maintenance:
        messages.error(request, 'Keine Wartungsarbeiten geplant.')
        return redirect('index_home')
    
    
    maintenance_start_time = maintenance.maintenance_start_time
    maintenance_end_time = maintenance.maintenance_end_time
    
    # Calculate progress percentage
    # Use timezone-aware current time if maintenance times are timezone-aware
    if timezone.is_aware(maintenance_start_time):
        current_time = timezone.now()
    else:
        # If maintenance times are naive, use naive current time
        current_time = datetime.now()
    
    if current_time < maintenance_start_time:
        progress_percentage = 0
    elif current_time > maintenance_end_time:
        progress_percentage = 100
    else:
        # Calculate percentage of time elapsed
        total_duration = (maintenance_end_time - maintenance_start_time).total_seconds()
        elapsed_duration = (current_time - maintenance_start_time).total_seconds()
        progress_percentage = min(round((elapsed_duration / total_duration) * 100), 99)

    # Format datetime for display in local timezone
    if hasattr(maintenance_end_time, 'strftime'):
        # Convert to local timezone if it's timezone-aware
        if timezone.is_aware(maintenance_end_time):
            local_end_time = timezone.localtime(maintenance_end_time)
        else:
            local_end_time = maintenance_end_time
            
        # Format the time in German
        try:
            import locale
            # Try to set German locale for date formatting
            try:
                locale.setlocale(locale.LC_TIME, 'de_DE.UTF-8')
            except locale.Error:
                try:
                    locale.setlocale(locale.LC_TIME, 'de_DE')
                except locale.Error:
                    # Fallback if German locale is not available
                    pass
                    
            # Format date in German style
            formatted_end_time = local_end_time.strftime("%d. %B %Y, %H:%M")
            
        except ImportError:
            # Simple fallback if locale module is not available
            formatted_end_time = local_end_time.strftime("%d. %m. %Y, %H:%M")
    else:
        formatted_end_time = maintenance_end_time
    
    return render(request, 'maintenance.html', {
        'maintenance_end_time': formatted_end_time,
        'progress_percentage': progress_percentage
    })
    
def token_login(request, token):
    try:
        custom_user = CustomUser.objects.get(token=token)
        user = custom_user.user
        login(request, user)
        return redirect('index_home')
    except Exception as e:
        messages.error(request, 'Ungültiger Token.')
        return redirect('index_home')
    
def first_login(request, username=None, einmalpasswort=None):
    if request.method == 'POST':
        form = FirstLoginForm(request.POST)
        if form.is_valid():
            user_name = form.cleaned_data['username']
            password = form.cleaned_data['password']
            einmalpasswort = form.cleaned_data['einmalpasswort']
            
            def redirect_to_first_login(username, einmalpasswort):
                if username and einmalpasswort:
                    return redirect('first_login_with_params', username=username, einmalpasswort=einmalpasswort)
                elif username:
                    return redirect('first_login_with_username', username=username)
                else:
                    return redirect('first_login')
            
            try:
                if _is_email(user_name):
                    user = User.objects.get(email=user_name)
                else:
                    user = User.objects.get(username=user_name)
            except User.DoesNotExist:
                messages.error(request, _('Benutzername oder E-Mail-Adresse nicht gefunden.'))
                return redirect_to_first_login(user_name, einmalpasswort)

            if not user.customuser:
                messages.error(request, _('Interner Fehler: Benutzer nicht gefunden. Kontaktiere den Administrator.'))
                return redirect_to_first_login(user_name, einmalpasswort)
            
            if not user.customuser.einmalpasswort:
                messages.error(request, _('Einmalpasswort bereits verwendet.'))
                return redirect_to_first_login(user_name, einmalpasswort)
            
            if user.customuser.einmalpasswort != einmalpasswort:
                messages.error(request, _('Ungültiges Einmalpasswort.'))
                return redirect_to_first_login(user_name, einmalpasswort)
            
            user.customuser.einmalpasswort = None
            user.customuser.save()

            user.set_password(password)
            user.save()

            # Re-authenticate with new password
            user = authenticate(username=user.username, password=password)
            if user is not None:
                login(request, user)
                return redirect('index_home')
            else:
                messages.error(request, _('Fehler beim Login. Bitte versuchen Sie es erneut.'))
                return redirect('first_login')
    else:
        initial = {}
        if username or request.GET.get('username'):
            initial['username'] = username or request.GET.get('username')
        if einmalpasswort or request.GET.get('einmalpasswort'):
            initial['einmalpasswort'] = einmalpasswort or request.GET.get('einmalpasswort')
        form = FirstLoginForm(initial=initial)

    return render(request, 'first_login.html', {'form': form})

def password_reset(request):
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                messages.success(request, 'Eine E-Mail mit einem Link zum Zurücksetzen des Passworts wurde an die angegebene E-Mail-Adresse gesendet.')
                user.customuser.send_registration_email()
                return redirect('first_login')
            except User.DoesNotExist:
                messages.error(request, 'Es gibt keinen Benutzer mit dieser E-Mail-Adresse.')
                return redirect('password_reset')
    else:
        form = PasswordResetForm()
    return render(request, 'password_reset.html', {'form': form})

@login_required
def password_change(request):
    if request.method == 'POST':
        form = SetPasswordForm(request.user, request.POST)
        user = request.user
        if form.is_valid():
            user.set_password(form.cleaned_data['new_password1'])
            user.save()
            messages.success(request, _('Ihr Passwort wurde erfolgreich geändert.'))
            
            new_user = authenticate(username=user.username, password=form.cleaned_data['new_password1'])
            login(request, new_user)
            
            return redirect('index_home')
    else:
        form = SetPasswordForm(request.user)
        
    form.fields['new_password1'].widget.attrs['class'] = 'form-control rounded-3'
    form.fields['new_password2'].widget.attrs['class'] = 'form-control rounded-3'
    return render(request, 'password_change.html', {'form': form})