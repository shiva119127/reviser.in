import os
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from groq import Groq
from ..config import GROQ_API_KEY, GROQ_MODEL
from .embedding_service import EmbeddingService
from .qdrant_service import QdrantService
from .manifest_service import ManifestService
from ..models.schema import SourceCitation, ChatResponse
from ..utils.logger import logger

SYSTEM_PROMPT = """You are YT Reviser, an expert AI tutor and senior computer science mentor for lecture revision.
Your mission is to provide accurate, deeply educational, and crystal-clear explanations strictly grounded in the concepts taught in the lecture transcripts.

CRITICAL SCOPE & GROUNDING RULES:
1. PLAYLIST-RELEVANT QUESTIONS (ALWAYS ANSWER):
   - If the student's question relates to the concepts, technologies, skills, or curriculum taught in the playlist (such as AI engineering, LLMs, prompt engineering, system role, temperature, RAG, AI agents, tools, APIs, interview prep, etc.), you MUST answer and explain it thoroughly!
   - For overview questions like "what is AI engineering", synthesize how the instructor teaches and approaches the field across the course (e.g. building practical LLM apps, AI agents, RAG systems, and tool integration without heavy math/theory to solve engineering problems and crack AI interviews).
   - Set "is_covered": true.

2. UNRELATED QUESTIONS (REFUSE ONLY THESE):
   - If and only if the student asks about a completely unrelated topic that is NOT part of this playlist's curriculum (for example: asking about Data Structures & Algorithms (DSA), competitive programming, frontend CSS frameworks, chemistry, or subjects outside this course), you MUST NOT answer from external knowledge or invent a tutorial.
   - In that case, set "is_covered": false, and state:
     "### ℹ️ Not Provided in Playlist Transcripts\\n\\nThis topic is not provided in the transcripts of the selected playlist. This course focuses on [actual topics covered in the playlist] and does not cover this subject."

MULTILINGUAL & HINGLISH MASTERY:
- The lecture transcripts are from real tech classrooms and courses where instructors teach in English, Hindi, and conversational Hinglish.
- Key technical terms are frequently spoken in Hinglish and transcribed in Devanagari or phonetic Hindi (e.g., "तेमप्रेच्र / तेमठ्रेचर / तापमान" = Temperature, "सिस्टम रोल" = System Role, "ललम / एलएलएम" = LLM, "राग" = RAG, "प्रॉम्प्ट" = Prompt, "स्टैक" = Stack, "बाइनरी सर्च" = Binary Search, "एजेंट" = AI Agent, "टोकन" = Token).
- Always comprehend these phonetic transcripts seamlessly and extract the instructor's core teachings when the concept is present.
- Ignore minor transcription speech disfluencies or repetitive background noise in the text.

PEDAGOGICAL TEACHING GUIDELINES (WHEN ANSWERING COVERED TOPICS):
1. Concept-First & Authoritative: Begin immediately with a clear, concise definition of the concept in accessible, professional language.
2. Step-by-Step Breakdown:
   - What the concept is as taught by the instructor.
   - How it works, its valid parameters/values (e.g. Temperature 0 to 2 in LLMs, default values, deterministic vs creative outputs).
   - The instructor's specific analogies, metaphors, and real-world intuition (e.g. the 3-year-old child predicting days of the week, Doctor agent needing Temperature 0 for facts vs Media agent needing higher Temperature for creativity, fan regulator analogy).
   - Practical engineering takeaway / implementation tip.
3. Rich Markdown Formatting: Use clean section headers (###), bullet points, bold key terms, tables, or code snippets to maximize readability.
4. Tone & Polish: Speak like a world-class tutor. Never refer to internal system components like "chunks", "Qdrant", "vector database", or "embeddings".
5. Follow-Up Inquiries: Always generate exactly 3 highly relevant follow-up questions related to what was taught in the lectures.

RESPONSE FORMAT (Strict JSON):
{
  "answer": "Your comprehensive explanation if covered, OR your clear refusal message if the topic is not covered in these lectures...",
  "is_covered": true,
  "follow_up_questions": [
    "First relevant follow-up question?",
    "Second relevant follow-up question?",
    "Third relevant follow-up question?"
  ]
}
"""

CONCEPT_EXPANSIONS: Dict[str, Dict[str, List[str]]] = {
    "ai engineering": {
        "keywords": ["AI engineer", "AI engineering", "LLM", "AI agents", "RAG", "prompt engineering", "interview", "projects"],
        "phonetics": ["एआई", "इंजीनियर", "ललम", "राग", "एजेंट"],
    },
    "ai engineer": {
        "keywords": ["AI engineer", "AI engineering", "LLM", "AI agents", "RAG", "prompt engineering", "interview", "projects"],
        "phonetics": ["एआई", "इंजीनियर", "ललम", "राग", "एजेंट"],
    },
    "temperature": {
        "keywords": ["temperature", "creativity", "randomness", "system role", "parameter", "0 to 2", "prediction"],
        "phonetics": ["तेमप्रेच्र", "तेमठ्रेचर", "तापमान", "क्रीटिविटी", "प्रेडिक्शन", "ललम"],
    },
    "system role": {
        "keywords": ["system role", "system prompt", "developer role", "user role", "assistant role", "personality"],
        "phonetics": ["सिस्टम रोल", "सिस्टम", "रोल", "असिस्टेंट", "पर्सनैलिटी"],
    },
    "llm": {
        "keywords": ["LLM", "large language model", "groq", "gpt", "model", "token", "prediction"],
        "phonetics": ["ललम", "एलएलएम", "मॉडल", "ग्रोक", "प्रेडिक्शन"],
    },
    "prompt": {
        "keywords": ["prompt engineering", "zero shot", "few shot", "system prompt", "context"],
        "phonetics": ["प्रॉम्प्ट", "प्राम्प्ट", "इंजीनियरिंग", "सिस्टम रोल"],
    },
    "agent": {
        "keywords": ["AI agent", "function calling", "tools", "assistant", "workflow"],
        "phonetics": ["एजेंट", "आजिन्त", "टूल्स", "असिस्टेंट"],
    },
    "rag": {
        "keywords": ["RAG", "retrieval augmented generation", "vector search", "embeddings", "chunks"],
        "phonetics": ["राग", "रिट्रीवल", "वेक्टर", "एम्बेडिंग"],
    },
    "binary search": {
        "keywords": ["binary search", "monotonic", "search space", "low high mid", "fan regulator"],
        "phonetics": ["बाइनरी सर्च", "मोनोटोनिक", "सर्च", "रेगुलेटर"],
    },
    "monotonic": {
        "keywords": ["monotonic", "increasing decreasing", "binary search", "stack", "truth table"],
        "phonetics": ["मोनोटोनिक", "बाइनरी सर्च", "सर्च"],
    },
    "stack": {
        "keywords": ["stack", "monotonic stack", "next greater element", "pop push", "daily temperature"],
        "phonetics": ["स्टैक", "मोनोटोनिक स्टैक", "पॉप", "पुश", "नेक्स्ट ग्रेटर"],
    },
    "merge interval": {
        "keywords": ["merge intervals", "intervals", "overlap", "start end", "range"],
        "phonetics": ["मर्ज इंटरवल", "इंटरवल", "ओवरलैप", "रेंज"],
    },
    "recursion": {
        "keywords": ["recursion", "recursive", "base case", "call stack", "subproblem"],
        "phonetics": ["रिकर्शन", "बेस केस", "कॉल स्टैक"],
    },
    "environment variable": {
        "keywords": ["environment variable", "os environ", "api key", "export", "dotenv"],
        "phonetics": ["एनवायरनमेंट वेरिएबल", "एपीआई की", "डॉट एनव"],
    },
}

def clean_whisper_text(text: str) -> str:
    """Removes Whisper hallucination loops, repeated words, and excessive punctuation."""
    if not text:
        return ""
    # Collapse repetitive word loops (e.g. "तो तो तो तो" -> "तो", "अगर अगर अगर" -> "अगर")
    cleaned = re.sub(r'(\b[\w\u0900-\u097F]+\b)(?:\s+\1){2,}', r'\1', text)
    # Collapse repeating non-word or special symbols (e.g. "़़़़", ".....", "-----")
    cleaned = re.sub(r'([^\w\s\u0900-\u097F])\1{2,}', r'\1', cleaned)
    # Collapse repeated short phrases (3-30 chars)
    cleaned = re.sub(r'(.{3,30}?)\1{3,}', r'\1', cleaned)
    # Normalize spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


class RAGService:
    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        qdrant_service: Optional[QdrantService] = None,
    ):
        self.embedding_service = embedding_service or EmbeddingService.get_instance()
        self.qdrant_service = qdrant_service or QdrantService.get_instance()
        
        if not GROQ_API_KEY:
            logger.warning("GROQ_API_KEY is not set. Groq completions will fail unless configured.")
            self.groq_client = None
        else:
            self.groq_client = Groq(api_key=GROQ_API_KEY)

    def is_ready(self) -> bool:
        return bool(self.groq_client and GROQ_API_KEY)

    @staticmethod
    def _normalize_query(query: str) -> str:
        """Fix common typos and normalize search terms."""
        cleaned = query.strip()
        typo_map = {
            r"\btemperture\b": "temperature",
            r"\btemperatue\b": "temperature",
            r"\btemprature\b": "temperature",
            r"\bengenering\b": "engineering",
            r"\benginering\b": "engineering",
            r"\bmaop\b": "map",
            r"\breccursion\b": "recursion",
            r"\brecurssion\b": "recursion",
            r"\bbinery\b": "binary",
            r"\bllms\b": "LLM",
            r"\bragg\b": "RAG",
            r"\bpromt\b": "prompt",
            r"\bsytem\b": "system",
        }
        for pattern, replacement in typo_map.items():
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        return cleaned

    def _retrieve_candidates(
        self,
        query: str,
        playlist_id: Optional[str] = None,
        video_id: Optional[str] = None,
        top_k: int = 6,
    ) -> List[Any]:
        normalized_q = self._normalize_query(query)
        logger.info(f"Retrieving for query: '{query}' (normalized: '{normalized_q}')")

        # 1. Primary semantic search
        primary_vec = self.embedding_service.embed_query(normalized_q)
        primary_results = self.qdrant_service.search(
            query_vector=primary_vec,
            top_k=max(top_k * 2, 10),
            playlist_id=playlist_id,
            video_id=video_id,
        )

        all_results_map: Dict[str, Tuple[Any, float]] = {}
        for r in primary_results:
            pid = str(r.id)
            score = float(getattr(r, "score", 0.0))
            all_results_map[pid] = (r, score)

        # 2. Concept expansion & multi-vector retrieval
        query_lower = normalized_q.lower()
        active_keywords = []
        active_phonetics = []

        for concept, meta in CONCEPT_EXPANSIONS.items():
            if concept in query_lower or any(kw in query_lower for kw in meta["keywords"][:2]):
                active_keywords.extend(meta["keywords"])
                active_phonetics.extend(meta["phonetics"])

        # Strip conversational question filler words
        stripped_keywords = re.sub(
            r"\b(what|is|are|the|how|to|in|of|and|for|a|an|explain|tell|me|about|can|you|describe|mean|by|why|does|do|with|from)\b",
            " ",
            query_lower,
            flags=re.IGNORECASE,
        ).strip()
        stripped_keywords = re.sub(r"\s+", " ", stripped_keywords)

        extra_queries = []
        if active_keywords:
            extra_queries.append(" ".join(active_keywords[:5]))
        if active_phonetics:
            extra_queries.append(" ".join(active_phonetics[:6]))
        if stripped_keywords and stripped_keywords != query_lower and len(stripped_keywords) > 2:
            extra_queries.append(stripped_keywords)

        for eq in extra_queries:
            logger.info(f"Concept expansion search: '{eq}'")
            eq_vec = self.embedding_service.embed_query(eq)
            eq_results = self.qdrant_service.search(
                query_vector=eq_vec,
                top_k=max(top_k * 2, 10),
                playlist_id=playlist_id,
                video_id=video_id,
            )
            for r in eq_results:
                pid = str(r.id)
                score = float(getattr(r, "score", 0.0))
                if pid in all_results_map:
                    prev_r, prev_score = all_results_map[pid]
                    all_results_map[pid] = (prev_r, max(prev_score, score) + 0.12)
                else:
                    all_results_map[pid] = (r, score * 0.95)

        # 3. Lexical / Title / Transliteration Boost
        search_terms = set(re.findall(r"\w+", query_lower)) | set(active_keywords) | set(active_phonetics)
        stop_words = {"what", "is", "are", "the", "how", "to", "in", "of", "and", "for", "a", "an", "do", "you", "me", "by"}
        search_terms = {t.lower() for t in search_terms if t.lower() not in stop_words and len(t) > 1}

        scored_candidates = []
        for pid, (res, base_score) in all_results_map.items():
            payload = res.payload or {}
            title = (payload.get("title") or "").lower()
            text = (payload.get("text") or "").lower()

            bonus = 0.0
            # Title match boost
            for term in search_terms:
                if term in title:
                    bonus += 0.25
                    break

            # Text keyword / phonetic match boost
            matched_terms = 0
            for term in search_terms:
                if term in text:
                    matched_terms += 1
            if matched_terms > 0:
                bonus += min(0.30, matched_terms * 0.08)

            final_score = base_score + bonus
            scored_candidates.append((res, final_score))

        # Sort descending by final composite score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        top_results = []
        for res, score in scored_candidates[:top_k]:
            res.score = round(score, 4)
            top_results.append(res)

        return top_results

    def _build_context(self, search_results: List[Any]) -> Tuple[str, List[SourceCitation]]:
        context_blocks = []
        sources = []
        seen_chunks = set()

        for res in search_results:
            payload = res.payload or {}
            chunk_id = payload.get("chunk_id", "")
            if chunk_id in seen_chunks:
                continue
            seen_chunks.add(chunk_id)

            video_id = payload.get("video_id", "")
            title = payload.get("title", "Lecture Video")
            start = float(payload.get("start", 0.0))
            end = float(payload.get("end", 0.0))
            raw_text = payload.get("text", "")
            cleaned_text = clean_whisper_text(raw_text)

            yt_url = payload.get("youtube_url", f"https://www.youtube.com/watch?v={video_id}")
            start_sec = int(start)
            timestamped_url = payload.get("timestamped_url") or f"https://www.youtube.com/watch?v={video_id}&t={start_sec}s"
            score = float(res.score) if hasattr(res, "score") else 0.0

            mins = int(start // 60)
            secs = int(start % 60)
            time_str = f"{mins:02d}:{secs:02d}"

            context_blocks.append(
                f"### Video: {title}\n"
                f"Timestamp: {time_str} ({start:.1f}s - {end:.1f}s)\n"
                f"URL: {timestamped_url}\n"
                f"Transcript Content:\n{cleaned_text}\n"
            )

            sources.append(
                SourceCitation(
                    video_id=video_id,
                    title=title,
                    start=start,
                    end=end,
                    text=cleaned_text,
                    youtube_url=yt_url,
                    timestamped_url=timestamped_url,
                    score=round(score, 4),
                )
            )

        return "\n\n".join(context_blocks), sources

    def answer_question(
        self,
        question: str,
        playlist_id: Optional[str] = None,
        video_id: Optional[str] = None,
        top_k: int = 6,
    ) -> ChatResponse:
        raw_question = question.strip()
        if not raw_question:
            return ChatResponse(
                answer="Please enter a question about your lectures.",
                sources=[],
                follow_up_questions=[],
            )

        # Resolve playlist title if playlist_id is provided
        playlist_title = None
        if playlist_id:
            try:
                manifest_service = ManifestService.get_instance()
                pl_entry = manifest_service.get_playlist(playlist_id)
                if pl_entry:
                    playlist_title = pl_entry.title
            except Exception:
                pass

        course_label = f"the **{playlist_title}** playlist" if playlist_title else "the selected lectures"

        # Retrieve candidates with hybrid multi-vector + lexical expansion
        results = self._retrieve_candidates(
            query=raw_question,
            playlist_id=playlist_id,
            video_id=video_id,
            top_k=top_k,
        )

        top_score = max((getattr(r, "score", 0.0) for r in results), default=0.0)

        # Early check: if no results or top similarity is too weak in filtered playlist
        if not results or (playlist_id and top_score < 0.38):
            return ChatResponse(
                answer=(
                    f"### ℹ️ No Information in Selected Course\n\n"
                    f"There is no information about **{raw_question}** in {course_label}.\n\n"
                    f"The lectures in this playlist focus on other topics and do not cover this question. "
                    f"Please ask a question related to what is taught in this course, or switch the filter to **All Indexed Lectures**."
                ),
                sources=[],
                follow_up_questions=[
                    f"What topics are covered in {playlist_title or 'this playlist'}?",
                    "Would you like to search across all playlists instead?",
                    "Can you ask a question related to this lecture series?",
                ],
            )

        context_text, sources = self._build_context(results)

        if not self.groq_client:
            return ChatResponse(
                answer="Groq API key is not configured. Please set GROQ_API_KEY in your .env file to enable AI answer generation.",
                sources=sources,
                follow_up_questions=[],
            )

        scope_instruction = ""
        if playlist_title:
            scope_instruction = (
                f"PLAYLIST RELEVANCE GUIDELINES:\n"
                f"- The student is revising the playlist: '{playlist_title}'.\n"
                f"- WHAT TO ANSWER (SET \"is_covered\": true): If the question asks about concepts, topics, or skills relevant to this course (such as AI engineering, building LLM apps, prompt engineering, system roles, temperature, AI agents, RAG, vector databases, tool calling, or interview prep), you MUST answer thoroughly by synthesizing what the instructor teaches, explains, and demonstrates across the lectures.\n"
                f"- WHAT TO REFUSE (SET \"is_covered\": false): If and only if the question is about a completely unrelated topic outside the course curriculum (for example: Data Structures & Algorithms (DSA), competitive programming, frontend CSS/React web development, chemistry, etc.), you MUST NOT answer from outside knowledge. In that case, set \"is_covered\": false, and respond:\n"
                f"  '### ℹ️ Not Provided in Playlist Transcripts\\n\\nThis topic is not provided in the transcripts of the {playlist_title} playlist. This course focuses on practical AI engineering (LLMs, AI agents, RAG, and prompt engineering) and does not cover this subject.'\n\n"
            )
        else:
            scope_instruction = (
                f"GROUNDING GUIDELINES:\n"
                f"- Answer questions relevant to the topics and lessons taught in the retrieved transcripts.\n"
                f"- If the topic is completely unrelated or absent from the lectures, set \"is_covered\": false and inform the student that it is not provided in the transcripts.\n\n"
            )

        user_prompt = (
            f"STUDENT QUESTION:\n{raw_question}\n\n"
            f"{scope_instruction}"
            f"RETRIEVED LECTURE TRANSCRIPT CONTEXT:\n{context_text}\n\n"
            f"Please synthesize the lecture teachings and provide your response in the required JSON format."
        )

        logger.info(f"Calling Groq model '{GROQ_MODEL}' with grounded context ({len(sources)} sources)...")
        try:
            response = self.groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"} if any(m in GROQ_MODEL for m in ("gpt", "llama", "qwen")) else None,
            )
            raw_content = response.choices[0].message.content.strip()

            try:
                data = json.loads(raw_content)
                answer = data.get("answer", raw_content)
                is_covered = data.get("is_covered", True)
                follow_ups = data.get("follow_up_questions", [])
            except Exception:
                answer = raw_content
                is_covered = True
                follow_ups = []

            # If the topic is not covered in the lecture context, clear citations to prevent misleading links
            if not is_covered or answer.startswith("### ℹ️"):
                sources = []

            return ChatResponse(
                answer=answer,
                sources=sources,
                follow_up_questions=follow_ups,
            )

        except Exception as e:
            logger.error(f"Groq generation error: {e}")
            return ChatResponse(
                answer=f"Error generating answer with LLM: {str(e)}. Retrieved lecture sources are listed below.",
                sources=sources,
                follow_up_questions=[],
            )


