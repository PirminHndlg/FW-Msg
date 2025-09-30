from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta

from FWMsg.decorators import required_role
from Global.models import Post2, Bilder2, UserAufgaben

# Base template for ehemalige views
base_template = 'baseEhemalige.html'


@login_required
@required_role('E')
def home(request):
    """Dashboard view for former volunteers (Ehemalige)."""
    # Import here to avoid circular import
    from Global.views import get_bilder, get_posts
    
    # Get recent posts relevant to former volunteers
    posts = []
    if request.user.customuser.person_cluster and request.user.customuser.person_cluster.posts:
        posts = get_posts(request.user.org, filter_person_cluster=request.user.customuser.person_cluster, limit=6)
    
    # Get recent images
    gallery_images = []
    if request.user.customuser.person_cluster and request.user.customuser.person_cluster.bilder:
        gallery_images = get_bilder(request.user.org, limit=6)
    
    # Get any tasks assigned to former volunteers
    my_tasks = UserAufgaben.objects.none()
    if request.user.customuser.person_cluster and request.user.customuser.person_cluster.aufgaben:
        my_tasks = UserAufgaben.objects.filter(
            org=request.user.org,
            user=request.user,
            erledigt=False
        ).select_related('aufgabe').order_by('faellig')[:5]
    
    context = {
        'posts': posts,
        'gallery_images': gallery_images,
        'my_tasks': my_tasks,
        'today': timezone.now().date(),
    }
    
    return render(request, 'ehemaligeHome.html', context)
