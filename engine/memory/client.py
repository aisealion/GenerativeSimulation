"""Single Graphiti instance for the whole process, connected to Neo4j.

Graphiti needs an LLM (entity/fact extraction, community summaries) and an
embedder (semantic search) of its own, separate from the fisher agent's
decision-making calls in llm_agents.py — this is Graphiti's own internal
plumbing, not something the fisher characters ever see or trigger. Both are
configurable via the same 'provider/name' convention llm_agents.py uses for
FISHER_MODEL, so the same LITELLM_API_KEY / OLLAMA_HOST already set up for
Stage 2 covers this too.
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from graphiti_core import Graphiti
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_client import OpenAIClient

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")

LITELLM_PROXY_BASE_URL = "https://llm.uod.otago.ac.nz/v1"
DEFAULT_MEMORY_LLM_MODEL = "litellm/Kimi-K2.5"
DEFAULT_MEMORY_EMBED_MODEL = "litellm/text-embedding-3-small"

# Neo4j vector indices are created with a fixed dimension up front — this
# must match what the configured embed model actually returns. Extend this
# as new embed models get used; an unknown model falls back to OpenAI's
# text-embedding-3-small default (1536) since that's the most likely case.
EMBEDDING_DIMS = {
    "text-embedding-3-small": 1536,
    "nomic-embed-text": 768,
    "nomic-embed-text:latest": 768,
}


def _resolve_provider(model_spec):
    """Same 'provider/name' convention as llm_agents.FISHER_MODEL, resolved
    to the (model_name, base_url, api_key) an OpenAI-compatible client needs."""
    provider, _, name = model_spec.partition("/")
    if provider == "litellm":
        return name, LITELLM_PROXY_BASE_URL, os.environ["LITELLM_API_KEY"]
    if provider == "ollama":
        ollama_host = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
        base = ollama_host if ollama_host.startswith("http") else f"http://{ollama_host}"
        return name, f"{base}/v1", "ollama"
    raise ValueError(
        f"unrecognized provider {provider!r} in {model_spec!r} — expected 'litellm/...' or 'ollama/...'"
    )


def _build_graphiti():
    llm_model, llm_base_url, llm_api_key = _resolve_provider(
        os.environ.get("MEMORY_LLM_MODEL", DEFAULT_MEMORY_LLM_MODEL)
    )
    embed_model, embed_base_url, embed_api_key = _resolve_provider(
        os.environ.get("MEMORY_EMBED_MODEL", DEFAULT_MEMORY_EMBED_MODEL)
    )

    llm_config = LLMConfig(api_key=llm_api_key, model=llm_model, base_url=llm_base_url)
    llm_client = OpenAIClient(llm_config)
    embedder = OpenAIEmbedder(
        OpenAIEmbedderConfig(
            api_key=embed_api_key,
            embedding_model=embed_model,
            base_url=embed_base_url,
            embedding_dim=EMBEDDING_DIMS.get(embed_model, 1536),
        )
    )
    # Unused by write.py/query.py (they bypass graphiti.search()'s reranking
    # entirely — see query.py's docstring), but Graphiti's constructor builds
    # one unconditionally, defaulting to needing OPENAI_API_KEY if not given
    # explicitly. Reuse the same LLM config so it never becomes a second
    # place needing its own credentials.
    cross_encoder = OpenAIRerankerClient(llm_config)

    return Graphiti(
        uri=os.environ["NEO4J_URI"],
        user=os.environ["NEO4J_USER"],
        password=os.environ["NEO4J_PASSWORD"],
        llm_client=llm_client,
        embedder=embedder,
        cross_encoder=cross_encoder,
    )


graphiti = _build_graphiti()
_indices_ready = False

# The neo4j async driver's connections are bound to whichever event loop was
# running when they were opened. write.py/query.py each call in from sync
# code (this whole codebase is sync) — calling asyncio.run() separately per
# call would open and tear down a fresh loop every time, but the *same*
# graphiti/driver instance is reused across all of them, so the second call
# would hand the driver's already-open connections to a loop they were never
# opened on ("Future attached to a different loop"). One persistent loop for
# the process's whole lifetime avoids that.
_loop = None


def run_async(coro):
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    return _loop.run_until_complete(coro)


async def ensure_indices():
    """The episode_content fulltext index and friends must exist before
    write.py/query.py can use them. Building the Graphiti client itself
    (above) doesn't touch the network — the neo4j driver connects lazily —
    but this call does, so it's deferred to first real use (awaited inside
    write.py/query.py's own asyncio.run(), not at import time) rather than
    run eagerly on import, which would make importing this module hang
    whenever Neo4j isn't reachable (e.g. simulate.py running on Aoraki,
    where the memory layer is intentionally not deployed yet)."""
    global _indices_ready
    if not _indices_ready:
        await graphiti.build_indices_and_constraints()
        _indices_ready = True


# Round numbers, not wall-clock time, are what matters for validity windows
# here — this fixed epoch just gives Graphiti's datetime-typed reference_time
# a monotonic value that preserves round ordering. Shared by write.py (sets
# reference_time) and query.py (filters "as of round N").
_EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)


def round_reference_time(round_num):
    return _EPOCH + timedelta(days=round_num)
