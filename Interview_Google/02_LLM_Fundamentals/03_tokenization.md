# Tokenization

## What Is It? (Plain English)

Language models don't read words — they read numbers. Tokenization is the process of converting raw text into a sequence of integer IDs that the model can process. But the unit of conversion is not a word (that would be too simple), and not a character (that would be too many numbers). Instead, modern LLMs use "subword" tokenization — splitting text into chunks that are somewhere between characters and full words, based on what's most frequent in the training data.

Think of it like Morse code: short, common letters get short codes (E is · , T is —), while rare patterns get longer codes. Similarly, a common word like "the" becomes a single token (one number), while a rare or complex word like "tokenization" might be split into ["token", "ization"] — two tokens. This approach gives a good balance between vocabulary size (not too many unique tokens) and sequence efficiency (not too many tokens per sentence).

Why does this matter practically? Because every AI API charges you per token. A 1,000-word document is roughly 1,300-1,500 tokens. A context window of 128K tokens can fit about 100,000 words — roughly a full novel. Code is more token-dense than English prose. Numbers are particularly inefficient — the number "12345678" might be split into ["123", "45", "678"] — three tokens for 8 digits. Understanding tokenization helps you estimate costs, understand why some inputs are "harder" for models to process, and debug unexpected model behaviors.

## How It Works

```
═══════════════════════════════════════════════════════════════
         BYTE PAIR ENCODING (BPE) — How Vocabulary is Built
═══════════════════════════════════════════════════════════════

Step 0: Start with character-level vocabulary
  Corpus: "low low lower newest newest widest"
  Initial vocab: {l, o, w, e, r, n, s, t, i, d, ' ', </w>}

Step 1: Count all adjacent byte pairs
  "l o" appears: 5 times (from "low" × 3, "lower" × 1, and parts)
  "o w" appears: 4 times
  "w e" appears: 2 times
  Most frequent pair: "l o" → merge into "lo"

Step 2: Replace merged pair in corpus, update vocab
  Corpus: "lo w  lo w  lo w er  ne w e st  ne w e st  w i d e st"
  New vocab: {lo, w, e, r, n, s, t, i, d, ' ', </w>}

Step 3: Repeat until target vocab size reached (e.g., 50,000)
  "lo w" → "low"
  "ne w" → "new"
  "new e" → "newe"
  "newe st" → "newest"
  ...

Final vocabulary after 50,000 merges:
  Common: "the", "is", "in", " the", " is" (space-prefixed variants)
  Medium: "ing", "tion", "##ing" (subword suffixes)
  Rare: split into characters

═══════════════════════════════════════════════════════════════
              TOKENIZATION EXAMPLE (GPT-4 / tiktoken)
═══════════════════════════════════════════════════════════════

Input: "Tokenization is fascinating!"

Tokens:    ["Token", "ization", " is", " fas", "cinating", "!"]
Token IDs: [5959,    1634,      374,   9555,   inating,    0  ]

Word boundaries are NOT preserved:
  "Tokenization" → 2 tokens  (Token + ization)
  "fascinating"  → 2 tokens  (fas + cinating)
  "!"            → 1 token

Input: "GPT-4 costs $0.03 per 1000 tokens"
Tokens: ["G","PT","-","4"," costs"," $","0",".","03"," per"," ","10","00"," tokens"]
Count: 14 tokens for a 7-word sentence (numbers are expensive!)

Input: "The cat sat on the mat."  (7 words)
Tokens: ["The", " cat", " sat", " on", " the", " mat", "."]
Count: 7 tokens (common English words ≈ 1 word = 1 token)

Rule of thumb: 1 token ≈ 0.75 words in English prose
               1 token ≈ 0.5 words in code
               Numbers and rare words: 2-4 tokens per "word"
```

**Tokenizer families:**
- **BPE (Byte Pair Encoding)**: Used by GPT-2, GPT-3, GPT-4 (tiktoken), LLaMA. Merges most frequent byte pairs iteratively.
- **WordPiece**: Used by BERT. Similar to BPE but selects merges based on maximizing likelihood rather than frequency. Words split at subword boundaries with ## prefix (e.g., "playing" → "play" + "##ing").
- **SentencePiece**: Used by T5, LLaMA (as an implementation framework). Language-agnostic, treats text as a byte stream — works well for multilingual models because it doesn't assume spaces delimit words (which isn't true in Chinese, Japanese, etc.).
- **Unigram LM**: Used in SentencePiece's unigram mode. Starts with a large vocabulary and prunes tokens with least impact on likelihood.

## Why Google Cares About This

Tokenization is a surprisingly deep topic that touches cost, quality, and fairness in LLMs. Google's own LLMs use SentencePiece, and the design of the tokenizer directly affects multilingual capability (does the model handle non-Latin scripts efficiently?), code generation quality (is code tokenized at meaningful boundaries?), and numerical reasoning (are numbers tokenized in a way that makes arithmetic difficult?). Senior candidates who understand tokenization can reason about why GPT-4 is worse at arithmetic than it is at prose, why some languages are more expensive to use LLMs with than others, and why LLM costs vary so dramatically by content type.

## Interview Questions & Answers

### Q1: What is Byte Pair Encoding (BPE) and why is it used instead of word-level or character-level tokenization?

**Answer:** Byte Pair Encoding was originally a data compression algorithm (1994) repurposed for NLP by Sennrich et al. (2016) for machine translation, and it's now the most widely used tokenization scheme for large language models. Understanding why it beats the alternatives requires first understanding what the alternatives get wrong.

**Word-level tokenization** (split on spaces, one token per word) has an unbounded vocabulary problem. English has hundreds of thousands of words, and when you add technical terms, names, misspellings, and words from other languages, the vocabulary grows without bound. A model trained with word-level tokenization cannot handle any word it didn't see during training — it has no mechanism for "unseen" words. Also, word-level vocabularies for multilingual models would be impractically large.

**Character-level tokenization** (one token per character, ~100 unique tokens for ASCII) solves the out-of-vocabulary problem — you can tokenize any text as a sequence of characters. But it creates very long sequences. "Hello, world!" is 13 characters = 13 tokens. At character level, a 100,000-word document would be ~600,000 tokens — hitting context window limits quickly and making self-attention (with its O(n²) complexity) extremely expensive.

**BPE** finds the sweet spot: it starts with character-level tokens, then iteratively merges the most frequent adjacent pairs. Common English words like "the," "is," "and" get merged into single tokens (frequent → merged early). Rare words or morphological variants like "unhappiness" get split into ["un," "happiness"] or ["un," "happy," "ness"] — meaningful subword units. The resulting vocabulary (typically 32K-128K tokens) is large enough to represent most common words as single tokens, but not so large that the embedding table dominates model size.

The BPE algorithm: (1) Initialize vocabulary with individual characters (or bytes, for byte-level BPE like GPT-2 uses). (2) Count frequency of all adjacent token pairs in the corpus. (3) Merge the most frequent pair into a new compound token. (4) Repeat steps 2-3 until the vocabulary reaches the target size. The merges are learned on the training corpus — so a tokenizer trained on code will merge programming-specific patterns differently from one trained on books.

The practical consequence: a token is not a word. "tokenization" → ["token", "ization"]; "ChatGPT" → ["Chat", "G", "PT"]; "antiestablishmentarianism" → multiple tokens. Always use the `tiktoken` library (for OpenAI) or the model's specific tokenizer to count tokens before estimating costs.

### Q2: Why are numbers and code tokenized inefficiently, and what are the practical implications?

**Answer:** Numbers and code are poorly handled by BPE tokenizers trained primarily on natural language text, and this has real consequences for model behavior, cost, and capability.

**Numbers**: BPE tokenizers break multi-digit numbers in unpredictable ways. "100" might be one token; "101" might be two tokens ["10", "1"]; "1001" might be three tokens ["100", "1"]. The key problem is that the tokenizer treats numbers as text sequences, not as mathematical quantities. There's no guarantee that adjacent numbers (e.g., "100" and "101") will be tokenized consistently. A model that sees "100" as one token and "101" as two tokens has to learn from context that these are numerically adjacent — a much harder learning task than if they were represented consistently.

This is a primary reason why LLMs struggle with multi-digit arithmetic. Adding "23756 + 48192" requires the model to first mentally "de-tokenize" these numbers, then add them, then re-tokenize the result — all in the attention mechanism, with no actual calculator. The tokenization boundary can fall in the middle of a number, making it harder for the model to "see" that 6 + 2 = 8 in the ones place. Models like Claude and GPT-4 now use code interpreters to work around this — execute Python code for arithmetic rather than doing it in the attention mechanism.

**Code**: Code is more token-dense than prose because identifiers, operators, and indentation each consume tokens. `calculate_inventory_reorder_quantity` (a single Python function name) might tokenize to ["calculate", "_", "inventory", "_", "re", "order", "_", "quantity"] — 8 tokens for one identifier. Indentation with spaces is particularly expensive: four spaces at the start of a Python line is up to 4 tokens. GitHub Copilot and other coding models use tokenizers specifically tuned for code (more code in the training corpus → code-specific merges happen earlier).

**Multilingual inequality**: Languages with larger scripts (Chinese, Japanese, Korean, Arabic) or less common in training data (Swahili, Yoruba) get shorter-length subwords than English. The result: processing the same information in English might cost 1x tokens, while the same information in Swahili might cost 3-5x tokens. This is both a cost inequity (non-English users pay more) and a capability inequity (less training data in those languages means the model is also less capable). Google's multilingual models try to address this with more balanced training data and cross-lingual tokenizers.

**Practical implications for system design**: (1) Always count tokens before sending to an LLM API — don't assume words ≈ tokens for non-English or code content. (2) For math-heavy tasks, route to models with tool use (calculator) rather than expecting the model to do arithmetic in its weights. (3) Be aware that the same information costs different amounts to process in different languages — factor this into cost estimates for international deployments.

### Q3: What is the difference between GPT's tokenizer and BERT's tokenizer, and why does it matter?

**Answer:** GPT uses byte-level BPE (tiktoken), while BERT uses WordPiece. The differences are subtle but matter for how you use each model.

**GPT's tiktoken (byte-level BPE)**: Operates at the byte level rather than character level — every byte (0-255) is in the vocabulary, so any UTF-8 text can be tokenized without "unknown token" issues. Spaces are included in tokens that follow them (" the" is one token, not " " + "the"), which preserves word boundary information efficiently. Tokens don't have special prefixes — you just see the subword strings.

**BERT's WordPiece**: Uses a ## prefix to mark subword continuations. "playing" tokenizes to ["play", "##ing"], where ## means "this token is a continuation of the previous token, not the start of a new word." This explicitly encodes word boundaries in the token representation. WordPiece also has an [UNK] token for truly unknown characters (a failing that byte-level BPE avoids). BERT's vocabulary was designed for English + some multilingual coverage; for multilingual BERT (mBERT), 110 languages are shared in a 119K vocabulary, which means rare languages get very fragmented tokenization.

**Why it matters:**
1. **Special tokens**: BERT requires explicit [CLS] and [SEP] tokens for its tasks; GPT uses special tokens like <|endoftext|> for document boundaries. When building prompts programmatically, you must use the right special tokens for the model.
2. **Max length**: BERT's standard maximum is 512 tokens (though extended variants exist). GPT models support much longer contexts. If your task involves long documents, BERT's limit is a hard constraint.
3. **Embedding vs. generation**: BERT's tokenizer is designed for a model that processes the full sequence bidirectionally and produces an embedding. GPT's tokenizer is designed for a model that generates tokens sequentially. If you're building a RAG system and want to embed documents for vector search, you'd use BERT's tokenizer with a BERT-family embedding model; if you want to generate text, you'd use GPT's tokenizer with a GPT-family generative model.

The practical rule: use the tokenizer that came with the model. Mixing tokenizers with models (BERT tokenizer → GPT model) will produce wrong results because the token IDs correspond to different tokens in each vocabulary. Hugging Face's `AutoTokenizer.from_pretrained()` loads the correct tokenizer automatically.

### Q4: How does tokenization affect LLM costs, and how do you estimate them accurately?

**Answer:** Every major LLM API charges per token, not per word or character. OpenAI charges differently for input tokens (what you send) vs. output tokens (what the model generates). Output tokens are typically more expensive (2-4x) because they require more compute — each output token requires a full forward pass through the model. Understanding this pricing structure lets you optimize costs intelligently.

**Estimating token counts:**
The rule of thumb "1 token ≈ 0.75 words" holds for typical English prose. But it fails significantly for:
- Code: 1 token ≈ 0.5 words (operators, symbols, indentation)
- Numbers: 1 token ≈ 0.33-0.5 "numeric units" (each multi-digit number splits into multiple tokens)
- Non-English languages: varies from 1.5x (French, German) to 4-5x (Arabic, Chinese) tokens per equivalent English word count
- Structured data (JSON, XML): often 1.5-2x prose due to delimiters, quotes, brackets

The only accurate way is to run your actual prompts through the model's tokenizer. For OpenAI models: `import tiktoken; enc = tiktoken.get_encoding("cl100k_base"); len(enc.encode(text))`. For Hugging Face models: `tokenizer = AutoTokenizer.from_pretrained("model_name"); len(tokenizer(text)["input_ids"])`.

**Cost optimization based on tokenization understanding:**
- **Compress JSON prompts**: `{"user_id": 123, "name": "Alice"}` has many delimiter tokens. If you're injecting structured data, consider a more compact representation when token budget is tight.
- **Avoid verbose few-shot examples**: Each example in a few-shot prompt costs the same every time it's sent. If you have 3 examples × 200 tokens each = 600 tokens per request × 1M requests/month = 600M tokens of example overhead alone. Compress or remove examples once the model has been fine-tuned on them.
- **Control output length**: Set `max_tokens` explicitly. An LLM that produces verbose 500-token answers when 100-token answers would suffice costs 5x more. Use instructions in your prompt to control verbosity ("Answer in 2-3 sentences maximum").
- **Use the right model**: GPT-4o-mini costs 30x less than GPT-4o per token. If the task works with GPT-4o-mini, there's no reason to use GPT-4o.

### Q5: What are common tokenization gotchas that cause unexpected model behavior?

**Answer:** Tokenization creates several non-obvious failure modes that are important to understand for debugging model behavior.

**The "invisible" space gotcha**: In many BPE tokenizers, " cat" (space before cat) and "cat" (no space) are different tokens with different IDs and potentially different embeddings. This means that how you write prompts matters at the character level. "Answer: yes" may tokenize differently than "Answer:yes" (without space). For programmatic prompt construction, this usually doesn't matter, but for tasks where you're looking for specific output tokens (e.g., "yes" or "no" for classification), you should always include the space: ` yes` and ` no`.

**Arithmetic and number boundaries**: The model's numerical reasoning is constrained by how numbers are tokenized. "1234" might be one token; "1235" might be two tokens. The model doesn't inherently understand that these are "close" numerically — it just sees different token patterns. This is why LLMs can fail at simple arithmetic that any calculator handles trivially: "What is 847 × 23?" requires the model to manipulate number tokens, not actual numbers. Always use tool use (code execution) for critical arithmetic.

**Capitalization and tokenization**: "Hello" and "hello" may be different tokens. "HELLO" may be three tokens ["H", "E", "ELLO"] while "hello" is one token. This means that prompts with unusual capitalization are tokenized differently and may produce different quality outputs. In practice, consistent capitalization in prompts improves reliability.

**Language mixing**: If a document switches between English and, say, Japanese mid-text, the tokenizer may produce very long token sequences for the Japanese portions because the vocabulary was trained primarily on English. This can push multilingual documents over context window limits unexpectedly.

**Special token collisions**: Models have special tokens with specific semantic meanings ([CLS], [SEP], <|im_start|>, <|endoftext|>). If user input contains these strings literally (e.g., a user types "<|endoftext|>" in a chatbox), the tokenizer may interpret them as special control tokens rather than literal text. This can cause unexpected behavior. Always sanitize user input to escape or remove special token strings. This is also a vector for prompt injection attacks.

**The "token healing" issue**: When asking a model to complete a prefix (e.g., "The capital of France is"), the last word of the prefix might be tokenized as a partial token if it happens to coincide with a token boundary in the continuation. For example, if the model's vocabulary has " Paris" as a single token but you end the prompt with "...is " (space), the model may not cleanly generate "Paris" in one token. Production inference frameworks like vLLM handle this with "token healing" — a technique that rolls back the last few characters of the prompt and re-encodes jointly with the first tokens of the generation.

## Key Points to Say in the Interview

- A token is **not a word** — it's a subword unit; 1 word ≈ 1.3 tokens in English, more in code and non-English
- BPE works by **iterative merging of frequent pairs** — trained on the same corpus as the model
- Numbers tokenize inefficiently → LLMs do poor arithmetic → always use **tool use for calculations**
- **tiktoken** (GPT) vs **WordPiece** (BERT) — know the difference and why it matters for special tokens
- Token count = cost = context window budget — always **estimate tokens before production deployment**
- Know the **space-before-token** gotcha: " cat" ≠ "cat" in most tokenizers
- Know that **multilingual text is more expensive per information unit** than English

## Common Mistakes to Avoid

- Saying "tokens are words" — they are **subwords**, and conflating them causes incorrect cost estimates
- Not knowing that **different models have different tokenizers** — OpenAI's tiktoken ≠ BERT's WordPiece ≠ LLaMA's SentencePiece
- Claiming LLMs are good at arithmetic without mentioning **the tokenization root cause** of their limitation
- Forgetting that **output tokens cost more than input tokens** in API pricing
- Not mentioning that **special tokens** can be injected via user input — a real security concern

## Further Reading

- [tiktoken by OpenAI](https://github.com/openai/tiktoken) — OpenAI's fast tokenizer library with playground to visualize tokenization
- [Hugging Face Tokenizers Documentation](https://huggingface.co/docs/tokenizers/index) — Comprehensive guide to BPE, WordPiece, and Unigram tokenizers with code examples
- [Neural Machine Translation of Rare Words with Subword Units](https://arxiv.org/abs/1508.07909) — Sennrich et al.'s original BPE for NLP paper (2016)
