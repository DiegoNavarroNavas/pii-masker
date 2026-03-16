"""Abstract base class for dataset loaders."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BenchmarkSample:
    """A single sample for benchmarking."""

    text: str
    """The text to analyze."""

    ground_truth: list[dict]
    """Ground truth spans as list of dicts with entity_type, start, end."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Optional metadata (locale, domain, etc.)."""


# Locale name mappings (common variations) - all map to ISO 639-1 codes
LOCALE_TO_CODE = {
    # Full names -> code
    "german": "de",
    "deutsch": "de",
    "english": "en",
    "spanish": "es",
    "french": "fr",
    "italian": "it",
    "portuguese": "pt",
    "chinese": "zh",
    "japanese": "ja",
    "korean": "ko",
    "dutch": "nl",
}


@dataclass
class FilterSpec:
    """Specification for filtering dataset samples."""

    locale: str | None = None
    """Filter by locale/language (e.g., 'de', 'en-US')."""

    domain: str | None = None
    """Filter by domain (e.g., 'finance', 'medical', 'code')."""

    custom_filters: dict[str, str] = field(default_factory=dict)
    """Arbitrary field=value filters."""

    def matches(self, item: dict[str, Any]) -> bool:
        """Check if an item matches all filter criteria."""
        # Locale filtering - check multiple possible field names
        if self.locale:
            locale_fields = ["locale", "language", "lang", "locale_id", "language_code"]
            item_locale = None
            for field in locale_fields:
                if field in item:
                    item_locale = str(item[field]).lower()
                    break
            if item_locale and not self._locale_matches(item_locale, self.locale.lower()):
                return False

        # Domain filtering
        if self.domain:
            domain_fields = ["domain", "category", "type", "source_domain"]
            item_domain = None
            for field in domain_fields:
                if field in item:
                    item_domain = str(item[field]).lower()
                    break
            if item_domain and item_domain != self.domain.lower():
                return False

        # Custom filters
        for key, value in self.custom_filters.items():
            if key in item and str(item[key]).lower() != value.lower():
                return False

        return True

    def _locale_matches(self, item_locale: str, filter_locale: str) -> bool:
        """Check if locales match (with fuzzy matching and aliases)."""
        # Normalize both to ISO 639-1 codes
        item_code = LOCALE_TO_CODE.get(item_locale, item_locale)
        filter_code = LOCALE_TO_CODE.get(filter_locale, filter_locale)

        # Exact match (after normalization)
        if item_code == filter_code:
            return True
        # Language code match (e.g., "de" matches "de-DE", "de-AT")
        if item_code.startswith(filter_code.split("-")[0]):
            return True
        # Reverse: filter "de-DE" matches item "de"
        if filter_code.startswith(item_code.split("-")[0]):
            return True
        return False


class DatasetLoader(ABC):
    """Abstract base class for dataset loaders."""

    def __init__(self, filters: FilterSpec | None = None):
        """Initialize loader with optional filters.

        Args:
            filters: Filter specification for loading specific subsets.
        """
        self.filters = filters or FilterSpec()

    @abstractmethod
    def load(self, max_samples: int | None = None) -> list[BenchmarkSample]:
        """Load samples from the dataset.

        Args:
            max_samples: Maximum number of samples to load (None for all).

        Returns:
            List of BenchmarkSample objects.
        """
        pass

    @abstractmethod
    def name(self) -> str:
        """Return the dataset name."""
        pass

    def set_filters(self, filters: FilterSpec) -> None:
        """Update filter specification."""
        self.filters = filters

    def list_fields(self) -> dict[str, list[str] | str]:
        """List available fields in the dataset.

        Returns:
            Dict with 'fields' list and optionally 'sample' for inspection.
        """
        return {"fields": [], "sample": "Not implemented for this loader"}
