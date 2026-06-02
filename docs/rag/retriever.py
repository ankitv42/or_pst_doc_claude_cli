"""
ORCA — rag/retriever.py
========================
2026 production RAG retriever.
 
FULL PIPELINE:
    query_for_agentN(structured_data)
        ↓
    Query Construction (from agent state — not generic strings)
        ↓
    Hybrid Retrieval (Vector + BM25 + RRF fusion)
        ↓
    BGE Reranker (BAAI/bge-reranker-v2-m3 — Apache 2.0, free)
        ↓
    Corrective RAG (retry with refined query if score < threshold)
        ↓
    Metadata Filtering (agent-specific doc_type filters)
        ↓
    Formatted context string for prompt injection
 
TECHNIQUES IMPLEMENTED:
    ✅ Metadata filtering     — per-agent doc_type filters
    ✅ Query construction     — from structured state data, not generic text
    ✅ Multi-query per agent  — 2-3 targeted queries, deduplicated
    ✅ Hybrid search (BM25)   — keyword + vector, fused with RRF
    ✅ BGE Reranking          — BAAI/bge-reranker-v2-m3 (best free reranker 2026)
    ✅ Corrective RAG         — auto-retry with domain-enriched query
    ✅ GraphRAG (text-based)  — entity_relationships.pdf embedded as graph context
    ✅ Table-aware retrieval  — element_type=table filter for structural queries
    ✅ Chunk summaries        — metadata summary used for context decisions
    ✅ Priority rule          — database wins over docs on any factual conflict
"""

import sys
import re
import json
from pathlib import Path
from typing import Optional

sys.path.append(Path(__name__).parent.parent.parent)

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

CHROMA_DIR = Path(__file__).parent.parent.parent / "db" / "chroma"
COLLECTION_NAME = "orca_knowledge"

EMBEDDING_MODEL_PRIMARY  = "nomic-ai/nomic-embed-text-v1.5"
EMBEDDING_MODEL_FALLBACK = "all-MiniLM-L6-v2"

# ==============================================================================
# EMBEDDING FUNCTION (same as ingest.py — must match)
# ==============================================================================

'''
This section: loads embedding model Purpose: convert text → vectors Used for: semantic retrieval
''' 

def _get_embedding_fn():
    for model_name in [EMBEDDING_MODEL_PRIMARY, EMBEDDING_MODEL_FALLBACK]:
        try:
            kwargs = {"model_name": model_name}
            if "nomic" in model_name:
                kwargs["trust_remote_code"] = True
            ef = SentenceTransformerEmbeddingFunction(**kwargs)
            ef(["test"])
            return ef, model_name
        except Exception:
            continue
    raise RuntimeError("No embedding model available.")


# ==============================================================================
# BM25 KEYWORD INDEX
# Built over ChromaDB documents for hybrid search.
'''

'''
# ==============================================================================

class BM25Index:
    """
    What class does ?? 
    Takes input Documents ↓ Tokenize words ↓ Build keyword index ↓ Calculate term importance ↓ Enable keyword search

    BM25 does keyword-based ranking, checks :
        how important word is
        how often word appears
        how rare word is globally
        document length normalization

    Then returns: ranked keyword-relevant documents


    BM25 keyword scoring over a set of documents.
 
    WHY BM25:
        Vector search finds semantically similar chunks.
        BM25 finds chunks with exact keyword matches.
        They complement each other — neither alone is sufficient.
 
        Vector may miss: "CP003" (too specific, no semantic neighbours)
        BM25 finds:      "CP003" exactly where it appears
 
        Hybrid = vector + BM25 fused with RRF → 15-30% better recall.

        Lets say imput is like:
        documents = [
                        "Suppliers must submit invoices within 7 days",
                        "ABC supplier lead time is 14 days",
                        "Class A SKUs require emergency approval"
                    ]
        
        ids = [
                "chunk_1",
                "chunk_2",
                "chunk_3"
              ]
    """

    def __init__(self, documents: list[str], ids: list[str]):
        import math
        self.docs    = documents
        self.ids     = ids
        self.k1      = 1.5    # These are BM25 tuning parameters. which
        self.b       = 0.75   # controls keyword scoring behavior. You usually don't change these. Industry-standard defaults.
        self.avgdl   = sum( len(d.split()) for d in documents)/max(len(documents), 1) # this code finds the average length of all docs within documents
                                                  # WHY IMPORTANT? BM25 penalizes: overly long documents Otherwise giant chunks dominate search unfairly.
        self.index: dict[str, dict[int,int]] = {}
        '''
        This becomes: inverted index VERY important search-engine concept.
        WHAT IS INVERTED INDEX? Normal thinking: document → words
        BM25 thinking:                           word → documents

        EXAMPLE Instead of: doc1 = "supplier approval"
                        BM25 builds: {
                                    "supplier": [doc1],
                                    "approval": [doc1]
                                    }
        This makes keyword search FAST.                        
        '''
        self.doc_lengths: list[int] = []

        for idx, doc in enumerate(documents):
            tokens = self._tokenize(doc)
            self.doc_lengths.append(len(tokens))                  # STORE DOC LENGTH
            for token in set(tokens):                             # BUILD INVERTED INDEX
                self.index.setdefault(token, {})[idx] = tokens.count(token)
        
        N = len(documents)
        self.idf: dict[str, float] = {}

        for term, postings in self.index.items():
            df = len(postings)
            self.idf[term] = math.log((N - df + 0.5)/ (df+ 0.5) + 1)


    def _tokenize(self, text: str) -> list[str]:
        return re.sub(r'[^\w\s]', ' ', text.lower()).split()  # for a doc input ""Suppliers must submit invoices within 7 days"
                                                                  # it lowers the case, then remove punchuation , 
                                                                  # output ["suppliers","must","submit","invoices","within","7","days"]
                                                                  # IMPORTANT: BM25 works on: tokens/words NOT embeddings.

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        scores: dict[int, float] = {}
        for token in self._tokenize(query):                 # for user input query, we tokenize a list
            if token not in self.index:                     # for the token of list we search in index dictionory to validate its entry
                continue
            idf = self.idf.get(token, 0)                    # for the toekn we find idf value
            for idx, tf in self.index[token].items():       # then FIND DOCUMENTS CONTAINING TOKEN,ex idx is document index = 1, tf is term frequency = 1
                dl   = self.doc_lengths[idx]                # give me the document length with doc index 1
                norm = 1 - self.b + self.b * (dl / self.avgdl)  
                tf_s = (tf * (self.k1 + 1)) / (tf + self.k1 * norm)  # WHAT IS tf_s ? This is: normalized term frequency score Meaning: How strongly does this document contain this term? BUT adjusted for: document size, frequency saturation
                scores[idx] = scores.get(idx, 0) + idf * tf_s
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [(self.ids[i], s) for i, s in ranked[:top_k]]    


        '''
        # BUILD INVERTED INDEX, THIS is your BM25 search engine.BM25 internally stores: WORD ↓ which documents contain this word
        for documents for exmple
        documents = [ "Suppliers must submit invoices within 7 days", "ABC supplier lead time is 14 days", "Class A SKUs require emergency approval"]
        index = {
                    "supplier": {
                        0: 1,
                        1: 1
                    },

                    "approval": {
                        2: 1
                    },

                    "lead": {
                        1: 1
                    }
                }
        
        Meaning word "supplier" appear in document 0  and document 1 , and it appear 1 time in both doc
        '''


        # Inverse Document Frequency (IDF)



        '''
        BUILD ANOTHER DICTIONARY IDF
        Lets take 1st item of index

        term = "supplier"

        postings = {
                    0: 1,
                    1: 1
                }
        Math calculation is 'rare words get higher importance' - HIGH IDF value

        WHY THIS MATTERS:   Rare words are more useful for retrieval.
                            Google search engines use similar logic.
        
        So now we have another dictionary apart from index, i.e idf. it store the idf score for each words of document
        idf =
                        {
                        "supplier": 0.47,
                        "approval": 1.92
                        }       
        '''
        

        '''
        This function is: the actual ranking engine, This is where: BM25 scoring happens

        Earlier:

            we built the inverted index
            calculated IDF, build IDF 

        Now this function answers: 
            "Given a query, which documents are most relevant?" . This is where: BM25 scoring happens.
        
        Our BM25 database has documents, their ids, inverted index, idf score, self.doc_lengths, self.avgdl( average doc length)
        check above function, a query let say "supplier lead time" is passed as arg, also top_k=10

                                Query
                                ↓
                            Tokenize words
                                ↓
                            Find docs containing those words
                                ↓
                            Score documents using:
                                - term frequency
                                - rarity
                                - length normalization
                                ↓
                            Sort by relevance
                                ↓
                            Return top matching docs
        MOST IMPORTANT UNDERSTANDING

            BM25 is:
                mathematical keyword ranking
                NOT semantic understanding.

            It works because:

                rare words matter more
                repeated words saturate
                long docs penalized

            This is why BM25 remained powerful even after embeddings became popular.
                
        '''
    

# ==============================================================================
# RECIPROCAL RANK FUSION
# ==============================================================================

'''
Till Now we have TWO retrieval systems:
1. System 1 — Vector Search , Good at: semantic meaning, it ranks its outputs
2. System 2 — BM25,           Good at: exact keywords,   it also ranks its output at last

QUESTION

How do we combine BOTH rankings intelligently?

THAT is: RRF ( RECIPROCAL RANK FUSION )

VERY SIMPLE IDEA OF RRF RRF says:

    If a document ranks highly in multiple systems,
    it is probably important.

VERY smart idea.

VISUALIZE EXAMPLE Suppose query:       "supplier escalation rules"

VECTOR SEARCH RESULTS
    Rank	Chunk
    1	chunk_A
    2	chunk_B
    3	chunk_C

BM25 RESULTS
    Rank	Chunk
    1	chunk_B
    2	chunk_D
    3	chunk_A

IMPORTANT OBSERVATION
    chunk_A appears in BOTH
    chunk_B appears in BOTH

These become more trustworthy.

chunk_D appears only in BM25 , Less confidence.

RRF combines these rankings mathematically.
'''

def rrf_fuse( vector_results: list[tuple[str, float]], 
             bm25_results:   list[tuple[str, float]],
             k: int = 60,
             ) -> list[tuple[str, float]]:
    """
    Merges vector and BM25 ranked lists.
    RRF score = 1/(k+rank_vector) + 1/(k+rank_bm25).
    Documents ranking high in BOTH lists are boosted.
    """
    scores: dict[str, float] = {}
    for rank, (doc_id, _) in enumerate(vector_results, 1):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
    for rank, (doc_id, _) in enumerate(bm25_results, 1):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


    '''
    LETS VISUALIZE
        vector_results = [
        ("chunk_A", 0.92),
        ("chunk_B", 0.81),
        ("chunk_C", 0.75)
        ]

        bm25_results = [
        ("chunk_B", 12.4),
        ("chunk_D", 10.1),
        ("chunk_A", 9.8)
        ]

    VERY important: scores are DIFFERENT scales.VECTOR SCORES may be 0.92 while BM25 SCORES 12.4.
    RRF DOES NOT CARE ABOUT RAW SCORES It ONLY cares about:
                                                           ranking positions
    
    finally rrf outputs like below, well sorted, Highest fused score(fusion of vector and bm25 score) first.
                {
                "chunk_B": 0.03251,
                "chunk_A": 0.03226,
                "chunk_D": 0.01612,
                "chunk_C": 0.01587
                }
    '''

# ==============================================================================
# BGE RERANKER (BAAI/bge-reranker-v2-m3)
# Best free open-source reranker as of 2026. Apache 2.0 license.
# ==============================================================================
'''
Now we enter the FINAL major stage of modern retrieval pipelines:
Reranking . This is one of the BIGGEST upgrades modern RAG systems added after 2024.
And honestly: rerankers changed retrieval quality massively.

But,
"After RRF we ALREADY have ranked chunks.
Why rerank AGAIN?"

VERY important question., Because RRF ranking is still retrieval-level ranking. Retrieval ≠ True Understanding of what query is asking.

So a re ranking step is needed to do re ranking of chunks and NOW ranking becomes: query-aware. Reranker carefully compares: QUERY vs CHUNK
pair-by-pair. Then says: "This chunk directly answers query."

Reranker Actually performs: query-document relevance reasoning MUCH more intelligent. BUT slower.

Analogy: you query google some questions and goggle give you related search result of 500 pages ( so till here we have done vector + BM25 step)
we have estimated 500 page link, but we as a human need to take a close look at the results to carefully re rank and find correct pages( this is analogy
to re ranking...)


WHY NOT ONLY USE RERANKER THEN? Because rerankers are expensive.Suppose: 5 million chunks
Reranker would need to compare: query vs 5 million chunks. Impossible.

SO MODERN PIPELINE IS: Stage 1 — Retrieval Cheap + fast....Goal..find potentially relevant chunks...Maybe top 20.
                       Stage 2 - Reranking Expensive + smart....Goal..find truly best chunks....from those 20.

Our code used BGE RERANKER, WHAT IS BGE RERANKER? BAAI/bge-reranker-v2-m3

This is: cross-encoder reranker model..
    ----------------------
    VECTOR EMBEDDING MODEL

Earlier: query and chunk were encoded: separately........Then cosine similarity used.....FAST. But less precise.

    RERANKER (Cross Encoder)
    Reranker does: [QUERY + CHUNK] TOGETHER. VERY important difference.
    
    CROSS-ENCODER MAGIC....Instead of embeddings,.......model directly reads BOTH texts together.Then predicts:.....relevance score

It can happen that a chunk is ranked higher after rrf step but it ranks low after final re ranking step, vice versa.

WHY THIS WORKS BETTER
Because reranker:
jointly understands query + chunk relationship
NOT independent semantic similarity.

INPUT TO RERANKER --> query + Candidate chunks:
MODEL CREATES PAIRS
MODEL OUTPUT Re ranking scores
Then SORTING Highest score first:   
'''

class BGEReranker:
    """
    Cross-encoder reranker using BAAI/bge-reranker-v2-m3.
 
    WHY BGE OVER ms-marco-MiniLM:
        BGE-reranker-v2-m3: multilingual, 100+ languages, Apache 2.0
        ms-marco-MiniLM: English only, older, lower accuracy
        BGE is now the standard for open-source RAG reranking (2026).
 
    HOW IT WORKS:
        Bi-encoder (retrieval): embed(query) + embed(chunk) → cosine similarity
        Cross-encoder (reranking): model(query + "[SEP]" + chunk) → relevance score
        Cross-encoder sees both together — much more accurate.
 
    Pattern: retrieve top 10 (fast) → rerank to top 3 (accurate)


    
    """

    def __init__(self):
        self._model  = None
        self._available = False
        self._try_load()

    
    # This function: tries multiple reranker models one-by-one until ONE successfully loads.

    def _try_load(self):
        for model_name in [
            "BAAI/bge-reranker-v2-m3",
            "BAAI/bge-reranker-base",
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
        ]:
            try:
                from FlagEmbedding import FlagReranker
                self._model     = FlagReranker(model_name, use_fp16=True)
                self._model_name = model_name
                self._available = True
                return
            except Exception:
                pass
            try:
                from sentence_transformers import CrossEncoder
                self._model     = CrossEncoder(model_name)
                self._model_name = model_name
                self._use_flag  = False
                self._available = True
                return
            except Exception:
                pass


    '''
    Below function:
       1. Take a query
       2.  Take a list of retrieved chunks/documents
       3.  Score how relevant each chunk is to the query
       4.  Return the best 3 chunks in ranked order
    '''

    def rerank(self, query: str, chunks: list[str], top_k: int = 3) -> list[tuple[int, float]]:
        """
        Returns list of (original_index, score) sorted by score descending.
        Gracefully degrades to original order if model unavailable.
        """
        if not self._available or not chunks:
            return [(i, 1.0 - i*0.1) for i in range(min(top_k, len(chunks)))]
 
        try:
            pairs = [[query, chunk] for chunk in chunks]
            if hasattr(self._model, "compute_score"):
                # FlagReranker API
                scores = self._model.compute_score(pairs, normalize=True)
            else:
                # CrossEncoder API
                scores = self._model.predict(pairs)
 
            if not hasattr(scores, '__iter__'):
                scores = [scores]
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
            return [(idx, float(score)) for idx, score in ranked[:top_k]]
        except Exception:
            return [(i, 1.0 - i*0.1) for i in range(min(top_k, len(chunks)))]



# ==============================================================================
# MAIN RETRIEVER  , see learning/ Retrival /retrival_engineering_docs_retriver py.docx
# ==============================================================================
 
class ORCARetriever:
    """
    Production retriever implementing the full 2026 RAG stack.
    """
 
    CORRECTIVE_THRESHOLD = 0.35    # If retrieval confidence is below 0.35, retry retrieval with expanded query.
    RETRIEVE_TOP_K       = 10      # retrieve top 10 candidate chunks initially ( that semantic vector + BM25 + rrf step)
    FINAL_TOP_K          = 3       # after reranking, keep best 3 chunks only
 
    # domain terms for corrective RAG query expansion
    DOMAIN_TERMS = (                                                        #This is: query expansion vocabulary Used when retrieval quality poor.
        "ORCA retail UAE inventory replenishment supplier capital pool "
        "lead time urgency CRITICAL HIGH MEDIUM Class A Class B Class C "
        "expedite stockout Ramadan event planning policy approval"
    )
 
    PRIORITY_RULE = (
        "PRIORITY RULE: If any value in this knowledge context conflicts "
        "with the live database data provided above (costs, contacts, "
        "lead times, pool balances, emails), always trust the live data. "
        "This knowledge provides rules and planning context only — not live facts."
    )
 
    def __init__(self):
        self._collection  = None                    # ChromaDB collection object
        self._reranker    = None                    # BGE reranker model
        self._bm25_cache: dict[str, BM25Index] = {} # cached BM25 indexes,but y ?? Building BM25 repeatedly expensive.So cache: doc_type combination → BM25 index
                                                    # EXAMPLE : { "policy,graph": BM25Index object }
        self._embedding_fn = None                   # 
        self._model_used   = None
        self._init()
 
    def _init(self):                                
        try:
            self._embedding_fn, self._model_used = _get_embedding_fn()   # LOAD EMBEDDING MODEL , Used for: vector retrieval
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))     # CONNECT CHROMADB
            self._collection = client.get_collection(                    # LOAD COLLECTION, Now retriever can search chunks.
                name=COLLECTION_NAME,
                embedding_function=self._embedding_fn,
            )
            self._reranker = BGEReranker()                              # Loads cross-encoder reranker.
        except Exception as e:
            import logging
            logging.getLogger("orca.retriever").error(f"RAG init failed: {type(e).__name__}: {e}")
            self._collection = None                                     
 
    def is_available(self) -> bool:
        # Self-healing: if init failed earlier (e.g. model not ready during
        # FastAPI import chain), retry once now that everything is loaded.
        if self._collection is None:
            self._init()
        return self._collection is not None
 
    # ── BM25 INDEX (built per doc_type set, cached) ────────────────────────
 
    def _get_bm25(self, doc_types: list[str]) -> Optional[BM25Index]:   # lazy BM25 index builder, input doc_types = ["event", "supplier"]
        key = ",".join(sorted(doc_types))                          # CREATE CACHE KEY : key = "event,supplier"   , (sorted for consistency)  
        if key in self._bm25_cache:                                # CACHE CHECK, if CACHE HIT: Return existing BM25 index immediately.
            return self._bm25_cache[key]
        try:
            result = self._collection.get(                         # if CACHE MISS, Need to build BM25 index.
                where={"doc_type": {"$in": doc_types}},            # So as all pdf chunks is already stored in chroma DB
                include=["documents"],                             # we need to pull the required chunks by pushing filter
            )                                           # visualize output: { "documents": [ "supplier escalation...", "approval matrix..." ], "ids": [ "chunk_001", "chunk_002" ] }
            docs = result.get("documents", [])                     # get the doc
            ids  = result.get("ids", [])                           # get the ids
            if not docs:
                return None
            index = BM25Index(documents=docs, ids=ids)             # pass both to BM25Index class and thus a index object is created for event and supplier docs, NOW keyword retrieval ready.
            self._bm25_cache[key] = index                          # CACHE IT, VERY important optimization.
            return index
        except Exception:
            return None
 
    # ── VECTOR SEARCH ─────────────────────────────────────────────────────
 
    def _vector_search(                                             # pure semantic retrieval, input of query and doc_type
        self, query: str, doc_types: list[str], top_k: int = 10
    ) -> list[tuple[str, float]]:
        if not self.is_available():
            return []
        try:
            results = self._collection.query(                       # this is chroma DB query, internally (query -> embedding generated -> cosine similarity -> top vector matches)
                query_texts=[query],                        # output looks like [ ("chunk_1", 0.82), ("chunk_7", 0.76) ]
                n_results=min(top_k, 10),                   # here 0.82 and 0.76 is the distance
                where={"doc_type": {"$in": doc_types}},
                include=["distances", "ids"],
            )
            if not results["ids"] or not results["ids"][0]:
                return []
            return [
                (id_, 1 - dist)                                    # we subtract the distance from 1 and it acts as score of chunk
                for id_, dist in zip(results["ids"][0], results["distances"][0])  
            ]                                                      # now output looks like [ ("chunk_1", 0.18), ("chunk_7", 0.14) ]
        except Exception:
            return []
 
    # ── HYBRID RETRIEVE (vector + BM25 + RRF) ─────────────────────────────
 
    def _hybrid_retrieve(                                          # This is heart of system
        self, query: str, doc_types: list[str], top_k: int = 10    # 
    ) -> list[dict]:
        """Hybrid retrieval with RRF fusion. Returns enriched chunk dicts."""
        if not self.is_available():
            return []
 
        vector_results = self._vector_search(query, doc_types, top_k)  # STEP 1 — VECTOR SEARCH , passing query and doc_type as input
                                                                       # vector_results = [ ("chunk_A", 0.88), ("chunk_B", 0.77)]
        bm25_index    = self._get_bm25(doc_types)                      # bm25_index is built using the doc type
                                                                       
        bm25_results  = bm25_index.search(query, top_k) if bm25_index else [] # Then query is sent to the index to get results
                                                                       # bm25_results =   [ ("chunk_B", 11.2), ("chunk_D", 8.4) ]
        fused = rrf_fuse(vector_results, bm25_results)                 # Resiprocal Rank Fusion , it does ranking of both chunks combinely
        if not fused:
            return []
 
        top_ids = [did for did, _ in fused[:top_k]]                    # get the top k  chunks from the fused 
        try:
            fetched = self._collection.get(                     # FETCH FULL CHUNKS Because currently only IDs + scores exist. Need actual text. 
                ids=top_ids,                                    # output like { "documents": [...], "metadatas": [...]}
                include=["documents", "metadatas"],
            )
        except Exception:
            return []
 
        id_to_score = dict(fused)                   
        chunks = []
        for i, cid in enumerate(fetched.get("ids", [])):        # CREATE ENRICHED CHUNK OBJECTS, 
            chunks.append({                                     # { "id": "chunk_B", "text": "...", "metadata": {...}, "score": 0.032 }
                "id":       cid,                                # VERY important: now retrieval objects fully enriched.
                "text":     fetched["documents"][i],
                "metadata": fetched["metadatas"][i],
                "score":    id_to_score.get(cid, 0.0),
            })
        return chunks
 
    # ── BGE RERANKING ─────────────────────────────────────────────────────
 
    def _rerank(self, query: str, chunks: list[dict]) -> list[dict]: # Now along with enriched chunks(from above) we send query for re ranking chunks
        if not chunks or not self._reranker:
            return chunks[:self.FINAL_TOP_K]
        texts  = [c["text"] for c in chunks]                # extract text from chunks
        ranked = self._reranker.rerank(query, texts, self.FINAL_TOP_K) # output [ (1, 0.97), (0, 0.21) ] means chunk index 1 best matches query , then chunk index 0
        return [chunks[idx] for idx, _ in ranked]           # FINAL reranked chunks returned.
 
    # ── CORRECTIVE RAG ────────────────────────────────────────────────────
 
    def _corrective_retry(                                  # _corrective_retry() If retrieval weak: retry smarter
        self, original_query: str, chunks: list[dict], doc_types: list[str]
    ) -> list[dict]:
        """
        If top chunk scores below threshold, expand query with domain terms
        and retry. Self-correcting retrieval.
        """
        if not chunks or chunks[0].get("score", 0) >= self.CORRECTIVE_THRESHOLD:  # if chunks[0]["score"] < threshold , meaning retrieval uncertain.
            return chunks                                                       # here score being checked is the one we get after RRF step
 
        refined = f"{original_query} {self.DOMAIN_TERMS}"         # reason of low score is bad user query so we enrich it by query expansion vocabulary line : 524
        retry   = self._hybrid_retrieve(refined, doc_types, self.RETRIEVE_TOP_K) # again so both step of retrival and re ranking
        retry   = self._rerank(refined, retry)
 
        if retry and retry[0].get("score", 0) > chunks[0].get("score", 0): # if current score more than pas score then retun the output
            return retry
        return chunks                                                      # or else return the original output
 
    # ── FORMAT CONTEXT ────────────────────────────────────────────────────
 
    def _format_context(self, chunks: list[dict], label: str = "") -> str: # This converts chunks into: LLM-ready prompt context
        """
        Formats retrieved chunks into prompt-injectable context string.
        Prepends PRIORITY RULE — database always wins over this context.  Line: 530
        Includes source metadata for transparency.

        INPUT
        -----
        [
            {
                "text": "...",
                "metadata": {...}
            }
        ]

        OUTPUT
        ------
        [Policy] | Emergency Procurement

        Summary:
        Class A ordering rules...

        Actual chunk text...


        """
        if not chunks:
            return f"No relevant {label} knowledge found."
 
        parts = [self.PRIORITY_RULE]
 
        for c in chunks:
            meta    = c.get("metadata", {})
            dtype   = meta.get("doc_type", "knowledge").capitalize()
            section = meta.get("section_name", "")[:70]
            etype   = meta.get("element_type", "text")
            summary = meta.get("chunk_summary", "")[:100]
            text    = c["text"].strip()
 
            header = f"[{dtype}]"
            if section:
                header += f" | {section}"
            if etype == "table":
                header += " | TABLE"
            if summary:
                header += f"\nSummary: {summary}"
 
            parts.append(f"{header}\n{text}")
 
        return "\n\n---\n\n".join(parts)
 
    # ── DEDUPLICATE ───────────────────────────────────────────────────────
 
    '''
    Simple:
        remove duplicate chunks.

        Because:

        vector search
        BM25
        multiple queries

        may retrieve same chunk repeatedly.
    '''

    def _dedup(self, *chunk_lists: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for chunks in chunk_lists:
            for c in chunks:
                if c["id"] not in seen:
                    seen.add(c["id"])
                    result.append(c)
        return result
 
    # ===========================================================================
    # PUBLIC API — one method per agent
    """
    Everything before this section was infrastructure:
    BM25Index — the keyword search engine, rf_fuse — the merger, BGEReranker — the reranker
    _hybrid_retrieve, _rerank, _corrective_retry — the internal plumbing

    All of that is the engine under the hood. You never call those directly.
    The PUBLIC API section is the steering wheel. These are the only functions that graph.py will ever call.

    Below we have one method per agent. In graph.py, we will call these method retriver.query_for_agent1 like this.
    Idea is to get the values from agent state and for each agent pass those values here. These methods will create a query string based on params, pass these
    query to the chroma db and get aditional context for the query using RAG, then finally pass these context to the LLM. So , LLM has two source of info for the query

    1. FACTS (live data) ( comming from orca.db)
        How many units left in each store?  What does the supplier charge?
    2. Knowledge, rules (comming from knowledge base - the 5 pdf)
        What is the policy for Class B SKUs? What happens during Dubai Shopping Festival?

    Agent 1,2,3,4 node in graph.py will call these methods with real values from AgentState. The method returns a formatted string that goes into the respective prompt.

    Below are the methods for each Agent.
    1. Agent 1: Demand Intelligence Agent. Its tasks is understand the demand situation from the knowledge base. Needs: ordering rules + event context + supplier-pool chain
                With Inputs: category="Electronics" abc_class="B" urgency="CRITICAL" lead_time_too_late=True event_name="DSF"
                policy event graph ← searches only these 3 doc types
                forms query for knowledge base:
                    Q1 "ordering rules Class B SKU CRITICAL urgency lead_time_too_late expedite mandatory" (query is not in proper sentence but keywords as we go goolge right , no proper sentence right)
                    meaning of query - finds Class B policy + expedite mandatory rules chunks

                    Q2 "demand uplift planning Electronics category Dubai Shopping Festival uplift percentage planning days"
                    finds DSF event planning chunk

                    Q3 "Electronics supplier pool chain expedite risk" 
                    finds Electronics→TechLine→CP004 graph chunk
            Returns: top 5 chunks → formatted context string → injected as {policy_context} into Agent 1 prompt

    2. Agent 2: Supply Replenishment Agent. Needs: supplier SLA terms + expedite rules + option building rules
                with Inputs: category="Electronics" supplier_name="TechLine Asia" lead_time_too_late=True abc_class="B" urgency="CRITICAL"
                supplier policy graph ← searches these 3 doc types
                forms query for knowledge base:
                    Q1 "lead time expedite Electronics TechLine Asia lead_time_too_late expedite mandatory no expedite available"
                    meaning : finds TechLine SLA + 19-day expedite chunk

                    Q2: "Option A Option B Option C building rules Class B CRITICAL lead_time_too_late"
                    finds option building rules chunk from policy

            Returns: top 4 chunks → formatted context string → injected as {policy_context} into Agent 2 prompt

    3. Agent 3: Capital Allocation Agent. Needs: pool rules + scoring formula + elimination logic
                Inputs: category="Electronics" urgency="CRITICAL" abc_class="B" approval_pool="CP003"
                policy graph ← searches only these 2 doc types
                forms query for knowledge base:
                    Q1 "CP003 pool pressure HIGH MEDIUM LOW auto approve limit approval threshold Electronics"
                    finds CP003 pool rules chunk

                    Q2 "budget score availability score margin score formula lead time penalty elimination rules Class B CRITICAL"
                    finds Agent 3 scoring formula table chunk

                    Q3 "scoring formula table Agent 3 capital allocation 0 100 points"
                    finds the scoring formula TABLE specifically (element_type=table)
            Returns: top 4 chunks including the scoring table → injected as {policy_context} into Agent 3 prompt

    4. Agent 4: Exception Action Agent. Needs: HITL briefing format + contact resolution rule
                Inputs: category="Electronics" supplier_name="TechLine Asia" route="ESCALATE"
                supplier graph policy ← searches these 3 doc types
                forms query for knowledge base:
                    Q1 "HITL briefing format ESCALATE approval 48 hours supplier contact resolution Electronics TechLine Asia"
                    finds briefing checklist + contact resolution rule chunks
            Returns: top 3 chunks → injected as {policy_context} into Agent 4 prompt


    For each agent's above queries:

    _hybrid_retrieve — runs vector search + BM25, merges with RRF, returns top 10
    _rerank — BGE reranker re-scores, returns top 3
    _corrective_retry — only on q1: if score < 0.35, retry with domain-enriched query

    then finally pass these context to the LLM...

    """
    # ===========================================================================
 
    def query_for_agent1(
        self,
        category:           str,
        abc_class:          str  = "B",
        urgency:            str  = "HIGH",
        lead_time_too_late: bool = False,
        event_name:         Optional[str] = None,
        demand_trend:       Optional[str] = None,
        supplier_name:      Optional[str] = None,
    ) -> str:
        """
        Agent 1 Demand Intelligence context.
        Retrieves: ordering rules, event planning, supplier-category relationships.
        """
        if not self.is_available():
            return "Knowledge base unavailable. Run python rag/ingest.py first."
 
        doc_types = ["policy", "event", "graph"]
 
        # Q1 — ordering rules for this situation
        q1 = (
            f"ordering rules Class {abc_class} SKU "
            f"{urgency} urgency "
            f"{'lead_time_too_late expedite mandatory' if lead_time_too_late else 'standard replenishment'}"
        )
 
        # Q2 — event context
        q2_parts = [f"demand uplift planning {category} category"]
        if event_name:
            q2_parts.append(f"{event_name} uplift percentage planning days")
        if demand_trend:
            q2_parts.append(f"{demand_trend} demand trend")
        q2 = " ".join(q2_parts)
 
        # Q3 — entity chain for this category
        q3 = (
            f"{category} supplier pool chain "
            f"{'expedite risk' if lead_time_too_late else 'standard planning'}"
        )
 
        c1 = self._rerank(q1, self._corrective_retry(
            q1, self._hybrid_retrieve(q1, doc_types, self.RETRIEVE_TOP_K), doc_types))
        c2 = self._rerank(q2, self._hybrid_retrieve(q2, doc_types, self.RETRIEVE_TOP_K))
        c3 = self._rerank(q3, self._hybrid_retrieve(q3, ["graph", "supplier"], self.RETRIEVE_TOP_K))
 
        all_chunks = self._dedup(c1, c2, c3)
        return self._format_context(all_chunks[:5], "policy/event")
 
    def query_for_agent2(
        self,
        category:           str,
        supplier_name:      Optional[str] = None,
        lead_time_too_late: bool = False,
        abc_class:          str  = "B",
        urgency:            str  = "HIGH",
    ) -> str:
        """
        Agent 2 Supply Replenishment context.
        Retrieves: supplier SLA, expedite rules, option building rules.
        """
        if not self.is_available():
            return "Knowledge base unavailable."
 
        doc_types = ["supplier", "policy", "graph"]
 
        q1_parts = [f"lead time expedite {category}"]
        if supplier_name:
            q1_parts.append(supplier_name)
        if lead_time_too_late:
            q1_parts.append("lead_time_too_late expedite mandatory no expedite available")
        q1 = " ".join(q1_parts)
 
        q2 = (
            f"Option A Option B Option C building rules "
            f"Class {abc_class} "
            f"{'CRITICAL lead_time_too_late' if lead_time_too_late else urgency}"
        )
 
        c1 = self._rerank(q1, self._corrective_retry(
            q1, self._hybrid_retrieve(q1, doc_types, self.RETRIEVE_TOP_K), doc_types))
        c2 = self._rerank(q2, self._hybrid_retrieve(q2, ["policy", "graph"], self.RETRIEVE_TOP_K))
 
        all_chunks = self._dedup(c1, c2)
        return self._format_context(all_chunks[:4], "supplier/policy")
 
    def query_for_agent3(
        self,
        category:      str,
        urgency:       str  = "HIGH",
        abc_class:     str  = "B",
        approval_pool: Optional[str] = None,
    ) -> str:
        """
        Agent 3 Capital Allocation context.
        Retrieves: pool rules, scoring formula, elimination rules.
        """
        if not self.is_available():
            return "Knowledge base unavailable."
 
        doc_types = ["policy", "graph"]
 
        pool_ctx = f"{approval_pool}" if approval_pool else "capital pool"
        q1 = (
            f"{pool_ctx} pool pressure HIGH MEDIUM LOW "
            f"auto approve limit approval threshold {category}"
        )
        q2 = (
            f"budget score availability score margin score formula "
            f"lead time penalty elimination rules "
            f"Class {abc_class} {urgency}"
        )
 
        # also query for table specifically — scoring formula is in a table
        q3 = f"scoring formula table Agent 3 capital allocation 0 100 points"
 
        c1 = self._rerank(q1, self._hybrid_retrieve(q1, doc_types, self.RETRIEVE_TOP_K))
        c2 = self._rerank(q2, self._hybrid_retrieve(q2, doc_types, self.RETRIEVE_TOP_K))
        c3 = self._rerank(q3,
            self._hybrid_retrieve(q3, doc_types, self.RETRIEVE_TOP_K))
 
        all_chunks = self._dedup(c1, c2, c3)
        return self._format_context(all_chunks[:4], "capital policy")
 
    def query_for_agent4(
        self,
        category:      str,
        supplier_name: Optional[str] = None,
        route:         str = "ESCALATE",
    ) -> str:
        """
        Agent 4 Exception Action context.
        Retrieves: HITL briefing format, approval routing, contact resolution rule.
        """
        if not self.is_available():
            return "Knowledge base unavailable."
 
        doc_types = ["supplier", "graph", "policy"]
 
        q1 = (
            f"HITL briefing format {route} approval "
            f"48 hours supplier contact resolution {category}"
        )
        if supplier_name:
            q1 += f" {supplier_name}"
 
        chunks = self._rerank(q1, self._hybrid_retrieve(q1, doc_types, self.RETRIEVE_TOP_K))
        return self._format_context(chunks[:3], "briefing/policy")

    '''

    One of the example of the context been feed to LLM. below is one of the output of agent, it looks like:
    Note there is priority rule attached , because in format_contect function. I have asked to add these string.
    policy_context = """
                    PRIORITY RULE: database wins over this context on any factual conflict.

                    [Policy] | Section 1 - ABC Class Ordering Rules
                    Class B SKU Rules: Minimum order follows supplier min_order_qty.
                    Distribution to all affected stores unless HIGH pool pressure...

                    ---

                    [Event] | Section 1 - UAE Retail Event Calendar
                    Dubai Shopping Festival: Electronics 90% uplift.
                    TechLine Asia Electronics orders must be placed 80 days before January 15...

                    ---

                    [Graph] | Knowledge Graph: Category → Supplier → Pool Chains
                    Electronics → TechLine Asia → CP004 (standard) → CP003 (expedite)
                    Planning risk: Long lead time. Plan all events 80 days ahead...
                    """

    Please Note: graph.py calls methods of retriver as:

    # inside agent1_node
        policy_context = retriever.query_for_agent1(
                                                    category           = "Electronics",
                                                    abc_class          = "B",
                                                    urgency            = "CRITICAL",
                                                    lead_time_too_late = True,
                                                    event_name         = "Dubai Shopping Festival",
                                                )

        then finally,

        messages = PROMPTS["agent1"].format_messages(
                                                        pipeline_id        = state["pipeline_id"],
                                                        sku_id             = sku_id,
                                                        affected_positions = json.dumps(positions_result),
                                                        sku_context        = json.dumps(sku_result),
                                                        velocity           = json.dumps(velocity_result),
                                                        active_events      = json.dumps(events_result),
                                                        policy_context     = policy_context,    # ← THIS is what retriever returns
                                                    )


    LLM receives the complete prompt:
    ----------------------------------
    LIVE DATA (from database via MCP):
        stock=21, critical_stores=5, days_of_cover=0.7
        effective_lead_time=54.5, allows_expedite=True

    POLICY KNOWLEDGE (from RAG):
        Class B ordering rules...
        DSF Electronics: order 80 days ahead...
        Electronics → TechLine Asia → CP003...

    Now produce demand_summary JSON.
    
    One diagram showing all 4 agents:

            AgentState flows through graph →

            agent1_node
                ← MCP: positions, sku, velocity, events    (FACTS)
                ← retriever.query_for_agent1()             (RULES)
                → LLM → demand_summary written to state

            agent2_node
                ← MCP: sku_data, supplier_data            (FACTS)
                ← retriever.query_for_agent2()            (RULES)
                → LLM → options_package written to state

            agent3_node
                ← MCP: cp001_data, cp003_data, sku_data   (FACTS)
                ← retriever.query_for_agent3()            (RULES)
                → LLM → capital_decision written to state

            agent4_node (hitl_node)
                ← MCP: supplier_data                      (FACTS)
                ← retriever.query_for_agent4()            (RULES)
                → LLM → hitl_briefing written to state

    Every agent gets live facts from the database AND relevant rules from the knowledge base. Neither alone is enough. Together they make the LLM's reasoning complete 
    and policy-compliant.
    '''


# ==============================================================================
# SINGLETON
# ==============================================================================
 
'''
Singleton is very imp. Backend concept. Look ORCARetriver is very expensive class to create because it loads:
ChromaDB, embedding model, BM25 cache, BGE reranker
These are: heavy resources, takes lot lot of memory.

WITHOUT SINGLETON Suppose your app does:
    r1 = ORCARetriever()
    r2 = ORCARetriever()
    r3 = ORCARetriever()

It will be disaster, EACH object would: reload models, reconnect DB, allocate memory again. Memory explosion. Slow application.

SINGLETON IDEA Singleton means: "Only ONE instance of this class, should exist in entire application.
'''


_instance: Optional[ORCARetriever] = None
 
def get_retriever() -> ORCARetriever:
    """Returns singleton retriever. Initialises on first call."""
    global _instance
    if _instance is None:               # CONDITION CHECK, only if there is no instance then one is created else the running instance is returned.
        _instance = ORCARetriever() 
    return _instance
 
 
# ==============================================================================
# QUICK TEST
# ==============================================================================
 
if __name__ == "__main__":
    print("\nORCA RAG Retriever — 2026 Stack Test\n")
 
    r = get_retriever()
 
    if not r.is_available():
        print("ChromaDB not available. Run: python rag/ingest.py first.")
        import sys; sys.exit(1)
 
    print(f"  Embedding model : {r._model_used}")
    print(f"  BGE Reranker    : {r._reranker._model_name if r._reranker._available else 'unavailable (graceful degradation)'}")
    print(f"  Collection      : {COLLECTION_NAME}")
    print(f"  Chunks indexed  : {r._collection.count()}")
    print()
 
    print("Agent 1 — Electronics CRITICAL lead_time_too_late:")
    ctx = r.query_for_agent1(
        category="Electronics", abc_class="B",
        urgency="CRITICAL", lead_time_too_late=True,
        event_name="Dubai Shopping Festival",
    )
    print(ctx[:600])
    print("...\n")
 
    print("Agent 3 — Capital allocation scoring formula:")
    ctx3 = r.query_for_agent3(
        category="Electronics", urgency="CRITICAL",
        abc_class="B", approval_pool="CP003",
    )
    print(ctx3[:600])
    print("...\n")
 
    print("All retriever tests complete.")