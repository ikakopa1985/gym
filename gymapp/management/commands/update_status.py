from django.core.management.base import BaseCommand
from django.utils import timezone

from gymapp.models import ClientMembership
from gymapp.models import ClientSync



class Command(BaseCommand):
    help = "ამოწმებს აბონემენტებს და საჭიროების შემთხვევაში ცვლის სტატუსს expired-ზე"

    def handle(self, *args, **kwargs):

        today = timezone.localdate()

        updated = 0

        cms = ClientMembership.objects.select_related("membership").filter(status="active")

        for cm in cms:

            mtype = cm.membership.membership_type

            expired = False

            if mtype == "fixed":
                if cm.end_date and cm.end_date < today:
                    expired = True

            if expired:

                cm.status = "expired"
                cm.save(update_fields=["status"])

                # ZKT-დან წასაშლელი task
                exists = ClientSync.objects.filter(
                    client=cm.client,
                    action="delete",
                    status="pending"
                ).exists()

                if not exists:
                    ClientSync.objects.create(
                        client=cm.client,
                        action="delete",
                        status="pending"
                    )

                updated += 1

        self.stdout.write(
            self.style.SUCCESS(f"შემოწმდა {cms.count()} აბონემენტი. ვადაგასული გახდა {updated}")
        )