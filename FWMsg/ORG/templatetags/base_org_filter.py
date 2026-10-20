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


@register.simple_tag
def person_clusters_for_view(user, view):
    """Active person clusters of the user's org with the given view (e.g. 'F'),
    in the same order as the person cluster filter of the list tables."""
    org = getattr(user, 'org', None)
    if org is None:
        return PersonCluster.objects.none()
    return PersonCluster.selectable_for_org(org, view=view).order_by('name')
