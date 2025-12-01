import json
from typing import Any
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

from .models import ConversationParticipant, Message


class ConversationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        user = self.scope.get('user')

        if not await self._is_participant(user):
            await self.close(code=4403)
            return

        self.group_name = f"conversation_{self.conversation_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data: str | bytes | None = None, bytes_data: bytes | None = None):
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'event': 'error',
                'data': {'message': 'Invalid JSON'}
            }))
            return

        action = data.get('action')
        
        if action == 'send_message':
            content = data.get('content', '').strip()
            if not content:
                await self.send(text_data=json.dumps({
                    'event': 'error',
                    'data': {'message': 'Content cannot be empty'}
                }))
                return

            try:
                message = await self._create_message(content)
                # Don't send via channel layer here - signal will handle broadcast
            except PermissionError as e:
                await self.send(text_data=json.dumps({
                    'event': 'error',
                    'data': {'message': str(e)}
                }))
            except Exception as e:
                await self.send(text_data=json.dumps({
                    'event': 'error',
                    'data': {'message': 'Failed to send message'}
                }))
        
        elif action == 'edit_message':
            message_id = data.get('message_id')
            content = data.get('content', '').strip()
            
            if not message_id:
                await self.send(text_data=json.dumps({
                    'event': 'error',
                    'data': {'message': 'message_id is required'}
                }))
                return
            
            if not content:
                await self.send(text_data=json.dumps({
                    'event': 'error',
                    'data': {'message': 'Content cannot be empty'}
                }))
                return

            try:
                message = await self._edit_message(message_id, content)
                # Signal will handle broadcast
            except PermissionError as e:
                await self.send(text_data=json.dumps({
                    'event': 'error',
                    'data': {'message': str(e)}
                }))
            except ValueError as e:
                await self.send(text_data=json.dumps({
                    'event': 'error',
                    'data': {'message': str(e)}
                }))
            except Exception as e:
                await self.send(text_data=json.dumps({
                    'event': 'error',
                    'data': {'message': 'Failed to edit message'}
                }))
        
        elif action == 'delete_message':
            message_id = data.get('message_id')
            
            if not message_id:
                await self.send(text_data=json.dumps({
                    'event': 'error',
                    'data': {'message': 'message_id is required'}
                }))
                return

            try:
                await self._delete_message(message_id)
                # Signal will handle broadcast
            except PermissionError as e:
                await self.send(text_data=json.dumps({
                    'event': 'error',
                    'data': {'message': str(e)}
                }))
            except ValueError as e:
                await self.send(text_data=json.dumps({
                    'event': 'error',
                    'data': {'message': str(e)}
                }))
            except Exception as e:
                await self.send(text_data=json.dumps({
                    'event': 'error',
                    'data': {'message': 'Failed to delete message'}
                }))
        
        else:
            await self.send(text_data=json.dumps({
                'event': 'error',
                'data': {'message': f'Unknown action: {action}'}
            }))

    async def chat_message(self, event: dict[str, Any]):
        """Handle new message event"""
        await self.send(text_data=json.dumps({
            'event': 'message',
            'data': event['payload']
        }))
    
    async def chat_message_updated(self, event: dict[str, Any]):
        """Handle message update/edit event"""
        await self.send(text_data=json.dumps({
            'event': 'message_updated',
            'data': event['payload']
        }))
    
    async def chat_message_deleted(self, event: dict[str, Any]):
        """Handle message delete event"""
        await self.send(text_data=json.dumps({
            'event': 'message_deleted',
            'data': event['payload']
        }))

    @database_sync_to_async
    def _is_participant(self, user):
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            return False
        return ConversationParticipant.objects.filter(conversation_id=self.conversation_id, user=user).exists()

    @database_sync_to_async
    def _create_message(self, content: str):
        # Check if user can post
        participant = ConversationParticipant.objects.filter(
            conversation_id=self.conversation_id,
            user=self.scope['user']
        ).first()

        if not participant or not participant.can_post:
            raise PermissionError("You are not allowed to post in this conversation.")

        msg = Message.objects.create(
            conversation_id=self.conversation_id,
            sender=self.scope['user'],
            content=content
        )
        return {
            'id': msg.id,
            'sender_id': msg.sender_id,
            'sender_username': msg.sender.username,
            'content': msg.content,
            'created_at': msg.created_at.isoformat(),
        }
    
    @database_sync_to_async
    def _edit_message(self, message_id: int, content: str):
        """Edit a message - only the sender can edit"""
        try:
            msg = Message.objects.get(
                id=message_id,
                conversation_id=self.conversation_id
            )
        except Message.DoesNotExist:
            raise ValueError("Message not found")
        
        # Only the sender can edit
        if msg.sender != self.scope['user']:
            raise PermissionError("You can only edit your own messages.")
        
        # Cannot edit deleted messages
        if msg.is_deleted:
            raise ValueError("Cannot edit a deleted message.")
        
        # Use the model's edit method
        msg.edit(content)
        
        return {
            'id': msg.id,
            'sender_id': msg.sender_id,
            'sender_username': msg.sender.username,
            'content': msg.content,
            'created_at': msg.created_at.isoformat(),
            'edited_at': msg.edited_at.isoformat() if msg.edited_at else None,
        }
    
    @database_sync_to_async
    def _delete_message(self, message_id: int):
        """Delete a message (soft delete) - only the sender can delete"""
        try:
            msg = Message.objects.get(
                id=message_id,
                conversation_id=self.conversation_id
            )
        except Message.DoesNotExist:
            raise ValueError("Message not found")
        
        # Only the sender can delete
        if msg.sender != self.scope['user']:
            raise PermissionError("You can only delete your own messages.")
        
        # Soft delete the message
        msg.soft_delete()
        
        return {
            'id': msg.id,
            'message_id': msg.id,
        }

