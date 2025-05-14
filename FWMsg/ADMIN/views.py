from django.shortcuts import redirect, render
from ORG.models import Organisation
from .forms import OrganisationForm

# Create your views here.
def admin_home(request):
    org_list = Organisation.objects.all()
    form = OrganisationForm()
    return render(request, 'admin_home.html', {'org_list': org_list, 'form': form})

def admin_org(request, org_id=None):
    if request.method == 'POST':
        if org_id:
            org = Organisation.objects.get(id=org_id)
            form = OrganisationForm(request.POST, request.FILES, instance=org)
        else:
            form = OrganisationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('admin_home')
    else:
        if org_id:
            org = Organisation.objects.get(id=org_id)
            form = OrganisationForm(instance=org)
        else:
            form = OrganisationForm()
    return render(request, 'admin_org.html', {'form': form})