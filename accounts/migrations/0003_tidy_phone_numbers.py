"""
One-off fix: accounts added in the staff admin before this change kept their
number exactly as typed (e.g. "0718989114"), so they couldn't log in.
This rewrites every number in the standard form (e.g. "+263718989114").
A number that is invalid, or would clash with another account, is left alone
and printed so staff can fix it by hand.
"""
import re

from django.db import migrations


def normalize(raw):
    raw = (raw or "").strip()
    has_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    if not has_plus:
        if digits.startswith("00"):
            digits = digits[2:]
        elif digits.startswith("0") and len(digits) == 10:
            digits = "263" + digits[1:]
    return "+" + digits if 9 <= len(digits) <= 15 else None


def tidy(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    taken = set(User.objects.values_list("phone", flat=True))
    for user in User.objects.all():
        new = normalize(user.phone)
        if not new or new == user.phone:
            if not new:
                print(f"\n  Check this number by hand in the admin: {user.full_name} {user.phone!r}")
            continue
        if new in taken:
            print(f"\n  Not changed (another account already uses {new}): {user.full_name} {user.phone!r}")
            continue
        taken.discard(user.phone)
        taken.add(new)
        user.phone = new
        user.save(update_fields=["phone"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_verification_message")]
    operations = [migrations.RunPython(tidy, migrations.RunPython.noop)]
