"""
ORCA — rag/ingest.py
=====================
2026 RAG ingestion pipeline using Docling + HybridChunker + nomic embeddings.
 
PIPELINE STAGES:
 
1. DOCUMENT PARSING (Docling):
   - Parses PDFs preserving tables, headers, nested sections, footnotes
   - Outputs DoclingDocument — structured representation of the whole doc
   - Tables kept as structured units, not flattened to broken text
   - Section hierarchy preserved: H1 → H2 → H3 → paragraph
   - Page numbers, coordinates, element types all captured
 
2. SEMANTIC + STRUCTURAL CHUNKING (HybridChunker):
   - HierarchicalChunker: splits at section boundaries, keeps tables whole
   - Token-aware: chunks sized for the embedding model's context window
   - Each chunk carries: headings path, page number, element type
   - Overlap between adjacent chunks for boundary coverage
   - This is WHY Docling exists — naive splitters destroy structure
 
3. METADATA ENRICHMENT:
   - doc_type: policy | supplier | event | graph | reasoning
   - agent_relevance: which agents query this doc
   - heading_path: full breadcrumb ["Section 1", "ABC Class Rules"]
   - element_type: text | table | heading
   - page_number: for citation
   - section_name: immediate parent section
 
4. EMBEDDING (nomic-embed-text-v1.5):
   - Better than all-MiniLM-L6-v2 for structured business text
   - 768-dimensional vectors (vs 384 for MiniLM)
   - Handles longer context windows
   - Free, open source, Apache 2.0
   - Falls back to all-MiniLM-L6-v2 if nomic not available
 
5. STORAGE (ChromaDB):
   - Persisted to disk at db/chroma/
   - Cosine similarity metric
   - Metadata stored alongside vectors for filtering
 
Usage:
    python rag/ingest.py              # ingest all 5 PDFs
    python rag/ingest.py --reset      # clear and re-ingest
    python rag/ingest.py --verify     # test retrieval quality only
"""
import sys
import json
import argparse
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

# paths
DOCS_DIR   = Path(__file__).parent.parent.parent / "docs"
CHROMA_DIR = Path(__file__).parent.parent.parent / "db" / "chroma"

COLLECTION_NAME = "orca_knowledge"
 
# Embedding model — nomic is better for business text
# Falls back to all-MiniLM if nomic not available

EMBEDDING_MODEL_PRIMARY  = "nomic-ai/nomic-embed-text-v1.5"
EMBEDDING_MODEL_FALLBACK = "all-MiniLM-L6-v2"

# ==============================================================================
# DOCUMENT REGISTRY
# Maps PDF filename → metadata injected into every chunk from that document
# agent_relevance tells retriever which agents should query this doc
# ==============================================================================

DOCUMENTS = {
    "supplier_sla.pdf": {
        "doc_type":        "supplier",
        "title":           "ORCA Supplier SLA and Planning Rules",
        "agent_relevance": "2,4",
    },
    "event_playbook.pdf": {
        "doc_type":        "event",
        "title":           "ORCA Event Playbook and Demand Uplift Data",
        "agent_relevance": "1,2",
    },
    "capital_pools.pdf": {
        "doc_type": "policy",
        "title" : "ORCA Capital Pool Structure and Approval Rules",
        "agent_relevance": "3,4",
    },
    "replenishment_policy.pdf": {
        "doc_type":        "policy",
        "title":           "ORCA Replenishment Policy and Decision Framework",
        "agent_relevance": "1,2,3,4",
    },
    "entity_relationships.pdf": {
        "doc_type":        "graph",
        "title":           "ORCA Entity Relationships and Agent Reasoning Patterns",
        "agent_relevance": "1,2,3,4",
    },
}


# ==============================================================================
# EMBEDDING FUNCTION — nomic with fallback
# ==============================================================================

def get_embedding_fn(verbose: bool = True):
    """
    Returns ChromaDB-compatible embedding function.
    Tries nomic-embed-text-v1.5 first (better quality, 768-dim).
    Falls back to all-MiniLM-L6-v2 (384-dim) if nomic not cached.
    """
    for model_name in [EMBEDDING_MODEL_PRIMARY, EMBEDDING_MODEL_FALLBACK]:
        try:
            kwargs = {"model_name": model_name}
            if "nomic" in model_name:
                kwargs["trust_remote_code"] = True # The nomic model needs a special permission flag (trust_remote_code) because it runs custom code from the internet
            ef = SentenceTransformerEmbeddingFunction(**kwargs)
            
            # test it actually loads
            ef(["test"])

            if verbose:
                print(f"  Embedding model : {model_name}")
            return ef, model_name
        except Exception as e:
            if verbose:
                print (f" {model_name} unavailable ({type(e).__name__}) — trying fallback ")
    
    raise RuntimeError("No embedding model available. Install sentence-transformers.")



# ==============================================================================
# DOCLING PARSING + HYBRID CHUNKING
# ==============================================================================

# This is the “data preparation” stage before embeddings + vector DB.
def parse_and_chunk_pdf(pdf_path: Path, base_metadata: dict) -> list[dict]:
    """
    Parses a PDF with Docling and chunks with HybridChunker.
 
    Docling preserves:
        - Table structure (not flattened to broken text), Section hierarchy (H1 > H2 > H3 > paragraph), Page numbers, Element types (table, text, heading, figure)
 
    HybridChunker:
        - Applies HierarchicalChunker first (section boundaries), Then token-aware sizing for the embedding model, Keeps tables as atomic units — never splits mid-row
        - Overlap between chunks for boundary coverage
 
    Returns list of chunk dicts ready for ChromaDB insertion.

    PDF -> Docling parses structure properly -> HybridChunker splits intelligently -> Creates clean chunks -> Metadata enrichment -> Clean vector-ready objects -> Ready for ChromaDB

    Real world analogy:

    
    Imagine you're reading a 50-page supplier SLA PDF. You extract a chunk of text — "Payment terms: Net 30 days".

    page_number → page 12
    headings → ["Terms & Conditions", "Payment"]
    origin → "table_cell" ← this chunk came from inside a table, not a paragraph
    So origin is the document structure type of where the text lived before it became a chunk. It's useful for filtering — e.g., "only search table chunks" or "ignore footer chunks."  

    """
    try:
        from docling.document_converter import DocumentConverter # using docling bcz PyPDFLodaer() simply extract raw text.table reduced to txt etc etc,
        from docling.chunking import HybridChunker               # Docling preserves this structure. VERY important in enterprise RAG.
    except ImportError:
        raise ImportError("docling not installed. Run: pip install docling")
    
    print(f"    Parsing {pdf_path.name} with Docling...")
    # Creates parser object.
    # This reads the PDF and creates: structured document containing hierarchy, tables, sections, metadata etc
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import PdfFormatOption

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False          # our PDFs are digital, no OCR needed
    pipeline_options.do_table_structure = True  # keep table parsing

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options
            )
        }
    )
    result = converter.convert(str(pdf_path))
    
    doc = result.document                                   # doc contains structured representation.Not plain text.VERY important concept.

    print(f"    Chunking with HybridChunker...")
    chunker = HybridChunker(tokenizer="sentence-transformers/all-MiniLM-L6-v2",  # Smart splitting engine.This tokenizer is NOT generating embeddings. It is only: counting tokens
                            max_token=512,      # Why? Because embedding models have token limits. Example: max 512 tokens max 1024 tokens Chunker must know: “How many tokens is this text?”
                            merge_peers=True)   # This means: small neighboring chunks can merge together. Without this: you may get tiny useless chunks    
    chunks_raw = list(chunker.chunk(doc))       # very imp line. convert Structured document into Multiple semantic chunks, 
                                                # Each chunk: meaningful, section aware, token-aware
    chunks = []

    for i, chunk in enumerate(chunks_raw):
        text = chunk.text.strip()
        if not text or len(text) < 30:  # VERY smart production logic. Why? Some chunks may be: empty useless noise broken OCR Skipping improves vector DB quality
            continue

        # extract rich metadata from Docling chunk
        headings = []
        if hasattr(chunk, "meta") and chunk.meta:                        # Checking: “Does chunk contain metadata?” Because some chunks may not.
            if hasattr(chunk.meta, "headings") and chunk.meta.headings:  # Checking: Does chunk containing metadata has headings
                headings = [h for h in chunk.meta.headings if h]         # Within chunk there be multiple headings preserve hierachy , [ "Financial Report", "Risk Analysis", "Market Risks" ]
            page_num = getattr(chunk.meta,"page_no", None)               # extract page no of that chuck      
            origin =chunk.meta.origin if hasattr(chunk.meta, "origin") else None # 
        else:
            page_num = None
            origin   = None

        # determine element type from content
        # tables have pipe characters or tab-separated structure

        element_type = "text"                                           # Detect Element Type 
        if "|" in text or text.count("|") > 3:
            element_type = "table"
        elif text.isupper() and len(text) < 100:
            element_type = "heading"
        
        section_name = headings[-1] if headings else "general"         # Gets most specific heading.
        heading_path = " > ".join(headings) if headings else ""        # ex Creates: Annual Report > Finance > Revenue
                                                                    # SUPER useful for: debugging, filtering, retrieval

        chunk_id = f"{pdf_path.stem}__chunk_{i:04d}"  # Unique Chunk ID, VERY important. Every chunk must have unique ID in vector DB.

        chunk_metadata = {
            **base_metadata,
            "chunk_index":   i,
            "section_name":  section_name[:100],
            "heading_path":  heading_path[:200],
            "element_type":  element_type,
            "page_number":   page_num or 0,
            "doc_file":      pdf_path.name,
        }

        chunks.append({
            "id":       chunk_id,
            "text":     text,
            "metadata": chunk_metadata,
        })
    
    
    return chunks

# ==============================================================================
# CHROMADB CLIENT AND COLLECTION
# ==============================================================================

"""
# Create storage folder if missing -> Connect to ChromaDB -> Return database client

Think of it like:

SQL world:
connection = mysql.connect(...)

Chroma world:
client = chromadb.PersistentClient(...)

The “client” is your connection object to the vector database.

"""
def get_client():
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))

'''
Below function:

Vector DB Collection Management: Below function handles: collection lifecycle, embedding configuration, similarity metric, reset/rebuild workflows.

Get ChromaDB client -> (Optional) delete old collection -> Create or fetch collection -> Attach embedding function -> Configure vector similarity metric -> Return collection object

Think of a collection like:
        SQL → table
        MongoDB → collection
        ChromaDB → vector collection

args
1. client       -> Database connection object. chromadb.PersistentClient(...)
2. embedding_fn -> This is the embedding model/function. OpenAIEmbeddingFunction(...), This function converts text → vectors.
3. reset=False  -> optional boolean parameter.VERY common in RAG, Sometimes you want: Delete old embeddings -> Rebuild vector DB from scratch (scenario- case of updated PDFs, changed embedding model, changed chunking strategy. old vectors become invalid. so need rebuild)

Collection object is your main interface for: insert, query, delete, update, search
'''




def get_collection(client, embedding_fn, reset: bool = False):
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f" Deleted existing collection: {COLLECTION_NAME} ")
        except Exception as e:
            print(f"Collection deletion failed: {e}")
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"}, # HNSW = Hierarchical Navigable Small World, Purpose: search millions of vectors quickly, "space": "cosine" means defines: similarity metric How vectors are compared.
    )


# ==============================================================================
# CHUNK SUMMARIES (advanced tip)
# Store a summary alongside each chunk for better retrieval
# ==============================================================================

'''
This is actually a VERY modern RAG engineering technique.
Most beginners only store: chunk text

But advanced systems now also store: summaries, keywords, synthetic questions, entities alongside chunks.
This improves retrieval quality significantly.

your code is implementing contextual chunk summaries

This function does: Chunk text ↓ Generate mini-summary ↓ Store summary in metadata ↓ Use later during retrieval/reranking

Why This Exists:
Imagine a chunk: The company recorded a 14% increase in quarterly
                 revenue due to expansion into Southeast Asian markets...

Instead of always reading entire chunk,
retrieval system can quickly inspect:  "14% revenue increase from Southeast Asia expansion"

Much faster for:
    reranking
    filtering
    context selection

Modern RAG Trend (2025–2026),Good RAG systems increasingly store:
    {
   "text": "full_chunk",
   "summary": "short_summary",
   "keywords": [...],
   "questions": [...]
    }

Because retrieval quality matters more than raw vector similarity now.



contextual retrieval, Modern RAG increasingly works like:
Vector retrieval
      ↓
Summary inspection
      ↓
Reranking
      ↓
Context selection



NOT just:

vector similarity only
'''
def _summarise_chunk(text: str, element_type: str) -> str:
    """
    Generates a short summary string for the chunk.
    Stored as metadata — retrieved alongside the full chunk.
    Useful for: deciding whether to include the full chunk in context.
 
    For tables: extracts header row as summary.
    For text: takes first sentence.

    for table like :
    
    Product ID | Product Name | Category | Price | Stock
    101 | iPhone 15 | Phones | 799 | 20
    102 | Dell XPS | Laptops | 1299 | 12

    function return : 
    [TABLE] Product ID | Product Name | Category | Price | Stock

    for text input:
    ORCA uses Agentic RAG to retrieve relevant retail data and reason over it. 
    It can answer questions about inventory, sales, and customer behavior.

    function return:
    ORCA uses Agentic RAG to retrieve relevant retail data and reason over it.
    -------------------
    Why this is useful in RAG

    Imagine your vector database stores a big chunk like this:

    {
    "content": "ORCA uses Agentic RAG to retrieve relevant retail data...",
    "metadata": {
        "summary": "ORCA uses Agentic RAG to retrieve relevant retail data and reason over it"
                }
    }

    When a user asks a question, your system can inspect the short summary first before deciding whether to send 
    the full chunk to the LLM.

    So instead of giving the model every giant chunk immediately, you have a compact description that helps 
    decide:
    Is this chunk relevant enough to include?

    """
    if element_type == "table":
        lines = text.split("\n")
        # first non-empty line is usually the header

        for line in lines:
            line = line.strip()
            if line and len(line) > 10:
                return f"[TABLE] {line[:150]}"
        return "[TABLE] tabular data"
        
    # for text: first sentence
    sentences = text.replace("\n", " ").split(".")
    for s in sentences:
        s = s.strip()
        if len(s)>20:
            return s[:200]
    return text[:200]




# ==============================================================================
# INGEST ONE DOCUMENT
# ==============================================================================


def ingest_document(collection, pdf_file:str, metadata:dict) -> int:
    pdf_path = DOCS_DIR / pdf_file
    if not pdf_path.exists():
        print(f"  WARNING: {pdf_file} not found. Run python rag/generate_docs.py first.")
        return 0 # meaning zero document ingested
    
    chunks = parse_and_chunk_pdf(pdf_path, metadata) 
    if not chunks:
        print(f"    No chunks extracted from {pdf_file}")
        return 0
    
    # check for existing
    ids = [c["id"] for c in chunks]
    existing = collection.get(ids = ids)
    existing_ids = set(existing["ids"])
    new_chunks = [ c for c in chunks if c["id"] not in existing_ids]

    if not new_chunks:
        print(f"    SKIP — already ingested ({len(chunks)} chunks)")
        return 0
    
    # add chunk summary to metadata (advanced tip)

    for c in new_chunks:
        c["metadata"]["chunk_summary"] = _summarise_chunk(c["text"], c["metadata"]["element_type"])

    collection.add(
        ids=       [c["id"]       for c in new_chunks],
        documents= [c["text"]     for c in new_chunks],
        metadatas= [c["metadata"] for c in new_chunks],
    )

    return len(new_chunks)


# ==============================================================================
# MAIN INGESTION PIPELINE
# ==============================================================================

def run_ingestion(reset: bool = False) -> None:
    print("\nORCA RAG — 2026 Ingestion Pipeline\n")
    print(f"  Parser         : Docling (IBM) — preserves tables + hierarchy")
    print(f"  Chunker        : HybridChunker — semantic + token-aware")
    print(f"  Storage        : ChromaDB at {CHROMA_DIR}")
    print(f"  Collection     : {COLLECTION_NAME}")
    print()

    embedding_fn, model_used = get_embedding_fn()
    client = get_client()
    collection = get_collection(client, embedding_fn, reset=reset)

    total_chunks = 0

    for pdf_file, metadata in DOCUMENTS.items():
        print(f" [{metadata['doc_type'].upper()}] {pdf_file}")
        n = ingest_document(collection, pdf_file, metadata)
        print(f"Stored {n} new chunks | agents: {metadata['agent_relevance']}")
        total_chunks += n
    
    final_count = collection.count()

    print(f"\n  Total chunks in collection : {final_count}")
    print(f"  New chunks added this run  : {total_chunks}")
    print(f"  Embedding model used       : {model_used}")
    print(f"\n  Ingestion complete.\n")


# ==============================================================================
# VERIFICATION — tests retrieval quality
# ==============================================================================

def verify_ingestion() -> None:
    print("  Verification — testing retrieval quality\n")
    embedding_fn, _ = get_embedding_fn(verbose=False)
    client     = get_client()
    collection = get_collection(client, embedding_fn)

    test_cases = [
        {
            "agent":  "Agent 1",
            "query":  "Class A SKU ordering rules CRITICAL urgency lead_time_too_late",
            "filter": {"doc_type": {"$in": ["policy", "graph"]}},
        },
        {
            "agent":  "Agent 2",
            "query":  "TechLine Asia Electronics lead time expedite premium planning window",
            "filter": {"doc_type": {"$in": ["supplier", "graph"]}},
        },
        {
            "agent":  "Agent 1",
            "query":  "Ramadan Dates demand uplift planning 75 days before",
            "filter": {"doc_type": {"$in": ["event", "graph"]}},
        },
        {
            "agent":  "Agent 3",
            "query":  "budget score availability score margin score formula elimination rules",
            "filter": {"doc_type": {"$in": ["policy", "graph"]}},
        },
        {
            "agent":  "Agent 4",
            "query":  "HITL briefing format supplier contact approval required 48 hours",
            "filter": {"doc_type": {"$in": ["graph", "policy"]}},
        },
        {
            "agent":  "Any",
            "query":  "scoring formula table Agent 3 capital allocation",
            "filter": {"element_type": {"$eq": "table"}},
        },
    ]


    scores = []
    for tc in test_cases:
        try:
            results = collection.query(
                query_texts=[tc["query"]],
                n_results=1,
                where=tc["filter"],
                include=["documents", "distances", "metadatas"],
            )
            if results["documents"] and results["documents"][0]:
                chunk    = results["documents"][0][0]
                meta     = results["metadatas"][0][0]
                distance = results["distances"][0][0]
                score    = round(1 - distance, 3)
                scores.append(score)
                quality  = "✅ GOOD" if score > 0.45 else "⚠  LOW"
                print(f"  [{tc['agent']}] {quality} (score={score})")
                print(f"    Query   : {tc['query'][:65]}...")
                print(f"    Source  : {meta.get('title','')} [{meta.get('doc_type','')}]")
                print(f"    Section : {meta.get('section_name','')[:65]}")
                print(f"    Type    : {meta.get('element_type','')}")
                print(f"    Summary : {meta.get('chunk_summary','')[:100]}")
                print()
            else:
                print(f"  [{tc['agent']}] ⚠ No result — check doc_type filter\n")
        except Exception as e:
            print(f"  [{tc['agent']}] Error: {e}\n")
 
    if scores:
        avg = sum(scores) / len(scores)
        print(f"  Average retrieval score: {avg:.3f} "
              f"({'✅ Good' if avg > 0.45 else '⚠ Needs tuning'})")
        

# ==============================================================================
# ENTRY POINT
# ==============================================================================
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ORCA RAG ingestion — 2026 stack")
    parser.add_argument("--reset",  action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
 
    if args.verify:
        verify_ingestion()
    else:
        run_ingestion(reset=args.reset)
        verify_ingestion()
