from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ClientMembership, ClientSync


@receiver(post_save, sender=ClientMembership)
def membership_status_sync(sender, instance, created, **kwargs):

    client = instance.client

    # კლიენტზე არსებული ყველა pending ჩანაწერი წავშალოთ
    ClientSync.objects.filter(client=client).delete()

    # არის თუ არა კლიენტი აქტიური მთლიანობაში
    is_active = client.has_active_membership

    if is_active:
        ClientSync.objects.create(
            client=client,
            action="add"
        )
    else:
        ClientSync.objects.create(
            client=client,
            action="delete"
        )