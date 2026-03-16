"""Placeholder to Faker generator and entity type mapping.

Maps template placeholders to Faker generators and canonical entity types.
"""

# Map placeholder names to Faker methods (as method name strings or callables)
# Format: "PLACEHOLDER_NAME": "faker_method_name" or None for custom handling
PLACEHOLDER_TO_FAKER = {
    # Person
    "NAME": "name",
    "FIRSTNAME": "first_name",
    "LASTNAME": "last_name",
    "PERSON": "name",

    # Contact
    "EMAIL": "email",
    "EMAIL_ADDRESS": "email",
    "PHONE": "swiss_phone",  # Custom provider
    "CELL_NUMBER": "phone_number",
    "FAX": "phone_number",
    "IP_ADDRESS": "ipv4",
    "MAC_ADDRESS": "mac_address",
    "URL": "url",

    # Location
    "STREET": "street_address",
    "STREAT": "street_address",  # Typo variant
    "CITY": "city",
    "CANTON": "canton_from_city",  # Custom provider
    "POSTCODE": "postcode",
    "STATE": "state",
    "COUNTRY": "country",
    "LOCATION_ADDRESS": "address",
    "CEMETERY_ADDRESS": "address",

    # Financial
    "CREDIT_CARD": "credit_card_number",
    "CREDIT_CARD_EXPIRATION": "credit_card_expire",
    "CVV": "credit_card_security_code",  # Note: typically shouldn't store
    "IBAN": "iban",
    "BANK": "company",
    "BANK_ACCOUNT": "bban",
    "ACCOUNT_NUMBER": "uuid4",  # Generate UUID-based account number
    "ROUTING_NUMBER": "pystr",  # Not directly applicable, use random string
    "MONEY": "pystr",  # Placeholder, handled specially
    "AMOUNT": "pyfloat",  # Handled specially with currency
    "CURRENCY": "currency_code",
    "INTEREST_RATE": "pyfloat",
    "PRICE": "pydecimal",

    # Swiss-specific IDs
    "AHV": "swiss_ahv",  # Custom provider
    "SSN": "ssn",
    "NATIONAL_ID_NUMBER": "ssn",
    "TAX_IDENTIFICATION_NUMBER": "pystr",
    "TAX_ID_NUMBER": "pystr",
    "IDENTITY_CARD_NUMBER": "pystr",
    "PASSPORT_NUMBER": "pystr",
    "DRIVER_LICENSE": "pystr",

    # Business/Reference IDs
    "CUSTOMER_ID": "uuid4",
    "POLICY_NUMBER": "pystr",
    "REFERENCE_NUMBER": "pystr",
    "CASE_NUMBER": "pystr",
    "CASE_REFERENCE": "pystr",
    "CERTIFICATE_NUMBER": "pystr",
    "ASSESSMENT_REFERENCE": "pystr",
    "CODE": "pystr",
    "NUMBER": "pystr",

    # Organization
    "COMPANY": "company",
    "ORGANIZATION": "company",
    "TRADEMARK_NAME": "company",
    "TRADE_UNION": "company",

    # Work/Title
    "JOB_TITLE": "job",
    "TITLE": "prefix",
    "WORK_TITLE": "job",
    "RANK": "job",

    # Digital/Secrets
    "USERNAME": "user_name",
    "PASSWORD": "password",
    "API_KEY": "uuid4",
    "PRIVATE_KEY": "sha256",
    "CRYPTO_WALLET": "pystr",
    "DEVICE_IDENTIFIER": "uuid4",

    # Demographics (GDPR sensitive - NRP)
    "NATIONALITY": "country",
    "RELIGION": "word",  # Avoid generating specific religious data
    "POLITICAL_AFFILIATION": "word",  # Avoid generating specific political data
    "POLITICAL": "word",
    "RACE": "word",
    "ETHNICITY": "word",
    "GENDER": "word",
    "BIRTH_GENDER": "word",
    "TARGET_GENDER": "word",
    "MARITAL_STATUS": "word",
    "SEXUAL_ORIENTATION": "word",  # Avoid generating specific data

    # Medical (HIPAA sensitive)
    "HEALTHCARE_NUMBER": "pystr",
    "MEDICAL_CODE": "pystr",
    "MEDICAL_CONDITION": "word",
    "MEDICAL_FACILITY": "company",
    "MEDICAL_LICENSE": "pystr",
    "MEDICAL_PROCESS": "sentence",
    "MEDICAL_PROFESSIONAL": "name",
    "MEDICAL_PROFEFESSIONAL": "name",  # Typo variant
    "BLOOD_TYPE": "pystr",
    "DOSE": "pystr",
    "DRUG": "word",
    "INJURY": "sentence",
    "CONDITION": "sentence",
    "TEST_RESULT": "sentence",
    "DIETARY_RESTRICTION": "word",
    "FAMILY_HISTORY": "sentence",
    "GENETIC_DATA": "sentence",
    "BIOMETRIC_IDENTIFIER": "uuid4",
    "SMOKING_STATUS": "word",

    # Legal/Justice
    "OFFENSE": "sentence",
    "ALLEGATION": "sentence",
    "CONVICTION_DATE": "date",
    "SENTENCE": "sentence",
    "OFFICER_NAMES": "name",
    "FIREARM_TYPE": "word",
    "WEAPON_SERIAL": "pystr",

    # Temporal
    "DATE": "date",
    "TIME": "time",
    "TIMESTAMP": "date_time",
    "DOB": "date_of_birth",
    "DATE_OF_DEATH": "date",
    "START_DATE": "date",
    "END_DATE": "date",
    "DURATION": "pystr",
    "WEEKS": "pyint",
    "YEARS": "pyint",

    # Education
    "COURSE": "sentence",
    "STUDY_PROGRAM": "sentence",
    "STUDY_TITLE": "sentence",
    "GRADE": "pystr",
    "CLASS_LIST": "sentence",
    "SPECIALTY": "word",

    # Employment
    "LEGAL_FORM": "company_suffix",
    "TRADE_TYPE": "job",
    "UNIT": "word",

    # Misc
    "DESCRIPTION": "sentence",
    "ACTIVITY_DESCRIPTION": "sentence",
    "PROJECT_DESCRIPTION": "sentence",
    "PURPOSE": "sentence",
    "REASON": "sentence",
    "RISK": "sentence",
    "PRODUCT_NAME": "word",
    "QUANTITY": "pyint",
    "RELATIONSHIP": "word",
    "PET_INFO": "sentence",
    "SECURITY": "word",
    "VEHICLE_ID": "pystr",
    "TABLE": "word",
}

# Map placeholder names to canonical coarse entity types
# These are used for ground truth labels in benchmark
PLACEHOLDER_TO_ENTITY_TYPE = {
    # Person
    "NAME": "PERSON",
    "FIRSTNAME": "PERSON",
    "LASTNAME": "PERSON",
    "PERSON": "PERSON",

    # Contact
    "EMAIL": "EMAIL_ADDRESS",
    "EMAIL_ADDRESS": "EMAIL_ADDRESS",
    "PHONE": "PHONE_NUMBER",
    "CELL_NUMBER": "PHONE_NUMBER",
    "FAX": "PHONE_NUMBER",
    "IP_ADDRESS": "IP_ADDRESS",
    "MAC_ADDRESS": "IP_ADDRESS",
    "URL": "URL",

    # Location
    "STREET": "LOCATION",
    "STREAT": "LOCATION",
    "CITY": "LOCATION",
    "CANTON": "LOCATION",
    "POSTCODE": "LOCATION",
    "STATE": "LOCATION",
    "COUNTRY": "LOCATION",
    "LOCATION_ADDRESS": "LOCATION",
    "CEMETERY_ADDRESS": "LOCATION",

    # Financial
    "CREDIT_CARD": "CREDIT_CARD",
    "CREDIT_CARD_EXPIRATION": "DATE_TIME",
    "CVV": "CRYPTO",
    "IBAN": "IBAN",
    "BANK": "ORGANIZATION",
    "BANK_ACCOUNT": "ID_NUMBER",
    "ACCOUNT_NUMBER": "ID_NUMBER",
    "ROUTING_NUMBER": "ID_NUMBER",
    "MONEY": "FINANCIAL",
    "AMOUNT": "FINANCIAL",
    "CURRENCY": "FINANCIAL",
    "INTEREST_RATE": "FINANCIAL",
    "PRICE": "FINANCIAL",

    # Swiss-specific IDs
    "AHV": "ID_NUMBER",
    "SSN": "ID_NUMBER",
    "NATIONAL_ID_NUMBER": "ID_NUMBER",
    "TAX_IDENTIFICATION_NUMBER": "ID_NUMBER",
    "TAX_ID_NUMBER": "ID_NUMBER",
    "IDENTITY_CARD_NUMBER": "ID_NUMBER",
    "PASSPORT_NUMBER": "PASSPORT",
    "DRIVER_LICENSE": "DRIVER_LICENSE",

    # Business/Reference IDs
    "CUSTOMER_ID": "ID_NUMBER",
    "POLICY_NUMBER": "ID_NUMBER",
    "REFERENCE_NUMBER": "ID_NUMBER",
    "CASE_NUMBER": "ID_NUMBER",
    "CASE_REFERENCE": "ID_NUMBER",
    "CERTIFICATE_NUMBER": "ID_NUMBER",
    "ASSESSMENT_REFERENCE": "ID_NUMBER",
    "CODE": "ID_NUMBER",
    "NUMBER": "ID_NUMBER",

    # Organization
    "COMPANY": "ORGANIZATION",
    "ORGANIZATION": "ORGANIZATION",
    "TRADEMARK_NAME": "ORGANIZATION",
    "TRADE_UNION": "ORGANIZATION",

    # Work/Title
    "JOB_TITLE": "TITLE",
    "TITLE": "TITLE",
    "WORK_TITLE": "TITLE",
    "RANK": "TITLE",

    # Digital/Secrets
    "USERNAME": "USERNAME",
    "PASSWORD": "PASSWORD",
    "API_KEY": "CRYPTO",
    "PRIVATE_KEY": "CRYPTO",
    "CRYPTO_WALLET": "CRYPTO",
    "DEVICE_IDENTIFIER": "ID_NUMBER",

    # Demographics (GDPR sensitive - NRP)
    "NATIONALITY": "NRP",
    "RELIGION": "NRP",
    "POLITICAL_AFFILIATION": "NRP",
    "POLITICAL": "NRP",
    "RACE": "NRP",
    "ETHNICITY": "NRP",
    "GENDER": "NRP",
    "BIRTH_GENDER": "NRP",
    "TARGET_GENDER": "NRP",
    "MARITAL_STATUS": "NRP",
    "SEXUAL_ORIENTATION": "NRP",

    # Medical (HIPAA sensitive)
    "HEALTHCARE_NUMBER": "ID_NUMBER",
    "MEDICAL_CODE": "ID_NUMBER",
    "MEDICAL_CONDITION": "MEDICAL",
    "MEDICAL_FACILITY": "ORGANIZATION",
    "MEDICAL_LICENSE": "ID_NUMBER",
    "MEDICAL_PROCESS": "MEDICAL",
    "MEDICAL_PROFESSIONAL": "PERSON",
    "MEDICAL_PROFEFESSIONAL": "PERSON",
    "BLOOD_TYPE": "MEDICAL",
    "DOSE": "MEDICAL",
    "DRUG": "MEDICAL",
    "INJURY": "MEDICAL",
    "CONDITION": "MEDICAL",
    "TEST_RESULT": "MEDICAL",
    "DIETARY_RESTRICTION": "MEDICAL",
    "FAMILY_HISTORY": "MEDICAL",
    "GENETIC_DATA": "MEDICAL",
    "BIOMETRIC_IDENTIFIER": "ID_NUMBER",
    "SMOKING_STATUS": "MEDICAL",

    # Legal/Justice
    "OFFENSE": "LEGAL",
    "ALLEGATION": "LEGAL",
    "CONVICTION_DATE": "DATE_TIME",
    "SENTENCE": "LEGAL",
    "OFFICER_NAMES": "PERSON",
    "FIREARM_TYPE": "LEGAL",
    "WEAPON_SERIAL": "ID_NUMBER",

    # Temporal
    "DATE": "DATE_TIME",
    "TIME": "DATE_TIME",
    "TIMESTAMP": "DATE_TIME",
    "DOB": "DATE_TIME",
    "DATE_OF_DEATH": "DATE_TIME",
    "START_DATE": "DATE_TIME",
    "END_DATE": "DATE_TIME",
    "DURATION": "DATE_TIME",
    "WEEKS": "DATE_TIME",
    "YEARS": "DATE_TIME",

    # Education
    "COURSE": "EDUCATION",
    "STUDY_PROGRAM": "EDUCATION",
    "STUDY_TITLE": "EDUCATION",
    "GRADE": "EDUCATION",
    "CLASS_LIST": "EDUCATION",
    "SPECIALTY": "EDUCATION",

    # Employment
    "LEGAL_FORM": "ORGANIZATION",
    "TRADE_TYPE": "TITLE",
    "UNIT": "ORGANIZATION",

    # Misc
    "DESCRIPTION": "OTHER",
    "ACTIVITY_DESCRIPTION": "OTHER",
    "PROJECT_DESCRIPTION": "OTHER",
    "PURPOSE": "OTHER",
    "REASON": "OTHER",
    "RISK": "OTHER",
    "PRODUCT_NAME": "OTHER",
    "QUANTITY": "OTHER",
    "RELATIONSHIP": "OTHER",
    "PET_INFO": "OTHER",
    "SECURITY": "OTHER",
    "VEHICLE_ID": "ID_NUMBER",
    "TABLE": "OTHER",

    # Age
    "AGE": "AGE",
    "RELIGIOUS_OFFICIAL": "PERSON",
}


def get_faker_method(placeholder: str) -> str | None:
    """Get the Faker method name for a placeholder.

    Args:
        placeholder: Placeholder name without braces (e.g., "NAME").

    Returns:
        Faker method name or None if not mapped.
    """
    return PLACEHOLDER_TO_FAKER.get(placeholder)


def get_entity_type(placeholder: str) -> str:
    """Get the canonical entity type for a placeholder.

    Args:
        placeholder: Placeholder name without braces (e.g., "NAME").

    Returns:
        Canonical entity type string.
    """
    return PLACEHOLDER_TO_ENTITY_TYPE.get(placeholder, "OTHER")
