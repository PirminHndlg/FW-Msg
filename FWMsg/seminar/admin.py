from django.contrib.admin import SimpleListFilter
from .models import Fragekategorie, Frage, Bewertung, Kommentar, DeadlineDateTime, Einheit
from django.contrib import admin


class FirstWishFilter(SimpleListFilter):
    title = 'Erstwunsch abgegeben'  # Displayed in the admin filter
    parameter_name = 'first_wish_filter'  # Query parameter name

    def lookups(self, request, model_admin):
        """
        Options displayed in the filter dropdown.
        """
        return [
            ('none', 'Nein'),
            ('any', 'Ja'),
        ]

    def queryset(self, request, queryset):
        """
        Filters the queryset based on the selected filter value.
        """
        if self.value() == 'none':
            return queryset.filter(first_wish__isnull=True)
        elif self.value() == 'any':
            return queryset.filter(first_wish__isnull=False)
        return queryset


class ZuteilungFilter(SimpleListFilter):
    title = 'Zuteilung'  # Displayed in the admin filter
    parameter_name = 'zuteilung_filter'  # Query parameter name

    def lookups(self, request, model_admin):
        return [
            ('none', 'Nein'),
            ('any', 'Ja'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'none':
            return queryset.filter(zuteilung__isnull=True)
        elif self.value() == 'any':
            return queryset.filter(zuteilung__isnull=False)
        return queryset


class BewertungFilter(SimpleListFilter):
    title = 'Bewertung vergeben'  # Displayed in the admin filter
    parameter_name = 'bewertung_filter'  # Query parameter name

    def lookups(self, request, model_admin):
        return [
            ('none', 'Nein'),
            ('any', 'Ja'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'none':
            return queryset.filter(endbewertung__isnull=True)
        elif self.value() == 'any':
            return queryset.filter(endbewertung__isnull=False)
        return queryset


class GegenstandFilter(SimpleListFilter):
    title = 'Gegenstand'  # Displayed in the admin filter
    parameter_name = 'gegenstand_filter'  # Query parameter name

    def lookups(self, request, model_admin):
        return [
            ('none', 'Nein'),
            ('any', 'Ja'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'none':
            return queryset.filter(gegenstand__isnull=True)
        elif self.value() == 'any':
            return queryset.filter(gegenstand__isnull=False)
        return queryset



@admin.register(Fragekategorie)
class FragekategorieAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Frage)
class FrageAdmin(admin.ModelAdmin):
    search_fields = ['text', 'kategorie']
    list_filter = ['kategorie']
    actions = ['change_min_to_one', 'change_max_to_five']

    def change_min_to_one(self, request, queryset):
        queryset.update(min=1)
        self.message_user(request, "Minimum wurde auf 1 gesetzt")

    def change_max_to_five(self, request, queryset):
        queryset.update(max=5)


@admin.register(Einheit)
class EinheitAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(Bewertung)
class BewertungAdmin(admin.ModelAdmin):
    list_display = ('bewerter', 'bewerber', 'bewertung', 'frage', 'einheit')
    search_fields = ['bewerter', 'bewerber', 'frage', 'einheit']
    list_filter = ['bewerter', 'bewerber', 'frage', 'einheit']
    actions = ['switchBewertung']

    def switchBewertung(self, request, queryset):
        for obj in queryset:
            bewertung = obj.bewertung
            match bewertung:
                case 1:
                    obj.bewertung = 5
                case 2:
                    obj.bewertung = 4
                case 3:
                    obj.bewertung = 3
                case 4:
                    obj.bewertung = 2
                case 5:
                    obj.bewertung = 1
            obj.save()
        self.message_user(request, "Bewertung wurde geändert")


@admin.register(Kommentar)
class KommentarAdmin(admin.ModelAdmin):
    search_fields = ['bewerter', 'bewerber', 'einheit']
    list_filter = ['bewerter', 'bewerber', 'einheit']


@admin.register(DeadlineDateTime)
class DeadlineDateTimeAdmin(admin.ModelAdmin):
    search_fields = ['deadline']
