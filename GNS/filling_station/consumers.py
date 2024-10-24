import json
from channels.generic.websocket import AsyncWebsocketConsumer


class YourConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # При подключении WebSocket
        self.room_name = 'example_room'
        self.room_group_name = 'example_group'

        # Присоединение к группе
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # При отключении WebSocket
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # При получении сообщения от WebSocket
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        # Отправка сообщения в группу
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message
            }
        )

    async def chat_message(self, event):
        # Получение сообщения из группы
        message = event['message']

        # Отправка сообщения обратно в WebSocket
        await self.send(text_data=json.dumps({
            'message': message
        }))
