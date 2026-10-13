"""
JSON API used by the website (web/site/index.html).

All requests use the browser's session cookie. Every POST/PATCH must send the
CSRF token in the X-CSRFToken header; Django's CsrfViewMiddleware checks it.
"""
import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from django.conf import settings
from django.utils import timezone

from . import codes, sender, throttle
from .backends import find_user
from .checklist import checklist
from .choices import (CHECKLIST_LENGTH, COLUMN_FIELDS, ROLE_CHOICES, ROLE_DRIVER, ROLE_FIELDS,
                      ROLE_INVESTOR, SAVEABLE_IDS)
from .models import Profile, User, looks_like_username, normalize_phone, normalize_username

ROLES = {k for k, _ in ROLE_CHOICES}


# ---------------------------------------------------------------- helpers
def body(request):
    try:
        data = json.loads(request.body or b"{}")
        return data if isinstance(data, dict) else {}
    except (ValueError, UnicodeDecodeError):
        return {}


def error(message, status=400, errors=None):
    payload = {"error": message}
    if errors:
        payload["errors"] = errors
    return JsonResponse(payload, status=status)


def me_payload(user):
    profile = getattr(user, "profile", None)
    return {
        "user": {
            "role": user.role,
            "full_name": user.full_name,
            "phone": user.phone,
            "username": user.username or "",
            "email": user.email,
            "whatsapp_consent": user.whatsapp_consent,
            "phone_verified": user.phone_verified,
            "phone_verified_at": user.phone_verified_at.isoformat() if user.phone_verified_at else None,
            "date_joined": user.date_joined.isoformat(),
        },
        "profile": profile.as_dict() if profile else {},
        "verification": profile.status_dict() if profile else None,
        "checklist": checklist(user),
        "saved": user.saved or {},
        "my_projects": my_projects(user),
    }


def my_projects(user):
    """Projects a farmer is growing, so they can follow them in their own space."""
    if user.role != "farmer":
        return []
    from projects.models import Project  # imported here to avoid a circular import
    return [p.as_dict() for p in user.farm_projects.exclude(status=Project.STATUS_DRAFT)]


def login_required_json(view):
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return error("Please log in.", status=401)
        return view(request, *args, **kwargs)
    wrapped.__name__ = view.__name__
    return wrapped


def clean_profile(role, raw, errors):
    """Check the role-specific answers against accounts/choices.py."""
    raw = raw if isinstance(raw, dict) else {}
    columns, details = {}, {}
    for key, (kind, opts, required) in ROLE_FIELDS[role].items():
        val = raw.get(key)
        empty = val in (None, "", []) or (isinstance(val, list) and not val)
        if empty:
            if required:
                errors[key] = "Pick at least one." if kind == "multi" else "Please fill this in."
            clean = [] if kind == "multi" else ""
        elif kind == "choice":
            if val not in opts:
                errors[key] = "Please choose one of the options."
                continue
            clean = val
        elif kind == "multi":
            if not isinstance(val, list) or any(v not in opts for v in val):
                errors[key] = "Please choose from the options."
                continue
            clean = list(dict.fromkeys(val))
        elif kind == "text":
            clean = str(val).strip()[: opts or 80]
        elif kind in ("number", "int"):
            try:
                num = Decimal(str(val))
                if num <= 0 or num > Decimal("1000000"):
                    raise InvalidOperation
                if kind == "int" and num != num.to_integral_value():
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                errors[key] = "Enter a number above zero."
                continue
            clean = num if key == "size" else int(num) if kind == "int" else str(num)
        if key in COLUMN_FIELDS:
            columns[key] = clean
        else:
            details[key] = clean
    return columns, details


def clean_account(data, errors, user=None, password_required=True):
    """Check name, phone, email, password and consent. Returns cleaned values."""
    out = {}
    name = str(data.get("full_name", "")).strip()
    if len(name) < 2:
        errors["name"] = "Please enter your full name."
    out["full_name"] = name[:120]

    try:
        phone = normalize_phone(str(data.get("phone", "")))
        taken = User.objects.filter(phone=phone)
        if user:
            taken = taken.exclude(pk=user.pk)
        if taken.exists():
            errors["phone"] = "There's already an account with this number. Log in instead."
        out["phone"] = phone
    except ValidationError as e:
        errors["phone"] = e.messages[0]

    raw_username = str(data.get("username", "") or "").strip()
    if raw_username:
        try:
            username = normalize_username(raw_username)
            taken = User.objects.filter(username=username)
            if user:
                taken = taken.exclude(pk=user.pk)
            if taken.exists():
                errors["username"] = "That username is taken. Try adding a number or your surname."
            out["username"] = username
        except ValidationError as e:
            errors["username"] = e.messages[0]
    elif user is None:
        errors["username"] = "Choose a username. You can log in with it or your WhatsApp number."
    else:
        out["username"] = user.username  # existing accounts may leave it blank

    email = str(data.get("email", "") or "").strip()
    if email:
        try:
            validate_email(email)
        except ValidationError:
            errors["email"] = "That email doesn't look right."
    out["email"] = email.lower()

    password = data.get("password") or ""
    if password or password_required:
        candidate = user or User(full_name=out["full_name"], email=out["email"], phone=out.get("phone", ""))
        try:
            validate_password(password, user=candidate)
        except ValidationError as e:
            errors["password"] = " ".join(e.messages)
    out["password"] = password

    if data.get("consent") is not True:
        errors["consent"] = "Please tick this so we can reach you."
    out["whatsapp_consent"] = data.get("consent") is True
    return out


def apply_profile(profile, columns, details):
    profile.province = columns.get("province", "")
    profile.area = columns.get("area", "")
    profile.size_ha = columns.get("size") or None
    profile.details = details


# ---------------------------------------------------------------- views
@require_GET
@ensure_csrf_cookie
def health(request):
    """The website calls this first. It also hands the browser its CSRF cookie."""
    return JsonResponse({"service": "murimi", "ok": True})


@require_POST
def register(request):
    if throttle.too_many(f"register:{throttle.client_ip(request)}", limit=10, window_seconds=3600):
        return error("Too many sign-ups from this connection. Please try again in an hour.", status=429)
    data = body(request)
    role = data.get("role")
    if role not in ROLES:
        return error("Please choose whether you're a farmer, landowner, investor or driver.")
    errors = {}
    account = clean_account(data, errors)
    columns, details = clean_profile(role, data.get("profile"), errors)
    if errors:
        return error("Please fix the highlighted fields.", errors=errors)

    with transaction.atomic():
        user = User.objects.create_user(
            phone=account["phone"], password=account["password"], full_name=account["full_name"],
            username=account["username"],
            email=account["email"], role=role, whatsapp_consent=account["whatsapp_consent"],
        )
        profile = Profile(user=user)
        apply_profile(profile, columns, details)
        profile.save()
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return JsonResponse(me_payload(user), status=201)


@require_POST
def login_view(request):
    data = body(request)
    identifier = str(data.get("login") or data.get("phone") or "").strip()
    password = data.get("password") or ""
    if not identifier:
        return error("Enter your WhatsApp number or username.")
    if looks_like_username(identifier):
        who = identifier.lower().lstrip("@")
    else:
        try:
            who = normalize_phone(identifier)
        except ValidationError:
            return error("Enter the WhatsApp number you signed up with, including the country code, or your username.")
    key = f"login:{throttle.client_ip(request)}:{who}"
    if throttle.too_many(key, limit=5, window_seconds=15 * 60):
        return error("Too many attempts. Please wait 15 minutes and try again.", status=429)
    user = authenticate(request, username=identifier, password=password)
    if user is None:
        return error("That number or username and password don't match. Check them and try again.")
    throttle.reset(key)
    login(request, user)
    return JsonResponse(me_payload(user))


@require_POST
def logout_view(request):
    logout(request)
    return JsonResponse({"ok": True})


@require_http_methods(["GET", "PATCH"])
@login_required_json
def me(request):
    user = request.user
    if request.method == "GET":
        return JsonResponse(me_payload(user))

    data = body(request)
    errors = {}
    account = clean_account(data, errors, user=user, password_required=False)
    role = user.role
    columns, details = clean_profile(role, data.get("profile"), errors) if role in ROLE_FIELDS else ({}, {})
    if errors:
        return error("Please fix the highlighted fields.", errors=errors)

    with transaction.atomic():
        user.full_name = account["full_name"]
        user.phone = account["phone"]
        user.username = account.get("username")
        user.email = account["email"]
        user.whatsapp_consent = account["whatsapp_consent"]
        if account["password"]:
            user.set_password(account["password"])
        user.save()
        if role in ROLE_FIELDS:
            profile, _ = Profile.objects.get_or_create(user=user)
            before = (profile.province, profile.area, profile.size_ha, profile.details)
            apply_profile(profile, columns, details)
            after = (profile.province, profile.area, profile.size_ha, profile.details)
            changed = (before[0], before[1], before[2] and Decimal(before[2]), before[3]) != \
                      (after[0], after[1], after[2] and Decimal(str(after[2])), after[3])
            if changed and profile.verification_status == Profile.STATUS_VERIFIED:
                # The farm or land details changed, so they need checking again.
                profile.verification_status = Profile.STATUS_PENDING
                profile.message_to_user = ""
            profile.save()
    if account["password"]:
        update_session_auth_hash(request, user)  # keep them logged in after a password change
    return JsonResponse(me_payload(user))


@require_POST
@login_required_json
def set_step(request):
    # People can't tick their own steps: each one is awarded when it's really done
    # (see accounts/checklist.py). Kept only so old pages get a clear answer.
    return error("Steps tick themselves when each one is done. You can't tick them yourself.", status=403)


@require_POST
@login_required_json
def set_saved(request):
    data = body(request)
    item = data.get("id")
    if item not in SAVEABLE_IDS:
        return error("Unknown item.")
    user = request.user
    saved = dict(user.saved or {})
    saved[item] = bool(data.get("saved"))
    user.saved = saved
    user.save(update_fields=["saved"])
    return JsonResponse(me_payload(user))


# ---------------------------------------------------------------- WhatsApp codes
def code_sent(code, phone, **extra):
    data = {"sent": True, "to": codes.mask(phone), "resend_in": codes.RESEND_SECONDS,
            "expires_in": codes.CODE_MINUTES * 60, "test_mode": sender.is_test_mode(), **extra}
    # Test mode on your own computer only: hand the code to the page so you can try it.
    if settings.DEBUG and sender.is_test_mode() and code:
        data["test_code"] = code
    return data


def code_error(e):
    resp = error(e.message, status=e.status)
    if e.retry_in:
        resp = JsonResponse({"error": e.message, "retry_in": e.retry_in}, status=e.status)
    return resp


@require_POST
@login_required_json
def phone_send_code(request):
    user = request.user
    if user.phone_verified:
        return JsonResponse({"sent": False, "already_confirmed": True, **me_payload(user)})
    try:
        code = codes.issue(user, codes.PhoneCode.PURPOSE_VERIFY)
    except codes.CodeError as e:
        return code_error(e)
    return JsonResponse(code_sent(code, user.phone))


@require_POST
@login_required_json
def phone_confirm(request):
    user = request.user
    if throttle.too_many(f"confirm:{user.pk}", limit=20, window_seconds=3600):
        return error("Too many tries. Please wait an hour.", status=429)
    try:
        codes.check(user, codes.PhoneCode.PURPOSE_VERIFY, body(request).get("code"))
    except codes.CodeError as e:
        return code_error(e)
    user.phone_verified_at = timezone.now()
    user.save(update_fields=["phone_verified_at"])
    return JsonResponse(me_payload(user))


@require_POST
def password_forgot(request):
    """Step 1 of 'Forgot password?': send a code to the account's WhatsApp number."""
    if throttle.too_many(f"forgot:{throttle.client_ip(request)}", limit=10, window_seconds=3600):
        return error("Too many requests from this connection. Please try again in an hour.", status=429)
    identifier = str(body(request).get("login") or "").strip()
    if not identifier:
        return error("Enter your WhatsApp number or username.")
    user = find_user(identifier)
    message = "If that account exists, we've sent a 6-digit code to its WhatsApp number."
    if user is None or not user.is_active:
        # Same answer either way, so nobody can use this to find out who has an account.
        return JsonResponse({"sent": True, "message": message, "resend_in": codes.RESEND_SECONDS,
                             "test_mode": sender.is_test_mode()})
    try:
        code = codes.issue(user, codes.PhoneCode.PURPOSE_RESET)
    except codes.CodeError as e:
        return code_error(e)
    data = code_sent(code, user.phone, message=message)
    data.pop("to")  # don't reveal part of someone's number to whoever typed their username
    return JsonResponse(data)


@require_POST
def password_reset(request):
    """Step 2: check the code, set the new password and log them in."""
    if throttle.too_many(f"reset:{throttle.client_ip(request)}", limit=20, window_seconds=3600):
        return error("Too many tries from this connection. Please try again in an hour.", status=429)
    data = body(request)
    user = find_user(str(data.get("login") or ""))
    if user is None or not user.is_active:
        return error("That code has expired. Ask for a new one.")
    password = data.get("password") or ""
    try:
        validate_password(password, user=user)
    except ValidationError as e:
        return error("Please choose a stronger password.", errors={"password": " ".join(e.messages)})
    try:
        codes.check(user, codes.PhoneCode.PURPOSE_RESET, data.get("code"))
    except codes.CodeError as e:
        return code_error(e)
    user.set_password(password)
    user.phone_verified_at = user.phone_verified_at or timezone.now()  # the code proves they own the number
    user.save()
    throttle.reset(f"login:{throttle.client_ip(request)}:{user.username or user.phone}")
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return JsonResponse(me_payload(user))
