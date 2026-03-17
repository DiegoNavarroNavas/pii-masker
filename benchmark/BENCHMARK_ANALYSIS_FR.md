# French (fr_CH) Benchmark Analysis

**Dataset:** Synthetic Swiss Benchmark
**Locale:** fr_CH (French - Switzerland)
**Samples:** 569
**Date:** 2026-03-17

---

## Overall Results

| Model | Precision | Recall | F1 Score | Time (569 samples) | Avg/Sample |
|-------|-----------|--------|----------|-------------------|------------|
| **XLM-R FR** | 62.5% | 25.0% | **35.7%** ⭐ | 480.2s | 844ms |
| **GLiNER FR** | 37.3% | 31.6% | **34.2%** | 734.0s | 1290ms |
| **Stanza FR** | 51.3% | 24.7% | **33.3%** | 897.1s | 1577ms |
| **Local Multihead FR** | 1.5% | 1.1% | **1.3%** | 477.0s | 838ms |

**Winner: XLM-R FR** (highest F1 score of 35.7%, best precision)

---

## Performance vs Speed Trade-off

```
F1 Score
   │
40%├─────────────────────────────────────────────────
   │
35%├─────────★ XLM-R (35.7%, 844ms)
   │         ★ GLiNER (34.2%, 1290ms)
30%├─────────────────────────────────────────────────
   │         ★ Stanza (33.3%, 1577ms)
25%├─────────────────────────────────────────────────
   │
20%├─────────────────────────────────────────────────
   │
15%├─────────────────────────────────────────────────
   │
10%├─────────────────────────────────────────────────
   │
 5%├─────────────────────────────────────────────────
   │  ★ Local Multihead (1.3%, 838ms) - Not usable
 0%└─────────────────────────────────────────────────
     600ms   800ms   1000ms  1200ms  1400ms  1600ms
                        Processing Time per Sample
```

### Speed Analysis

| Model | Relative Speed | F1/Second (Efficiency) |
|-------|----------------|------------------------|
| **Local Multihead FR** | 1.0x (fastest) | 0.002 (not usable) |
| **XLM-R FR** | 1.01x | 0.042 ⭐ |
| **GLiNER FR** | 1.53x | 0.026 |
| **Stanza FR** | 1.87x (slowest) | 0.021 |

**Key Insight:** XLM-R offers the best balance of accuracy and speed for French text - highest F1 with reasonable processing time.

---

## Per-Model Analysis

### 1. XLM-R FR (F1: 35.7%, 844ms/sample) ⭐ Best Overall

**Strengths:**
- IBAN: 100% precision, 100% recall
- EMAIL_ADDRESS: 99.2% precision, 98.4% recall
- DATE_TIME: 99.8% precision, 70.8% recall
- IP_ADDRESS: 100% precision, 97.5% recall
- PHONE_NUMBER: 100% precision, 18.0% recall

**Weaknesses:**
- ID_NUMBER: 0% (not detected)
- FINANCIAL: 0% (not detected)
- CRYPTO: 0% (not detected)
- LOCATION: 29.3% precision, 8.3% recall

**Performance:** Fastest usable model at 844ms per sample. Best efficiency score among usable models.

**Summary:** Best all-around performer for French with optimal accuracy/speed trade-off. Excellent at structured formats and competitive on NER tasks.

---

### 2. GLiNER FR (F1: 34.2%, 1290ms/sample)

**Strengths:**
- IBAN: 100% precision, 89.4% recall
- EMAIL_ADDRESS: 99.1% precision, 94.0% recall
- PHONE_NUMBER: 94.1% precision, 96.4% recall ⭐
- IP_ADDRESS: 92.8% precision, 96.3% recall
- DATE_TIME: 98.3% precision, 66.7% recall
- CRYPTO: 95.5% precision, 21.4% recall

**Weaknesses:**
- ID_NUMBER: 78.9% precision but only 4.8% recall
- ORGANIZATION: 2.7% precision (many false positives)
- LOCATION: 9.7% precision, 11.6% recall
- FINANCIAL: 62.5% precision but only 1.2% recall

**Performance:** Slower at 1290ms per sample (1.53x slower than XLM-R).

**Summary:** Strong performance on phone numbers and structured data. Good recall but lower precision on many entities. Slower than XLM-R.

---

### 3. Stanza FR (F1: 33.3%, 1577ms/sample)

**Strengths:**
- IBAN: 100% precision, 97.8% recall
- EMAIL_ADDRESS: 99.2% precision, 97.6% recall
- IP_ADDRESS: 100% precision, 97.5% recall
- DATE_TIME: 99.8% precision, 70.0% recall

**Weaknesses:**
- PHONE_NUMBER: 100% precision but only 17.0% recall
- ID_NUMBER: 0% (not detected)
- FINANCIAL: 0% (not detected)
- CRYPTO: 0% (not detected)
- LOCATION: 18.2% precision, 11.2% recall

**Performance:** Slowest model at 1577ms per sample (1.87x slower than XLM-R).

**Summary:** High precision but lower recall and slowest processing time. Good for structured formats but misses many entity types.

---

### 4. Local Multihead FR (F1: 1.3%, 838ms/sample) ❌ Not Recommended

**Strengths:**
- Fast processing at 838ms per sample
- IP_ADDRESS: 46.2% precision, 15.0% recall

**Weaknesses:**
- All major entity types near 0%:
  - LOCATION: 0%
  - ID_NUMBER: 0%
  - DATE_TIME: 0%
  - FINANCIAL: 0%
  - EMAIL_ADDRESS: 0%
  - IBAN: 0%
- PERSON: 6.2% precision, 4.7% recall
- ORGANIZATION: 2.8% precision, 2.3% recall

**Critical Issues:**
- Model appears trained on English data without French/multilingual support
- Near-zero accuracy across most entity types
- Speed advantage is irrelevant given unusable accuracy

**Summary:** Not suitable for French PII detection. Requires retraining on French/multilingual data.

---

## Entity-Level Comparison

### Structured Formats (High Performance)

| Entity | Best Model | Precision | Recall | F1 |
|--------|------------|-----------|--------|-----|
| IBAN | XLM-R | 100% | 100% | 100% ⭐ |
| EMAIL_ADDRESS | XLM-R | 99.2% | 98.4% | 98.8% ⭐ |
| DATE_TIME | XLM-R/Stanza | ~99% | 70% | ~82% |
| IP_ADDRESS | XLM-R/Stanza | 100% | 97.5% | ~99% |

### NER-Based Entities (Variable Performance)

| Entity | Best Model | Precision | Recall | F1 |
|--------|------------|-----------|--------|-----|
| PHONE_NUMBER | **GLiNER** | 94.1% | 96.4% | 95.2% ⭐ |
| PERSON | XLM-R | 31.6% | 28.2% | 29.8% |
| ORGANIZATION | XLM-R | 20.3% | 15.6% | 17.6% |
| LOCATION | XLM-R | 29.3% | 8.3% | 12.9% |

### Undetected Entities (All Models Struggle)

| Entity | Support | Best Recall |
|--------|---------|-------------|
| ID_NUMBER | 934 | 4.8% (GLiNER) |
| FINANCIAL | 429 | 1.2% (GLiNER) |
| MEDICAL | 234 | 0% |
| CRYPTO | 98 | 21.4% (GLiNER) |
| TITLE | 96 | 0% |

---

## Key Findings

### 1. XLM-R is the Best Choice for French PII

XLM-R achieves the highest F1 score (35.7%) with the best precision (62.5%). It's the **fastest among high-performing models** (844ms/sample) and excels at structured format detection.

### 2. GLiNER Excels at Phone Detection

GLiNER is the **only model with reliable phone number detection** for French (95.2% F1). This is critical for Swiss/French documents where phone numbers are common PII. However, it's slower (1290ms/sample) and has lower precision than XLM-R.

### 3. Stanza is Slow with Lower Recall

Stanza has the slowest processing time (1577ms/sample) with lower recall (24.7%). Its high precision (51.3%) doesn't compensate for the speed penalty and lower coverage.

### 4. All Models Struggle with ID Numbers and Financial Data

No model reliably detects:
- ID_NUMBER (Swiss AVS numbers, customer IDs) - best is 4.8% recall
- FINANCIAL (monetary amounts) - best is 1.2% recall
- MEDICAL entities - 0% across all models
- TITLE (job titles) - 0% across all models

This suggests a gap in training data or the need for custom recognizers.

### 5. Local Multihead is Not Suitable for French

With only 1.3% F1, the local_multihead model is not production-ready for French text. It needs:
- Retraining on French/multilingual data
- Fine-tuning for European PII formats
- Support for French text tokenization

### 6. Structured Formats are Well-Handled

All Presidio-based models (XLM-R, GLiNER, Stanza) handle structured formats excellently:
- IBANs (European bank accounts)
- Email addresses
- IP addresses
- Dates/times

---

## Comparison: French vs German Performance

| Model | German F1 | French F1 | Difference |
|-------|-----------|-----------|------------|
| **GLiNER** | 45.8% | 34.2% | -11.6% |
| **Stanza** | 44.5% | 33.3% | -11.2% |
| **XLM-R** | 32.2% | 35.7% | +3.5% |
| **Local Multihead** | 1.6% | 1.3% | -0.3% |

**Key Insight:** XLM-R performs relatively better on French (+3.5%) while GLiNER and Stanza perform better on German (-11%). This suggests XLM-R's multilingual training provides more balanced coverage across languages.

---

## Recommendations

### For Production Use

1. **Primary Model:** Use **XLM-R FR** (`configs/xlmr_fr.yaml`)
   - Highest F1 score (35.7%)
   - Best precision (62.5%)
   - Fastest among high-performing models (844ms/sample)
   - Excellent structured format detection

2. **When to use GLiNER FR:**
   - If phone number detection is critical (95.2% F1)
   - If recall is more important than precision
   - If processing time is not a concern (1.53x slower than XLM-R)

3. **Hybrid Approach:** Consider combining models:
   - XLM-R for: IBAN, EMAIL, DATE_TIME, IP_ADDRESS, PERSON
   - GLiNER for: PHONE_NUMBER (superior detection)
   - Note: This increases processing time

4. **Add Custom Recognizers for:**
   - ID_NUMBER (Swiss AVS format: 756.XXXX.XXXX.XX)
   - FINANCIAL (currency amounts)
   - MEDICAL entities
   - TITLE (job titles)

### For High-Volume Processing

| Throughput Target | Recommended Model |
|-------------------|-------------------|
| < 1 doc/sec | XLM-R FR (844ms/doc) |
| 1-2 docs/sec | Consider batch processing with XLM-R |
| > 2 docs/sec | Parallel processing or GPU acceleration |

### For Future Development

1. **Local Multihead:** Requires retraining with:
   - French training data
   - European PII formats
   - Multilingual tokenizer
   - Target: Match XLM-R accuracy at 838ms/sample

2. **Benchmark Expansion:** Add more test cases for:
   - ID numbers (934 instances in current dataset)
   - Financial data (429 instances)
   - Medical entities (234 instances)
   - Titles (96 instances)

3. **Custom Recognizers:** Develop pattern-based recognizers for:
   - Swiss AVS numbers
   - French postal codes
   - Currency amounts
   - Phone number variations

---

## Appendix: Full Entity Metrics

### XLM-R FR (480.2s total, 844ms/sample)

| Entity | Precision | Recall | F1 | Support |
|--------|-----------|--------|-----|---------|
| IBAN | 100.0% | 100.0% | 100.0% | 179 |
| EMAIL_ADDRESS | 99.2% | 98.4% | 98.8% | 367 |
| IP_ADDRESS | 100.0% | 97.5% | 98.7% | 80 |
| DATE_TIME | 99.8% | 70.8% | 82.8% | 766 |
| PHONE_NUMBER | 100.0% | 18.0% | 30.5% | 411 |
| PERSON | 31.6% | 28.2% | 29.8% | 879 |
| ORGANIZATION | 20.3% | 15.6% | 17.6% | 301 |
| LOCATION | 29.3% | 8.3% | 12.9% | 1184 |
| ID_NUMBER | 0.0% | 0.0% | 0.0% | 934 |
| FINANCIAL | 0.0% | 0.0% | 0.0% | 429 |

### GLiNER FR (734.0s total, 1290ms/sample)

| Entity | Precision | Recall | F1 | Support |
|--------|-----------|--------|-----|---------|
| IBAN | 100.0% | 89.4% | 94.4% | 179 |
| EMAIL_ADDRESS | 99.1% | 94.0% | 96.5% | 367 |
| PHONE_NUMBER | 94.1% | 96.4% | 95.2% | 411 |
| IP_ADDRESS | 92.8% | 96.3% | 94.5% | 80 |
| DATE_TIME | 98.3% | 66.7% | 79.5% | 766 |
| CRYPTO | 95.5% | 21.4% | 35.0% | 98 |
| PERSON | 17.9% | 32.3% | 23.0% | 879 |
| USERNAME | 72.2% | 61.9% | 66.7% | 42 |
| ID_NUMBER | 78.9% | 4.8% | 9.1% | 934 |
| LOCATION | 9.7% | 11.6% | 10.5% | 1184 |
| ORGANIZATION | 2.7% | 5.3% | 3.6% | 301 |
| FINANCIAL | 62.5% | 1.2% | 2.3% | 429 |

### Stanza FR (897.1s total, 1577ms/sample)

| Entity | Precision | Recall | F1 | Support |
|--------|-----------|--------|-----|---------|
| IBAN | 100.0% | 97.8% | 98.9% | 179 |
| EMAIL_ADDRESS | 99.2% | 97.6% | 98.4% | 367 |
| IP_ADDRESS | 100.0% | 97.5% | 98.7% | 80 |
| DATE_TIME | 99.8% | 70.0% | 82.3% | 766 |
| LOCATION | 18.2% | 11.2% | 13.9% | 1184 |
| PERSON | 29.9% | 28.0% | 28.9% | 879 |
| PHONE_NUMBER | 100.0% | 17.0% | 29.1% | 411 |
| ORGANIZATION | 2.9% | 3.3% | 3.1% | 301 |
| ID_NUMBER | 0.0% | 0.0% | 0.0% | 934 |
| FINANCIAL | 0.0% | 0.0% | 0.0% | 429 |

### Local Multihead FR (477.0s total, 838ms/sample)

| Entity | Precision | Recall | F1 | Support |
|--------|-----------|--------|-----|---------|
| IP_ADDRESS | 46.2% | 15.0% | 22.6% | 80 |
| PERSON | 6.2% | 4.7% | 5.3% | 879 |
| PHONE_NUMBER | 1.9% | 1.7% | 1.8% | 411 |
| ORGANIZATION | 2.8% | 2.3% | 2.6% | 301 |
| All others | 0.0% | 0.0% | 0.0% | - |
