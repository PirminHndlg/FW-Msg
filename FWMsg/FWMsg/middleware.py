from threading import local

_thread_locals = local()

class RequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Store request in thread local storage
        _thread_locals.request = request
        response = self.get_response(request)
        # Clean up
        del _thread_locals.request
        return response

def get_current_request():
    """Returns the current request from thread local storage"""
    return getattr(_thread_locals, 'request', None) 