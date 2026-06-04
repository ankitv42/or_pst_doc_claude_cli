# Data Structures — The Building Blocks of Efficient Programs

## What Is It? (Plain English)

A data structure is a way of organising data in memory so that certain operations (insert, find, delete, iterate) can be performed efficiently. Choosing the right data structure is often the difference between an algorithm that runs in one second and one that takes an hour. The concept is straightforward: different shapes of organising data make different operations easy or hard, and a skilled engineer recognises which shape fits the problem at hand.

Think of it like kitchen organisation. A spice rack (array) lets you see everything at a glance and grab item number 5 instantly, but inserting a new spice in the middle requires shifting everything. A filing cabinet (sorted list) makes finding items by name fast, but requires effort to maintain sorted order as you add new items. A labelled bin system (hash map) lets you grab any item instantly by label, with no particular order. Each organisation system is optimal for different usage patterns.

For senior AI engineers, data structures matter in two contexts. First, in coding interviews (Google's technical rounds will include LeetCode-style problems where choosing the right data structure is the key insight). Second, in system design: choosing the right structure for an in-memory cache, a priority queue for agent planning, or an efficient set membership check in a real-time ML pipeline can make or break production performance.

## How It Works

```ascii
CORE DATA STRUCTURES — TIME COMPLEXITY SUMMARY

┌─────────────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ Structure           │ Access   │ Search   │ Insert   │ Delete   │ Space    │
├─────────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ Array               │ O(1)     │ O(n)     │ O(n)     │ O(n)     │ O(n)     │
│ Sorted Array        │ O(1)     │ O(log n) │ O(n)     │ O(n)     │ O(n)     │
│ Linked List         │ O(n)     │ O(n)     │ O(1)*    │ O(1)*    │ O(n)     │
│ Hash Map            │ O(1)**   │ O(1)**   │ O(1)**   │ O(1)**   │ O(n)     │
│ Binary Search Tree  │ O(log n) │ O(log n) │ O(log n) │ O(log n) │ O(n)     │
│ Balanced BST(AVL)   │ O(log n) │ O(log n) │ O(log n) │ O(log n) │ O(n)     │
│ Heap (Min/Max)      │ O(1)***  │ O(n)     │ O(log n) │ O(log n) │ O(n)     │
│ Graph (Adj. List)   │ O(1)     │ O(V+E)   │ O(1)     │ O(E)     │ O(V+E)   │
│ Stack               │ O(n)     │ O(n)     │ O(1)     │ O(1)     │ O(n)     │
│ Queue               │ O(n)     │ O(n)     │ O(1)     │ O(1)     │ O(n)     │
└─────────────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
* At known node; O(n) if you must search first
** Average case; O(n) worst case with hash collisions
*** Access min/max only

KEY STRUCTURES VISUALISED:

ARRAY: [10, 20, 30, 40, 50]
        ↑            ↑
       [0]           [4]   ← Direct index access O(1)

HASH MAP: {"SKU-001": 142, "SKU-002": 38, "SKU-003": 7}
           Key → hash(key) → bucket → value   O(1) average

MIN-HEAP:          3
                 /   \
               15     5
              / \   / \
             20  17  8  10
Rule: parent ≤ both children
Access minimum: O(1) (always root)
Pop minimum: O(log n) (re-heapify)
Push: O(log n) (bubble up)

BINARY SEARCH TREE:
         50
        /  \
      30    70
     / \   / \
   20  40 60  80
Left subtree < node < right subtree
Balanced: O(log n) search; degenerate (all one side): O(n)
```

**Arrays** are contiguous blocks of memory. Index access is O(1) because the memory address of element `i` is simply `base_address + i × element_size`. The cost: insertion in the middle requires shifting all subsequent elements.

**Hash maps** (Python: `dict`) use a hash function to map keys to array indices (buckets). Collisions (two keys mapping to the same bucket) are resolved by chaining or open addressing. Python's dict is an extremely efficient hash map implementation with O(1) average operations. For AI systems, hash maps are the primary in-memory cache structure.

**Heaps** maintain the "heap property" — in a min-heap, every parent is ≤ its children. The minimum element is always at the root (O(1) access). Python's `heapq` module implements min-heap operations. Heaps power priority queues — the structure that processes tasks in order of priority rather than arrival time.

**Graphs** represent networks. Adjacency lists store a dictionary mapping each node to its list of connected nodes — efficient for sparse graphs. Adjacency matrices use a 2D array where `matrix[i][j] = 1` if edge exists — efficient for dense graphs but O(V²) memory.

## Why Google Cares About This

Google's technical interviews universally include coding rounds. For senior roles, the expectation is not just that you can solve LeetCode problems, but that you can articulate why you chose a particular data structure and reason about time/space complexity trade-offs. Beyond interviews, Google engineers work on systems that process billions of events daily — understanding which data structures are O(1) vs O(n) vs O(log n) determines whether a service is viable at scale.

## Interview Questions & Answers

### Q1: When would you use a heap (priority queue) over a sorted array, and give an AI example?

**Answer:** Both a heap and a sorted array can give you the minimum (or maximum) element and maintain an ordered collection. The critical difference is the cost of inserting new elements. In a sorted array, inserting an element in the correct sorted position requires O(n) time (binary search to find position: O(log n), then shifting elements: O(n)). In a min-heap, inserting an element costs O(log n) — it goes to the end, then "bubbles up" by swapping with its parent while it is smaller than its parent.

Use a heap when you need to repeatedly insert items AND repeatedly extract the minimum/maximum, but you do not need the entire collection to be sorted at all times. The heap is "lazily sorted" — it only guarantees the root is minimum, not that the whole structure is sorted.

A concrete AI example: **BFS/Dijkstra's algorithm in agent planning**. In an AI agent that plans a sequence of actions by searching a graph of states (like a planning system that tries different reorder decision paths), Dijkstra's algorithm uses a priority queue (min-heap) keyed on the accumulated cost of reaching each state. At each step, the algorithm pops the lowest-cost state, expands it, and pushes new states. With a heap, each pop and push is O(log n) where n is the number of states in the queue. With a sorted array, each push is O(n) due to shifting — completely impractical for large state spaces.

Another AI example: **beam search in LLM decoding**. When a language model generates text, beam search maintains the k most probable token sequences at each step. Implementing this with a min-heap of size k (keeping only the top k candidates) is O(n log k) per decoding step, where n is the vocabulary size. Using a sorted list would be O(n log n) — significantly slower when n is 50,000+ tokens.

Python's `heapq` module: `import heapq; heap = []; heapq.heappush(heap, (priority, item)); min_item = heapq.heappop(heap)`. The items are tuples where the first element is the priority.

### Q2: Explain hash maps in depth — how do they achieve O(1) and what causes worst-case O(n)?

**Answer:** A hash map (also called hash table or dictionary) achieves O(1) average-case operations through a two-step process. Step 1: apply a hash function to the key, which maps the key to an integer (the hash). Step 2: compute `bucket_index = hash % array_size`, and look up the value at that bucket in an underlying array. Since array access by index is O(1), the lookup is O(1).

The hash function must be deterministic (same input always produces same output), fast to compute, and distribute keys uniformly across buckets to minimise collisions. Python's built-in `hash()` for strings computes a hash based on all characters in the string. For integers, `hash(n) = n` (the integer is its own hash). For custom objects, you override `__hash__`.

Collisions occur when two different keys hash to the same bucket. Python resolves collisions using **open addressing with probing**: if bucket i is occupied, try bucket i+1, i+2, etc. until finding an empty slot. This means in the worst case (many collisions), lookup must check many buckets — O(n) worst case. This worst case occurs when many keys hash to the same value, which can be deliberately triggered by an adversary who knows your hash function (a hash collision attack). Python 3.3+ uses randomised hash seeds to prevent this.

Python dictionaries maintain insertion order (since Python 3.7) and automatically **resize** when the load factor (filled buckets / total buckets) exceeds ~0.67. Resizing doubles the array and rehashes all keys — an O(n) operation, but it happens so infrequently (geometrically less often as the dictionary grows) that the amortised cost per insertion remains O(1).

For AI systems, hash maps are used for: inference result caching (input_hash → output), feature lookup tables (entity_id → feature_vector), vocabulary mappings (token_string → token_id in LLM tokenisers), and deduplication of training examples (content_hash → bool). Python's `dict` is one of the most optimised hash map implementations in any language — you can rely on its performance.

### Q3: What is the difference between a stack and a queue, and when is each used in AI systems?

**Answer:** A **stack** is a Last-In-First-Out (LIFO) structure — like a stack of plates. You add (push) to the top and remove (pop) from the top. The last item added is the first item removed. Python implementation: use a regular list with `list.append()` (push) and `list.pop()` (pop from end — O(1)).

A **queue** is First-In-First-Out (FIFO) — like a queue at a checkout. You add (enqueue) to the back and remove (dequeue) from the front. The first item added is the first item removed. Python implementation: `from collections import deque; q = deque(); q.append(item); q.popleft()`. A `deque` (double-ended queue) is O(1) for both append and popleft. Do not use a regular list for a queue — `list.pop(0)` is O(n) because it shifts all elements.

In AI systems: **Stacks** are used in: (1) DFS (Depth-First Search) graph traversal — used in knowledge graph exploration and agent planning; (2) function call stacks in recursive neural network computations; (3) undo/redo functionality in ML experiment management UI; (4) parsing nested structures (JSON parsing, expression evaluation).

**Queues** are used in: (1) BFS (Breadth-First Search) — finding the shortest path in a graph, used in knowledge graph link prediction; (2) producer-consumer patterns (ML inference queue — requests arrive and are processed in order); (3) breadth-first traversal of decision trees in model interpretability; (4) the ORCA alert queue (alerts are processed FIFO — oldest, most-at-risk items handled first within the same priority level).

A common interview trick question: "Can you implement a queue using two stacks?" Answer: yes — push to Stack1; to dequeue, if Stack2 is empty, pop all elements from Stack1 and push to Stack2 (reversing the order), then pop from Stack2. Amortised O(1) per operation.

### Q4: Explain Big-O notation and give examples for common operations a Data Science Manager should understand.

**Answer:** Big-O notation describes how an algorithm's runtime (or memory usage) grows relative to the size of its input. It ignores constants and lower-order terms — we care about the shape of growth, not the exact coefficient. The key insight is that for large inputs, the dominant term overwhelms everything else.

The most important classes: **O(1) — constant time**: independent of input size. Dictionary lookup, array index access, appending to the end of a list. Examples: looking up a SKU by ID in a dictionary, checking if a feature is in a set.

**O(log n) — logarithmic**: grows very slowly. Binary search in a sorted array, B-tree index lookup, heap insert/pop. Doubling the input only adds 1 to the operation count. Examples: finding a specific date in a sorted time-series index.

**O(n) — linear**: grows proportionally with input. Scanning every element in a list, computing average of an array, linear search. Examples: computing a rolling average over all inventory snapshots for a SKU.

**O(n log n) — log-linear**: the complexity of efficient sorting (merge sort, heapSort, Python's built-in sort). Acceptable for large inputs. Examples: sorting 10 million inventory events by timestamp before processing.

**O(n²) — quadratic**: grows with the square of input. Nested loops over the same collection. Becomes very slow for large n. Examples: naively finding all pairs of SKUs that share a supplier (loop over all SKUs × loop over all SKUs). For 10,000 SKUs, that is 100 million operations.

**O(2^n) — exponential**: each element doubles the work. Trying all possible subsets. Completely impractical beyond ~30 elements. Important to recognise and avoid.

For a Data Science Manager: when your data pipeline gets 10x more data and it now takes 100x longer, your algorithm is O(n²). When it takes 10x longer, it is O(n). When it takes only 3.3x longer (log 10 × old_time), it is O(n log n). This is how you diagnose performance issues without profiling.

### Q5: When would you use a graph data structure in an AI application and how do you represent it in Python?

**Answer:** A graph data structure represents entities (nodes/vertices) and their pairwise relationships (edges). Use a graph when your problem involves traversing connections between entities — finding paths, measuring connectivity, clustering by relationship patterns, or propagating signals through a network.

AI applications requiring graphs: **knowledge graphs** (entities connected by semantic relationships — the foundation of RAG over structured knowledge), **dependency graphs** for ML pipeline execution (Task A must complete before Task B and Task C can start in parallel — a directed acyclic graph), **social networks** for recommendation systems (users connected to other users and items), **supply chain networks** (suppliers connected to products connected to stores — the ORCA use case), **neural networks** are graphs (layers are nodes, weight connections are edges).

Python graph representations:

```python
# Adjacency list (most common — efficient for sparse graphs)
graph = {
    "SKU-001": ["Supplier-A", "Supplier-B", "Store-NYC"],
    "Supplier-A": ["SKU-001", "SKU-002"],
    "Store-NYC": ["SKU-001", "SKU-003"],
}

# Weighted adjacency list (for Dijkstra's, etc.)
weighted_graph = {
    "Supplier-A": [("SKU-001", 3), ("SKU-002", 5)],  # (node, weight)
    "SKU-001": [("Store-NYC", 1)],
}

# Using NetworkX (standard Python graph library)
import networkx as nx
G = nx.DiGraph()  # directed graph
G.add_edge("Supplier-A", "SKU-001", lead_time=3)
G.add_edge("Supplier-A", "SKU-002", lead_time=5)

# BFS from a node (find all reachable nodes)
reachable = list(nx.bfs_tree(G, "Supplier-A").nodes())

# Shortest path
path = nx.shortest_path(G, "Supplier-A", "Store-NYC")

# Detect cycles (important for DAG validation in ML pipelines)
has_cycle = not nx.is_directed_acyclic_graph(G)
```

For interviews: always clarify whether the graph is directed or undirected, weighted or unweighted, and whether it can have cycles. These properties determine which algorithm to use. BFS for shortest path in unweighted graphs; Dijkstra's for shortest path in weighted graphs; topological sort for DAG execution order.

## Key Points to Say in the Interview

- Arrays are O(1) access by index but O(n) insert/delete in the middle — use when you need random access by position
- Hash maps are O(1) average for all operations — the go-to data structure for caching, counting, and fast lookup
- Heaps give O(1) access to min/max and O(log n) insert/pop — essential for priority queues in graph algorithms and beam search
- Stacks (LIFO) for DFS and recursive algorithms; Queues (FIFO) for BFS and producer-consumer patterns — use `collections.deque` for queues
- Big-O describes growth rate, not actual speed — O(n²) is fine for n=100, catastrophic for n=1,000,000
- For graphs, always clarify: directed/undirected, weighted/unweighted, cyclic/acyclic before choosing an algorithm
- Python's `dict`, `set`, `heapq`, `collections.deque` and `collections.Counter` are your primary data structure toolkit

## Common Mistakes to Avoid

- Do not use a list as a queue (`list.pop(0)` is O(n)) — always use `collections.deque` for FIFO queues
- Do not assume a regular Python list "append" is always O(1) — it is amortised O(1) due to occasional resizing; in tight loops where predictability matters, pre-allocate
- Do not use a set when you need to preserve insertion order — Python `set` is unordered; use `dict` keys for an ordered unique collection
- Do not ignore hash collision edge cases — for security-sensitive applications (user-controlled keys), use a hash function with randomised seeds
- Do not try to use a BST without balancing — an unbalanced BST degenerates to O(n) for worst-case inputs; use Python's `sortedcontainers.SortedList` for a balanced sorted structure

## Further Reading

- [Python Data Structures Documentation](https://docs.python.org/3/tutorial/datastructures.html) — Official Python tutorial on lists, tuples, dicts, and sets
- [collections module documentation](https://docs.python.org/3/library/collections.html) — deque, Counter, defaultdict, OrderedDict
- [heapq module documentation](https://docs.python.org/3/library/heapq.html) — Python's heap/priority queue implementation
- [NetworkX Documentation](https://networkx.org/documentation/stable/) — The standard Python graph library for prototyping graph algorithms
- [Big-O Cheat Sheet](https://www.bigocheatsheet.com/) — Quick reference for time/space complexity of common data structures and algorithms
