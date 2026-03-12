from django.core.management.base import BaseCommand
from django.utils import timezone

from gymapp.models import ClientMembership


class Command(BaseCommand):
    help = "ამოწმებს აბონემენტებს და საჭიროების შემთხვევაში ცვლის სტატუსს expired-ზე"

    def handle(self, *args, **kwargs):

        today = timezone.localdate()

        updated = 0

        cms = ClientMembership.objects.select_related("membership").filter(status="active")

        for cm in cms:

            mtype = cm.membership.membership_type

            expired = False

            if mtype == "limited":
                if (cm.remaining_visits or 0) <= 0:
                    expired = True

            elif mtype == "unlimited":
                if cm.end_date and cm.end_date < today:
                    expired = True

            elif mtype == "fixed":
                if cm.end_date and cm.end_date < today:
                    expired = True

            if expired:
                cm.status = "expired"
                cm.save(update_fields=["status"])
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(f"შემოწმდა {cms.count()} აბონემენტი. ვადაგასული გახდა {updated}")
        )