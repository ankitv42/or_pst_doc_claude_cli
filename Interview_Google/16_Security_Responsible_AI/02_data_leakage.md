# Data Leakage in AI Systems

## What Is It? (Plain English)

Data leakage in AI means a system accidentally reveals information it should keep private. This is different from an intentional data breach — leakage happens because AI systems learn patterns from their training data, and those patterns can sometimes be extracted by a clever adversary asking the right questions. It is the difference between a safe with a weak lock (intentional breach) and a safe whose combination was accidentally written on a nearby whiteboard (leakage).

AI systems face unique leakage risks that traditional software does not. A trained language model has, in a sense, compressed its training data into billions of numeric weights. Under the right prompting conditions, that compressed data can sometimes be uncompressed — reproduced verbatim. A medical AI trained on patient records might, if prompted carefully, complete a partial patient name with real medical details. This is not speculation; researchers have demonstrated GPT models reproducing memorised training examples including email addresses and names.

The leakage problem exists at two stages: during training (what the model memorised) and during inference (what the deployed system reveals through its responses). Both stages require different mitigations, and both are active concerns for any production AI system handling sensitive data.

## How It Works

```
TYPES OF DATA LEAKAGE IN AI SYSTEMS
═══════════════════════════════════════════════════════════════════

1. TRAINING DATA MEMORISATION
   Training data → Model weights → Extraction attack
   
   Attacker prompts: "My phone number is 555-..."
   Vulnerable model: "...555-1234 (completing memorised pattern)"
   
   Risk factors:
   - Small training dataset (less data → more per-example memorisation)
   - Repeated examples (duplicated data memorised more strongly)
   - Large models (more capacity → more exact memorisation)

2. RAG KNOWLEDGE BASE LEAKAGE
   User query → Retrieval → LLM includes PII in response
   
   KB contains: "Patient John Smith DOB 1985-03-12 diagnosed with..."
   User asks: "What do you know about John Smith?"
   Vulnerable system: returns the full patient record

3. MODEL INVERSION ATTACK
   Attacker repeatedly queries model to reconstruct training data
   │
   ├── Query: "Complete this partial employee record: Name=J.S., Salary=$..."
   ├── Query 1000x with variations
   └── Reconstruct: likely training examples from response patterns

4. MEMBERSHIP INFERENCE ATTACK
   Attacker asks: "Was this specific record in your training data?"
   Method: measure model confidence on known vs unknown records
   Higher confidence on a specific record → likely in training data

LEAKAGE AT TRAINING VS INFERENCE:
─────────────────────────────────────────────────────────────
Training-time leakage:
  Source: training dataset contains PII
  Mechanism: model memorises exact training examples
  Detection: canary tokens (planted fake records); if model repeats
             a canary, you know memorisation happened
  Mitigation: data cleaning before training, differential privacy,
              deduplicate training data

Inference-time leakage:
  Source: RAG knowledge base or system prompt contains PII
  Mechanism: LLM includes retrieved PII in its response
  Detection: output scanning for PII patterns
  Mitigation: PII scrubbing from KB, output filtering, access control
═══════════════════════════════════════════════════════════════════
```

## Why Google Cares About This

Google handles some of the world's most sensitive personal data — search history, emails, health queries, location history. Any AI feature that ingests this data to improve itself or provide personalised responses must guarantee it cannot be used to extract information about one user when another user queries the system. This is both an ethical requirement and a legal one: GDPR Article 25 mandates "privacy by design," which includes technical measures to prevent LLM memorisation of personal data. For senior AI engineers, demonstrating awareness of these risks — and knowing the mitigation techniques — is table stakes in interviews.

## Interview Questions & Answers

### Q1: What is training data memorisation, and what conditions make it worse?

**Answer:** Training data memorisation is when a language model learns to reproduce verbatim sequences from its training data rather than just learning statistical patterns. If a model was trained on a dataset that contained the sentence "Alice Johnson's phone number is 555-0192," a sufficiently memorised model can be prompted to reproduce it: if you feed it "Alice Johnson's phone number is" it completes with "555-0192."

This is not a bug in the model — it is an emergent property of how language models are trained. The model learns to predict the next token given context, and for rare or unique sequences (which PII tends to be), exact reproduction is the highest-probability prediction.

Conditions that increase memorisation severity:

**Dataset size relative to model size.** A model with 70 billion parameters trained on 100 billion tokens has one parameter per ~1.4 tokens — high capacity relative to data. A model with 7 billion parameters trained on 10 trillion tokens has much less capacity per training token. Smaller models on larger datasets memorise less.

**Data duplication.** Carlini et al. (2023) showed that examples duplicated in training data are memorised at dramatically higher rates. If a specific email address appears 100 times in the training set, the model is 100x more likely to reproduce it than if it appeared once. Data deduplication before training is one of the most effective memorisation mitigations.

**Sequence length and uniqueness.** Long, unique sequences (a specific person's medical history) are more likely to be memorised verbatim than short, common phrases. PII is inherently unique and often appears in structured formats (email: `name@domain.com`, SSN: `XXX-XX-XXXX`) that the model can easily reproduce.

**Model capability.** Larger, more capable models memorise more. GPT-4 memorises more training data than GPT-2, even controlling for training set size.

Detection method: plant canary tokens — unique fake records that should never appear in outputs. If a model ever outputs a canary, you have confirmed memorisation of training data.

---

### Q2: What is the difference between membership inference attacks and model inversion attacks?

**Answer:** Both are privacy attacks on trained models, but they aim at different information.

**Membership inference attacks** answer the question: "Was this specific record in the training data?" The attacker does not need to reproduce the record — they just need a yes/no answer. The technique exploits the observation that models tend to have higher confidence (lower loss) on examples they were trained on versus examples they have not seen.

```python
# Simplified membership inference concept
def is_in_training_data(model, candidate_record: str) -> bool:
    # Models are "more confident" about training examples
    loss_score = model.compute_loss(candidate_record)
    # Compare to average loss on known non-training examples
    threshold = 0.35  # learned from shadow model attack
    return loss_score < threshold   # low loss → likely in training set
```

A practical attack: an adversary trains a "shadow model" on a dataset similar to the target model's training set. They can then estimate what loss threshold separates training members from non-members. This is an existential threat for models trained on medical records, private communications, or proprietary code.

**Model inversion attacks** aim to reconstruct training examples, not just determine membership. The attacker repeatedly queries the model with variations of a partial record and observes the outputs to reconstruct what the training data looked like.

```
Membership inference:     Model inversion:
"Was John Smith in        "Reconstruct what John Smith's
training data? Yes/No"    record contained"

Attack: single query      Attack: thousands of queries
        + loss analysis           + reconstruction algorithm
Result: binary            Result: approximate training example
```

Mitigations:
- Differential privacy during training (adds calibrated noise to gradients, provides formal privacy guarantees)
- Prediction confidence capping (do not return exact probabilities, return top-k labels only)
- Rate limiting and anomaly detection on query patterns
- Model output perturbation (add small noise to outputs)

---

### Q3: How can a RAG system leak sensitive data? Describe an attack scenario and the corresponding defence.

**Answer:** A RAG system's knowledge base often contains sensitive internal documents. If access control is not implemented correctly at the retrieval layer, a query can surface documents that the querying user should not see.

**Attack scenario:** An enterprise RAG chatbot ingests HR documents into a shared ChromaDB collection. The collection contains: (1) general HR policies (all employees can read), (2) salary bands (managers only), (3) performance improvement plans (HR only). All 10,000 documents are embedded into the same vector collection with no metadata about access level.

A regular employee asks: "What is the salary range for a Principal Engineer?" The retriever does a semantic search and returns the closest matching chunk, which happens to be from a restricted salary document. The LLM includes this in its response. The employee now has salary information they were not supposed to see.

```
SECURE RAG ARCHITECTURE:
═══════════════════════════════════════════════════════════════
User Query + User Identity
      │
      ▼
Query Rewriter
      │
      ▼
Retriever ──► Vector DB ──► Filter by access_level metadata
      │            │
      │            │ Only returns chunks WHERE
      │            │ access_level IN user.permissions
      ▼
Reranker (cross-encoder)
      │
      ▼
LLM with retrieved context
      │
      ▼
Output Scanner (PII detection)
      │
      ▼
Response
═══════════════════════════════════════════════════════════════
```

Defences:
1. **Document-level access control at ingest:** Tag every document chunk with its access level metadata when ingesting into the vector store.
2. **Query-time filtering:** When retrieving, filter by `access_level IN [user.roles]` before returning any results. ChromaDB, Weaviate, and Pinecone all support metadata filtering.
3. **Separate collections:** Use separate ChromaDB collections for different access tiers. Public documents in one collection, sensitive documents in another. Only retrieve from collections the user has access to.
4. **Output PII scanning:** Run the final response through a PII detector before returning it. Block responses that contain names + job titles + salaries.

---

### Q4: What is differential privacy, and when would you use it in an AI system?

**Answer:** Differential privacy (DP) is a mathematical framework that provides formal, quantifiable privacy guarantees. The core idea: a computation is differentially private if the probability of any output is nearly the same whether or not any single individual's data is included. This means no query result can reveal whether a specific person's data was in the dataset.

Formally: a mechanism M is ε-differentially private if for all datasets D and D' that differ by one record, and all possible outputs S:

```
P[M(D) ∈ S] ≤ e^ε × P[M(D') ∈ S]

Where ε (epsilon) is the privacy budget:
  ε < 1  → strong privacy (lots of noise added)
  ε = 1  → moderate
  ε > 10 → weak privacy (little noise)
```

In practice, DP is implemented by adding calibrated Gaussian or Laplace noise to sensitive computations. In ML training, DP-SGD (Differentially Private Stochastic Gradient Descent) clips individual gradients and adds noise before summing them, preventing the model from memorising any individual training example.

```python
# DP-SGD: the key modification to standard SGD
# Standard SGD: gradient = sum(individual_gradients)
# DP-SGD:
for batch in training_data:
    grads = [compute_gradient(model, example) for example in batch]
    clipped_grads = [clip(g, max_norm=C) for g in grads]    # bound sensitivity
    noisy_sum = sum(clipped_grads) + Gaussian(0, σ²)        # add noise
    model.update(noisy_sum / batch_size)
```

Use differential privacy when:
- Training on genuinely sensitive data (medical records, financial data, private communications)
- You need a formal privacy guarantee for regulatory or audit purposes
- You can accept a reduction in model utility (DP always reduces accuracy — the trade-off is quantifiable)

DP is not appropriate when you need maximum model accuracy and the data is already anonymised or non-sensitive. For ORCA, which uses synthetic inventory data, DP is overkill. For a healthcare AI trained on real patient records, DP is a requirement.

---

### Q5: How do you audit an AI system for data leakage risk? What does that process look like?

**Answer:** A data leakage audit for an AI system should cover three areas: the training data pipeline, the inference pipeline, and the model itself.

**Training data audit:**
1. Inventory all data sources. Document where each training example came from and its sensitivity classification (public, internal, confidential, PII).
2. Run automated PII scanning over the training dataset before it reaches the model. Tools: Presidio (Microsoft), SpaCy NER, regex patterns for common PII formats.
3. Check for data duplicates. Deduplicate the training set — duplicate examples are memorised at higher rates.
4. Plant canary tokens. Insert 50-100 unique fake records (fake names, phone numbers, etc.) that should never appear in model outputs. After training, red-team the model by trying to extract canaries.

**Inference pipeline audit (RAG system):**
1. Access control review: for every document in the knowledge base, is there a metadata access level? Is retrieval filtered by user permissions?
2. Red-team retrieval: ask queries designed to surface documents from other users or higher access tiers.
3. Output scanning: run 1,000 sample queries and scan all outputs for PII patterns (names, emails, phone numbers, SSNs).

```
AUDIT CHECKLIST:
─────────────────────────────────────────────────────────────
Training pipeline:
  □ PII scan and removal before training
  □ Data deduplication
  □ Canary token insertion and post-training extraction test
  □ Differential privacy applied (if required by policy)

RAG knowledge base:
  □ Every document tagged with access level
  □ Query-time filtering by access level implemented
  □ Red-team test: can user A see user B's documents?

Inference outputs:
  □ Output PII scanner on all LLM responses
  □ Rate limiting and anomaly detection on queries
  □ Audit log of all queries and responses (for incident investigation)
  □ No secrets in system prompt
```

**Model audit:**
1. Membership inference test: gather a set of examples you know were in training and a set you know were not. Check if the model has statistically higher confidence on training examples.
2. Extraction test: use known prompt templates that have been shown to elicit memorised content (ask the model to "repeat verbatim").
3. For fine-tuned models: test if fine-tuning data (which may be smaller and more easily memorised) can be extracted.

The output of this audit should be a risk register: each identified risk with its likelihood, impact, and recommended mitigation.

## Key Points to Say in the Interview

- "Training data memorisation is worse for duplicated data, small datasets relative to model size, and more capable models."
- "Membership inference determines if a record was in training; model inversion reconstructs what training records looked like."
- "RAG leakage is primarily an access control problem — every document chunk needs a metadata access level, and retrieval must filter by it."
- "Differential privacy provides formal mathematical privacy guarantees — add calibrated noise to gradients during training."
- "Canary tokens are the most practical way to detect training memorisation: plant fake records, then test if the model can be made to reproduce them."
- "PII must be scanned and removed before ingestion — both before embedding into vector databases and before fine-tuning datasets."
- "Inference-time leakage is often more exploitable than training-time leakage because it is more targeted and repeatable."

## Common Mistakes to Avoid

- Assuming that a model that has never been trained on personal data is safe — indirect ingestion through RAG or tool outputs can still leak.
- Using a shared vector collection without access control metadata — trivially exploitable for cross-user data leakage.
- Treating data anonymisation as equivalent to privacy — re-identification attacks can often undo simple anonymisation.
- Not logging LLM inputs and outputs — makes it impossible to investigate a suspected leakage incident.
- Over-relying on the LLM to refuse to output PII — models can be jailbroken; output scanning is a more reliable defence.

## Further Reading

- [Extracting Training Data from Large Language Models (Carlini et al. 2021)](https://arxiv.org/abs/2012.07805) — foundational paper demonstrating verbatim training data extraction from GPT-2
- [Deep Learning with Differential Privacy (Abadi et al. 2016)](https://arxiv.org/abs/1607.00133) — the DP-SGD paper that established differentially private training for neural networks
- [Microsoft Presidio](https://microsoft.github.io/presidio/) — open-source PII detection and anonymisation library for Python
