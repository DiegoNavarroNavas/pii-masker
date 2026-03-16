"""Core template filler for generating synthetic PII benchmark data.

Provides the TemplateFiller class that replaces placeholders in templates
with Faker-generated values and tracks character offsets for ground truth.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from faker import Faker

from benchmark.synthetic.faker_provider import SwissProvider
from benchmark.synthetic.placeholder_mapping import (
    get_entity_type,
    get_faker_method,
)


@dataclass
class EntitySpan:
    """A single entity span in generated text."""

    entity_type: str
    """Canonical entity type (e.g., 'PERSON', 'EMAIL_ADDRESS')."""

    start: int
    """Character offset of entity start (UTF-8 safe)."""

    end: int
    """Character offset of entity end (exclusive)."""

    value: str
    """The actual text value."""

    placeholder: str
    """Original placeholder name."""


@dataclass
class FilledTemplate:
    """Result of filling a template with Faker data."""

    text: str
    """Generated text with placeholders replaced."""

    spans: list[EntitySpan]
    """Ground truth entity spans."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Template metadata (locale, domain, etc.)."""


class TemplateFiller:
    """Fill templates with Faker-generated PII data.

    Handles placeholder extraction, value generation, and character offset
    calculation for ground truth spans.
    """

    # Regex pattern for placeholders
    PLACEHOLDER_PATTERN = re.compile(r"\{\{([A-Z_]+)\}\}")

    def __init__(self, locale: str = "de_CH", seed: int | None = None):
        """Initialize the template filler.

        Args:
            locale: Faker locale (e.g., 'de_CH', 'fr_CH', 'it_CH').
            seed: Random seed for reproducibility.
        """
        # Map synthetic locale to Faker locale
        faker_locale = self._map_locale(locale)
        self.faker = Faker(faker_locale)
        self.original_locale = locale

        # Add Swiss provider for custom generators
        self.faker.add_provider(SwissProvider)

        if seed is not None:
            Faker.seed(seed)
            self.faker.seed_instance(seed)

        # Track generated values to avoid duplicates in same template
        self._generated_values: dict[str, str] = {}

    def _map_locale(self, locale: str) -> str:
        """Map synthetic locale to Faker locale.

        Args:
            locale: Synthetic locale (e.g., 'de_CH').

        Returns:
            Faker-compatible locale.
        """
        # Swiss locales
        locale_map = {
            "de_CH": "de_DE",  # German (Swiss) -> German
            "fr_CH": "fr_FR",  # French (Swiss) -> French
            "it_CH": "it_IT",  # Italian (Swiss) -> Italian
            "de": "de_DE",
            "fr": "fr_FR",
            "it": "it_IT",
            "en": "en_US",
        }
        return locale_map.get(locale, "en_US")

    def fill_template(self, template_str: str, metadata: dict | None = None) -> FilledTemplate:
        """Fill a template with Faker-generated values.

        Args:
            template_str: Template string with {{PLACEHOLDER}} markers.
            metadata: Optional metadata to include in result.

        Returns:
            FilledTemplate with text and ground truth spans.
        """
        self._generated_values.clear()

        # Extract all placeholders with their positions
        placeholders = self._extract_placeholders(template_str)

        # Generate values for each unique placeholder
        generated = {}
        for ph_name, _, _ in placeholders:
            if ph_name not in generated:
                generated[ph_name] = self._generate_value(ph_name)

        # Build the filled text and track positions
        text, spans = self._build_text_with_spans(template_str, placeholders, generated)

        return FilledTemplate(
            text=text,
            spans=spans,
            metadata=metadata or {},
        )

    def _extract_placeholders(self, template: str) -> list[tuple[str, int, int]]:
        """Extract placeholders with their positions.

        Args:
            template: Template string.

        Returns:
            List of (placeholder_name, start, end) tuples.
        """
        matches = []
        for match in self.PLACEHOLDER_PATTERN.finditer(template):
            ph_name = match.group(1)
            start = match.start()
            end = match.end()
            matches.append((ph_name, start, end))
        return matches

    def _generate_value(self, placeholder: str) -> str:
        """Generate a Faker value for a placeholder.

        Args:
            placeholder: Placeholder name (without braces).

        Returns:
            Generated string value.
        """
        faker_method = get_faker_method(placeholder)

        if faker_method is None:
            # Unknown placeholder, generate random string
            return self.faker.pystr(min_chars=8, max_chars=12)

        # Handle special cases
        if faker_method == "swiss_phone":
            return self.faker.swiss_phone()
        elif faker_method == "swiss_ahv":
            return self.faker.swiss_ahv()
        elif faker_method == "canton_from_city":
            return self.faker.canton_abbr()
        elif faker_method == "pyfloat":
            # Generate reasonable monetary amounts
            return f"{self.faker.pyfloat(min_value=100, max_value=100000, right_digits=2):.2f}"
        elif faker_method == "pydecimal":
            return f"{self.faker.pydecimal(left_digits=4, right_digits=2, positive=True)}"
        elif faker_method == "pyint":
            return str(self.faker.pyint(min_value=1, max_value=100))
        elif faker_method == "pystr":
            return self.faker.pystr(min_chars=8, max_chars=12).upper()
        elif faker_method == "uuid4":
            return str(self.faker.uuid4())[:8].upper()
        elif faker_method == "sha256":
            return self.faker.sha256()[:32]
        elif faker_method == "password":
            return self.faker.password(length=12)
        elif faker_method == "date_of_birth":
            return self.faker.date_of_birth(minimum_age=18, maximum_age=90).isoformat()
        elif faker_method == "date_time":
            return self.faker.date_time().isoformat()
        elif faker_method == "date":
            return self.faker.date()
        elif faker_method == "time":
            return self.faker.time()

        # Standard Faker method
        try:
            method = getattr(self.faker, faker_method)
            result = method()
            return str(result)
        except AttributeError:
            return self.faker.pystr(min_chars=8, max_chars=12)

    def _build_text_with_spans(
        self,
        template: str,
        placeholders: list[tuple[str, int, int]],
        generated: dict[str, str],
    ) -> tuple[str, list[EntitySpan]]:
        """Build filled text and calculate spans.

        This handles character offset calculation correctly for UTF-8 text
        (using Python's native string indexing which is Unicode-aware).

        Args:
            template: Original template string.
            placeholders: List of (name, start, end) tuples.
            generated: Dict mapping placeholder names to generated values.

        Returns:
            Tuple of (filled_text, entity_spans).
        """
        # Build text by replacing placeholders
        result_parts = []
        spans = []
        current_pos = 0

        for ph_name, ph_start, ph_end in placeholders:
            # Add text before this placeholder
            result_parts.append(template[current_pos:ph_start])

            # Track position in result string
            prefix_len = sum(len(p) for p in result_parts)

            # Get generated value
            value = generated[ph_name]
            result_parts.append(value)

            # Calculate span positions (Unicode-aware)
            start = prefix_len
            end = prefix_len + len(value)

            # Get entity type
            entity_type = get_entity_type(ph_name)

            spans.append(EntitySpan(
                entity_type=entity_type,
                start=start,
                end=end,
                value=value,
                placeholder=ph_name,
            ))

            current_pos = ph_end

        # Add remaining text after last placeholder
        result_parts.append(template[current_pos:])

        text = "".join(result_parts)
        return text, spans

    def fill_template_dict(self, template_dict: dict) -> FilledTemplate:
        """Fill a template from a template dict.

        Args:
            template_dict: Dict with 'template' key and metadata.

        Returns:
            FilledTemplate with text and spans.
        """
        template_str = template_dict.get("template", "")
        metadata = {k: v for k, v in template_dict.items() if k != "template"}

        return self.fill_template(template_str, metadata)
