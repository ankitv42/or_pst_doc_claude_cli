# Regularization

## What Is It? (Plain English)

If a student has unlimited time to prepare for a single test, they might spend all their time memorizing that test's specific questions rather than actually learning the subject. The grade they get reflects their memorization skill, not their understanding. A teacher who wants to assess real understanding might add a time limit (forcing the student to prioritize), test on unseen questions (forcing generalization), or penalize students for using too many "tricks" (forcing elegant solutions). All of these are forms of regularization — constraints added to force simpler, more generalizable solutions.

In machine learning, regularization is any technique that reduces a model's tendency to overfit by penalizing complexity or adding controlled noise during training. The core insight is this: given the same training data, there are infinitely many models that fit the data well. Of these, simpler models tend to generalize better to new data. Regularization is the mechanism that steers the training process toward simpler solutions when multiple solutions would fit the training data equally well.

The most intuitive way to think about it: regularization is like Occam's Razor applied to machine learning. "Given two models that explain the data equally well, prefer the simpler one." The L1 and L2 regularization methods discussed here are mathematical implementations of this preference — they literally add a penalty for complexity to the loss function, so the model pays a cost for being complex, and only becomes complex if that complexity genuinely earns its keep.

## How It Works

```
Regularization Techniques Comparison:

LOSS FUNCTION WITHOUT REGULARIZATION:
Loss = Σ (y_true - y_pred)²

LOSS FUNCTION WITH L2 REGULARIZATION (Ridge):
Loss = Σ (y_true - y_pred)² + λ × Σ(w_i²)
            │                      │
      prediction error       complexity penalty
      (get predictions right)  (keep weights small)

LOSS FUNCTION WITH L1 REGULARIZATION (Lasso):
Loss = Σ (y_true - y_pred)² + λ × Σ|w_i|
            │                      │
      prediction error       sparsity penalty
                             (drives many weights to 0)

Effect on weights:
───────────────────────────────────────────────────────────
                    L1 (Lasso)        L2 (Ridge)
───────────────────────────────────────────────────────────
Effect             Drives many        Shrinks all weights
                   weights to ZERO    toward zero (but
                   (sparse model)     rarely exact zero)
───────────────────────────────────────────────────────────
Best when          Many features      All features
                   are irrelevant     contribute somewhat
───────────────────────────────────────────────────────────
Feature            Yes (implicit      No
Selection          — zero weight
                   = feature removed)
───────────────────────────────────────────────────────────
Geometric          Diamond-shaped     Circle-shaped
constraint         constraint region  constraint region
───────────────────────────────────────────────────────────

Dropout Regularization (for neural networks):

Training:                          Inference:
                                   
  Input ──►[Layer]──►[Dropout 50%]  Input ──►[Layer]──►[×0.5]
             ↑                                            ↑
         40 neurons                                  all 40 active
         20 randomly                               (outputs scaled)
         set to 0
         at each step

Batch Normalization:

  Mini-batch of inputs ──► Normalize to μ=0, σ=1 ──► Scale and shift
  [2.1, 0.3, 8.7, 1.2]   [0.2, -1.1, 1.4, -0.5]  [γ×0.2+β, ...]
  (raw activations)       (normalized)               (learned γ, β)
```

## Why Google Cares About This

Regularization is core curriculum for any production ML system. Google trains models at scales where overfitting is a constant risk — the internet's data is vast but not infinitely diverse, and models with hundreds of billions of parameters can memorize vast corpora. Understanding which regularization technique to apply, and why, is a fundamental signal of ML engineering competence. Interviewers specifically probe L1 vs L2, dropout, and batch normalization because these appear in almost every Google production model.

## Interview Questions & Answers

### Q1: Explain the geometric intuition for why L1 regularization drives weights to zero while L2 does not.

**Answer:** The geometric intuition is one of the most beautiful explanations in machine learning. Both L1 and L2 regularization can be interpreted as constrained optimization: you're looking for the model weights that minimize your prediction error (the loss) while staying inside a geometric region in "weight space" defined by the regularization constraint.

For L2, the constraint region is a sphere (in 2D, a circle): the set of all weight vectors where the sum of squared weights is below a threshold. The loss function's minimum (the unconstrained best weights) is some point in weight space, and you're looking for the nearest point to that minimum that still lies inside the sphere. Because spheres are smooth with no corners, the constrained optimum almost never falls exactly on an axis — it lies somewhere on the curved surface where the loss function's contour lines are tangent to the sphere. Almost no weights end up exactly zero; they're just pushed toward zero.

For L1, the constraint region is a "diamond" shape (in 2D, a square rotated 45 degrees): the set of all weight vectors where the sum of absolute weights is below a threshold. This diamond has sharp corners that lie exactly on the axes (where one weight is zero and the others sum to the budget). When the loss function's contour lines are tangent to a flat face of the diamond, the tangent point is on a corner — meaning several weights are exactly zero. This happens far more often geometrically because corners concentrate on the axes. The result: L1 naturally produces sparse solutions with many exact zeros.

The practical takeaway: use L1 (Lasso) when you believe many of your features are irrelevant and you want the model to perform automatic feature selection. Use L2 (Ridge) when you believe all features contribute something and you want to prevent any single feature from dominating. Elastic Net combines both penalties (a weighted sum of L1 and L2), giving you both sparsity and stability — useful when you have many correlated features.

### Q2: What is batch normalization and how does it help training? Is it purely a regularization technique?

**Answer:** Batch normalization (BatchNorm) was introduced by Ioffe and Szegedy in 2015 as a technique to stabilize the training of deep neural networks, not primarily as a regularization technique — though it has a useful regularization side effect. Understanding both roles is important.

The primary problem BatchNorm solves is called internal covariate shift: as neural network weights update during training, the distribution of activations in each layer changes, which means each layer constantly needs to readapt to a shifting input distribution. This slows training and can cause gradient instabilities in very deep networks. BatchNorm addresses this by normalizing the activations of each layer to have zero mean and unit variance within each mini-batch, then applying learnable scale (γ) and shift (β) parameters to let the layer find its optimal operating range. The normalization happens before the activation function, ensuring each layer receives inputs with a stable distribution regardless of what the previous layers are doing.

The regularization effect is secondary: because each mini-batch is different (a random sample of the training data), the normalization statistics (mean and variance) vary from batch to batch. This adds noise to each activation — a neuron that would normally activate strongly for a specific input pattern will be normalized differently depending on what other examples happen to be in the same mini-batch. This noise acts like a mild regularizer, similar to dropout but less aggressive. In practice, BatchNorm often reduces the need for dropout in deep networks.

At inference time, BatchNorm cannot use batch statistics (there's no batch, just one input at a time). Instead, it uses running statistics accumulated during training: a moving average of the mean and variance computed across all training batches. This is a critical implementation detail — if you switch a BatchNorm model from training mode to inference mode without properly tracking these running statistics, predictions will be wildly wrong.

### Q3: How do you choose the regularization strength λ? What happens if λ is too high or too low?

**Answer:** The regularization strength λ controls the tradeoff between fitting the training data (low λ) and keeping weights small (high λ). Getting this right is essential: too low and you overfit; too high and you underfit (the complexity penalty overwhelms the prediction loss, forcing the model to keep all weights near zero regardless of the data).

The right way to choose λ is cross-validation: try a range of λ values (typically a logarithmic grid: 0.001, 0.01, 0.1, 1, 10, 100), train a model for each, evaluate on validation folds, and select the λ that minimizes validation error. The regularization path — how model performance changes as you vary λ — is a useful diagnostic. If the performance curve has a clear peak, you've found the sweet spot. If it's flat over a wide range of λ, the model is not very sensitive to regularization, which suggests the data is sufficient to constrain the model naturally.

When λ is too small: the regularization term is negligible, and the model behaves as if there were no regularization. You'll observe the classic overfitting pattern: low training error, high validation error. When λ is too large: the regularization term dominates the loss function, pushing all weights to near zero (for L2) or exactly zero (for L1). The model loses its ability to learn any pattern from the data. You'll observe underfitting: high training error and high validation error, often with the model defaulting to predicting the training mean for all inputs.

An important consideration: optimal λ scales inversely with dataset size. Doubling the training data allows you to halve λ while maintaining the same effective regularization. Intuitively, more data provides more natural constraints on the model — you need less external regularization to prevent memorization. As you collect more production data, periodically re-tune λ downward. Teams that set λ once during initial training and never revisit it will see performance left on the table as their dataset grows.

### Q4: When should you use L1 vs L2 vs elastic net regularization?

**Answer:** The choice between L1, L2, and elastic net should be driven by your beliefs about the underlying data structure — specifically, how many of your input features are actually relevant to the prediction task.

Use L1 (Lasso) when you believe only a small subset of features are genuinely predictive and you want the model to automatically identify them. L1's sparsity property makes it a feature selection tool built into the optimization. If you have a genomics model with 50,000 gene expression features predicting disease risk, but you believe only a few hundred genes are actually relevant, L1 will drive the 49,700+ irrelevant gene coefficients to exactly zero. The resulting model is sparse and interpretable. The downsides: L1 is not differentiable at zero (creating optimization challenges), and when features are highly correlated, L1 will arbitrarily zero out all but one correlated feature rather than distributing weight among them.

Use L2 (Ridge) when you believe all or most features contribute to the prediction, just some more than others. Ridge shrinks all weights but keeps them all nonzero. It is computationally stable (the squared penalty is smooth and differentiable everywhere), and handles correlated features gracefully — it distributes weight among correlated features rather than picking one. Ridge is often the default choice when you're not sure, because it provides stable regularization without accidentally eliminating features you might need.

Use elastic net (a weighted sum of L1 and L2: `α × L1 + (1-α) × L2`) when you want both sparsity and stability. In situations with groups of correlated features (e.g., genes in the same pathway, highly correlated financial metrics), elastic net will typically select the most representative feature from each group (sparse behavior) while still retaining all groups (stability behavior). Elastic net was specifically developed for genomics applications but is broadly useful for high-dimensional data with structure.

### Q5: How does weight decay relate to L2 regularization, and why is it the preferred implementation in deep learning?

**Answer:** Weight decay and L2 regularization are mathematically equivalent for standard gradient descent, which is why the terms are often used interchangeably. The connection is elegant: when you take the gradient of the L2-regularized loss with respect to a weight, you get the prediction loss gradient plus `2λw` (which just says: "also push this weight toward zero by an amount proportional to its current value"). This means the gradient update becomes: `w_new = w_old - learning_rate × (prediction_gradient + 2λ × w_old)`. Rearranging: `w_new = (1 - 2λ × learning_rate) × w_old - learning_rate × prediction_gradient`. The factor `(1 - 2λ × learning_rate)` is less than 1, so it "decays" the weight toward zero at each step — hence "weight decay."

However, for adaptive optimizers like Adam (the most commonly used optimizer for neural networks), weight decay and L2 regularization are NOT equivalent. This distinction, identified by Loshchilov and Hutter in the "Decoupled Weight Decay Regularization" paper (2017, the AdamW paper), is practically important. When you apply L2 regularization with Adam, the regularization gradient `2λw` is adapted by Adam's learning rate scaling — so features with large gradients have their regularization scaled up as well. This produces inconsistent regularization that biases Adam toward different features. AdamW (Adam with decoupled weight decay) applies the weight decay directly to the weights without going through Adam's adaptive scaling, producing consistent regularization behavior regardless of gradient magnitude.

In practice: for deep learning, always use AdamW rather than Adam+L2. The PyTorch optimizer `torch.optim.AdamW(parameters, weight_decay=0.01)` is the modern standard. The weight decay value `0.01` (1% decay per step) is a reasonable starting point for most models; tune it if you see overfitting (increase) or underfitting (decrease).

## Key Points to Say in the Interview

- L1 drives many weights to exactly zero (feature selection); L2 shrinks all weights toward zero but rarely to exactly zero
- The geometric intuition: L2's circular constraint vs L1's diamond constraint with corners on the axes
- Batch normalization primarily accelerates training by stabilizing internal distributions; regularization is a useful side effect
- Optimal λ scales inversely with dataset size — retune as data grows
- Elastic net combines L1 sparsity with L2 stability; best for correlated feature groups
- For deep learning with Adam: use AdamW (decoupled weight decay), not Adam + L2 regularization

## Common Mistakes to Avoid

- Don't conflate weight decay and L2 regularization for adaptive optimizers (Adam) — they're equivalent only for vanilla SGD
- Don't say batch normalization is "primarily" a regularization technique — it's primarily a training stabilization technique
- Don't forget to tune λ with cross-validation — saying "I'd set it to 0.01" without justification shows superficial knowledge
- Don't apply L2 to biases — biases don't cause overfitting and regularizing them adds computational cost with no benefit
- Don't claim L1 always outperforms L2 — when all features are relevant, L1's arbitrary sparsity hurts performance

## Further Reading

- [Decoupled Weight Decay Regularization (Loshchilov & Hutter, 2017 — AdamW paper)](https://arxiv.org/abs/1711.05101) — Essential reading on why weight decay != L2 for Adam
- [An Overview of Regularization Techniques in Deep Learning (Lilian Weng)](https://lilianweng.github.io/posts/2019-01-31-lasso/) — Comprehensive technical overview with derivations
- [Regularization in Machine Learning (Google ML Education)](https://developers.google.com/machine-learning/crash-course/regularization-for-simplicity/l2-regularization) — Google's own clear, accessible treatment of L1 and L2
