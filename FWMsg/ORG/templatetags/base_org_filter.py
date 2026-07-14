from django import template
from Global.models import Attribute, PersonCluster, UserAttribute
from urllib.parse import unquote

register = template.Library()

@register.filter
def get_person_cluster(user):
    return user.person_cluster

@register.filter
def get_person_cluster_name(user):
    return user.person_cluster.name

@register.filter
def decode_url(value):
    """Decode URL-encoded text."""
    return unquote(value)

@register.filter
def get_attribute(request):
    person_cluster_id = request.COOKIES.get('selectedPersonCluster')
    print(person_cluster_id)
    person_cluster = PersonCluster.selectable_for_org(
        request.user.org,
        id=person_cluster_id,
    ).first()
    print(person_cluster)
    if person_cluster:
        attribute = Attribute.objects.filter(org=request.user.org, person_cluster=person_cluster)
        print(attribute)
        return attribute
    else:
        return Attribute.objects.filter(org=request.user.org)
