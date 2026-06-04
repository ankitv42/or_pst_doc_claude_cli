# Feature Engineering

## What Is It? (Plain English)

Raw data rarely arrives in a form that machine learning models can work with directly. A customer record might have a date of birth field (a string like "1985-03-15"), a city name, a purchase history list, and missing values in half the columns. A model cannot learn from these directly — it needs numbers that encode the meaningful patterns hidden in those raw fields. Feature engineering is the process of transforming raw data into the numerical representations that best help a model learn the underlying patterns.

Think of feature engineering as translation work. Raw data is written in the language of business (dates, names, categories, dollar amounts). Machine learning models speak only the language of mathematics (real numbers, vectors). A skilled data scientist translates between these languages, preserving the business meaning while making the information accessible to the algorithm. The quality of this translation is often the single biggest driver of model performance — not the choice of algorithm, not the amount of training data, but how well you translated the raw data.

Even in the era of deep learning, which can theoretically learn features automatically from raw data, thoughtful feature engineering remains valuable for tabular data (spreadsheet-style business data), time-series data, and cases where you have limited training data. The intuition you bring from domain knowledge — "in retail, day-of-week effects matter, January is slow, and the last day of the month is high" — can be encoded as features in a way that would take a deep learning model millions of examples to discover on its own.

## How It Works

```
Feature Engineering Transformation Pipeline:

RAW DATA:
──────────────────────────────────────────────────────────
customer_id  | dob        | city        | purchase_date | amount | last_buy
1042         | 1985-03-15 | New York, NY| 2026-05-20    | 127.50 | NULL
──────────────────────────────────────────────────────────

STEP 1: Handle Missing Values
  last_buy = NULL → last_buy = 9999 (sentinel for "never")
  OR last_buy = median(last_buy)

STEP 2: Extract Time-Based Features from dates
  dob → age = 2026 - 1985 = 41
  purchase_date → day_of_week = 2 (Tuesday)
  purchase_date → is_weekend = 0
  purchase_date → days_since_last_purchase = (2026-05-20 - last_buy)
  purchase_date → month = 5
  purchase_date → quarter = 2

STEP 3: One-Hot Encode Categorical Variables
  city = "New York, NY"
  → city_new_york = 1
  → city_los_angeles = 0
  → city_chicago = 0
  → city_other = 0

STEP 4: Normalize Numeric Variables
  amount = 127.50
  → amount_normalized = (127.50 - mean_amount) / std_amount
  → amount_normalized = (127.50 - 85.20) / 42.30 = 1.00

STEP 5: Create Interaction Features
  age × amount → captures "older customers spend more" if true
  is_weekend × amount → captures "weekend spending is different"

ENGINEERED FEATURE VECTOR:
[41, 2, 0, 5, 2, 1, 0, 0, 0, 1.00, 9999, 41*1.00, 0*1.00, ...]
──────────────────────────────────────────────────────────
Model can now learn from this vector.
```

## Why Google Cares About This

Feature engineering is where domain knowledge meets algorithmic learning, and Google's ML teams work across diverse domains — Search, Ads, Maps, Healthcare, Finance — where understanding the business context and translating it into useful features is a critical skill. Even at Google scale with large training datasets, thoughtful feature engineering dramatically improves model efficiency: a well-engineered feature can do what a neural network would take 10x more data to learn automatically. Senior ML engineers at Google are expected to think critically about what information is actually predictive and why, not just plug raw data into AutoML.

## Interview Questions & Answers

### Q1: Why does normalization matter, and what happens if you skip it?

**Answer:** Normalization (also called scaling) is the process of transforming numeric features so they are on a comparable scale — typically with mean 0 and standard deviation 1 (called standardization) or squeezed into the range [0, 1] (called min-max scaling). Skipping normalization causes serious problems for gradient-based optimization algorithms and distance-based models.

Here is a concrete example. Suppose you are predicting house prices using two features: square footage (ranges from 500 to 5,000) and number of bedrooms (ranges from 1 to 6). Without normalization, the square footage feature will dominate because its values are 1,000 times larger. In gradient descent, the gradient component from square footage will also be 1,000 times larger, causing the optimizer to take large steps in the square footage direction and tiny steps in the bedroom direction. The optimization will be very inefficient, converging slowly and potentially oscillating.

For k-nearest neighbors and clustering algorithms, normalization is even more critical. These algorithms measure distances between data points — if one feature has range 0-5000 and another has range 0-1, the first feature numerically dominates all distance calculations, and the second feature is effectively ignored. A house that is "close" in the feature space will be determined almost entirely by square footage and almost not at all by bedrooms, regardless of whether bedrooms are actually predictive.

The two standard approaches: standardization (subtract mean, divide by standard deviation) is best when the feature is approximately normally distributed; min-max scaling (shift and scale to [0,1]) is best when you know the feature has hard bounds. For neural networks, a variant called batch normalization (applied between layers during training) has largely replaced manual feature normalization as the first preprocessing step.

### Q2: What is one-hot encoding and when should you use it vs label encoding?

**Answer:** One-hot encoding converts a categorical variable with N possible values into N binary columns, where exactly one column is 1 (hot) and all others are 0. "City = New York" becomes `[1, 0, 0, 0]` where the four columns represent New York, Los Angeles, Chicago, and Other. Label encoding converts categories to integers: New York = 0, Los Angeles = 1, Chicago = 2.

The choice depends entirely on whether the integer ordering imposed by label encoding is meaningful. For ordinal categories (Small=1, Medium=2, Large=3; Monday=1, Tuesday=2, ..., Sunday=7), label encoding is appropriate because the numbers genuinely represent order. For nominal categories (colors, city names, product categories), label encoding is actively harmful because it implies a false ordering: Chicago=2 is not somehow "between" New York=0 and Los Angeles=1, but label encoding implies it is. A model will incorrectly treat cities with nearby integer codes as similar.

One-hot encoding avoids this problem — it makes no assumptions about ordering. However, it creates a dimensionality problem: a category with 10,000 unique values (like ZIP codes) creates 10,000 new columns. This is called the high-cardinality problem. Solutions include: frequency encoding (replace each category with how many times it appears in training data), target encoding (replace each category with the mean target value for that category — but requires careful cross-validation to prevent data leakage), and embedding layers (for deep learning, learn a dense low-dimensional representation of each category, which is how language models handle word vocabularies).

For tree-based models (Random Forest, XGBoost), label encoding with any consistent integer mapping often works fine because trees make splits based on threshold comparisons and are not affected by the specific integer values. For linear models and neural networks, always use one-hot or embeddings for nominal categoricals.

### Q3: What are interaction features and when do they add value?

**Answer:** Interaction features capture the relationship between two or more variables that matters beyond their individual effects. The simplest form is the product of two features: `age × income` as a feature means "the combined effect of being both old AND rich," which might be more predictive of luxury car purchases than either age or income alone.

The classic example is converting a cold numeric feature into something more meaningful. Suppose you have hours_worked and is_overtime_eligible as separate features. Neither alone tells the full story of total overtime pay. But `hours_worked × is_overtime_eligible × overtime_rate` directly computes overtime pay, which is the businesssignificant quantity. Tree models can discover this interaction implicitly through sequential splits, but linear models cannot — they need the interaction explicitly provided as a feature.

Time-based interaction features are particularly powerful in business contexts: `day_of_week × is_holiday` captures "holiday weekends are different from regular weekends"; `product_category × month` captures seasonal demand patterns that differ by category. These patterns can be derived from domain knowledge before the model sees a single data point.

The risk is combinatorial explosion: with 20 features, there are 190 possible two-way interactions and 1,140 possible three-way interactions. Not all interactions are meaningful, and including irrelevant ones adds noise and increases model complexity unnecessarily. Feature selection techniques (mutual information, recursive feature elimination, LASSO regularization which drives unimportant feature weights to zero) help identify which interactions are genuinely predictive. In practice, start with interactions suggested by domain knowledge and business intuition, not by exhaustive search.

### Q4: How do you handle missing values in production ML systems?

**Answer:** Missing values are nearly universal in real-world data and must be handled explicitly — most ML algorithms cannot process NaN (not-a-number) values and will fail or produce garbage predictions. The right handling strategy depends on why the data is missing.

Data can be missing completely at random (MCAR) — a sensor happened to fail during that reading with no connection to the actual value. Missing at random (MAR) — values are missing based on other observable variables (e.g., income data is more often missing for older survey respondents). Or missing not at random (MNAR) — the absence itself carries information (e.g., credit score is missing because the applicant has no credit history, which is highly predictive of credit risk). Treating MNAR data with simple imputation destroys the signal.

For MCAR and MAR data, common strategies: mean/median imputation (fast, doesn't change the distribution shape, but loses variance); mode imputation for categoricals; forward-fill for time series (use the last known value); and model-based imputation (train a model to predict the missing value from other features — most accurate but most expensive). For MNAR data, the best approach is to create a binary indicator feature: `income_is_missing = 1` if income is missing, 0 otherwise, and keep this as a feature alongside the imputed value. The model can then learn that the missingness itself is predictive.

In production systems, you must track the missing value rate as a data quality metric. If a feature that was rarely missing during training suddenly has 40% missing values in production (sensor failure, schema change, API change), your imputation assumptions break down and model predictions become unreliable. Build monitoring alerts for features whose missing value rate deviates significantly from training-time rates — this is a common source of silent model degradation in production.

### Q5: Why does feature engineering still matter in the age of deep learning?

**Answer:** Deep learning's great promise is automatic feature learning — in principle, a sufficiently deep neural network trained on enough data can learn the optimal features directly from raw inputs. For images and text, this promise has largely been delivered: CNNs learn edge detectors, texture detectors, and object detectors automatically; Transformers learn word and sentence representations without manual feature engineering. But for tabular business data, the promise is largely unfulfilled as of 2026.

Tabular data has properties that make automatic feature learning difficult. The features are heterogeneous (mixing continuous, categorical, ordinal, temporal, and text fields), sparse (many zero or missing values), and the meaningful relationships are often highly non-linear and domain-specific in ways that require tiny quantities of labeled data to learn. A retail pricing model might need to learn that "weekend × holiday × pre-Christmas" is a special demand multiplier — but there are only a handful of such data points per year. A neural network trained on tabular data rarely outperforms a well-engineered XGBoost model, as documented in the "Tabular data: Deep Learning is not all you need" paper by Shwartz-Ziv and Armon (2021) and subsequent benchmarks.

The deeper point is that feature engineering encodes domain knowledge that would require enormous amounts of data for a model to discover autonomously. When you create a `days_since_last_purchase` feature, you are telling the model "recency is a meaningful business concept" — information that took a business analyst years of experience to know. When you create a `price_relative_to_category_median` feature, you are encoding "customers respond to price position relative to alternatives, not just absolute price." These insights dramatically accelerate learning and reduce data requirements.

The practical advice: for deep learning on images/audio/text, let the model learn features and focus your engineering effort on data quality and diversity. For tabular business data, invest heavily in feature engineering — the returns are high, the interpretability is valuable, and it directly incorporates business expertise into the model.

## Key Points to Say in the Interview

- Feature engineering translates business knowledge into mathematical representations models can learn from
- Normalization is required for gradient-based and distance-based algorithms; tree models are more robust without it
- One-hot encoding for nominal categories; label encoding only for ordinal categories; embeddings for high-cardinality
- Handle missing data based on why it's missing: impute MCAR/MAR, create indicator features for MNAR
- Interaction features encode domain knowledge that models would need huge amounts of data to discover
- Feature engineering still matters for tabular data even with deep learning; deep learning learns features for images and text

## Common Mistakes to Avoid

- Don't claim deep learning eliminates feature engineering — it does for images/text, not for tabular business data
- Don't apply label encoding to nominal categoricals — it creates false ordinal relationships
- Don't impute all missing data the same way — distinguish MCAR/MAR from MNAR (absence is signal)
- Don't forget to normalize at inference time using train-set statistics (not test-set statistics — that's data leakage)
- Don't skip missing value monitoring in production — missing rate changes are a primary source of model drift

## Further Reading

- [Feature Engineering for Machine Learning (Zheng and Casari, O'Reilly)](https://www.oreilly.com/library/view/feature-engineering-for/9781491953235/) — The definitive practitioner's book on the topic
- [Kaggle Feature Engineering Tutorial](https://www.kaggle.com/learn/feature-engineering) — Hands-on interactive course with real datasets
- [Why do tree-based models still outperform deep learning on tabular data? (Grinsztajn et al., 2022)](https://arxiv.org/abs/2207.08815) — Research paper documenting the limits of automatic feature learning for tabular data
