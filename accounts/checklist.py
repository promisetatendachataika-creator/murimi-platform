"""
Each person's "Next steps" checklist.

Nobody can tick their own steps. Every tick is worked out on the server from
what has actually happened:
  - "auto"  steps tick when the system sees it done (a document uploaded,
            the account verified, a project or job picked);
  - "staff" steps are ticked by Murimi staff in the admin (Users → person →
            "Steps only staff can tick") after it really happened.
If something is undone (e.g. a document marked "Needs redoing"), the tick goes away.
"""

STAFF_STEPS = {
    "visit": "Field officer visit done",
    "call": "Call with the Murimi team done",
}

HOW = {
    "upload": "Ticks when you upload it below",
    "verified": "Ticks when Murimi has checked and verified you",
    "staff_visit": "Ticked by Murimi after the field officer's visit",
    "staff_call": "Ticked by Murimi after your call",
    "project": "Ticks when you press “I'm interested” on a project",
    "job": "Ticks when you mark a job you're interested in",
}


def checklist(user):
    from documents.models import Document  # imported here to avoid a circular import

    role = user.role
    if not role:
        return []
    docs = Document.objects.filter(owner=user).exclude(status=Document.STATUS_REJECTED)

    def uploaded(kind, n=1):
        return docs.filter(kind=kind).count() >= n

    profile = getattr(user, "profile", None)
    verified = bool(profile and profile.verification_status == "verified")
    staff = user.steps or {}

    if role == "farmer":
        items = [
            ("Upload your ID", uploaded("national_id"), "upload"),
            ("Add 3 photos of your farm", uploaded("farm_photo", 3), "upload"),
            ("Field officer visits your farm", bool(staff.get("visit")), "staff_visit"),
            ("Get verified", verified, "verified"),
        ]
    elif role == "landowner":
        items = [
            ("Upload your ID", uploaded("national_id"), "upload"),
            ("Upload your title deed or offer letter", uploaded("title_deed"), "upload"),
            ("Field officer checks the land and water", bool(staff.get("visit")), "staff_visit"),
            ("Get verified", verified, "verified"),
        ]
    elif role == "investor":
        items = [
            ("Upload your ID or passport", uploaded("national_id"), "upload"),
            ("Have a call with the Murimi team", bool(staff.get("call")), "staff_call"),
            ("Get verified", verified, "verified"),
            ("Pick a project you like", user.interests.exists(), "project"),
        ]
    elif role == "driver":
        items = [
            ("Upload your driver's licence", uploaded("drivers_licence"), "upload"),
            ("Add your truck registration", uploaded("truck_registration"), "upload"),
            ("Get verified", verified, "verified"),
            ("Mark a job you're interested in", user.job_interests.exists(), "job"),
        ]
    else:
        return []
    return [{"label": label, "done": done, "how": HOW[how]} for label, done, how in items]
