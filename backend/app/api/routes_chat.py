from fastapi import APIRouter, HTTPException
from ..models.schema import ChatRequest, ChatResponse, QuestionRequest
from ..services.rag_service import RAGService
from ..utils.logger import logger

router = APIRouter(tags=["Chat & Question Answering"])
_rag_service = None

def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service

@router.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    rag = get_rag_service()
    return rag.answer_question(
        question=request.question,
        playlist_id=request.playlist_id,
        video_id=request.video_id,
        top_k=request.top_k,
    )

@router.post("/api/ask", response_model=ChatResponse)
def ask_endpoint(request: QuestionRequest):
    """Backwards compatibility for previous frontend implementations."""
    rag = get_rag_service()
    return rag.answer_question(
        question=request.question,
        top_k=5,
    )
