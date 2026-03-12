import json
from channels.generic.websocket import AsyncWebsocketConsumer


class CardConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        print("CardConsumer")
        await self.channel_layer.group_add(
            "cards",
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):

        await self.channel_layer.group_discard(
            "cards",
            self.channel_name
        )

    async def card_event(self, event):

        await self.send(
            text_data=json.dumps(event["data"])
        )