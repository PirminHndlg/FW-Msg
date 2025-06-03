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
    def decorator(view_func):
        # @user_passes_test(lambda u: u.is_authenticated and hasattr(u, 'customuser'))
        def _wrapped_view(request, *args, **kwargs):
            try:
                if not request.user.customuser.person_cluster.view in roles and roles != '' and not request.user.is_superuser:
                    raise PermissionDenied
            except:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
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