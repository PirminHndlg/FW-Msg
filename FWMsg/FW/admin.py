from django.contrib import admin
from .models import Freiwilliger, Entsendeform, Einsatzland, Einsatzstelle, Notfallkontakt, Post, Aufgabe, \
    Aufgabenprofil, FreiwilligerAufgabenprofil, Ampel, FreiwilligerAufgaben, Jahrgang, \
    CustomUser, Bilder, BilderGallery


# Register your models here.
@admin.register(Freiwilliger)
class FreiwilligerAdmin(admin.ModelAdmin):
    search_fields = ['first_name', 'last_name']


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


@admin.register(Jahrgang)
class JahrgangAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    search_fields = ['user']


@admin.register(Bilder)
class BilderAdmin(admin.ModelAdmin):
    search_fields = ['name']

@admin.register(BilderGallery)
class BilderGalleryAdmin(admin.ModelAdmin):
    search_fields = ['bilder']