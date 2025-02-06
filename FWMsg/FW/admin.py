from django.contrib import admin
from .models import Freiwilliger, Entsendeform, Einsatzland, Einsatzstelle, Notfallkontakt, Post, Aufgabe, \
    Aufgabenprofil, FreiwilligerAufgabenprofil, Ampel, FreiwilligerAufgaben, Jahrgang, \
    CustomUser, Bilder, BilderGallery


# Register your models here.
@admin.register(Freiwilliger)
class FreiwilligerAdmin(admin.ModelAdmin):
    search_fields = ['first_name', 'last_name']
    actions = ['send_register_email', 'give_user_name']

    def send_register_email(self, request, queryset):
        for freiwilliger in queryset:
            from FW.tasks import send_register_email_task
            send_register_email_task.delay(freiwilliger.id)

    def give_user_name(self, request, queryset):
        for freiwilliger in queryset:
            freiwilliger.user.first_name = freiwilliger.first_name
            freiwilliger.user.last_name = freiwilliger.last_name
            freiwilliger.user.save()


@admin.register(Entsendeform)
class EntsendeformAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Einsatzland)
class EinsatzlandAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Einsatzstelle)
class EinsatzstelleAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Notfallkontakt)
class NotfallkontaktAdmin(admin.ModelAdmin):
    search_fields = ['first_name', 'last_name']


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    search_fields = ['title']


@admin.register(Aufgabe)
class AufgabeAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Aufgabenprofil)
class AufgabenprofilAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(FreiwilligerAufgabenprofil)
class FreiwilligerAufgabenprofilAdmin(admin.ModelAdmin):
    search_fields = ['freiwilliger', 'aufgabenprofil']


@admin.register(Ampel)
class AmpelAdmin(admin.ModelAdmin):
    search_fields = ['status']


@admin.register(FreiwilligerAufgaben)
class FreiwilligerAufgabenAdmin(admin.ModelAdmin):
    search_fields = ['freiwilliger', 'aufgabe']
    actions = ['send_aufgaben_email']

    def send_aufgaben_email(self, request, queryset):
        for freiwilliger_aufgabe in queryset:
            freiwilliger_aufgabe.send_reminder_email()
        msg = f"Erinnerungen wurden gesendet"
        self.message_user(request, msg)


@admin.register(Jahrgang)
class JahrgangAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Bilder)
class BilderAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_display = ('titel', 'user', 'date_created')

@admin.register(BilderGallery)
class BilderGalleryAdmin(admin.ModelAdmin):
    search_fields = ['bilder']