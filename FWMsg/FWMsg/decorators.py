from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

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
        @user_passes_test(lambda u: u.is_authenticated and hasattr(u, 'customuser') and (u.customuser.role in roles or roles == ''))
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.role in roles and roles != '':
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator