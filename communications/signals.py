from django.db.models.signals import m2m_changed, post_save
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


@receiver(post_save, sender=Message)
def broadcast_new_message(sender, instance: Message, created: bool, **kwargs):
    if not created or instance.is_deleted:
        return

    # Lazy import to avoid circulars
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        group_name = f"conversation_{instance.conversation_id}"
        payload = {
            'id': instance.id,
            'sender_id': instance.sender_id,
            'sender_username': instance.sender.username,
            'content': instance.content,
            'created_at': instance.created_at.isoformat(),
            'edited_at': instance.edited_at.isoformat() if instance.edited_at else None,
        }
        async_to_sync(channel_layer.group_send)(group_name, {
            'type': 'chat.message',
            'payload': payload
        })
    except Exception as e:
        # Log error but don't fail the message creation
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to broadcast message {instance.id}: {e}")

