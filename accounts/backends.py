"""
Lets people log in with EITHER their WhatsApp number OR their username,
on the website and on the staff admin.
"""
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import ValidationError

from .models import User, looks_like_username, normalize_phone


def find_user(identifier):
    identifier = (identifier or "").strip()
    try:
        if looks_like_username(identifier):
            return User.objects.get(username=identifier.lower().lstrip("@"))
        return User.objects.get(phone=normalize_phone(identifier))
    except (User.DoesNotExist, ValidationError):
        return None


class PhoneOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user = find_user(username or kwargs.get("phone"))
        if user is None:
            User().set_password(password)  # same work either way, so timing doesn't reveal which accounts exist
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
