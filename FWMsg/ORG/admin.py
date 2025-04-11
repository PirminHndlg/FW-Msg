from django.contrib import admin
from .models import Ordner, Dokument, Referenten, JahrgangTyp, DokumentColor
from simple_history.admin import SimpleHistoryAdmin

# Register your models here.

@admin.register(Ordner)
class OrdnerAdmin(SimpleHistoryAdmin):
    search_fields = ['ordner_name']
    actions = ['all_to_incoming', 'all_to_outgoing', 'move_to_new']

    def all_to_incoming(self, request, queryset):
        for ordner in queryset:
            ordner.typ = JahrgangTyp.objects.get(name='Incoming')
            ordner.save()
            
    def all_to_outgoing(self, request, queryset):
        for ordner in queryset:
            ordner.typ = JahrgangTyp.objects.get(name='Outgoing')
            ordner.save()

    def move_to_new(self, request, queryset):
        from Global.models import Ordner2, PersonCluster

        person_cluster = PersonCluster.objects.get(name='Freiwilliger')

        for ordner in queryset:
            ordner2, created = Ordner2.objects.get_or_create(
                org=ordner.org,
                ordner_name=ordner.ordner_name,
            )
            if created:
                ordner2.typ = person_cluster
                ordner2.save()
                

@admin.register(Dokument)
class DokumentAdmin(SimpleHistoryAdmin):
    search_fields = ['ordner', 'dokument', 'beschreibung']
    actions = ['move_to_new', 'move_to_new_2']


    def move_to_new(self, request, queryset):

        for dokument in queryset:
            import os
            from Global.models import Dokument2, Ordner2

            if dokument.dokument and os.path.exists(dokument.dokument.path):
                pass
                dokument2, created = Dokument2.objects.get_or_create(
                    org=dokument.org,
                    ordner=Ordner2.objects.get(ordner_name=dokument.ordner.ordner_name),
                    dokument=dokument.dokument,
                    link=dokument.link,
                    titel=(dokument.titel or dokument.dokument.name)[:100],
                    beschreibung=dokument.beschreibung,
                    date_created=dokument.date_created,
                    date_modified=dokument.date_modified,
                    preview_image=dokument.preview_image,
                )
                dokument2.save()
            elif dokument.dokument:
                doc_pdf = dokument.dokument.path.replace('.doc', '.pdf')
                docx_pdf = dokument.dokument.path.replace('.docx', '.pdf')
                xls_pdf = dokument.dokument.path.replace('.xls', '.pdf')
                xlsx_pdf = dokument.dokument.path.replace('.xlsx', '.pdf')
                odt_pdf = dokument.dokument.path.replace('.odt', '.pdf')
                # Check for PDF versions of various document types
                pdf_paths = {
                    'doc': doc_pdf,
                    'docx': docx_pdf, 
                    'xls': xls_pdf,
                    'xlsx': xlsx_pdf,
                    'odt': odt_pdf
                }
                
                # Find first existing PDF path
                path = None
                for pdf_path in pdf_paths.values():
                    if pdf_path and os.path.exists(pdf_path):
                        path = pdf_path
                        break
                        
                if path:
                    from django.core.files import File
                    with open(path, 'rb') as f:
                        dokument2, created = Dokument2.objects.get_or_create(
                            org=dokument.org,
                            ordner=Ordner2.objects.get(ordner_name=dokument.ordner.ordner_name),
                            link=dokument.link,
                            titel=(dokument.titel or dokument.dokument.name)[:100],
                            beschreibung=dokument.beschreibung,
                            date_created=dokument.date_created,
                            date_modified=dokument.date_modified,
                            preview_image=dokument.preview_image,
                        )
                        dokument2.dokument.save(os.path.basename(path), File(f))
                        dokument2.save()
                

    def move_to_new_2(self, request, queryset):
        from Global.models import Dokument2, Ordner2

        for dokument in queryset:
            if not dokument.dokument and (dokument.link or dokument.titel or dokument.beschreibung):
                dokument2, created = Dokument2.objects.get_or_create(
                    org=dokument.org,
                    ordner=Ordner2.objects.get(ordner_name=dokument.ordner.ordner_name),
                    dokument=dokument.dokument,
                    link=dokument.link,
                    titel=(dokument.titel or dokument.dokument.name)[:100],
                    beschreibung=dokument.beschreibung,
                    date_created=dokument.date_created,
                    date_modified=dokument.date_modified,
                    preview_image=dokument.preview_image,
                )
                dokument2.save()
        

@admin.register(DokumentColor)
class DokumentColorAdmin(SimpleHistoryAdmin):
    search_fields = ['name']

@admin.register(Referenten)
class ReferentenAdmin(SimpleHistoryAdmin):
    search_fields = ['first_name', 'last_name', 'email', 'phone']
    actions = ['anonymize_user', 'set_name', 'move_to_new']

    def anonymize_user(self, request, queryset):
        for referent in queryset:
            referent.email = f'{referent.first_name[0]}.{referent.last_name[0]}@p0k.de'
            referent.user.email = f'{referent.first_name[0]}.{referent.last_name[0]}@p0k.de'
            referent.phone_work = None
            referent.phone_mobil = None
            referent.save()
            referent.user.save()
        
    def set_name(self, request, queryset):
        for referent in queryset:
            referent.user.first_name = referent.first_name
            referent.user.last_name = referent.last_name
            referent.user.save()

    def move_to_new(self, request, queryset):
        from Global.models import Einsatzland2, PersonCluster
        from TEAM.models import Team

        person_cluster = PersonCluster.objects.get(name='Team')

        for referent in queryset:
            team, created = Team.objects.get_or_create(
                org=referent.org,
                user=referent.user,
            )
            print(created)
            if created:
                team.user.customuser.person_cluster = person_cluster
                team.user.customuser.save()
                land = referent.land.all()
                for l in land:
                    team.land.add(Einsatzland2.objects.get(name=l.name))
            team.save()

@admin.register(JahrgangTyp)
class JahrgangTypAdmin(SimpleHistoryAdmin):
    search_fields = ['name']