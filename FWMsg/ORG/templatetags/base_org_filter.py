from django import template
from Global.models import Attribute, PersonCluster, UserAttribute

register = template.Library()

@register.filter
def get_person_cluster(user):
    return user.customuser.person_cluster

@register.filter
def get_person_cluster_name(user):
    return user.customuser.person_cluster.name


@register.filter
def get_attribute(request):
    person_cluster_id = request.COOKIES.get('selectedPersonCluster')
    print(person_cluster_id)
    person_cluster = PersonCluster.objects.filter(id=person_cluster_id, org=request.user.org).first()
    print(person_cluster)
    if person_cluster:
        attribute = Attribute.objects.filter(org=request.user.org, person_cluster=person_cluster)
        print(attribute)
        return attribute
    else:
        return Attribute.objects.filter(org=request.user.org)

