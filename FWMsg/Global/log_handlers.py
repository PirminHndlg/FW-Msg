import logging
import traceback
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from .models import Log

class DatabaseLogHandler(logging.Handler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def emit(self, record):
        try:
            # Get the request from the record if available
            request = getattr(record, 'request', None)
            user = getattr(request, 'user', None) if request else None

            # If user is not authenticated, set to None
            if user and not user.is_authenticated:
                user = None

            # Create the log entry
            Log.objects.create(
                level=record.levelname,
                message=self.format(record),
                source=record.name,
                user=user,
                trace=traceback.format_exc() if record.exc_info else None
            )
        except Exception:
            # If there's an error logging to the database, fallback to console
            print(f"Error saving log to database: {traceback.format_exc()}") 