from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import ApplicationQuestion, ApplicationAnswer, ApplicationText, Bewerber, ApplicationFileQuestion, ApplicationAnswerFile

# Register your models here.
admin.site.register(ApplicationQuestion)
admin.site.register(ApplicationAnswer)
admin.site.register(ApplicationText)
admin.site.register(ApplicationFileQuestion)
admin.site.register(ApplicationAnswerFile)


class HasSeminarFilter(admin.SimpleListFilter):
    title = 'Hat Seminar'
    parameter_name = 'has_seminar'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Ja'),
            ('no', 'Nein'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            # Filter for bewerber who have a seminar
            return queryset.filter(seminar_bewerber__isnull=False).distinct()
        elif self.value() == 'no':
            # Filter for bewerber who don't have a seminar
            return queryset.filter(seminar_bewerber__isnull=True)
        return queryset


@admin.register(Bewerber)
class BewerberAdmin(SimpleHistoryAdmin):
    search_fields = ['user__first_name', 'user__last_name']
    list_display = ['user__first_name', 'user__last_name', 'first_wish_einsatzland', 'second_wish_einsatzland', 'third_wish_einsatzland', 'no_wish_einsatzland', 'zuteilung']
    list_filter = [HasSeminarFilter]
    