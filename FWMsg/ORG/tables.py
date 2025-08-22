import django_tables2 as tables
from django_tables2 import TemplateColumn
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from Global.models import (
    Einsatzland2, Einsatzstelle2, Attribute, Aufgabe2, 
    Notfallkontakt2, UserAufgaben, CustomUser, PersonCluster, 
    AufgabenCluster, KalenderEvent
)
from BW.models import ApplicationText, ApplicationQuestion, ApplicationFileQuestion


class BaseOrgTable(tables.Table):
    """Base table with common functionality for all org tables"""
    
    actions = TemplateColumn(
        template_name='components/table_actions.html',
        verbose_name=_('Aktionen'),
        orderable=False,
        attrs={'th': {'style': 'width: 120px;'}}
    )
    
    class Meta:
        template_name = 'django_tables2/bootstrap5.html'
        attrs = {
            'class': 'table table-hover align-middle',
            'thead': {'class': 'z-1'},
        }
        per_page = 25
    
    def __init__(self, *args, **kwargs):
        self.model_name = kwargs.pop('model_name', None)
        super().__init__(*args, **kwargs)
        
    def get_actions_context(self, record):
        """Get context for actions column"""
        model_name = self.model_name
        if not model_name:
            # Try to get model name from table's Meta if available
            meta = getattr(self, '_meta', None)
            model = getattr(meta, 'model', None) if meta else None
            model_meta = getattr(model, '_meta', None) if model else None
            model_name = getattr(model_meta, 'model_name', None)
            if model_name:
                model_name = model_name.lower()
            else:
                model_name = ''
        return {
            'record': record,
            'model_name': model_name,
            'edit_url': reverse('edit_object', args=[model_name, record.pk]),
            'delete_url': reverse('delete_object', args=[model_name, record.pk]),
            'pk': record.pk,
        }


class EinsatzlandTable(BaseOrgTable):
    name = tables.Column(verbose_name=_('Name'))
    notfallnummern = tables.Column(verbose_name=_('Notfallnummern'), orderable=False)
    arztpraxen = tables.Column(verbose_name=_('Arztpraxen'), orderable=False)
    apotheken = tables.Column(verbose_name=_('Apotheken'), orderable=False)
    informationen = tables.Column(verbose_name=_('Weitere Informationen'), orderable=False)
    
    class Meta(BaseOrgTable.Meta):
        model = Einsatzland2
        fields = ('name', 'code', 'notfallnummern', 'arztpraxen', 'apotheken', 'informationen', 'actions')


class EinsatzstelleTable(BaseOrgTable):
    name = tables.Column(verbose_name=_('Name'))
    land = tables.Column(verbose_name=_('Einsatzland'))
    partnerorganisation = tables.Column(verbose_name=_('Partnerorganisation'), orderable=False)
    arbeitsvorgesetzter = tables.Column(verbose_name=_('Arbeitsvorgesetzte:r'), orderable=False)
    mentor = tables.Column(verbose_name=_('Mentor:in'), orderable=False)
    botschaft = tables.Column(verbose_name=_('Botschaft'), orderable=False)
    konsulat = tables.Column(verbose_name=_('Konsulat'), orderable=False)
    informationen = tables.Column(verbose_name=_('Weitere Informationen'), orderable=False)
    
    class Meta(BaseOrgTable.Meta):
        model = Einsatzstelle2
        fields = ('name', 'land', 'partnerorganisation', 'arbeitsvorgesetzter', 'mentor', 'botschaft', 'konsulat', 'informationen', 'max_freiwillige', 'actions')


class AttributeTable(BaseOrgTable):
    name = tables.Column(verbose_name=_('Bezeichnung'))
    type_display = tables.Column(
        accessor='get_type_display',
        verbose_name=_('Datentyp'),
        orderable=False
    )
    person_cluster = tables.ManyToManyColumn(
        verbose_name=_('Für Benutzergruppen'),
        transform=lambda obj: obj.name if hasattr(obj, 'name') else str(obj),
        orderable=True
    )
    value_for_choices = tables.Column(verbose_name=_('Auswahloptionen'), orderable=False)
    
    class Meta(BaseOrgTable.Meta):
        model = Attribute
        fields = ('name', 'type_display', 'value_for_choices', 'person_cluster', 'actions')


class AufgabeTable(BaseOrgTable):
    name = tables.Column(verbose_name=_('Name'))
    beschreibung = tables.Column(
        verbose_name=_('Beschreibung'),
        attrs={'td': {'style': 'max-width: 300px; word-wrap: break-word;'}}
    )
    person_cluster = tables.ManyToManyColumn(
        verbose_name=_('Für Benutzergruppen'),
        transform=lambda obj: obj.name if hasattr(obj, 'name') else str(obj)
    )
    mitupload = tables.BooleanColumn(verbose_name=_('Datei-Upload notwendig'))
    
    class Meta(BaseOrgTable.Meta):
        model = Aufgabe2
        fields = ('name', 'beschreibung', 'mitupload', 'requires_submission', 'faellig_tag', 'faellig_monat', 'faellig_tage_nach_start', 'faellig_tage_vor_ende', 'wiederholung', 'wiederholung_interval_wochen', 'wiederholung_ende', 'repeat_push_days', 'person_cluster', 'actions')


class NotfallkontaktTable(BaseOrgTable):
    first_name = tables.Column(verbose_name=_('Vorname'))
    last_name = tables.Column(verbose_name=_('Nachname'))
    phone = tables.Column(
        verbose_name=_('Telefon'),
        attrs={'td': {'class': 'text-nowrap'}}
    )
    email = tables.EmailColumn(verbose_name=_('E-Mail'))
    
    def render_phone(self, value):
        if value:
            return format_html('<a href="tel:{}">{}</a>', value, value)
        return ''
    
    class Meta(BaseOrgTable.Meta):
        model = Notfallkontakt2
        fields = ('first_name', 'last_name', 'phone', 'email', 'user', 'actions')


class UserAufgabenTable(BaseOrgTable):
    user = tables.Column(verbose_name=_('Benutzer'))
    aufgabe = tables.Column(verbose_name=_('Aufgabe'))
    status = tables.Column(
        accessor='get_status_display',
        verbose_name=_('Status'),
        orderable=False
    )
    datum_erledigt = tables.DateColumn(
        verbose_name=_('Erledigt am'),
        format='d.m.Y'
    )
    
    class Meta(BaseOrgTable.Meta):
        model = UserAufgaben
        fields = ('user', 'aufgabe', 'status', 'datum_erledigt', 'actions')


class CustomUserTable(BaseOrgTable):
    # Add special action for sending registration mail
    actions = TemplateColumn(
        template_name='components/user_table_actions.html',
        verbose_name=_('Aktionen'),
        orderable=False,
        attrs={'th': {'style': 'width: 150px;'}},
    )
    
    class Meta(BaseOrgTable.Meta):
        model = CustomUser
        fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email', 'geburtsdatum', 'person_cluster', 'einmalpasswort', 'mail_notifications', 'actions')


class PersonClusterTable(BaseOrgTable):
    name = tables.Column(verbose_name=_('Name'))
    
    class Meta(BaseOrgTable.Meta):
        model = PersonCluster
        fields = ('name', 'view', 'aufgaben', 'calendar', 'dokumente', 'ampel', 'notfallkontakt', 'bilder', 'posts', 'actions')


class AufgabenClusterTable(BaseOrgTable):
    name = tables.Column(verbose_name=_('Name'))
    person_cluster = tables.ManyToManyColumn(
        verbose_name=_('Für Benutzergruppen'),
        transform=lambda obj: obj.name if hasattr(obj, 'name') else str(obj),
        orderable=True
    )
    
    class Meta(BaseOrgTable.Meta):
        model = AufgabenCluster
        fields = ('name', 'type', 'person_cluster', 'actions')


class KalenderEventTable(BaseOrgTable):
    title = tables.Column(verbose_name=_('Titel'))
    
    class Meta(BaseOrgTable.Meta):
        model = KalenderEvent
        fields = ('title', 'start', 'end', 'description', 'user', 'actions')


class ApplicationTextTable(BaseOrgTable):
    welcome = tables.Column(
        verbose_name=_('Begrüßung'),
        attrs={'td': {'style': 'max-width: 400px; word-wrap: break-word;'}}
    )
    footer = tables.Column(
        verbose_name=_('Fußzeile'),
        attrs={'td': {'style': 'max-width: 400px; word-wrap: break-word;'}}
    )
    deadline = tables.DateColumn(
        verbose_name=_('Abgabefrist'),
        format='d.m.Y'
    )
    
    class Meta(BaseOrgTable.Meta):
        model = ApplicationText
        fields = ('welcome', 'footer', 'deadline', 'welcome_account_create', 'actions')


class ApplicationQuestionTable(BaseOrgTable):
    question = tables.Column(
        verbose_name=_('Frage'),
        attrs={'td': {'style': 'max-width: 400px; word-wrap: break-word;'}}
    )
    order = tables.Column(verbose_name=_('Position'))
    max_length = tables.Column(verbose_name=_('Max. Länge'))

    class Meta(BaseOrgTable.Meta):
        model = ApplicationQuestion
        fields = ('order','question', 'description', 'choices', 'max_length', 'actions')


class ApplicationFileQuestionTable(BaseOrgTable):
    name = tables.Column(
        verbose_name=_('Name'),
        attrs={'td': {'style': 'max-width: 400px; word-wrap: break-word;'}}
    )
    description = tables.Column(
        verbose_name=_('Beschreibung'),
        attrs={'td': {'style': 'max-width: 400px; word-wrap: break-word;'}}
    )
    order = tables.Column(verbose_name=_('Position'))
    
    class Meta(BaseOrgTable.Meta):
        model = ApplicationFileQuestion
        fields = ('order', 'name', 'description', 'actions')


# Mapping of model names to table classes
MODEL_TABLE_MAPPING = {
    'einsatzland': EinsatzlandTable,
    'einsatzstelle': EinsatzstelleTable,
    'attribute': AttributeTable,
    'aufgabe': AufgabeTable,
    'notfallkontakt': NotfallkontaktTable,
    'useraufgaben': UserAufgabenTable,
    'user': CustomUserTable,
    'personcluster': PersonClusterTable,
    'aufg-filter': AufgabenClusterTable,
    'kalender': KalenderEventTable,
    'bewerbung-text': ApplicationTextTable,
    'bewerbung-frage': ApplicationQuestionTable,
    'bewerbung-datei': ApplicationFileQuestionTable,
}
