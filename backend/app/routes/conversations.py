from fastapi import APIRouter, Depends, Response, status

from app.core.dependencies import get_conversations
from app.schemas.conversation import (
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    ConversationUpdate,
)
from app.core.dependencies import get_settings_service
from app.services.conversation_service import ConversationService
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationOut])
async def list_conversations(service: ConversationService = Depends(get_conversations)):
    """All conversations, most recently updated first."""
    return await service.list_conversations()


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    service: ConversationService = Depends(get_conversations),
    settings: SettingsService = Depends(get_settings_service),
):
    title = " ".join((body.title or "").split()) or "New chat"
    return await service.create_conversation(title, settings.get().model)


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: str, service: ConversationService = Depends(get_conversations)):
    conversation = await service.get_conversation(conversation_id)
    messages = await service.list_messages(conversation_id)
    return {**conversation, "messages": messages}


@router.patch("/{conversation_id}", response_model=ConversationOut)
async def rename_conversation(
    conversation_id: str,
    body: ConversationUpdate,
    service: ConversationService = Depends(get_conversations),
):
    return await service.rename_conversation(conversation_id, body.title)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: str, service: ConversationService = Depends(get_conversations)):
    await service.delete_conversation(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{conversation_id}/messages", status_code=status.HTTP_204_NO_CONTENT)
async def clear_conversation(conversation_id: str, service: ConversationService = Depends(get_conversations)):
    """Clear the history of a conversation but keep the conversation itself."""
    await service.clear_messages(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
