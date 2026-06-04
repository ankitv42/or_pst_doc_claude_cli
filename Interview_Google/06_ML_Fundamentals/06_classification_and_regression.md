# Classification and Regression

## What Is It? (Plain English)

Almost every supervised machine learning task falls into one of two categories. If your target variable is a number on a continuous scale — house price, temperature, revenue, number of days until a part fails — you have a regression problem. If your target variable is a category — spam or not spam, which of 10 product types, fraudulent or legitimate transaction — you have a classification problem. Choosing the right type of model, the right loss function, and the right evaluation metric depends entirely on which type of problem you're solving.

The distinction sounds obvious until you encounter real-world ambiguity. "Predict whether a customer will churn" is clearly classification (yes/no). "Predict customer lifetime value" is clearly regression (a dollar amount). But "predict the probability a transaction is fraudulent" is a classification problem (the output is a probability between 0 and 1, and you pick a threshold to convert it to yes/no). "Predict the number of days until a machine fails" could be treated as regression (count the days) or classification (will it fail within 7 days: yes/no). Understanding which framing is more appropriate for the business need is a design decision.

The loss function is the mathematical specification of "what counts as a good prediction" — it is what the model optimizes during training. Using the wrong loss function is one of the most common sources of production model failures: a model trained with mean squared error on house prices will penalize missing a $10M house by $1M more than missing a $100K house by $1M, which might not be what the business wants (percentage error might be more appropriate).

## How It Works

```
Supervised Learning Task Types:

REGRESSION TASKS:
─────────────────────────────────────────────────────────────
Output: continuous number (price, temperature, revenue, etc.)
Loss Functions Used During Training:
  MSE (Mean Squared Error):  (1/n) × Σ(y_true - y_pred)²
  MAE (Mean Absolute Error): (1/n) × Σ|y_true - y_pred|
  Huber Loss: MSE when error is small, MAE when error is large

Evaluation Metrics:
  RMSE = √(MSE)          — same units as the target
  MAE                    — average absolute error
  MAPE = mean(|error|/y_true) × 100%  — percentage error
  R²  = 1 - SS_res/SS_tot — proportion of variance explained

CLASSIFICATION TASKS:
─────────────────────────────────────────────────────────────
Binary (2 classes): spam/not spam, fraud/not fraud
  Loss:   Binary Cross-Entropy = -Σ[y×log(p) + (1-y)×log(1-p)]
  Metrics: Accuracy, Precision, Recall, F1, AUC-ROC

Multiclass (N classes): which of 10 product categories?
  Loss:   Categorical Cross-Entropy = -Σ Σ y_ij × log(p_ij)
  Metrics: Macro/Micro F1, Confusion Matrix, Top-K Accuracy

Confusion Matrix (Binary Classification):
                     Actual Positive  Actual Negative
Predicted Positive       TP               FP
Predicted Negative       FN               TN

Precision = TP / (TP + FP)   "When you say positive, how often right?"
Recall    = TP / (TP + FN)   "Of all positives, how many did you catch?"
F1        = 2 × Prec × Recall / (Prec + Recall)   Harmonic mean
AUC-ROC   = area under the ROC curve (TPR vs FPR at all thresholds)

ROC Curve Shape:
  TPR │       ╭──────────────────
  1.0 │    ╭──╯   Model B (good)
      │   ╱
      │  ╱  AUC = 0.90
      │ ╱
  0.5 │╱    Model A (random, AUC = 0.5)
      │ ╱  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
  0.0 └────────────────────────────
       0.0          0.5          1.0
                   FPR
```

## Why Google Cares About This

Classification and regression are the foundation of Google's entire business. Search ranking is classification (relevant/not) and regression (relevance score). Ad click prediction is binary classification. YouTube watch-time prediction is regression. Spam detection is binary classification. Google expects senior candidates to know not just "which loss to use" but the subtle implications of metric choice: why AUC matters more than accuracy for imbalanced data, when MAPE is misleading, why F1 is the right metric for precision-recall tradeoffs in information retrieval. These are live issues in Google's daily ML work.

## Interview Questions & Answers

### Q1: Why is accuracy a bad metric for imbalanced classification problems? What should you use instead?

**Answer:** Accuracy measures the fraction of all predictions that are correct. For balanced datasets (roughly equal classes), this is meaningful. For imbalanced datasets — which are extremely common in real problems — accuracy is misleading to the point of being actively harmful for decision-making.

A concrete example: credit card fraud detection. Suppose 99.9% of transactions are legitimate and 0.1% are fraudulent. A model that predicts "legitimate" for every single transaction achieves 99.9% accuracy — which sounds excellent. But this model catches exactly zero fraudulent transactions. It is completely useless for its intended purpose. Accuracy cannot distinguish between "99.9% accuracy because the model learned something" and "99.9% accuracy because the model always predicts the majority class."

For imbalanced problems, the right metrics are: precision (what fraction of transactions your model flagged as fraud were actually fraud — minimizes false alarms), recall (what fraction of actual fraud transactions your model caught — minimizes missed fraud), and F1 (their harmonic mean — useful when both matter). The relative importance of precision vs recall depends on the business problem: missing fraud costs the bank money (high recall is critical); incorrectly flagging legitimate transactions annoys customers (high precision is critical). You cannot maximize both simultaneously, and the right tradeoff is a business decision.

AUC-ROC (Area Under the Receiver Operating Characteristic Curve) is the most robust single metric for imbalanced binary classification. It measures model performance across all possible classification thresholds, plotting True Positive Rate against False Positive Rate. A model that always predicts the majority class gets AUC = 0.5 (the diagonal random-chance line). A useful model gets AUC > 0.5; a perfect model gets AUC = 1.0. AUC is independent of class imbalance and independent of the threshold you choose, making it the gold standard for comparing binary classifiers.

### Q2: When should you use MSE vs MAE as your regression loss function?

**Answer:** MSE (Mean Squared Error) penalizes large errors much more heavily than small errors because errors are squared — a prediction that's off by 10 contributes 100 to the loss; a prediction that's off by 1 contributes only 1. This makes MSE highly sensitive to outliers: a single training example where the model is very wrong will dominate the loss and heavily influence how the model's weights are adjusted. When you are working with data where large errors are genuinely much worse than small ones, MSE is the right choice. House price prediction where missing a $1M house by $100K is a serious error is a good fit for MSE.

MAE (Mean Absolute Error) treats all errors proportionally — each unit of error contributes equally to the loss. A prediction off by 10 contributes 10; a prediction off by 1 contributes 1 (not squared). This makes MAE much more robust to outliers. When your training data has genuinely anomalous examples — days when a storm made sales unusually low, transactions during a system outage — MAE won't let these outliers distort the model's weights as much as MSE would. For time-series forecasting where demand spikes can occur for exogenous reasons, MAE is often preferred.

The choice also affects the model's behavior for the "average case." A model trained with MSE tends to predict the mean of the target distribution (because the mean minimizes expected squared error). A model trained with MAE tends to predict the median (because the median minimizes expected absolute error). If your target distribution has a long tail — many customers spending $50 but a few spending $5,000 — a MSE-trained model will chase the high-value outliers; an MAE-trained model will serve the median customer better.

For a practical decision rule: use MSE when you care about proportionality of penalty (a 2× error is twice as bad as a 1× error, but a 10× error is much worse than proportional); use MAE when you want outlier robustness and care about absolute error equally regardless of magnitude. Huber loss is a hybrid that uses MSE for small errors and MAE for large ones, giving you smooth optimization near zero while reducing outlier sensitivity.

### Q3: Explain cross-entropy loss and why it's used for classification instead of MSE.

**Answer:** Cross-entropy loss is the standard training objective for classification models. For binary classification, it is: `Loss = -[y × log(p) + (1-y) × log(1-p)]`, where y is the true label (0 or 1) and p is the model's predicted probability that the label is 1. For the correct class, this heavily penalizes low predicted probabilities (if the true label is 1 and you predicted p=0.01, the loss is -log(0.01) = 4.6, which is huge); for the incorrect class, it heavily penalizes high predicted probabilities. This is the right objective for classification because it directly measures how well the model's probability estimates match reality.

MSE can technically be used for classification — treat "0" and "1" as regression targets and minimize squared error between predictions and labels. There are two problems. First, MSE treats class labels as numbers with a metric, implying "0.5 is halfway between 0 and 1." For classification, there's no such interpretation. Second and more important, MSE does not work well with the sigmoid and softmax activation functions used in classification. The sigmoid/softmax functions create regions where the gradient of MSE becomes nearly zero (the "vanishing gradient" problem), causing training to stall. Cross-entropy combined with sigmoid/softmax has gradients proportional to the prediction error, which means training always has a useful signal even when predictions are very wrong.

The deep connection: minimizing cross-entropy is equivalent to maximizing the likelihood of the observed data under the model's probability distribution. This gives cross-entropy a principled statistical justification — it is the "right" loss for probabilistic classification from first principles, not just a heuristic choice. This is why every serious classification model uses cross-entropy, from logistic regression to modern transformers.

### Q4: What is the precision-recall tradeoff and how do you choose the right operating point?

**Answer:** Every probabilistic classification model produces a score between 0 and 1, and you must choose a threshold to convert this score into a binary "positive" or "negative" prediction. If you set the threshold low (say 0.1), you'll flag many things as positive — high recall (you catch most true positives) but low precision (many false positives). If you set the threshold high (say 0.9), you'll only flag the most certain cases — high precision (few false alarms) but low recall (you miss many true positives). This is the precision-recall tradeoff, and it is a business decision, not an ML decision.

The right operating point depends on the asymmetric costs of false positives and false negatives in your specific context. For cancer screening, the cost of a false negative (missing actual cancer) vastly outweighs the cost of a false positive (unnecessary follow-up biopsy). Set a low threshold — high recall, lower precision. For email spam filtering, the cost of a false positive (sending a legitimate email to spam — user misses it) is significant and the cost of a false negative (allowing spam through — mild annoyance) is lower. Set a higher threshold — higher precision, lower recall.

The precision-recall curve plots precision against recall across all possible thresholds. The area under this curve (AUC-PR or average precision) is a single number summarizing model quality across all thresholds, useful for comparing models on imbalanced datasets. For highly imbalanced datasets, AUC-PR is often more informative than AUC-ROC because it focuses on the positive class performance rather than being dominated by the much-larger negative class.

To choose the actual threshold for deployment: express the false positive and false negative costs in the same units (often dollars), then find the threshold that minimizes `FP_cost × FP_rate + FN_cost × FN_rate`. This turns the threshold choice into a quantitative optimization rather than an arbitrary decision. At Google's scale, even tiny improvements in threshold calibration translate to significant business impact.

### Q5: What is the difference between multiclass and multilabel classification? Give a production example of each.

**Answer:** In multiclass classification, each example belongs to exactly one class out of N possible classes, and the classes are mutually exclusive. A photo recognition model that assigns each image to exactly one category (cat, dog, bird, car, or other) is multiclass. The model outputs a probability for each class using softmax, and the probabilities sum to 1.0. A standard cross-entropy loss works directly.

In multilabel classification, each example can belong to multiple classes simultaneously. A content tagging model that assigns each article the labels "sports," "politics," "technology," and "culture" (where an article can be tagged with multiple labels — a tech company's political lobbying scandal could be all three) is multilabel. Each label is an independent binary decision, not a mutually exclusive choice.

The technical differences are significant. For multilabel: use sigmoid (not softmax) as the output activation — each output is an independent [0,1] probability, not part of a probability distribution. Use binary cross-entropy loss computed independently for each label and summed. Use threshold selection per label (the right threshold for a rare label may differ from a common label). For multilabel, metrics are different: exact match ratio (all labels correct), macro F1 (average F1 across labels, giving equal weight to each), and micro F1 (F1 computed globally across all label decisions).

A production example of multiclass: Google Search's query intent classification — is this query navigational (wants a specific website), informational (wants to learn something), or transactional (wants to buy something)? Exactly one intent category per query. A production example of multilabel: YouTube video content rating — a single video can simultaneously be tagged as "educational," "English-language," "suitable for children," and "news-related." All four tags can apply independently, and the presence of one doesn't preclude the others.

## Key Points to Say in the Interview

- Regression: continuous target, MSE or MAE loss, evaluated with RMSE/R²/MAE; Classification: categorical target, cross-entropy loss, evaluated with F1/AUC/precision/recall
- Accuracy is meaningless for imbalanced classification; use F1 or AUC-ROC
- MSE heavily penalizes large errors (outlier-sensitive); MAE treats all errors equally (robust to outliers)
- Cross-entropy is the right loss for classification because it has useful gradients and maximizes likelihood; MSE does not
- Precision-recall tradeoff: the right operating threshold is a business decision based on relative costs of false positives and false negatives
- Multiclass = exactly one class (softmax output, sums to 1); multilabel = multiple simultaneous classes (sigmoid output, independent probabilities)

## Common Mistakes to Avoid

- Don't report only accuracy on imbalanced datasets — this is a red flag for ML practitioners
- Don't use MSE for classification — it doesn't work with sigmoid/softmax and has no probabilistic interpretation
- Don't claim there's a universal best threshold for classification — it must be tuned based on business cost asymmetry
- Don't apply softmax to multilabel problems — labels are not mutually exclusive; sigmoid is correct
- Don't ignore MAPE's failure case: when true values are near zero, percentage error explodes

## Further Reading

- [Classification: ROC Curve and AUC (Google ML Education)](https://developers.google.com/machine-learning/crash-course/classification/roc-and-auc) — Google's own clear explanation of AUC-ROC
- [Metrics to Evaluate Machine Learning Algorithms in Python (Jason Brownlee, Machine Learning Mastery)](https://machinelearningmastery.com/metrics-evaluate-machine-learning-algorithms-python/) — Comprehensive practical guide with code
- [An Introduction to Statistical Learning: Chapters 3 (Regression) and 4 (Classification)](https://www.statlearning.com/) — Free textbook covering both topics with mathematical rigor and intuition
