from django.contrib import admin
from .models import ApplicationQuestion, ApplicationAnswer, ApplicationText, Bewerber

# Register your models here.
admin.site.register(ApplicationQuestion)
admin.site.register(ApplicationAnswer)
admin.site.register(ApplicationText)
admin.site.register(Bewerber)
