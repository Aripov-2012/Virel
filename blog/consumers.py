import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .models import Conversation, Message

_BIDI_CONTROL_CHARS = dict.fromkeys(
    [
        0x200E,  # LRM
        0x200F,  # RLM
        0x061C,  # ALM
        0x202A,  # LRE
        0x202B,  # RLE
        0x202C,  # PDF
        0x202D,  # LRO
        0x202E,  # RLO
        0x2066,  # LRI
        0x2067,  # RLI
        0x2068,  # FSI
        0x2069,  # PDI
    ],
    None,
)

def _maybe_reverse_cyrillic(text: str) -> str:
    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) < 2:
        return text

    first = next((ch for ch in text if ch.isalpha()), "")
    last = next((ch for ch in reversed(text) if ch.isalpha()), "")
    if not first or not last:
        return text

    # Heuristic: if message looks like reversed Cyrillic (starts lowercase, ends uppercase)
    if first.islower() and last.isupper():
        return text[::-1]

    return text


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if not self.scope['user'].is_authenticated:
            await self.close()
            return

        self.conversation_id = int(self.scope['url_route']['kwargs']['conversation_id'])
        self.group_name = f'chat_{self.conversation_id}'

        is_member = await self._user_in_conversation(self.scope['user'].id, self.conversation_id)
        if not is_member:
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        payload = json.loads(text_data)
        message_text = (payload.get('message') or '').strip()
        message_text = message_text.translate(_BIDI_CONTROL_CHARS)
        if await self._should_reverse_for_user(self.scope['user'].id):
            message_text = _maybe_reverse_cyrillic(message_text)
        if not message_text:
            return

        message_data = await self._create_message(
            conversation_id=self.conversation_id,
            sender_id=self.scope['user'].id,
            text=message_text,
        )

        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'chat.message',
                'message': message_data['text'],
                'sender': message_data['sender'],
                'sender_id': message_data['sender_id'],
                'timestamp': message_data['timestamp'],
            },
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))
    @database_sync_to_async
    def _user_in_conversation(self, user_id, conversation_id):
        return Conversation.objects.filter(id=conversation_id, participants__id=user_id).exists()

    @database_sync_to_async
    def _create_message(self, conversation_id, sender_id, text):
        conversation = Conversation.objects.get(id=conversation_id)
        message = Message.objects.create(
            conversation=conversation,
            sender_id=sender_id,
            text=text,
        )
        conversation.save(update_fields=['updated_at'])
        sender_username = message.sender.username
        sender_id = message.sender_id
        timestamp = timezone.localtime(message.created_at).strftime('%Y-%m-%d %H:%M')
        return {
            'text': message.text,
            'sender': sender_username,
            'sender_id': sender_id,
            'timestamp': timestamp,
        }

    @database_sync_to_async
    def _should_reverse_for_user(self, user_id):
        return Conversation.objects.filter(
            id=self.conversation_id,
            participants__id=user_id,
            participants__profile__reverse_mobile_messages=True,
        ).exists()
