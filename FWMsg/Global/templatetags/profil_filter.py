from django import template

from FW.models import Freiwilliger
from TEAM.models import Team
from Ehemalige.models import Ehemalige

register = template.Library()

@register.filter
def get_laender(user_param):
    """Return all countries assigned to a user across their profiles."""
    all_countries_codes = []
    country_ids = set()

    def _add_country_to_list(model, field, is_many_to_many_field=False):
        obj = model.objects.filter(user=user_param).first()
        if obj is None:
            return

        countries = getattr(obj, field)
        if is_many_to_many_field:
            countries = countries.all()
        elif countries is None:
            return
        else:
            countries = [countries]

        for country in countries:
            if country.pk not in country_ids:
                country_ids.add(country.pk)
                all_countries_codes.append(country.code)

    _add_country_to_list(Freiwilliger, "einsatzland2")
    _add_country_to_list(Team, "land", True)
    _add_country_to_list(Ehemalige, "land", True)

    return all_countries_codes
