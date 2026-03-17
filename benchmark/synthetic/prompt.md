## Basic labels

Generate 200 diverse, realistic text templates for a Swiss PII detection dataset. These templates will be programmatically filled with synthetic personal data for benchmarking a privacy protection system.

**CRITICAL RULES:**
1. Use EXACTLY these placeholders (curly braces, uppercase): {{NAME}}, {{FIRSTNAME}}, {{LASTNAME}}, {{EMAIL}}, {{PHONE}}, {{AHV}}, {{IBAN}}, {{STREET}}, {{POSTCODE}}, {{CITY}}, {{CANTON}}, {{DOB}}, {{COMPANY}}, {{JOB_TITLE}}, {{CUSTOMER_ID}}, {{POLICY_NUMBER}}, {{INSURANCE_NUMBER}}, {{PASSPORT_NUMBER}}, {{DRIVER_LICENSE}}, {{AMOUNT}}, {{CURRENCY}}, {{REFERENCE_NUMBER}}, {{DATE}}, {{TIME}}

2. Output format: Strict JSON array. Each object must have:
   - "template": The text string with placeholders
   - "locale": One of ["de_CH", "fr_CH", "it_CH"] 
   - "domain": One of ["banking", "insurance", "healthcare", "hr_admin", "customer_service", "legal", "ecommerce", "real_estate", "telecom", "government"]
   - "length_category": One of ["short", "medium", "long"]
   - "pii_density": One of ["low", "medium", "high"]
   - "tone": One of ["formal", "informal", "urgent", "neutral"]

**DIVERSITY REQUIREMENTS (MANDATORY):**
- Mix document types: emails (formal/informal), letters, SMS/chat messages, forms, invoices, contracts, medical records, HR documents, customer tickets, legal notices, insurance claims, banking transactions
- Length distribution: 30% short (1-2 sentences), 50% medium (paragraph), 20% long (2+ paragraphs)
- PII scenarios: Single entity per text, multiple scattered entities, nested entities (e.g., "Contact {{NAME}} at {{EMAIL}} or call {{PHONE}}"), entities in headers vs body vs footers
- Swiss cultural specifics: Use Swiss German phrases for de_CH (not Germany German), Swiss French for fr_CH (not France French), Swiss Italian for it_CH. Include Swiss formalities (e.g., "Sehr geehrte Damen und Herren", "Messieurs", "Gentili Signore e Signori")
- Context variations: Payment reminders, appointment confirmations, complaint handling, policy updates, job applications, medical referrals, tax documents, rental agreements

**EXAMPLES OF GOOD TEMPLATES:**

{"template": "Sehr geehrte/r {{NAME}},\n\nWir bestätigen den Erhalt Ihrer AHV-Nummer {{AHV}}. Ihre IBAN {{IBAN}} wird für die Auszahlung verwendet.\n\nFreundliche Grüsse\n{{COMPANY}}", "locale": "de_CH", "domain": "government", "length_category": "short", "pii_density": "high", "tone": "formal"}

{"template": "{{COMPANY}} AG\n{{STREET}} {{POSTCODE}} {{CITY}}\n\nRechnung #{{REFERENCE_NUMBER}}\nKunde: {{NAME}}\nBetrag: {{CURRENCY}} {{AMOUNT}}\nZahlung an: {{IBAN}}", "locale": "de_CH", "domain": "banking", "length_category": "medium", "pii_density": "medium", "tone": "neutral"}

{"template": "Bonjour {{FIRSTNAME}},\nVotre numéro AVS {{AHV}} est incomplet. Merci de nous contacter au {{PHONE}} ou par email {{EMAIL}}.\nCdt", "locale": "fr_CH", "domain": "insurance", "length_category": "short", "pii_density": "high", "tone": "informal"}

{"template": "Gentile Signora {{LASTNAME}},\n\nLa informiamo che la sua polizza {{POLICY_NUMBER}} è stata rinnovata. I dati bancari registrati sono: IBAN {{IBAN}}.\n\nPer qualsiasi domanda: {{EMAIL}}\n\nDistinti saluti\n{{JOB_TITLE}} {{NAME}}", "locale": "it_CH", "domain": "insurance", "length_category": "medium", "pii_density": "high", "tone": "formal"}

{"template": "URGENT: Kundennummer {{CUSTOMER_ID}} - Zahlungserinnerung\nSehr geehrter Herr {{LASTNAME}},\n\nTrotz unserer Mahnung vom {{DATE}} haben wir noch keinen Zahlungseingang für Rechnung {{REFERENCE_NUMBER}} erhalten. Bitte überweisen Sie den Betrag von {{AMOUNT}} {{CURRENCY}} auf folgendes Konto:\n{{IBAN}}\n\nBei Rückfragen: {{PHONE}}", "locale": "de_CH", "domain": "customer_service", "length_category": "long", "pii_density": "high", "tone": "urgent"}

{"template": "Patient: {{NAME}}\nGeburtsdatum: {{DOB}}\nAHV-Nr.: {{AHV}}\nVersicherung: {{INSURANCE_NUMBER}}\nAdresse: {{STREET}}, {{POSTCODE}} {{CITY}} ({{CANTON}})\n\nDiagnose: [...medical text without PII...]\nTermin: {{DATE}} um {{TIME}}", "locale": "de_CH", "domain": "healthcare", "length_category": "long", "pii_density": "high", "tone": "neutral"}

**GENERATE 200 UNIQUE TEMPLATES NOW.**
Ensure high diversity - do not generate 20 versions of the same email structure. Each template should feel distinct in layout, context, and purpose. Include edge cases like PII in email signatures, PII in subject lines, PII in tables/forms format, and conversational vs official tones.

## Comprehensive labels

Generate 200 unique, diverse Swiss PII text templates for privacy detection benchmarking. Use the full comprehensive label set below creatively across varied document types and narrative structures.

**FULL PLACEHOLDER INVENTORY** (Use 5-15 per template, mixing categories creatively):

Personal Identity: {{PERSON}}, {{FIRSTNAME}}, {{LASTNAME}}, {{NAME}}, {{DOB}}, {{AGE}}, {{GENDER}}, {{MARITAL_STATUS}}
Contact: {{EMAIL_ADDRESS}}, {{PHONE}}, {{FAX}}, {{IP_ADDRESS}}, {{URL}}, {{MAC_ADDRESS}}
Location: {{LOCATION_ADDRESS}}, {{STREET}}, {{CITY}}, {{STATE}}, {{COUNTRY}}, {{POSTCODE}}, {{CANTON}}
Financial: {{CREDIT_CARD}}, {{CREDIT_CARD_EXPIRATION}}, {{CVV}}, {{BANK_ACCOUNT}}, {{ROUTING_NUMBER}}, {{IBAN}}, {{ACCOUNT_NUMBER}}, {{MONEY}}, {{CURRENCY}}, {{SSN}}, {{CRYPTO_WALLET}}
Identification Documents: {{PASSPORT_NUMBER}}, {{DRIVER_LICENSE}}, {{VEHICLE_ID}}, {{IDENTITY_CARD_NUMBER}}, {{NATIONAL_ID_NUMBER}}, {{TAX_ID_NUMBER}}, {{TAX_IDENTIFICATION_NUMBER}}, {{USERNAME}}, {{PASSWORD}}
Healthcare (PHI): {{HEALTHCARE_NUMBER}}, {{MEDICAL_CODE}}, {{MEDICAL_PROFESSIONAL}}, {{MEDICAL_LICENSE}}, {{MEDICAL_CONDITION}}, {{CONDITION}}, {{MEDICAL_PROCESS}}, {{DRUG}}, {{DOSE}}, {{BLOOD_TYPE}}, {{INJURY}}
Organization: {{ORGANIZATION}}, {{MEDICAL_FACILITY}}, {{COMPANY}}, {{JOB_TITLE}}
HIPAA Additions: {{DEVICE_IDENTIFIER}}, {{BIOMETRIC_IDENTIFIER}}, {{CERTIFICATE_NUMBER}}
GDPR Article 9 (Sensitive): {{NATIONALITY}}, {{RELIGION}}, {{RACE}}, {{ETHNICITY}}, {{POLITICAL_AFFILIATION}}, {{POLITICAL}}, {{TRADE_UNION}}, {{TRADE_UNION_MEMBERSHIP}}, {{SEXUAL_ORIENTATION}}, {{GENETIC_DATA}}
Work: {{JOB_TITLE}}, {{TITLE}}
Secrets/Technical: {{API_KEY}}, {{PRIVATE_KEY}}, {{REFERENCE_NUMBER}}, {{CUSTOMER_ID}}, {{POLICY_NUMBER}}, {{INSURANCE_NUMBER}}
Temporal: {{DATE}}, {{TIME}}, {{TIMESTAMP}}

**CRITICAL CONSTRAINTS:**
1. **NO REPETITIVE FOOTERS**: Never end with "Kontakt:", "Bei Fragen:", "Weitere Details", "Mit freundlichen Grüssen [contact info]", or similar boilerplate
2. **NO STANDARD SIGNATURE BLOCKS**: Avoid formal letter closings with full contact repeats
3. **VARIED LENGTHS**: 30% short (1-3 sentences), 40% medium (paragraph), 30% long (3+ paragraphs)
4. **UNIQUE STRUCTURE EVERY TIME**: Mix:
   - Narrative stories ("Als {{FIRSTNAME}} {{LASTNAME}} ({{AHV}}) am {{DATE}}...")
   - Dialog/conversations (medical consults, phone scripts, chat logs)
   - Technical logs (server logs, access records, transaction trails)
   - Fragmented documents (email threads with quoted replies, form sections)
   - Lists/scattered PII (packing slips, medical schedules, billing line items)
   - Legal/medical narrative (investigation reports, case histories, proceedings)
   - Unstructured notes (handwritten style, abbreviations, typos)
   - System-generated (SMS alerts, push notifications, automated emails)

**SWISS LOCALIZATION** (rotate evenly de_CH/fr_CH/it_CH):
- de_CH: Swiss German formalities ("Grüezi", "Merci vielmals", "Velo", specific canton references)
- fr_CH: Swiss French ("adieu", "banne", "maman/papa", Romandy region style)
- it_CH: Ticino style, formal "Lei" but Swiss context

**DOMAINS** (wide variety):
banking, insurance, healthcare, hr_admin, customer_service, legal, ecommerce, real_estate, telecom, government, tech, education, travel, logistics, utilities, non-profit, research

**CREATIVE PLACEMENT RULES**:
- Place PII unexpectedly: in subject lines, timestamps, file metadata, URL parameters, code comments
- Use nested/recursive PII: "{{EMAIL}} (Backup: {{PHONE}}, ext {{EXTENSION}})"
- Include "leaky" repetition: same entity appears 2-3 times in different formats
- Messy realism: abbreviations ("Dr. {{NAME}}"), codes mixed with text ("Ref{{REFERENCE_NUMBER}}X"), typos in domains
- Contextual density: some templates sparse (2-3 PII), some dense (12-15 PII scattered throughout)

**EXAMPLE STRUCTURES** (inspiration only, do not copy):

1. **Narrative**: "{{FIRSTNAME}} {{LASTNAME}}, {{AGE}}-jährige {{NATIONALITY}} mit {{RELIGION}}-Hintergrund, zog am {{DOB}} nach {{CITY}}. Ihre {{POLITICAL_AFFILIATION}}-Mitgliedschaft und {{TRADE_UNION}}-Zugehörigkeit wurden unter {{EMAIL_ADDRESS}} registriert."

2. **Fragmented**: "AW: Termin\n\nVon: {{NAME}} <{{EMAIL_ADDRESS}}>\nGesendet: {{DATE}} {{TIME}}\nAn: {{MEDICAL_FACILITY}} <{{EMAIL_ADDRESS}}>\n\nMeine {{MEDICAL_LICENSE}}-Nummer ist {{REFERENCE_NUMBER}}. Blutgruppe: {{BLOOD_TYPE}}. Medikament: {{DRUG}} {{DOSE}}.\n\n> Am {{DATE}} schrieb Dr. {{MEDICAL_PROFESSIONAL}}:\n> Patient {{NAME}} ({{HEALTHCARE_NUMBER}}) hat {{CONDITION}}."

3. **Technical Log**: "[{{TIMESTAMP}}] auth: user={{USERNAME}}|{{PASSWORD}} ip={{IP_ADDRESS}} mac={{MAC_ADDRESS}}\n[{{TIMESTAMP}}] txn: iban={{IBAN}} amt={{MONEY}} cc={{CREDIT_CARD}} cvv={{CVV}} exp={{CREDIT_CARD_EXPIRATION}}\n[{{TIMESTAMP}}] bio: {{BIOMETRIC_IDENTIFIER}} device={{DEVICE_IDENTIFIER}} api={{API_KEY}}"

4. **Investigation Report**: 250-word narrative describing an insurance fraud investigation with PII naturally embedded: "{{NAME}}, geboren {{DOB}}, AHV {{SSN}}, wohnhaft {{STREET}} {{POSTCODE}} {{CITY}}, beruflich {{JOB_TITLE}} bei {{COMPANY}}..."

5. **Form/List**: "Reiseplan {{NAME}} ({{PASSPORT_NUMBER}})\n{{DATE}}: Flug {{REFERENCE_NUMBER}}, Sitz {{VEHICLE_ID}}\nHotel: {{COMPANY}}, {{STREET}}, {{CITY}}\nNotfall: {{PHONE}} / {{EMAIL_ADDRESS}}\nKreditkarte: {{CREDIT_CARD}} ({{CVV}})\nVersicherung: {{POLICY_NUMBER}}"

6. **Code/Config**: 
User Config for {{CUSTOMER_ID}}
db_url = "postgres://{{USERNAME}}:{{PASSWORD}}@{{IP_ADDRESS}}:5432/{{REFERENCE_NUMBER}}"
api_key = "{{API_KEY}}"
private_key = "{{PRIVATE_KEY}}"
wallet = "{{CRYPTO_WALLET}}"
notify = "{{EMAIL_ADDRESS}}"


7. **Sensitive Data Exposure**: "HR-Notiz: Mitarbeiter {{NAME}} ({{GENDER}}, {{SEXUAL_ORIENTATION}}, {{MARITAL_STATUS}}) hat {{GENETIC_DATA}}-Marker. Ethnische Zugehörigkeit: {{ETHNICITY}}/{{RACE}}."

**OUTPUT FORMAT**:
JSON array with objects:
{
  "template": "...",
  "locale": "de_CH|fr_CH|it_CH",
  "domain": "...",
  "structure_type": "narrative|dialog|log|form|list|legal_text|medical_record|chat|code_config|investigation|other",
  "estimated_word_count": number,
  "pii_count": number,
  "pii_categories_used": ["financial", "healthcare", "gdpr_sensitive", "technical"]
}

Generate 200 templates. Ensure ZERO end with repetitive contact blocks. Each must be structurally unique.