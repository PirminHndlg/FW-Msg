from allauth.mfa.models import Authenticator
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from admin_mfa import audit


class Command(BaseCommand):
    help = (
        "Remove all second factors (passkeys, TOTP, recovery codes) of a user who "
        "lost them. Their next login sets up a new one (ADMIN_MFA_FIRST_ENROLMENT)."
    )

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--yes", action="store_true", help="do not ask for confirmation")

    def handle(self, username, yes, **options):
        User = get_user_model()
        try:
            user = User.objects.get(**{User.USERNAME_FIELD: username})
        except User.DoesNotExist as e:
            raise CommandError(f"no user {username!r}") from e
        authenticators = Authenticator.objects.filter(user=user)
        count = authenticators.count()
        if not count:
            self.stdout.write(f"{username} has no second factor.")
            return
        if not yes:
            answer = input(f"Remove {count} authenticator(s) of {username}? [y/N] ")
            if answer.strip().lower() != "y":
                raise CommandError("aborted")
        types = sorted({a.type for a in authenticators})
        authenticators.delete()
        audit.event("authenticators_reset_by_command", None, user, types=",".join(types))
        self.stdout.write(self.style.SUCCESS(f"Removed {count} authenticator(s) of {username}."))
