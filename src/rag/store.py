import json
from uuid import uuid4

import chromadb

from src.config import Settings
from src.llm import build_embeddings
from src.models import TravelFact


class TravelFactStore:
    def __init__(self, session_id: str, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.session_id = session_id
        self.settings.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.settings.chroma_dir))
        self.collection = self.client.get_or_create_collection(
            name=f"tripforge_{_safe_collection_name(session_id)}"
        )
        self.embeddings = build_embeddings(self.settings)

    def add_facts(self, facts: list[TravelFact]) -> int:
        if not facts:
            return 0

        documents = [f"{fact.title}\n{fact.summary}" for fact in facts]
        embeddings = self.embeddings.embed_documents(documents)
        ids = [str(uuid4()) for _ in facts]
        metadatas = [
            {
                "session_id": self.session_id,
                "source": fact.source,
                "title": fact.title,
                "category": fact.category,
                "metadata_json": json.dumps(fact.metadata, ensure_ascii=False),
            }
            for fact in facts
        ]
        self.collection.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
        return len(facts)

    def search(self, query: str, limit: int = 6) -> list[TravelFact]:
        embedding = self.embeddings.embed_query(query)
        result = self.collection.query(query_embeddings=[embedding], n_results=limit)
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        facts: list[TravelFact] = []
        for document, metadata in zip(documents, metadatas, strict=False):
            title = metadata.get("title") or document.splitlines()[0]
            facts.append(
                TravelFact(
                    source=metadata.get("source", "chroma"),
                    title=title,
                    summary=document,
                    category=metadata.get("category", "travel"),
                    metadata=json.loads(metadata.get("metadata_json", "{}")),
                )
            )
        return facts


def _safe_collection_name(session_id: str) -> str:
    value = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in session_id)
    return value[:48] or "default"