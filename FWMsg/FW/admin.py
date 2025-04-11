from django.contrib import admin
from .models import Freiwilliger
from simple_history.admin import SimpleHistoryAdmin


# Register your models here.
@admin.register(Freiwilliger)
class FreiwilligerAdmin(SimpleHistoryAdmin):
    search_fields = ['user__first_name', 'user__last_name']
    list_display = ['user__first_name', 'user__last_name', 'einsatzland2', 'einsatzstelle2', 'start_geplant', 'start_real', 'ende_geplant', 'ende_real']