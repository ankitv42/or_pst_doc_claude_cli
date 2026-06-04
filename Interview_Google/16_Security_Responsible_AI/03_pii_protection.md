# PII Protection in AI Systems

## What Is It? (Plain English)

Personally Identifiable Information (PII) is any data that can be used to identify a specific individual — names, email addresses, phone numbers, Social Security numbers, dates of birth, location data, IP addresses, and increasingly, AI-generated inferences about individuals (health status, political views, financial situation). The challenge with AI systems is that PII can enter the system through many channels: users provide it in queries, documents contain it, databases store it, and tool outputs may include it.

Protecting PII in an AI context means more than just keeping passwords secure. It means ensuring that a language model cannot be prompted to reveal what it knows about a specific person, that a RAG system's knowledge base cannot be used to surface private records about individuals, and that the model itself has not memorised PII from training data in ways that can be extracted.

The stakes are high: GDPR fines can reach 4% of global annual revenue (Google was fined €50 million in 2019 for GDPR violations). HIPAA violations in healthcare can result in criminal charges. Beyond compliance, a PII leak from an AI system can permanently damage user trust in ways that take years to recover from.

## How It Works

```
PII PROTECTION LAYERS IN AN AI SYSTEM
═══════════════════════════════════════════════════════════════
                    DATA FLOW
Raw data → [PII Detection] → [Masking/Pseudonymisation] → Storage/Processing
                                       │
                                       ▼
                          AI Pipeline (no raw PII)
                                       │
                                       ▼
                               [Output Scanning]
                                       │
                                       ▼
                                  User Response


PII DETECTION METHODS:
──────────────────────────────────────────────────────────────
Method          | Example              | Recall | Precision
───────────────────────────────────────────────────────────────
Regex patterns  | SSN: \d{3}-\d{2}-\d{4} | Medium | High
NER (spaCy)     | "John Smith" → PERSON | High   | Medium
ML classifier   | fine-tuned BERT       | High   | High
Rule-based      | email domain checks   | Low    | Very High

MASKING STRATEGIES:
──────────────────────────────────────────────────────────────
Redaction:       "John Smith earned $120k" → "[PERSON] earned $120k"
Tokenisation:    "John Smith" → "PERSON_0042" (reversible with key)
Pseudonymisation:"John Smith" → "Alex Johnson" (consistent fake name)
Generalisation:  "Age 34" → "Age 30-40"
Suppression:     Remove PII-containing records entirely
═══════════════════════════════════════════════════════════════
```

## Why Google Cares About This

Google processes PII at a scale that no other organization matches — billions of search queries, emails, documents, and location pings daily. Every AI feature Google ships that touches user data must have a PII protection story baked in from the start, not added as an afterthought. Regulators globally (EU GDPR, California CCPA, India DPDPA, China PIPL) have specific requirements for AI systems that process personal data. A senior AI engineer joining Google will be expected to ask "does this handle PII correctly?" as a reflex, not a checklist item.

## Interview Questions & Answers

### Q1: How do you detect PII in free-text data? What are the trade-offs between regex, NER, and ML-based approaches?

**Answer:** PII detection is fundamentally a named entity recognition (NER) problem — identifying spans of text that correspond to personal information. The three main approaches trade off precision, recall, coverage, and operational complexity.

**Regex patterns** work well for structured PII with consistent formats: email addresses, phone numbers, Social Security numbers, credit card numbers, dates. They are fast, deterministic, and easy to audit.

```python
import re

PII_PATTERNS = {
    "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    "phone_us": r'\b(\+1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b',
    "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
    "credit_card": r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
}

def scan_text_regex(text: str) -> dict[str, list[str]]:
    results = {}
    for pii_type, pattern in PII_PATTERNS.items():
        matches = re.findall(pattern, text)
        if matches:
            results[pii_type] = matches
    return results
```

Problem: regex fails for unstructured PII. "John Smith lives in Seattle" requires understanding that "John Smith" is a name and "Seattle" is a location — regex cannot do this.

**SpaCy NER** is a pre-trained model that identifies entities (PERSON, ORG, GPE, DATE, MONEY). It handles unstructured text well and has high recall for common entity types. The limitation: it was not specifically trained on PII, and it misses rare or non-Western names, unusual organisations, and domain-specific identifiers.

```python
import spacy

nlp = spacy.load("en_core_web_lg")

def scan_text_ner(text: str) -> list[dict]:
    doc = nlp(text)
    return [{"text": ent.text, "type": ent.label_, "start": ent.start_char}
            for ent in doc.ents
            if ent.label_ in {"PERSON", "GPE", "LOC", "ORG", "DATE"}]
```

**Fine-tuned ML classifiers** (BERT-based, or tools like Microsoft Presidio with ML components) achieve the best precision and recall. They can handle context — "Call Mike at the office" identifies "Mike" as PII even without a surname. They also handle multilingual PII. The cost is inference latency (~50-200ms per document) and the need for labelled training data.

Best practice: combine all three. Use regex for structured PII (fast, precise), NER for unstructured PII (moderate speed, high recall), ML classifier for high-stakes decisions (slower, highest accuracy). Microsoft's Presidio library implements this layered approach and is widely used in production.

---

### Q2: What is the difference between data masking, pseudonymisation, and anonymisation? When is each appropriate?

**Answer:** These three terms are often used interchangeably but have important legal and technical differences, especially under GDPR.

**Data masking** (also called redaction) replaces PII with a generic placeholder. It is irreversible by design. The original value is discarded.

```
Original: "Patient John Smith, DOB 1985-03-12, diagnosed with diabetes"
Masked:   "Patient [PERSON], DOB [DATE], diagnosed with diabetes"
```

Masking is appropriate when you need to share data for analysis but the actual values are irrelevant to the analysis (e.g., testing that a system correctly processes patient records — the real names don't matter).

**Pseudonymisation** replaces PII with a consistent substitute that allows re-linking to the original data using a separate key. GDPR explicitly recognises pseudonymisation as a security measure that reduces (but does not eliminate) risk. The key must be stored securely and separately from the pseudonymised data.

```
Original: "John Smith" (user_id: real_123)
Pseudonymised: "Alex Johnson" (user_id: pseudo_456)
Key table (stored separately, encrypted): real_123 → pseudo_456

Same person appearing in multiple records gets the same pseudonym,
preserving analytical utility while removing direct identifiability.
```

**Anonymisation** is irreversible removal or transformation of PII such that the individual cannot be re-identified — not by the data controller, not by anyone. GDPR does not apply to truly anonymised data. But true anonymisation is much harder than it appears — research has repeatedly shown that "anonymised" datasets can be re-identified by combining with other data sources (the Netflix Prize dataset was de-anonymised by cross-referencing with IMDb reviews).

```
Anonymisation techniques:
  k-anonymity: each record is indistinguishable from k-1 others
               on quasi-identifying attributes
  l-diversity:  k-anonymity + at least l distinct sensitive values
               in each equivalence class
  t-closeness:  distribution of sensitive attributes in each group
               matches overall distribution within threshold t
```

For AI systems: pseudonymise data before embedding into vector databases (allows re-linking for debugging while protecting production data). Mask data in logs and monitoring. Aim for anonymisation in published datasets and research.

---

### Q3: How do you build a RAG system that cannot be manipulated into revealing personal data about individuals?

**Answer:** The core principle is defence in depth — multiple independent layers, each of which alone would be insufficient but together make data exposure very difficult.

**Layer 1 — Ingest-time PII scanning and removal.** Before any document enters the vector database, run it through a PII detector. Mask or remove all PII found. The vector database should never contain raw PII if possible.

```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

def sanitise_before_ingest(text: str) -> str:
    """Remove PII before embedding into vector store."""
    results = analyzer.analyze(text=text, language='en')
    anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
    return anonymized.text

# In the ingest pipeline:
for doc in documents:
    clean_text = sanitise_before_ingest(doc.page_content)
    vectorstore.add_texts([clean_text])
```

**Layer 2 — Access control on retrieval.** Every document chunk gets a metadata field: `{"access_level": "public", "data_owner": "hr_dept", "contains_pii": false}`. Retrieval queries filter by access level matching the requesting user's permissions.

**Layer 3 — Query intent classification.** Before running retrieval, classify the user's query. Queries that appear to be asking about specific individuals ("What do you know about John Smith?", "Find records for employees named Sarah") should trigger additional scrutiny or be blocked.

```python
def is_pii_seeking_query(query: str) -> bool:
    """Detect queries that may be attempting PII extraction."""
    pii_query_patterns = [
        r"(what|tell me|show me).*(about|regarding)\s+(the\s+)?\w+\s+\w+",
        r"find\s+(all\s+)?(records|information|data)\s+for",
        r"who\s+is\s+\w+\s+\w+"
    ]
    return any(re.search(p, query, re.IGNORECASE) for p in pii_query_patterns)
```

**Layer 4 — Output scanning.** Run the LLM's generated response through a PII detector before returning it to the user. If any PII is detected in the output, block it, log the incident, and return a generic response.

**Layer 5 — Audit logging.** Log every query and response (with the response PII-scrubbed in the log itself). This enables incident investigation and demonstrates compliance to auditors.

The combination of these layers means an attacker would need to simultaneously bypass PII scrubbing at ingest, access control at retrieval, query filtering, and output scanning — a very high bar.

---

### Q4: What does GDPR require for AI systems that process personal data? What are the key engineering implications?

**Answer:** GDPR (General Data Protection Regulation) is the EU's comprehensive privacy law. For AI systems, the most important requirements are:

**Lawful basis for processing.** The system must have a legal reason to process personal data: user consent, contractual necessity, legitimate interest, or legal obligation. For an AI assistant that learns from user interactions, you typically need explicit consent.

**Data minimisation.** Collect only the data that is strictly necessary for the specified purpose. Engineering implication: avoid logging full user queries if aggregate statistics are sufficient. Do not embed personal details into vector databases unless they are essential to the retrieval task.

**Right to erasure (Right to be forgotten).** A user can request their data be deleted. Engineering implication: this is complex for AI systems because data may be embedded in model weights (hard to erase) and vector database chunks (easier to delete but requires re-embedding). You need a data map: where does each user's data live? For vector databases, you need to track which chunks came from which user and be able to delete them.

```python
def delete_user_data(user_id: str, vectorstore: Chroma):
    """Implement right to erasure for RAG knowledge base."""
    # Find all chunks belonging to this user
    results = vectorstore.get(
        where={"user_id": user_id}
    )
    if results["ids"]:
        vectorstore.delete(ids=results["ids"])
        logger.info(f"Deleted {len(results['ids'])} chunks for user {user_id}")
    
    # Also delete from primary database
    db.execute("DELETE FROM user_documents WHERE user_id = ?", (user_id,))
```

**Data protection by design and by default (Article 25).** Privacy must be built into the system architecture, not bolted on. Highest privacy settings must be the default. Engineering implication: the default should be not to log, not to retain, not to share — opt-in to data collection, not opt-out.

**Data Protection Impact Assessment (DPIA).** For high-risk AI processing (automated decision-making, large-scale profiling), a DPIA is required before deployment. ORCA's automated inventory reorder decisions would qualify as automated decision-making affecting a business, requiring documentation of the decision logic and human oversight mechanisms.

**Key engineering checklist for GDPR compliance:**
- Data map: know exactly where every piece of personal data lives
- Deletion mechanism: ability to delete data from all systems including vector DBs
- Consent management: capture and record consent, honour withdrawals
- Data minimisation: automated process to detect and remove unnecessary PII
- Breach notification: ability to detect and notify of breaches within 72 hours

---

### Q5: How would you implement a PII-safe logging system for an AI pipeline?

**Answer:** Logging is essential for observability and debugging, but raw AI logs are a PII minefield — they capture full user queries, LLM responses, and retrieved documents, all of which may contain personal information. A PII-safe logging system scrubs sensitive information before writing to log storage while preserving enough information for debugging.

The architecture: write to a fast, in-memory buffer that applies PII scrubbing before writing to durable storage. The scrubbing happens asynchronously to avoid adding latency to the request path.

```python
import logging
import re
from presidio_analyzer import AnalyzerEngine

analyzer = AnalyzerEngine()

class PIISafeFormatter(logging.Formatter):
    """Log formatter that scrubs PII before writing."""
    
    STRUCTURED_PATTERNS = {
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b': '[EMAIL]',
        r'\b\d{3}-\d{2}-\d{4}\b': '[SSN]',
        r'\b(\+1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b': '[PHONE]',
    }
    
    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        # Fast regex pass for structured PII
        for pattern, replacement in self.STRUCTURED_PATTERNS.items():
            message = re.sub(pattern, replacement, message)
        return message

# For query/response logging: hash user queries for correlation without storing raw content
import hashlib

def log_query_safely(user_id: str, query: str, response: str, run_id: str):
    query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
    response_pii_scrubbed = scrub_pii(response)
    logger.info(
        "pipeline_query",
        extra={
            "run_id": run_id,
            "user_id_hash": hashlib.sha256(user_id.encode()).hexdigest()[:16],
            "query_hash": query_hash,   # for correlation, not content
            "query_length": len(query),
            "response_scrubbed": response_pii_scrubbed,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
```

Additional safeguards:
- Set log retention policies: auto-delete logs containing any PII after 30 days
- Separate log streams: system performance logs (no PII) vs detailed debugging logs (PII-scrubbed, short retention)
- Encrypt logs at rest: even scrubbed logs may contain sensitive information
- Access control on log storage: not everyone who can access the application should access its logs
- Include log audit trails: who accessed the logs, when, for what purpose

## Key Points to Say in the Interview

- "PII protection requires multiple independent layers: detect at ingest, control at retrieval, filter at output."
- "Pseudonymisation preserves analytical utility while removing direct identifiability — GDPR recognises it as a risk reduction measure."
- "True anonymisation is very hard — k-anonymity, l-diversity, and t-closeness are the formal measures."
- "Right to erasure is an engineering challenge for AI systems: you need a data map and deletion mechanism for every system where user data lives, including vector databases."
- "Data protection by design means privacy defaults to maximum restriction — users opt-in to data collection, not opt-out."
- "Logging is a major PII risk: scrub before writing, hash user identifiers, set retention policies."
- "Microsoft Presidio is the production-ready open-source tool for PII detection and anonymisation in Python."

## Common Mistakes to Avoid

- Embedding raw PII into vector databases without scrubbing — the PII becomes very difficult to remove later.
- Treating regex-based PII detection as complete — it misses unstructured PII like names, which require NER.
- Not implementing right-to-erasure mechanisms before going to production — adding them retroactively is much harder.
- Logging raw user queries without PII scrubbing — logs are a frequent target in data breaches and often overlooked.
- Confusing pseudonymisation with anonymisation — GDPR still applies to pseudonymised data.

## Further Reading

- [Microsoft Presidio](https://microsoft.github.io/presidio/) — open-source PII detection and anonymisation tool, widely used in Python production systems
- [GDPR AI Guidance (European Data Protection Board)](https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-032021-use-personal-data-context-artificial_en) — official guidance on GDPR requirements for AI systems
- [k-Anonymity: A Model for Protecting Privacy (Sweeney 2002)](https://dl.acm.org/doi/10.1142/S0218488502001648) — foundational paper on formal anonymisation guarantees
