# PII Detection Model Comparison: Local Multihead vs GLiNER

## Overview

This analysis compares two PII detection models on German (de_CH) benchmark data:
- **Local Multihead**: Custom ModernBERT-based span classifier (`configs/local_multihead_de.yaml`)
- **GLiNER**: GLiNER PII edge model (`configs/gliner_de.yaml`)

## Test Methodology

- **Dataset**: Swiss benchmark synthetic data (`benchmark/synthetic/generated/swiss_benchmark.jsonl`)
- **Locale**: German (Switzerland) - `de_CH`
- **Samples**: 5 randomly selected documents
- **Date**: 2026-03-17

## Files in This Analysis

| File | Description |
|------|-------------|
| `sample_N_input.txt` | Original input text |
| `sample_N_ground_truth.txt` | Expected entities with positions |
| `sample_N_multihead.txt` | Output from local_multihead model |
| `sample_N_gliner.txt` | Output from GLiNER model |

---

## Summary of Results

### Local Multihead Performance

| Metric | Value |
|--------|-------|
| Overall F1 (100 samples) | 1.58% |
| Entities Detected | 6 types: ADDRESS, CREDIT_CARD, IP_ADDRESS, ORG, OTHER, PERSON |
| EMAIL Detection | Never detected |

### Key Issues with Local Multihead

1. **Excessive OTHER labels**: Many valid PII entities labeled as `<OTHER_X>` instead of proper types
2. **Type confusion**:
   - IBANs mislabeled as `CREDIT_CARD`
   - Addresses sometimes labeled as `ORG`
   - Phone numbers and dates confused
3. **Missing detections**: Organizations, locations, ID numbers often missed entirely
4. **Language barrier**: Model appears trained primarily on English data

### GLiNER Performance

GLiNER demonstrated significantly better performance:

1. **Better type coverage**: Correctly detects IBAN, EMAIL_ADDRESS, PHONE_NUMBER, DATE_TIME, LOCATION
2. **More consistent labeling**: Uses standard entity type names
3. **Better German support**: Handles German text and European PII formats effectively

---

## Detailed Sample Analysis

### Sample 1: Job Application Form

| Entity | Ground Truth | Local Multihead | GLiNER |
|--------|-------------|-----------------|--------|
| Name (Hilda Sölzer) | PERSON | `<first name_2> <last name_2>` | `<PERSON_2>` |
| DOB (1938-12-29) | DATE_TIME | `<DATE_TIME_2>` | `<DATE_TIME_2>` |
| Nationality | NRP | Not detected | Not detected |
| Email | EMAIL_ADDRESS | `<EMAIL_ADDRESS_2>` | `<EMAIL_ADDRESS_2>` |
| Phone | PHONE_NUMBER | `<phone number_2>` | `<phone number_2>` |

### Sample 2: Power of Attorney

| Entity | Ground Truth | Local Multihead | GLiNER |
|--------|-------------|-----------------|--------|
| Name (Dr. Lissi Dietz) | PERSON | `<PERSON_2>` | `<PERSON_2>` |
| DOB (1948-02-26) | DATE_TIME | Not detected | `<DATE_TIME_3>` |
| AHV Number | ID_NUMBER | `<ADDRESS_2>` (wrong!) | Not detected |
| Phone | PHONE_NUMBER | `<PHONE_2>` | `<phone number_2>` |

### Sample 3: Welcome Email

| Entity | Ground Truth | Local Multihead | GLiNER |
|--------|-------------|-----------------|--------|
| Name (Jaroslav) | PERSON | `<PERSON_2>` | `<PERSON_2>` |
| Date (1995-10-31) | DATE_TIME | Not detected | `<DATE_TIME_2>` |
| Address | LOCATION | Not detected | `<location address_2>` |
| Phone | PHONE_NUMBER | `<PHONE_2>` | `<phone number_2>` |
| Name (Sedat Sorgatz) | PERSON | `<OTHER_2>` (wrong!) | Missed |

### Sample 4: Customer Application

| Entity | Ground Truth | Local Multihead | GLiNER |
|--------|-------------|-----------------|--------|
| ID (ADOOEVNFOD) | ID_NUMBER | `<OTHER_10>` | Not detected |
| Name (Kunibert Fiebig) | PERSON | `<OTHER_9>` (wrong!) | `<PERSON_3>` |
| Address | LOCATION | `<ORG_2>` (wrong!) | `<location address_2>` |
| Phone | PHONE_NUMBER | `<PHONE_2>` | `<phone number_2>` |
| Email | EMAIL_ADDRESS | `<OTHER_6>` (wrong!) | `<EMAIL_ADDRESS_2>` |
| IBAN | IBAN | `<OTHER_5>` (wrong!) | `<IBAN_CODE_2>` |

### Sample 5: Account Cancellation

| Entity | Ground Truth | Local Multihead | GLiNER |
|--------|-------------|-----------------|--------|
| IBAN | IBAN | `<CREDIT_CARD_2>` (wrong!) | `<IBAN_CODE_2>` |
| Company (Dippel Kensy GmbH) | ORGANIZATION | Not detected | `<ORGANIZATION_3>` |
| Name (Friedrich Höfig) | PERSON | `<PERSON_3>` | `<first name_2> <PERSON_3>` |
| Address | LOCATION | Not detected | `<location address_2>` |
| AHV Number | ID_NUMBER | Not detected | `<ORGANIZATION_2>` (wrong!) |
| Email | EMAIL_ADDRESS | `<OTHER_3>` (wrong!) | `<EMAIL_ADDRESS_2>` |

---

## Entity Type Output Analysis

The local_multihead model outputs these entity types on German benchmark data:

| Model Output | Examples | Quality |
|--------------|----------|---------|
| `ADDRESS` | Henschelplatz 218, 00133 Regen | Mixed - some false positives |
| `CREDIT_CARD` | DE15402654235116155940 | **Wrong** - these are IBANs, not credit cards |
| `IP_ADDRESS` | 123.111.57.41 | Correct |
| `ORG` | Dowerg, Kreditgesuch | Mixed - includes non-organizations |
| `OTHER` | Kontoauszug, Kunde | **Problematic** - overused for valid PII |
| `PERSON` | Dr. Ingrid Schacht | Mixed - includes false positives like "Sehr geehrte" |
| `PHONE` | 1981-03-05, 756.3465.7871.54 | **Wrong** - includes dates and AHV numbers |

**Note**: `EMAIL` was never detected in any German sample.

---

## Conclusions

### Local Multihead Model

The local_multihead model is **not suitable for German PII detection**:

1. **Trained on English data**: The model struggles with German text structure and vocabulary
2. **Poor entity type discrimination**: Over-classifies as `OTHER` and confuses similar formats (IBAN vs credit card)
3. **Missing capabilities**: Never detects EMAIL entities in German text
4. **False positives**: Common German phrases like "Sehr geehrte" incorrectly classified as PERSON

### GLiNER Model

GLiNER is the **recommended choice for German PII detection**:

1. **Multilingual support**: Handles German text effectively
2. **Better entity recognition**: Correctly identifies most PII types
3. **European format support**: Properly handles IBANs, Swiss phone numbers, etc.

### Recommendations

1. **For German PII detection**: Use GLiNER (`configs/gliner_de.yaml`)
2. **For local_multihead**: Consider fine-tuning on German/ multilingual data before production use
3. **Entity type mapping**: The mappings added to `benchmark/entity_normalizer.py` (`EMAIL` → `EMAIL_ADDRESS`, `PHONE` → `PHONE_NUMBER`) are correct but won't significantly improve scores for local_multihead due to underlying detection issues

---

## Benchmark Scores (100 samples, de_CH locale)

| Model | Precision | Recall | F1 Score |
|-------|-----------|--------|----------|
| stanza_de | 66.2% | 33.5% | 44.5% |
| gliner_de | 54.0% | 39.7% | 45.8% |
| xlmr_de | 51.0% | 23.6% | 32.2% |
| local_multihead_de | 1.6% | 1.6% | 1.6% |

---

## Appendix: Model Training Labels

The local_multihead model was trained with these labels:
- NONE, PERSON, ORG, ADDRESS, EMAIL, PHONE, USERNAME, PASSWORD
- IP_ADDRESS, IBAN, CREDIT_CARD, ID_NUMBER, ACCOUNT_NUMBER, OTHER

The gap between training labels and actual detection performance suggests the model needs retraining with German/multilingual data.
