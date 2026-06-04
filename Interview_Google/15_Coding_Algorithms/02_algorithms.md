# Core Algorithms for Technical Interviews

## What Is It? (Plain English)

Algorithms are step-by-step recipes for solving computational problems efficiently. When you search for a word in a dictionary, you probably open it near the middle and decide whether to go left or right — that's binary search. When you navigate a city with a map, finding the shortest path through intersections is a graph traversal problem. These everyday intuitions map directly to the algorithms that appear in Google interviews.

What makes an algorithm "good" is not just that it produces the right answer, but that it does so quickly (time efficiency) and without wasting memory (space efficiency). Big-O notation is the shared vocabulary for describing this — it lets engineers compare algorithms without arguing about hardware differences.

At Google, you will be asked to solve these problems live on a whiteboard or in a shared coding environment. The goal is not just to get the answer but to demonstrate that you can think systematically, articulate trade-offs, and write clean code under pressure.

## How It Works

The most commonly tested algorithm families and their core ideas:

```
ALGORITHM FAMILIES & WHEN TO REACH FOR THEM
=============================================

Problem type                   → Algorithm to reach for
─────────────────────────────────────────────────────────
"Is X in a sorted list?"       → Binary Search       O(log n)
"Explore all nodes in graph"   → BFS (level-order)   O(V+E)
"Find shortest path (unweighted)" → BFS              O(V+E)
"All paths, detect cycles"     → DFS                 O(V+E)
"Overlapping sub-problems"     → Dynamic Programming O(n²) typical
"Max/sum of contiguous subarray" → Sliding Window    O(n)
"Two elements sum to target"   → Two Pointers        O(n)
"Put in order"                 → Merge/Quick Sort     O(n log n)

BFS uses a queue (FIFO).  DFS uses a stack (recursion = implicit stack).
```

Step-by-step for binary search:
```
Array: [2, 5, 8, 12, 16, 23, 38, 56, 72, 91]   Target: 23

Step 1: lo=0, hi=9, mid=4  → arr[4]=16  < 23  → move lo to mid+1=5
Step 2: lo=5, hi=9, mid=7  → arr[7]=56  > 23  → move hi to mid-1=6
Step 3: lo=5, hi=6, mid=5  → arr[5]=23  == 23 → FOUND at index 5

Each step eliminates half the search space → O(log n)
```

## Why Google Cares About This

Google's products operate at planetary scale — Search processes billions of queries daily, Maps routes hundreds of millions of trips, YouTube recommends from a catalog of hundreds of millions of videos. An engineer who writes O(n²) code where O(n log n) is possible creates real infrastructure costs. Algorithm interviews proxy for this judgement. Google specifically looks for engineers who can intuitively recognise which algorithm family fits a problem, articulate why, and then implement it cleanly. The interview is also testing communication: can you explain your reasoning out loud while coding?

## Interview Questions & Answers

### Q1: Walk me through how you would solve a two-sum problem and explain the trade-offs between different approaches.

**Answer:** The two-sum problem: given an array of integers and a target, return indices of two numbers that add up to the target.

The naive approach is a nested loop: for each element, check every other element. This is O(n²) time and O(1) space. It works for tiny inputs but collapses at scale.

The optimal approach uses a hash map. In a single pass, for each element x, check whether (target - x) already exists in the hash map. If yes, we found the pair. If no, store x in the map. This is O(n) time and O(n) space — we trade memory for speed.

```python
def two_sum(nums: list[int], target: int) -> list[int]:
    seen = {}               # value → index
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []

# Time:  O(n)  — one pass through the array
# Space: O(n)  — hash map stores up to n entries
```

The two-pointer approach works when the array is sorted: place one pointer at each end and move them toward each other. This is O(n) time and O(1) space — but it requires sorting first (O(n log n)) and returns values, not indices. Choosing between hash map and two-pointer depends on whether the array is already sorted and whether you need indices or values.

At Google, the key insight to demonstrate is that you recognised the hash map as a look-up acceleration structure, not just as "a dictionary". This shows you understand why it works, not just that it works.

---

### Q2: Explain the difference between BFS and DFS. When would you choose one over the other?

**Answer:** Both BFS (Breadth-First Search) and DFS (Depth-First Search) are graph traversal algorithms — ways of visiting every node in a graph or tree. The difference is in the order of exploration.

BFS explores level by level. It uses a queue (FIFO). You process all nodes at distance 1 before nodes at distance 2. DFS goes as deep as possible down one path before backtracking. It uses a stack (or recursion, which uses the call stack implicitly).

```
Graph:          BFS order (queue):    DFS order (stack/recursion):
    A            A → B → C → D → E    A → B → D → E → C
   / \
  B   C
 / \
D   E

BFS: [(A)] → dequeue A, enqueue B,C → [(B,C)] → dequeue B, enqueue D,E ...
DFS: visit A → visit B → visit D (dead end) → backtrack → visit E → backtrack → visit C
```

Choose BFS when:
- You need the shortest path in an unweighted graph (BFS guarantees the first time you reach a node is via the shortest path)
- You need to process nodes level by level (e.g., binary tree level-order traversal)
- The answer is likely to be near the start node (BFS finds it faster)

Choose DFS when:
- You need to detect cycles
- You need to explore all possible paths (e.g., all permutations, maze solving)
- You need topological sort
- Space is constrained and the tree is wide (BFS queue can get large for wide graphs)

In interviews, the most common DFS pattern is recursive DFS on trees. The most common BFS pattern is shortest path in a grid or word ladder problem.

---

### Q3: Explain dynamic programming. What is the difference between memoisation and tabulation?

**Answer:** Dynamic programming (DP) is a technique for solving problems that have two properties: (1) overlapping sub-problems — the same smaller problem appears multiple times, and (2) optimal substructure — the optimal solution can be constructed from optimal solutions to sub-problems.

The classic example is Fibonacci: fib(5) = fib(4) + fib(3). If you compute this naively with recursion, fib(3) is computed multiple times. DP avoids this redundancy.

**Memoisation** is top-down DP. You write the natural recursive solution but cache results in a dictionary. The first time you compute fib(3), you store it. The second time you encounter fib(3), you return the cached value immediately.

```python
from functools import lru_cache

@lru_cache(maxsize=None)
def fib(n: int) -> int:
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)

# Time:  O(n) — each value computed exactly once
# Space: O(n) — cache + call stack
```

**Tabulation** is bottom-up DP. You build a table from the smallest sub-problem up to the full problem, filling in values iteratively. No recursion, no call stack.

```python
def fib(n: int) -> int:
    if n <= 1:
        return n
    dp = [0] * (n + 1)
    dp[1] = 1
    for i in range(2, n + 1):
        dp[i] = dp[i-1] + dp[i-2]
    return dp[n]

# Time:  O(n)
# Space: O(n) — can be reduced to O(1) by only keeping last two values
```

Choose memoisation when the problem is naturally recursive and not all sub-problems need to be solved. Choose tabulation when you know you need all sub-problems or want to avoid stack overflow on deep recursion. Google interviewers appreciate when you can articulate this trade-off.

---

### Q4: Describe merge sort and quicksort. When would you prefer each?

**Answer:** Both are O(n log n) average sorting algorithms. The key differences are stability, worst-case behaviour, and memory usage.

**Merge sort** is a divide-and-conquer algorithm. Split the array in half, recursively sort each half, then merge the two sorted halves. It is stable (equal elements keep their original order) and always O(n log n) — no bad inputs can degrade it. But it requires O(n) extra space for the merge step.

```
Merge sort:
[38, 27, 43, 3, 9, 82, 10]
  Split:   [38,27,43,3]    [9,82,10]
  Split:   [38,27] [43,3]  [9,82] [10]
  Sort:    [27,38] [3,43]  [9,82] [10]
  Merge:   [3,27,38,43]    [9,10,82]
  Merge:   [3,9,10,27,38,43,82]
```

**Quicksort** picks a pivot, partitions elements into "less than pivot" and "greater than pivot," then recursively sorts the partitions. Average case is O(n log n) with O(log n) space (call stack), making it faster in practice than merge sort due to better cache locality. However, worst case (bad pivot on sorted input) is O(n²). Modern implementations use randomised pivots or median-of-three to avoid this.

```
Quicksort (pivot = last element):
[38, 27, 43, 3, 9, 82, 10]   pivot = 10
Partition: [3, 9] | 10 | [38, 27, 43, 82]
Recurse on left and right...
```

Use merge sort when: stability matters (sorting objects by multiple keys), worst-case guarantees are needed, or sorting linked lists (merge sort is efficient on linked lists).

Use quicksort when: average performance matters most, memory is tight, and the input is not adversarial (or you use randomised pivot).

Python's built-in `sorted()` uses Timsort — a hybrid of merge sort and insertion sort that is adaptive and stable.

---

### Q5: How do you approach a LeetCode-style problem in a Google interview? Walk me through your process.

**Answer:** Google interviewers are not just evaluating whether you get the right answer — they are evaluating your thought process, communication, and ability to handle ambiguity. Here is the framework I use:

**Step 1 — Clarify requirements (2 minutes).** Ask about edge cases before writing any code. Are there negative numbers? Can the array be empty? Can there be duplicates? What should I return if there's no answer? This demonstrates senior thinking — you do not assume, you ask.

**Step 2 — Think out loud about approaches (3 minutes).** Name the brute-force solution and its complexity. Then explain why it's insufficient and what insight unlocks a better approach. For example: "The naive O(n²) approach would work but we can use a hash map to get O(n) because lookup is O(1)."

**Step 3 — Write clean code (10-15 minutes).** Use meaningful variable names. Add one-line comments on non-obvious logic. Break the code into helper functions if it gets complex. Do not optimise prematurely — get it working first.

**Step 4 — Test with examples (3 minutes).** Walk through the code manually with a simple example, then a tricky edge case (empty input, single element, all duplicates). This catches bugs before the interviewer catches them for you.

**Step 5 — Analyse complexity.** State time and space complexity. If you see a way to optimise, mention it even if you don't implement it — it shows awareness.

```
TIME COMPLEXITY CHEAT SHEET
===========================================
O(1)        Dictionary lookup, array index
O(log n)    Binary search, balanced BST ops
O(n)        Single loop, hash map build
O(n log n)  Sorting, divide-and-conquer
O(n²)       Nested loops
O(2^n)      Recursive subsets (exponential)
O(n!)       Permutations
===========================================
```

The cardinal sin is staying silent. Even wrong ideas spoken out loud are better than silence — they show how you think and give the interviewer a chance to nudge you in the right direction.

## Key Points to Say in the Interview

- "Let me start with the brute-force solution to establish a baseline, then optimise."
- "The key insight here is..." (always articulate why the algorithm works)
- "This is O(n) time and O(n) space because..." (state complexity before being asked)
- "Edge cases I'm thinking about: empty input, single element, integer overflow."
- "BFS guarantees shortest path in unweighted graphs; DFS is better for exhaustive search."
- "DP applies when I see overlapping sub-problems — the same calculation repeating."
- "Two pointers work on sorted arrays; hash maps work on unsorted arrays."
- "Python's `sorted()` is Timsort — O(n log n) and stable."

## Common Mistakes to Avoid

- Jumping into code without clarifying requirements — ask edge case questions first.
- Forgetting the base cases in recursive solutions — leads to infinite loops or wrong answers.
- Off-by-one errors in binary search — always verify `lo <= hi` vs `lo < hi` and `mid+1`/`mid-1`.
- Modifying an array while iterating over it — create a copy or iterate in reverse.
- Claiming O(n log n) for DP that is actually O(n²) — work through the nested loops carefully.

## Further Reading

- [LeetCode Patterns](https://seanprashad.com/leetcode-patterns/) — categorised problems by algorithm pattern (essential for focused practice)
- [Big-O Cheat Sheet](https://www.bigocheatsheet.com/) — visual complexity comparisons for all major data structures and algorithms
- [Python Algorithms (Hetland)](https://link.springer.com/book/10.1007/978-1-4842-4842-4) — the definitive Python algorithms reference for engineers
