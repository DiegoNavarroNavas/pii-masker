"""Entity type normalization for benchmarking.

Maps various entity type schemas (NER models, GLiNER, etc.)
to canonical coarse types for fair comparison.
"""

from benchmark.entity_schema import COARSE_ENTITY_TYPES


# Standard NER model outputs -> coarse
NER_TO_COARSE = {
    "PER": "PERSON",
    "PERSON": "PERSON",
    "LOC": "LOCATION",
    "GPE": "LOCATION",  # Geopolitical entity
    "FAC": "LOCATION",  # Facility
    "ORG": "ORGANIZATION",
    "ORGANIZATION": "ORGANIZATION",
    "DATE": "DATE_TIME",
    "TIME": "DATE_TIME",
    "MISC": "OTHER",
}

# GLiNER PII model entity types -> coarse
# Source: https://huggingface.co/knowledgator/gliner-pii-edge-v1.0
# Includes trained labels and zero-shot labels
GLINER_TO_COARSE = {
    # Person
    "PERSON": "PERSON",
    "NAME": "PERSON",
    "FIRST NAME": "PERSON",
    "LAST NAME": "PERSON",
    # Contact
    "EMAIL": "EMAIL_ADDRESS",
    "EMAIL ADDRESS": "EMAIL_ADDRESS",
    "PHONE NUMBER": "PHONE_NUMBER",
    "MOBILE PHONE NUMBER": "PHONE_NUMBER",
    "LANDLINE PHONE NUMBER": "PHONE_NUMBER",
    "FAX NUMBER": "PHONE_NUMBER",
    # Location
    "ADDRESS": "LOCATION",
    "FULL ADDRESS": "LOCATION",
    "LOCATION ADDRESS": "LOCATION",
    "LOCATION CITY": "LOCATION",
    "LOCATION STATE": "LOCATION",
    "LOCATION COUNTRY": "LOCATION",
    "LOCATION ZIP": "LOCATION",
    "POSTAL CODE": "LOCATION",
    "CITY": "LOCATION",
    "STATE": "LOCATION",
    "COUNTRY": "LOCATION",
    # Dates
    "DATE OF BIRTH": "DATE_TIME",
    "DOB": "DATE_TIME",
    "DATE": "DATE_TIME",
    "CREDIT CARD EXPIRATION DATE": "DATE_TIME",
    "PASSPORT EXPIRATION DATE": "DATE_TIME",
    # IDs
    "PASSPORT NUMBER": "PASSPORT",
    "PASSPORT": "PASSPORT",
    "PASSPORT_NUMBER": "PASSPORT",
    "DRIVER'S LICENSE NUMBER": "DRIVER_LICENSE",
    "DRIVER LICENSE": "DRIVER_LICENSE",
    "DRIVER LICENCE": "DRIVER_LICENSE",
    "IDENTITY CARD NUMBER": "ID_NUMBER",
    "IDENTITY DOCUMENT NUMBER": "ID_NUMBER",
    "NATIONAL ID NUMBER": "ID_NUMBER",
    "SOCIAL SECURITY NUMBER": "ID_NUMBER",
    "SSN": "ID_NUMBER",
    "SOCIAL_SECURITY_NUMBER": "ID_NUMBER",
    "TAX IDENTIFICATION NUMBER": "ID_NUMBER",
    "CPF": "ID_NUMBER",
    "CNPJ": "ID_NUMBER",
    "BIRTH CERTIFICATE NUMBER": "ID_NUMBER",
    "BANK ACCOUNT NUMBER": "ID_NUMBER",
    "BANK ACCOUNT": "ID_NUMBER",
    "ROUTING NUMBER": "ID_NUMBER",
    "ACCOUNT NUMBER": "ID_NUMBER",
    "HEALTH INSURANCE ID NUMBER": "ID_NUMBER",
    "HEALTH INSURANCE NUMBER": "ID_NUMBER",
    "NATIONAL HEALTH INSURANCE NUMBER": "ID_NUMBER",
    "HEALTHCARE NUMBER": "ID_NUMBER",
    "INSURANCE NUMBER": "ID_NUMBER",
    "STUDENT ID NUMBER": "ID_NUMBER",
    "REGISTRATION NUMBER": "ID_NUMBER",
    "LICENSE PLATE NUMBER": "ID_NUMBER",
    "VEHICLE REGISTRATION NUMBER": "ID_NUMBER",
    "VEHICLE ID": "ID_NUMBER",
    "SERIAL NUMBER": "ID_NUMBER",
    "TRANSACTION NUMBER": "ID_NUMBER",
    "RESERVATION NUMBER": "ID_NUMBER",
    "FLIGHT NUMBER": "ID_NUMBER",
    "TRAIN TICKET NUMBER": "ID_NUMBER",
    "VISA NUMBER": "ID_NUMBER",
    "MEDICAL CODE": "ID_NUMBER",
    # Digital
    "IP ADDRESS": "IP_ADDRESS",
    "USERNAME": "USERNAME",
    "PASSWORD": "PASSWORD",
    "SOCIAL MEDIA HANDLE": "USERNAME",
    "DIGITAL SIGNATURE": "CRYPTO",
    "CVV": "CRYPTO",
    "CVC": "CRYPTO",
    "URL": "URL",
    # Financial
    "CREDIT CARD NUMBER": "CREDIT_CARD",
    "CREDIT CARD": "CREDIT_CARD",
    "IBAN": "IBAN",
    "MONEY": "FINANCIAL",
    # Organization
    "ORGANIZATION": "ORGANIZATION",
    "COMPANY": "ORGANIZATION",
    "INSURANCE COMPANY": "ORGANIZATION",
    # Demographics (zero-shot)
    "AGE": "AGE",
    "GENDER": "GENDER",
    "NATIONALITY": "NRP",
    "RELIGION": "NRP",
    # Work (zero-shot)
    "JOB TITLE": "TITLE",
    "TITLE": "TITLE",
    # Secrets (zero-shot)
    "API KEY": "CRYPTO",
    "SECRET KEY": "CRYPTO",
    "TOKEN": "CRYPTO",
    "PRIVATE KEY": "CRYPTO",
}


def normalize_entity_type(entity_type: str) -> str:
    """Normalize any entity type to canonical coarse type.

    Args:
        entity_type: Original entity type string from any source.

    Returns:
        Canonical coarse entity type string.
    """
    # If already a coarse type, return as-is
    if entity_type in COARSE_ENTITY_TYPES:
        return entity_type

    # Normalize to uppercase for lookup
    upper = entity_type.upper()

    # Check if already a coarse type
    if upper in COARSE_ENTITY_TYPES:
        return upper

    # Try each mapping in order
    for mapping in [GLINER_TO_COARSE, NER_TO_COARSE]:
        if upper in mapping:
            coarse = mapping[upper]
            # Some mappings go to other non-coarse types (e.g., SECADDRESS -> ADDRESS)
            # Recursively normalize until we get a coarse type
            if coarse not in COARSE_ENTITY_TYPES:
                return normalize_entity_type(coarse)
            return coarse

    # Unknown type passes through unchanged
    return entity_type


def normalize_entities(entities: list[dict]) -> list[dict]:
    """Normalize entity types in a list of entity dicts.

    Args:
        entities: List of entity dicts with 'entity_type' key.

    Returns:
        New list with normalized entity types.
    """
    return [
        {**e, "entity_type": normalize_entity_type(e["entity_type"])}
        for e in entities
    ]
