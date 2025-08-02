from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class OnlineStatusMiddleware(MiddlewareMixin):
    """
    Middleware to track user online status by updating last_seen timestamp
    """
    
    def process_request(self, request):
        # Only track authenticated users
        if request.user.is_authenticated:
            try:
                # Update last seen timestamp
                if hasattr(request.user, 'customuser'):
                    request.user.customuser.update_last_seen()
            except Exception:
                # Silently fail to avoid breaking the request
                pass
        
        return None


class OfflineStatusMiddleware(MiddlewareMixin):
    """
    Middleware to mark users as offline after periods of inactivity
    This runs periodically to clean up old online statuses
    """
    
    def process_request(self, request):
        # Only run this cleanup occasionally to avoid performance issues
        import random
        if random.randint(1, 100) == 1:  # Run on ~1% of requests
            try:
                from .models import CustomUser
                from datetime import timedelta
                
                # Mark users as offline if they haven't been seen for 5+ minutes
                offline_threshold = timezone.now() - timedelta(minutes=5)
                CustomUser.objects.filter(
                    last_seen__lt=offline_threshold,
                    is_online=True
                ).update(is_online=False)
                
            except Exception:
                # Silently fail to avoid breaking the request
                pass
        
        return None 