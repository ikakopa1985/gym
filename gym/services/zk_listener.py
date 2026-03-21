import os
from gym.settings import ipSettings
import threading
from pyzkaccess import ZKAccess
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gym.settings")

from gymapp.models import *

running = False
thread = None

ip = ipSettings

def listener():
    time.sleep(2)

    global running

    connstr = f"""protocol=TCP,ipaddress={ip},port=4370,timeout=4000,passwd="""
    zk = ZKAccess(connstr)

    channel_layer = get_channel_layer()

    while running:
        print("listeningggg")

        for event in zk.doors[0].events.poll(timeout=1):

            card = event.card

            if not card or card == "0":
                continue

            print("CARD:", card)

            try:
                client = Client.objects.get(card_number=card)
                membership = client.memberships.filter(status="active").first()
                if membership:
                    active_memnarship = ClientMembership.objects.get(client=client, status="active")
                if not membership:
                    data = {
                        "status": "no_membership",
                        "name": client.first_name,
                        "lastname": client.last_name,
                        "photo": client.photo.url if client.photo else "",
                    }

                else:

                    # CheckIn ჩაწერა
                    CheckIn.objects.create(client=client)

                    data = {
                        "status": "ok",
                        "name": client.first_name,
                        "lastname": client.last_name,
                        "photo": client.photo.url if client.photo else "",
                        "card":card,
                        "start_date":str(active_memnarship.start_date),
                        "end_date":str(active_memnarship.end_date),
                    }

            except Client.DoesNotExist:

                data = {
                    "status": "unknown_card",
                    "name": "",
                    "lastname": "",
                    "photo": ""
                }

            async_to_sync(channel_layer.group_send)(
                "cards",
                {
                    "type": "card_event",
                    "data": data
                }
            )

    zk.disconnect()


def process_card(card, channel_layer):
    print("CARD:", card)

    try:
        client = Client.objects.get(card_number=card)
        membership = client.memberships.filter(status="active").first()
        if membership:
            active_memnarship = ClientMembership.objects.get(client=client, status="active")
        if not membership:

            data = {
                "status": "no_membership",
                "name": client.first_name,
                "lastname": client.last_name,
                "photo": client.photo.url if client.photo else "",
            }

        else:

            # CheckIn ჩაწერა
            CheckIn.objects.create(client=client)

            data = {
                "status": "ok",
                "name": client.first_name,
                "lastname": client.last_name,
                "photo": client.photo.url if client.photo else "",
                "card":card,
                "start_date":str(active_memnarship.start_date),
                "end_date":str(active_memnarship.end_date),
            }

    except Client.DoesNotExist:
        print("Client.DoesNotExist:")
        data = {
            "status": "unknown_card",
            "name": "",
            "lastname": "",
            "photo": ""
        }

    async_to_sync(channel_layer.group_send)(
        "cards",
        {
            "type": "card_event",
            "data": data
        }
    )

def start():

    print("started")
    global running, thread

    if running:
        return

    running = True
    thread = threading.Thread(target=listener, daemon=True)
    thread.start()


def stop():
    print("stopped")
    # imitate()
    global running
    running = False


def imitate():
    print("imitate")
    channel_layer = get_channel_layer()
    process_card("3041",channel_layer)

