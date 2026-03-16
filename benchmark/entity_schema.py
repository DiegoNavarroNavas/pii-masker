"""Canonical coarse entity types for benchmarking."""

from enum import Enum


class CoarseEntityType(str, Enum):
    """Canonical coarse entity types for normalization.

    These represent the unified entity types used for evaluation,
    allowing comparison between models with different type granularities.
    """

    PERSON = "PERSON"
    EMAIL_ADDRESS = "EMAIL_ADDRESS"
    PHONE_NUMBER = "PHONE_NUMBER"
    LOCATION = "LOCATION"
    ORGANIZATION = "ORGANIZATION"
    DATE_TIME = "DATE_TIME"
    CREDIT_CARD = "CREDIT_CARD"
    IP_ADDRESS = "IP_ADDRESS"
    URL = "URL"
    USERNAME = "USERNAME"
    PASSWORD = "PASSWORD"
    CRYPTO = "CRYPTO"  # API keys, tokens, secrets
    PASSPORT = "PASSPORT"
    DRIVER_LICENSE = "DRIVER_LICENSE"
    ID_NUMBER = "ID_NUMBER"  # Generic ID cards, social numbers
    TITLE = "TITLE"
    AGE = "AGE"
    GENDER = "GENDER"
    NRP = "NRP"  # Nationality, Religion, Political affiliation
    ADDRESS = "ADDRESS"
    IBAN = "IBAN"
    US_SSN = "US_SSN"
    OTHER = "OTHER"


COARSE_ENTITY_TYPES = {e.value for e in CoarseEntityType}
