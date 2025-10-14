from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.shortcuts import redirect

def group_required(group_name):
    def decorator(view_func):
        @user_passes_test(lambda u: u.is_authenticated and u.groups.filter(name=group_name).exists())
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.groups.filter(name=group_name).exists():
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def required_role(roles):
    """
    Decorator to check if user has required role(s).
    
    Args:
        roles: String of allowed role characters (e.g., 'T' for Team, 'TE' for Team or Ehemalige)
               Empty string '' allows all authenticated users
    
    Example:
        @required_role('T')  # Only Team members
        @required_role('TE') # Team or Ehemalige members
        @required_role('O')  # Only Organization members
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            try:
                # Superusers bypass role checks
                if request.user.is_superuser:
                    return view_func(request, *args, **kwargs)
                
                # Empty string means allow all authenticated users
                if roles == '':
                    return view_func(request, *args, **kwargs)
                
                # Check if user has customuser with person_cluster
                if not hasattr(request.user, 'customuser') or not request.user.customuser.person_cluster:
                    raise PermissionDenied
                
                # Get user's role/view
                user_view = request.user.customuser.person_cluster.view
                
                # Check if user's view is in allowed roles
                if user_view not in roles:
                    raise PermissionDenied
                
                return view_func(request, *args, **kwargs)
            except AttributeError:
                raise PermissionDenied
            
        return _wrapped_view
    return decorator

def required_person_cluster(person_cluster_attribute):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            try:
                if not request.user.customuser.person_cluster or not getattr(request.user.customuser.person_cluster, person_cluster_attribute):
                    messages.error(request, 'Du hast keine Berechtigung, diese Seite zu sehen')
                    return redirect('index_home')
            except:
                messages.error(request, 'Du hast keine Berechtigung, diese Seite zu sehen')
                return redirect('index_home')
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator