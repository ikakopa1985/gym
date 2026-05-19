from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from gymapp.models import ClientMembership
from gymapp.models import ClientSync



class Command(BaseCommand):
    help = "ამოწმებს აბონემენტებს და საჭიროების შემთხვევაში ცვლის სტატუსს expired-ზე"

    def handle(self, *args, **kwargs):

        today = timezone.localdate()

        updated = 0

        cms = ClientMembership.objects.select_related("membership").filter(
            status="active"
        ).filter(
            Q(start_date__gt=today) |
            Q(end_date__lt=today)
        )

        for cm in cms:

            expired = False

            if cm.membership.membership_type == "fixed":
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

        cms_to_activate = ClientMembership.objects.select_related("membership").filter(
            status__in=["expired", "paused"],
            start_date__lte=today,
            end_date__gte=today
        )

        for cm in cms_to_activate:

            cm.status = "active"
            cm.save(update_fields=["status"])

            # ZKT-დან წასაშლელი task
            exists = ClientSync.objects.filter(
                client=cm.client,
                action="add",
                status="pending"
            ).exists()

            if not exists:
                ClientSync.objects.create(
                    client=cm.client,
                    action="add",
                    status="pending"
                )

            updated += 1

        self.stdout.write(
            self.style.SUCCESS(f"შემოწმდა {cms.count()} აბონემენტი. დაკორექტირდა  {updated}")
        )