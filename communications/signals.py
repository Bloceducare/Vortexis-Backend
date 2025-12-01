from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver

from team.models import Team
from hackathon.models import Hackathon
from .models import Conversation, ConversationParticipant, Message


@receiver(m2m_changed, sender=Team.members.through)
def sync_team_conversation_members(sender, instance: Team, action, pk_set, **kwargs):
    if action not in {'post_add', 'post_remove', 'post_clear'}:
        return
    conv, _ = Conversation.objects.get_or_create(type='team', team=instance, defaults={
        'created_by': instance.organizer or instance.members.first(),
        'hackathon': instance.hackathon,
        'title': f"Team: {instance.name}",
    })
    if action in {'post_add'} and pk_set:
        ConversationParticipant.objects.bulk_create([
            ConversationParticipant(conversation=conv, user_id=uid, is_admin=(uid == (instance.organizer_id or -1)))
            for uid in pk_set
            if not ConversationParticipant.objects.filter(conversation=conv, user_id=uid).exists()
        ])
    elif action in {'post_remove', 'post_clear'}:
        if action == 'post_clear':
            ConversationParticipant.objects.filter(conversation=conv).delete()
        else:
            ConversationParticipant.objects.filter(conversation=conv, user_id__in=pk_set).delete()


@receiver(m2m_changed, sender=Hackathon.judges.through)
def sync_judges_conversation_members(sender, instance: Hackathon, action, pk_set, **kwargs):
    if action not in {'post_add', 'post_remove', 'post_clear'}:
        return
    conv, _ = Conversation.objects.get_or_create(type='judges', hackathon=instance, defaults={
        'created_by': instance.judges.first(),
        'organization': instance.organization,
    })
    if action == 'post_add' and pk_set:
        ConversationParticipant.objects.bulk_create([
            ConversationParticipant(conversation=conv, user_id=uid)
            for uid in pk_set
            if not ConversationParticipant.objects.filter(conversation=conv, user_id=uid).exists()
        ])
    elif action in {'post_remove', 'post_clear'}:
        if action == 'post_clear':
            ConversationParticipant.objects.filter(conversation=conv).delete()
        else:
            ConversationParticipant.objects.filter(conversation=conv, user_id__in=pk_set).delete()

    # Ensure organization organizer and moderators are present
    org = instance.organization
    if org:
        ensure_ids = set()
        if org.organizer_id:
            ensure_ids.add(org.organizer_id)
        ensure_ids.update(org.moderators.values_list('id', flat=True))
        for uid in ensure_ids:
            ConversationParticipant.objects.get_or_create(conversation=conv, user_id=uid, defaults={'is_admin': True})


# Store previous state to detect changes
_previous_message_state = {}

@receiver(pre_save, sender=Message)
def store_message_state(sender, instance: Message, **kwargs):
    """Store the previous state of the message before saving"""
    if instance.pk:
        try:
            old_instance = Message.objects.get(pk=instance.pk)
            _previous_message_state[instance.pk] = {
                'content': old_instance.content,
                'is_deleted': old_instance.is_deleted,
                'edited_at': old_instance.edited_at,
            }
        except Message.DoesNotExist:
            pass

@receiver(post_save, sender=Message)
def broadcast_message_changes(sender, instance: Message, created: bool, **kwargs):
    # Lazy import to avoid circulars
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        group_name = f"conversation_{instance.conversation_id}"
        previous_state = _previous_message_state.get(instance.pk, {})
        was_deleted_before = previous_state.get('is_deleted', False)
        
        # Determine the event type based on state transitions
        if created and not instance.is_deleted:
            # New message created
            event_type = 'chat.message'
            payload = {
                'id': instance.id,
                'sender_id': instance.sender_id,
                'sender_username': instance.sender.username,
                'content': instance.content,
                'created_at': instance.created_at.isoformat(),
                'edited_at': instance.edited_at.isoformat() if instance.edited_at else None,
                'is_deleted': instance.is_deleted,
            }
        elif instance.is_deleted and not was_deleted_before:
            # Message was just deleted (transition from not deleted to deleted)
            event_type = 'chat.message_deleted'
            payload = {
                'id': instance.id,
                'message_id': instance.id,
            }
        elif not created and not instance.is_deleted and previous_state.get('content') != instance.content:
            # Message was edited (content changed and not deleted)
            event_type = 'chat.message_updated'
            payload = {
                'id': instance.id,
                'sender_id': instance.sender_id,
                'sender_username': instance.sender.username,
                'content': instance.content,
                'created_at': instance.created_at.isoformat(),
                'edited_at': instance.edited_at.isoformat() if instance.edited_at else None,
                'is_deleted': instance.is_deleted,
            }
        else:
            # No significant change to broadcast
            if instance.pk in _previous_message_state:
                del _previous_message_state[instance.pk]
            return

        async_to_sync(channel_layer.group_send)(group_name, {
            'type': event_type,
            'payload': payload
        })
        
        # Clean up stored state
        if instance.pk in _previous_message_state:
            del _previous_message_state[instance.pk]
            
    except Exception as e:
        # Log error but don't fail the message operation
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to broadcast message {instance.id}: {e}")

