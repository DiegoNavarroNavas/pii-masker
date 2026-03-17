# German (de_CH) Benchmark Analysis

**Dataset:** Synthetic Swiss Benchmark
**Locale:** de_CH (German - Switzerland)
**Samples:** 100
**Date:** 2026-03-17

---

## Overall Results

| Model | Precision | Recall | F1 Score | Time (100 samples) | Avg/Sample |
|-------|-----------|--------|----------|-------------------|------------|
| **GLiNER DE** | 54.3% | 39.6% | **45.8%** ⭐ | 43.4s | 434ms |
| **Stanza DE** | 66.2% | 33.5% | **44.5%** | 81.8s | 818ms |
| **XLM-R DE** | 51.0% | 23.6% | 32.2% | 54.9s | 549ms |
| **Local Multihead DE** | 1.6% | 1.6% | 1.6% | 38.1s | 381ms |

**Winner: GLiNER DE** (highest F1 score of 45.8%, fastest among usable models)

---

## Performance vs Speed Trade-off

```
F1 Score
   │
50%├─────────────────────────────────────────────────
   │                     ★ GLiNER (45.8%, 434ms)
45%├─────────────────────────────────────────────────
   │         ★ Stanza (44.5%, 818ms)
40%├─────────────────────────────────────────────────
   │
35%├─────────────────────────────────────────────────
   │                              ★ XLM-R (32.2%, 549ms)
30%├─────────────────────────────────────────────────
   │
25%├─────────────────────────────────────────────────
   │
20%├─────────────────────────────────────────────────
   │
15%├─────────────────────────────────────────────────
   │
10%├─────────────────────────────────────────────────
   │
 5%├─────────────────────────────────────────────────
   │  ★ Local Multihead (1.6%, 381ms) - Not usable
 0%└─────────────────────────────────────────────────
     300ms    400ms    500ms    600ms    700ms    800ms    900ms
                        Processing Time per Sample
```

### Speed Analysis

| Model | Relative Speed | F1/Second (Efficiency) |
|-------|----------------|------------------------|
| **GLiNER DE** | 1.0x (fastest usable) | 1.06 ⭐ |
| **Local Multihead DE** | 0.88x | 0.04 (not usable) |
| **XLM-R DE** | 1.26x | 0.59 |
| **Stanza DE** | 1.88x (slowest) | 0.54 |

**Key Insight:** GLiNER offers the best balance of accuracy and speed - it's both the most accurate AND the fastest among usable models.

---

## Per-Model Analysis

### 1. Stanza DE (F1: 44.5%, 818ms/sample)

**Strengths:**
- IBAN: 100% precision, 100% recall
- EMAIL_ADDRESS: 100% precision, 100% recall
- DATE_TIME: 100% precision, 85.7% recall

**Weaknesses:**
- PHONE_NUMBER: 0% (not detected)
- ID_NUMBER: 0% (not detected)
- FINANCIAL: 0% (not detected)
- TITLE: 0% (not detected)

**Performance:** Slowest model at 818ms per sample (1.9x slower than GLiNER). The high precision (66.2%) doesn't compensate for the speed penalty when recall is low.

**Summary:** Excellent at structured formats (IBAN, email, dates) but misses phones and ID numbers entirely. High precision but lower recall overall. Slow performance.

---

### 2. GLiNER DE (F1: 45.8%, 434ms/sample) ⭐ Best Overall

**Strengths:**
- PHONE_NUMBER: 97.5% precision, 95.1% recall ⭐
- IBAN: 100% precision, 96.9% recall
- EMAIL_ADDRESS: 100% precision, 100% recall
- DATE_TIME: 100% precision, 85.7% recall
- PERSON: 42.5% precision, 45.3% recall

**Weaknesses:**
- ID_NUMBER: 0% (not detected)
- TITLE: 0% (not detected)
- ORGANIZATION: 5.7% precision (many false positives)
- FINANCIAL: 1.1% recall (almost none detected)

**Performance:** Fastest usable model at 434ms per sample. Best efficiency score (F1/second = 1.06).

**Summary:** Best all-around performer with optimal accuracy/speed trade-off. Excels at phone number detection (which other models miss entirely). Good balance of precision and recall.

---

### 3. XLM-R DE (F1: 32.2%, 549ms/sample)

**Strengths:**
- IBAN: 100% precision, 100% recall
- EMAIL_ADDRESS: 100% precision, 98.4% recall
- DATE_TIME: 100% precision, 85.7% recall

**Weaknesses:**
- PHONE_NUMBER: 0% (not detected)
- ID_NUMBER: 0% (not detected)
- FINANCIAL: 0% (not detected)
- LOCATION: 22.7% precision, 6.8% recall

**Performance:** 549ms per sample (1.26x slower than GLiNER). Lower efficiency than GLiNER.

**Summary:** Similar pattern to Stanza - good at structured formats but poor at NER-based detection. Lower performance than Stanza overall and slower than GLiNER.

---

### 4. Local Multihead DE (F1: 1.6%, 381ms/sample) ❌ Not Recommended

**Strengths:**
- Fastest model at 381ms per sample

**Weaknesses:**
- All entity types near 0% except:
  - PERSON: 10.7% precision, 7.3% recall
  - ORGANIZATION: 2.7% precision, 7.9% recall
  - PHONE_NUMBER: 2.3% precision, 2.5% recall

**Critical Issues:**
- LOCATION: 0% (292 ground truth instances missed)
- DATE_TIME: 0% (119 instances missed)
- ID_NUMBER: 0% (112 instances missed)
- EMAIL_ADDRESS: 0% (62 instances missed)
- IBAN: 0% (32 instances missed)

**Performance:** Technically the fastest at 381ms/sample, but the speed advantage is meaningless given the near-zero accuracy.

**Summary:** Model is not suitable for German PII detection. Appears to be trained on English data without multilingual support. Speed advantage is irrelevant given unusable accuracy.

---

## Entity-Level Comparison

### Structured Formats (High Performance)

| Entity | Best Model | Precision | Recall | F1 |
|--------|------------|-----------|--------|-----|
| IBAN | Stanza/GLiNER/XLM-R | 100% | 97-100% | ~99% |
| EMAIL_ADDRESS | Stanza/GLiNER/XLM-R | 100% | 98-100% | ~99% |
| DATE_TIME | Stanza/GLiNER/XLM-R | 100% | 85.7% | 92.3% |

### NER-Based Entities (Variable Performance)

| Entity | Best Model | Precision | Recall | F1 |
|--------|------------|-----------|--------|-----|
| PERSON | GLiNER | 42.2% | 45.3% | 43.7% |
| LOCATION | Stanza | 69.6% | 27.4% | 39.3% |
| ORGANIZATION | Stanza | 41.7% | 26.3% | 32.3% |
| PHONE_NUMBER | **GLiNER** | 97.5% | 95.1% | 96.3% ⭐ |

### Undetected Entities (All Models Struggle)

| Entity | Support | Best Recall |
|--------|---------|-------------|
| ID_NUMBER | 112 | 0% (none detected) |
| FINANCIAL | 94 | 1.1% (GLiNER) |
| TITLE | 15 | 0% (none detected) |
| DRIVER_LICENSE | 1 | 0% |
| PASSPORT | 1 | 0% |

---

## Key Findings

### 1. GLiNER is the Best Choice for German PII

GLiNER achieves the highest F1 score (45.8%) AND is the fastest among usable models (434ms/sample). It's the **only model that reliably detects phone numbers** (96.3% F1). This is critical for Swiss/German documents where phone numbers are common PII.

### 2. Stanza is Slow Despite Lower Recall

Stanza has the slowest processing time (818ms/sample) despite having the highest precision (66.2%). Its lower recall (33.5%) and slow speed make it less efficient than GLiNER for production use.

### 3. All Models Struggle with ID Numbers

No model reliably detects:
- ID_NUMBER (Swiss AHV numbers, customer IDs)
- FINANCIAL (monetary amounts)
- TITLE (job titles)

This suggests a gap in training data or the need for custom recognizers.

### 4. Local Multihead is Not Suitable for German

With only 1.6% F1, the local_multihead model is not production-ready for German text. Its speed advantage (381ms/sample) is irrelevant given unusable accuracy. It needs:
- Retraining on German/multilingual data
- Fine-tuning for European PII formats

### 5. Structured Formats are Well-Handled

All Presidio-based models (Stanza, GLiNER, XLM-R) handle structured formats excellently:
- IBANs (European bank accounts)
- Email addresses
- Dates/times

This is likely due to Presidio's pattern-based recognizers.

---

## Recommendations

### For Production Use

1. **Primary Model:** Use **GLiNER DE** (`configs/gliner_de.yaml`)
   - Best overall F1 score (45.8%)
   - Fastest among usable models (434ms/sample)
   - Only model with reliable phone detection
   - Good PERSON detection
   - Best efficiency (F1/second = 1.06)

2. **When to use Stanza DE:**
   - If precision is more important than recall
   - If phone number detection is not needed
   - If processing time is not a concern (1.9x slower than GLiNER)

3. **Hybrid Approach:** Consider combining models:
   - GLiNER for: PERSON, PHONE_NUMBER, DATE_TIME
   - Stanza for: LOCATION, ORGANIZATION (higher precision)
   - Note: This doubles processing time

4. **Add Custom Recognizers for:**
   - ID_NUMBER (Swiss AHV format: 756.XXXX.XXXX.XX)
   - FINANCIAL (currency amounts)
   - TITLE (job titles)

### For High-Volume Processing

| Throughput Target | Recommended Model |
|-------------------|-------------------|
| < 2 docs/sec | GLiNER DE (434ms/doc) |
| 2-3 docs/sec | Consider batch processing with GLiNER |
| > 3 docs/sec | Local Multihead after retraining, or parallel processing |

### For Future Development

1. **Local Multihead:** Requires retraining with:
   - German training data
   - European PII formats
   - Multilingual tokenizer
   - Target: Match GLiNER accuracy at 381ms/sample

2. **Benchmark Expansion:** Add more test cases for:
   - ID numbers (currently 112 instances)
   - Financial data (94 instances)
   - Titles (15 instances - increase coverage)

---

## Appendix: Full Entity Metrics

### Stanza DE (81.8s total, 818ms/sample)

| Entity | Precision | Recall | F1 | Support |
|--------|-----------|--------|-----|---------|
| IBAN | 100.0% | 100.0% | 100.0% | 32 |
| EMAIL_ADDRESS | 100.0% | 100.0% | 100.0% | 62 |
| DATE_TIME | 100.0% | 85.7% | 92.3% | 119 |
| LOCATION | 69.6% | 27.4% | 39.3% | 292 |
| PERSON | 32.9% | 34.0% | 33.4% | 150 |
| ORGANIZATION | 41.7% | 26.3% | 32.3% | 38 |
| ID_NUMBER | 0.0% | 0.0% | 0.0% | 112 |
| PHONE_NUMBER | 0.0% | 0.0% | 0.0% | 81 |
| FINANCIAL | 0.0% | 0.0% | 0.0% | 94 |

### GLiNER DE (43.4s total, 434ms/sample)

| Entity | Precision | Recall | F1 | Support |
|--------|-----------|--------|-----|---------|
| IBAN | 100.0% | 96.9% | 98.4% | 32 |
| EMAIL_ADDRESS | 100.0% | 100.0% | 100.0% | 62 |
| PHONE_NUMBER | 97.5% | 95.1% | 96.3% | 81 |
| DATE_TIME | 100.0% | 85.7% | 92.3% | 119 |
| PERSON | 42.2% | 45.3% | 43.7% | 150 |
| LOCATION | 33.1% | 16.8% | 22.3% | 292 |
| FINANCIAL | 100.0% | 1.1% | 2.1% | 94 |
| ORGANIZATION | 5.7% | 18.4% | 8.7% | 38 |
| ID_NUMBER | 0.0% | 0.0% | 0.0% | 112 |

### XLM-R DE (54.9s total, 549ms/sample)

| Entity | Precision | Recall | F1 | Support |
|--------|-----------|--------|-----|---------|
| IBAN | 100.0% | 100.0% | 100.0% | 32 |
| EMAIL_ADDRESS | 100.0% | 98.4% | 99.2% | 62 |
| DATE_TIME | 100.0% | 85.7% | 92.3% | 119 |
| LOCATION | 22.7% | 6.8% | 10.5% | 292 |
| PERSON | 13.8% | 12.0% | 12.9% | 150 |
| ORGANIZATION | 12.1% | 10.5% | 11.3% | 38 |
| ID_NUMBER | 0.0% | 0.0% | 0.0% | 112 |
| PHONE_NUMBER | 0.0% | 0.0% | 0.0% | 81 |
| FINANCIAL | 0.0% | 0.0% | 0.0% | 94 |

### Local Multihead DE (38.1s total, 381ms/sample)

| Entity | Precision | Recall | F1 | Support |
|--------|-----------|--------|-----|---------|
| PERSON | 10.7% | 7.3% | 8.7% | 150 |
| ORGANIZATION | 2.7% | 7.9% | 4.1% | 38 |
| PHONE_NUMBER | 2.3% | 2.5% | 2.4% | 81 |
| All others | 0.0% | 0.0% | 0.0% | - |
