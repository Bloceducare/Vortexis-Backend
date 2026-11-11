from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = (
        "Grant the organizer role to users whose organization is already approved but who "
        "never received it. Approving an organization from the admin console used to set "
        "is_approved without setting User.is_organizer, so those organizers cannot create "
        "hackathons. Dry run by default; pass --apply to write."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Actually update the users. Without this flag nothing is written.',
        )

    def handle(self, *args, **options):
        affected = (
            User.objects.filter(organizations__is_approved=True, is_organizer=False)
            .distinct()
            .order_by('id')
        )
        ids = list(affected.values_list('id', flat=True))

        if not ids:
            self.stdout.write(self.style.SUCCESS('Nothing to fix: every approved organization\'s organizer already has the role.'))
            return

        self.stdout.write(f'{len(ids)} organizer(s) belong to an approved organization but lack the organizer role.')
        for user in affected.only('id', 'username'):
            self.stdout.write(f'  - user #{user.id} ({user.username})')

        if not options['apply']:
            self.stdout.write(self.style.WARNING('Dry run: nothing was changed. Re-run with --apply to grant the role.'))
            return

        updated = User.objects.filter(id__in=ids).update(is_organizer=True)
        self.stdout.write(self.style.SUCCESS(f'Granted the organizer role to {updated} user(s).'))
