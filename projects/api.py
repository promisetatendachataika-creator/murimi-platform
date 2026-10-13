from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from accounts.api import body, error, login_required_json
from accounts.checklist import checklist
from accounts.choices import ROLE_INVESTOR

from .models import Interest, Project


@require_GET
@login_required_json
def project_list(request):
    """Projects investors can see (drafts and closed projects stay hidden)."""
    items = Project.objects.filter(status__in=Project.VISIBLE)
    return JsonResponse({"projects": [p.as_dict(request.user) for p in items]})


@require_POST
@login_required_json
def set_interest(request, pk):
    user = request.user
    if user.role != ROLE_INVESTOR:
        return error("Only investors can register interest in a project.", status=403)
    try:
        project = Project.objects.get(pk=pk, status__in=Project.VISIBLE)
    except Project.DoesNotExist:
        return error("That project isn't available.", status=404)
    if body(request).get("interested"):
        Interest.objects.get_or_create(investor=user, project=project)
    else:
        Interest.objects.filter(investor=user, project=project).delete()
    return JsonResponse({"project": project.as_dict(user), "checklist": checklist(user)})
