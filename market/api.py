from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from accounts.api import body, error, login_required_json
from accounts.checklist import checklist
from accounts.choices import ROLE_DRIVER

from .models import HaulJob, JobInterest, latest_prices


@require_GET
@login_required_json
def prices(request):
    return JsonResponse({"prices": latest_prices()})


def jobs_for(user):
    """Open jobs that fit the driver's trucks, plus any job assigned to them."""
    profile = getattr(user, "profile", None)
    details = (profile.details if profile else {}) or {}
    sizes = details.get("trucks") or []
    cold = details.get("cold") == "Yes"
    open_jobs = HaulJob.objects.filter(status=HaulJob.STATUS_OPEN, truck_size__in=sizes)
    if not cold:
        open_jobs = open_jobs.filter(needs_cold=False)
    mine = HaulJob.objects.filter(driver=user).exclude(status__in=[HaulJob.STATUS_DRAFT, HaulJob.STATUS_CANCELLED])
    other_open = HaulJob.objects.filter(status=HaulJob.STATUS_OPEN).exclude(pk__in=open_jobs).count()
    return {
        "jobs": [j.as_dict(user) for j in open_jobs],
        "mine": [j.as_dict(user) for j in mine],
        "other_open": other_open,
    }


@require_GET
@login_required_json
def jobs(request):
    if request.user.role != ROLE_DRIVER:
        return error("Haulage jobs are for drivers.", status=403)
    return JsonResponse(jobs_for(request.user))


@require_POST
@login_required_json
def job_interest(request, pk):
    user = request.user
    if user.role != ROLE_DRIVER:
        return error("Only drivers can take haulage jobs.", status=403)
    try:
        job = HaulJob.objects.get(pk=pk, status=HaulJob.STATUS_OPEN)
    except HaulJob.DoesNotExist:
        return error("That job isn't open any more.", status=404)
    if body(request).get("interested"):
        JobInterest.objects.get_or_create(driver=user, job=job)
    else:
        JobInterest.objects.filter(driver=user, job=job).delete()
    data = jobs_for(user)
    data["checklist"] = checklist(user)
    return JsonResponse(data)
