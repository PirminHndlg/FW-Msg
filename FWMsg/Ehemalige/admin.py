from django.contrib import admin
from .models import Ehemalige
from simple_history.admin import SimpleHistoryAdmin

# Register your models here.
@admin.register(Ehemalige)
class EhemaligeAdmin(SimpleHistoryAdmin):
    search_fields = ['user__first_name', 'user__last_name']
    filter_horizontal = ['land']