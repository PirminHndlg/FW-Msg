import django_tables2 as tables
from django_tables2 import TemplateColumn
from django.urls import reverse
from django.utils.html import format_html
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from FW.models import Freiwilliger
from Global.models import (
    BewerberKommentar, Einsatzland2, Einsatzstelle2, Attribute, Aufgabe2,
    Notfallkontakt2, UserAufgaben, CustomUser, PersonCluster,
    AufgabenCluster, KalenderEvent, UserAttribute
)
from django.db.models import OuterRef, Subquery
from BW.models import ApplicationText, ApplicationQuestion, ApplicationFileQuestion, Bewerber


class BaseOrgTable(tables.Table):
    """Base table with common functionality for all org tables"""
    
    actions = TemplateColumn(
        template_name='components/table_actions.html',
        verbose_name=_('Aktionen'),
        orderable=False,
        attrs={
            'th': {
                'style': 'width: 120px;',
            }, 
            'td': {
                'style': 'position: sticky; right: 0; background-color: white; z-index: 1;',
            }
        }
    )
    
    class Meta:
        template_name = 'django_tables2/bootstrap5.html'
        attrs = {
            'class': 'table table-hover align-middle',
            'thead': {
                'class': 'z-1',
                'style': 'position: sticky; top: 0; background-color: white;'
            },
        }
        per_page = 100
    
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
            'record': record['freiwilliger'],
            'model_name': model_name,
            'edit_url': reverse('edit_object', args=[model_name, record.pk]),
            'delete_url': reverse('delete_object', args=[model_name, record.pk]),
            'pk': record.pk,
        }
        
    def render_user__username(self, value, record):
        try:
            user_id = record.user.id
        except Exception:
            return value
        url = reverse('profil', args=[user_id])
        return format_html('<a href="{}"><i class="bi bi-person-fill me-1"></i>{}</a>', url, value)


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
    
    def render_actions(self, value, record):
        context = {
            'model_name': 'einsatzstelle',
            'action_url': reverse('einsatzstellen_notiz', args=[record.pk]),
            'color': 'primary',
            'icon': 'bi bi-journal-text',
            'title': _('Notizen'),
            'record': record,
            'button_text': '',
        }
        html = render_to_string('components/additional_table_actions.html', context)
        return mark_safe(html)

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
        fields = ('name', 'type_display', 'value_for_choices', 'person_cluster', 'visible_in_profile', 'actions')


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
    def render_actions(self, value, record):
        context = {
            'model_name': 'user',
            'action_url': '',
            'onclick': f'sendRegistrationMail({record.pk}, this)',
            'color': 'info',
            'icon': 'bi bi-envelope',
            'title': _('Registrierungsmail senden'),
            'record': record,
            'button_text': '',
        }
        html = render_to_string('components/additional_table_actions.html', context)
        return mark_safe(html)
    
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
        
class MaterializeCssCheckboxColumn(tables.CheckBoxColumn):
    def render(self, value, bound_column, record):
        default = {"type": "checkbox", "name": bound_column.name, "value": value, "class": "row-checkbox"}
        if self.is_checked(value, record):
            default.update({"checked": "checked"})
            
        general = self.attrs.get("input")
        specific = self.attrs.get("td__input")
        attrs = tables.utils.AttributeDict(default, **(specific or general or {}))
        return mark_safe("<p><label><input %s/><span></span></label></p>" % attrs.as_html())
    
    @property
    def header(self):
        header_checkbox = '<label><input type="checkbox" id="select-all-checkbox" class="select-all-checkbox"/><span></span></label>'
        script = """
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            const selectAllCheckbox = document.getElementById('select-all-checkbox');
            if (selectAllCheckbox) {
                selectAllCheckbox.addEventListener('change', function() {
                    const checkboxes = document.querySelectorAll('.row-checkbox');
                    checkboxes.forEach(checkbox => {
                        checkbox.checked = this.checked;
                    });
                });
            }
        });
        </script>
        """
        return mark_safe(header_checkbox + script)
        

def _create_dynamic_table_class(
    person_cluster, 
    org, 
    model_class, 
    model_name, 
    base_columns, 
    column_sequence, 
    render_methods, 
    actions_renderer
):
    """
    Generic function to create a dynamic table with attribute columns.
    
    Args:
        person_cluster: The person cluster to filter by
        org: The organization
        model_class: The model class (Freiwilliger, Bewerber, Team)
        model_name: String name for the model ('freiwilliger', 'bewerber', 'team')
        base_columns: Dict of base table columns
        column_sequence: List of column names in order
        render_methods: Dict of custom render methods
        actions_renderer: Function to render actions column
    
    Returns:
        (table_class, data_list)
    """
    # Fetch objects and attributes
    objects = model_class.objects.filter(
        org=org, 
        user__customuser__person_cluster=person_cluster
    ).select_related('user', 'user__customuser')
    
    attributes = Attribute.objects.filter(org=org, person_cluster=person_cluster)
    
    # Build data structure: list of dicts with object and attrs dict
    data = []
    for obj in objects:
        obj_data = {model_name: obj, 'attrs': {}}
        
        # Fetch all user attributes
        user_attributes = UserAttribute.objects.filter(
            org=org, user=obj.user, attribute__in=attributes
        ).select_related('attribute')
        
        # Populate attrs dict
        for user_attr in user_attributes:
            obj_data['attrs'][user_attr.attribute.name] = user_attr.value or ''
        
        # Ensure all attributes have keys (even if empty)
        for attribute in attributes:
            obj_data['attrs'].setdefault(attribute.name, '')
        
        data.append(obj_data)
    
    # Helper to create attribute column with proper closure
    def make_attribute_column(attr_name):
        class AttributeColumn(tables.Column):
            def __init__(self, *args, **kwargs):
                kwargs['accessor'] = f'attrs__{attr_name}'
                kwargs['orderable'] = True
                super().__init__(*args, **kwargs)
                
            def render(self, value, record, bound_column):
                if isinstance(record, dict):
                    val = record.get('attrs', {}).get(attr_name, '')
                    return val if val else '—'
                return '—'
        return AttributeColumn
    
    # Actions column with custom rendering
    class ActionsColumn(tables.TemplateColumn):
        def render(self, record, table, value, bound_column, **kwargs):
            return actions_renderer(record, org)
    
    # Build table attributes dictionary
    table_attrs = base_columns.copy()
    table_attrs.update(render_methods)
    table_attrs['Meta'] = type('Meta', (), {
        'template_name': 'django_tables2/bootstrap5.html',
        'attrs': {'class': 'table table-hover align-middle', 'thead': {'class': 'z-1', 'style': 'position: sticky; top: 0; background-color: white;'}},
        'per_page': 100
    })
    
    # Add attribute columns dynamically
    final_column_sequence = column_sequence.copy()
    for attribute in attributes:
        column_name = f'attr_{attribute.id}'
        AttributeColumnClass = make_attribute_column(attribute.name)
        table_attrs[column_name] = AttributeColumnClass(verbose_name=attribute.name)
        final_column_sequence.append(column_name)
        
    # Add actions column
    table_attrs['actions'] = ActionsColumn(
        template_name='components/additional_table_actions.html',
        verbose_name=_('Aktionen'),
        orderable=False,
        attrs={
            'th': {'style': 'width: 120px;'},
            'td': {'style': 'position: sticky; right: 0; background-color: white; z-index: 1;'}
        }
    )
    final_column_sequence.append('actions')
    table_attrs['Meta'].sequence = final_column_sequence
    
    # Create and return the table class
    table_name = f'Dynamic{model_class.__name__}Table'
    return type(table_name, (tables.Table,), table_attrs), data


def get_freiwilliger_table_class(person_cluster, org):
    """
    Create a dynamic FreiwilligerTable with attribute columns.
    Returns: (table_class, data_list)
    """
    # Define render methods
    def render_user(self, value, record):
        freiwilliger = record['freiwilliger']
        return format_html(
            '<a href="{}"><i class="bi bi-person-fill me-1"></i>{}</a>', 
            reverse('profil', args=[freiwilliger.user.id]), 
            f"{freiwilliger.user.first_name} {freiwilliger.user.last_name}"
        )
    
    def actions_renderer(record, org):
        freiwilliger = record['freiwilliger']
        context = {
            'record': freiwilliger,
            'model_name': 'freiwilliger',
            'action_url': '',
            'color': 'primary',
            'icon': '',
            'title': '',
            'button_text': '',
            'hide_button': True,
        }
        return render_to_string('components/additional_table_actions.html', context)
    
    # Define base columns
    base_columns = {
        'user': tables.Column(
            verbose_name=_('Benutzer'),
            accessor='freiwilliger.user',
            order_by='freiwilliger.user__first_name'
        ),
        'einsatzland2': tables.Column(
            verbose_name=_('Einsatzland'),
            accessor='freiwilliger.einsatzland2',
            order_by='freiwilliger.einsatzland2__name'
        ),
        'einsatzstelle2': tables.Column(
            verbose_name=_('Einsatzstelle'),
            accessor='freiwilliger.einsatzstelle2',
            order_by='freiwilliger.einsatzstelle2__name'
        ),
        'start_geplant': tables.DateColumn(
            verbose_name=_('Start geplant'),
            accessor='freiwilliger.start_geplant',
            format='d.m.Y'
        ),
        'start_real': tables.DateColumn(
            verbose_name=_('Start real'),
            accessor='freiwilliger.start_real',
            format='d.m.Y'
        ),
        'ende_geplant': tables.DateColumn(
            verbose_name=_('Ende geplant'),
            accessor='freiwilliger.ende_geplant',
            format='d.m.Y'
        ),
        'ende_real': tables.DateColumn(
            verbose_name=_('Ende real'),
            accessor='freiwilliger.ende_real',
            format='d.m.Y'
        ),
    }
    
    column_sequence = [
        'user', 'einsatzland2', 'einsatzstelle2', 
        'start_geplant', 'start_real', 'ende_geplant', 'ende_real'
    ]
    
    render_methods = {'render_user': render_user}
    
    return _create_dynamic_table_class(
        person_cluster, org, Freiwilliger, 'freiwilliger',
        base_columns, column_sequence, render_methods, actions_renderer
    )



def get_bewerber_table_class(person_cluster, org):
    """
    Create a dynamic BewerberTable with attribute columns.
    Returns: (table_class, data_list)
    """
    # Define render methods
    def render_user(self, value, record):
        bewerber = record['bewerber']
        return format_html(
            '<a href="{}" title="Zum Profil"><i class="bi bi-person-fill me-1"></i>{}</a> '
            '<a href="mailto:{}" data-bs-toggle="tooltip" data-bs-placement="top" data-bs-title="Email senden" class="ms-1">'
            '<i class="bi bi-envelope-arrow-up"></i></a>',
            reverse('profil', args=[bewerber.user.id]),
            f"{bewerber.user.first_name} {bewerber.user.last_name}",
            bewerber.user.email,
        )
    
    def render_application_pdf(self, value, record):
        bewerber = record['bewerber']
        if bewerber.application_pdf:
            return format_html(
                '<a href="{}" target="_blank"><i class="bi bi-file-earmark-pdf"></i> {}</a>', 
                reverse('application_answer_download', args=[bewerber.id]), 
                _('PDF herunterladen')
            )
        return '—'
    
    def render_interview_persons(self, value, record):
        bewerber = record['bewerber']
        if bewerber.interview_persons.all():
            return ', '.join([f"{interview_person}" for interview_person in bewerber.interview_persons.all()])
        return '—'
    
    def render_has_seminar(self, value, record):
        bewerber = record['bewerber']
        if bewerber.has_seminar():
            return format_html('<i class="bi bi-check-circle-fill text-success"></i>')
        else:
            return format_html('<i class="bi bi-x-circle-fill text-danger"></i>')
    
    def actions_renderer(record, org):
        bewerber = record['bewerber']
        bewerber_kommentare_count = BewerberKommentar.objects.filter(bewerber=bewerber, org=org).count()
        context = {
            'record': bewerber,
            'model_name': 'bewerber',
            'action_url': '',
            'onclick': f"open_bewerber_kommentar_modal(this, {bewerber.pk})",
            'color': 'primary',
            'icon': 'bi bi-chat-left-text',
            'title': 'Kommentare anzeigen',
            'button_text': f'{bewerber_kommentare_count}',
            'hide_button': False,
        }
        return render_to_string('components/additional_table_actions.html', context)
    
    # Define base columns
    base_columns = {
        'checkbox': MaterializeCssCheckboxColumn(
            verbose_name=_('Ausgewählt'),
            accessor='bewerber.id',
            orderable=False
        ),
        'user': tables.Column(
            verbose_name=_('Benutzer'),
            accessor='bewerber.user',
            order_by='bewerber.user__first_name'
        ),
        'application_pdf': tables.Column(
            verbose_name=_('PDF der Bewerbung'),
            accessor='bewerber.application_pdf',
            orderable=False
        ),
        'interview_persons': tables.Column(
            verbose_name=_('Interviewpersonen/Ehemalige'),
            accessor='bewerber.interview_persons',
            orderable=False
        ),
        'has_seminar': tables.Column(
            verbose_name=_('Seminar'),
            accessor='bewerber.has_seminar',
            orderable=True
        ),
    }
    
    column_sequence = ['checkbox', 'user', 'application_pdf', 'has_seminar', 'interview_persons']
    
    render_methods = {
        'render_user': render_user,
        'render_application_pdf': render_application_pdf,
        'render_interview_persons': render_interview_persons,
        'render_has_seminar': render_has_seminar
    }   
    
    return _create_dynamic_table_class(
        person_cluster, org, Bewerber, 'bewerber',
        base_columns, column_sequence, render_methods, actions_renderer
    )


def get_team_table_class(person_cluster, org):
    """
    Create a dynamic TeamTable with attribute columns.
    Returns: (table_class, data_list)
    """
    from TEAM.models import Team
    
    # Define render methods
    def render_user(self, value, record):
        team = record['team']
        return format_html(
            '<a href="{}"><i class="bi bi-person-fill me-1"></i>{}</a>', 
            reverse('profil', args=[team.user.id]), 
            f"{team.user.first_name} {team.user.last_name}"
        )
    
    def render_land(self, value, record):
        team = record['team']
        lands = team.land.all()
        if lands:
            return ', '.join([land.name for land in lands])
        return '—'
    
    def actions_renderer(record, org):
        team = record['team']
        context = {
            'record': team,
            'model_name': 'team',
            'action_url': '',
            'color': 'primary',
            'icon': '',
            'title': '',
            'button_text': '',
            'hide_button': True,
        }
        return render_to_string('components/additional_table_actions.html', context)
    
    # Define base columns
    base_columns = {
        'user': tables.Column(
            verbose_name=_('Benutzer'),
            accessor='team.user',
            order_by='team.user__first_name'
        ),
        'land': tables.Column(
            verbose_name=_('Länderzuständigkeit'),
            accessor='team.land',
            orderable=False
        ),
    }
    
    column_sequence = ['user', 'land']
    
    render_methods = {
        'render_user': render_user,
        'render_land': render_land
    }
    
    return _create_dynamic_table_class(
        person_cluster, org, Team, 'team',
        base_columns, column_sequence, render_methods, actions_renderer
    )
    
def get_ehemalige_table_class(person_cluster, org):
    """
    Create a dynamic EhemaligeTable with attribute columns.
    Returns: (table_class, data_list)
    """
    from Ehemalige.models import Ehemalige
    
    # Define render methods
    def render_user(self, value, record):
        ehemalige = record['ehemalige']
        return format_html(
            '<a href="{}"><i class="bi bi-person-fill me-1"></i>{}</a>', 
            reverse('profil', args=[ehemalige.user.id]), 
            f"{ehemalige.user.first_name} {ehemalige.user.last_name}"
        )
    
    def render_land(self, value, record):
        ehemalige = record['ehemalige']
        lands = ehemalige.land.all()
        if lands:
            return ', '.join([land.name for land in lands])
        return '—'
    
    def actions_renderer(record, org):
        ehemalige = record['ehemalige']
        context = {
            'record': ehemalige,
            'model_name': 'ehemalige',
            'action_url': '',
            'color': 'primary',
            'icon': '',
            'title': '',
            'button_text': '',
            'hide_button': True,
        }
        return render_to_string('components/additional_table_actions.html', context)
    
    # Define base columns
    base_columns = {
        'user': tables.Column(
            verbose_name=_('Benutzer'),
            accessor='ehemalige.user',
            order_by='ehemalige.user__first_name'
        ),
        'land': tables.Column(
            verbose_name=_('Länderzuständigkeit'),
            accessor='ehemalige.land',
            orderable=False
        ),
    }
    
    column_sequence = ['user', 'land']
    
    render_methods = {
        'render_user': render_user,
        'render_land': render_land
    }
    
    return _create_dynamic_table_class(
        person_cluster, org, Ehemalige, 'ehemalige',
        base_columns, column_sequence, render_methods, actions_renderer
    )
    
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
