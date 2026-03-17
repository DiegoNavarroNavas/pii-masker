"""Swiss-specific Faker providers.

Provides custom generators for Swiss PII types like AHV numbers,
Swiss phone numbers, and canton mappings.
"""

from faker.providers import BaseProvider


class SwissProvider(BaseProvider):
    """Faker provider for Swiss-specific data."""

    # Swiss cantons with their abbreviations
    CANTONS = {
        "Zürich": "ZH",
        "Bern": "BE",
        "Luzern": "LU",
        "Uri": "UR",
        "Schwyz": "SZ",
        "Obwalden": "OW",
        "Nidwalden": "NW",
        "Glarus": "GL",
        "Zug": "ZG",
        "Fribourg": "FR",
        "Solothurn": "SO",
        "Basel-Stadt": "BS",
        "Basel-Landschaft": "BL",
        "Schaffhausen": "SH",
        "Appenzell Ausserrhoden": "AR",
        "Appenzell Innerrhoden": "AI",
        "St. Gallen": "SG",
        "Graubünden": "GR",
        "Aargau": "AG",
        "Thurgau": "TG",
        "Ticino": "TI",
        "Vaud": "VD",
        "Valais": "VS",
        "Neuchâtel": "NE",
        "Genève": "GE",
        "Jura": "JU",
    }

    # Major Swiss cities mapped to their cantons
    CITY_TO_CANTON = {
        # German-speaking
        "Zürich": "ZH",
        "Bern": "BE",
        "Basel": "BS",
        "Luzern": "LU",
        "St. Gallen": "SG",
        "Lugano": "TI",
        "Winterthur": "ZH",
        "Biel/Bienne": "BE",
        "Chur": "GR",
        "Aarau": "AG",
        "Baden": "AG",
        "Wettingen": "AG",
        "Uster": "ZH",
        "Volketswil": "ZH",
        "Zug": "ZG",
        "Dübendorf": "ZH",
        "Kriens": "LU",
        "Rapperswil-Jona": "SG",
        "Yverdon-les-Bains": "VD",
        "Dietikon": "ZH",
        "Montreux": "VD",
        "Frauenfeld": "TG",
        "Wetzikon": "ZH",
        "Wädenswil": "ZH",
        "Baar": "ZG",
        "Renens": "VD",
        "Wil": "SG",
        "Nyon": "VD",
        "Allschwil": "BL",
        "Bulle": "FR",
        "Horgen": "ZH",
        "Meyrin": "GE",
        "Kloten": "ZH",
        "Uzwil": "SG",
        "Sitten": "VS",
        "Carouge": "GE",
        "Vernier": "GE",
        # French-speaking
        "Genf": "GE",
        "Lausanne": "VD",
        "Fribourg": "FR",
        "Neuenburg": "NE",
        "Biel": "BE",
        # Italian-speaking
        "Lugano": "TI",
        "Bellinzona": "TI",
        "Locarno": "TI",
        "Lugano": "TI",
    }

    # Swiss phone number area codes (for realistic numbers)
    AREA_CODES = [
        "21",  # Lausanne
        "22",  # Geneva
        "24",  # Yverdon
        "26",  # Fribourg
        "27",  # Valais
        "31",  # Bern
        "32",  # Biel/Neuchâtel
        "33",  # Thun
        "34",  # Burgdorf
        "41",  # Luzern/Zug
        "43",  # Zurich (new)
        "44",  # Zurich
        "52",  # Winterthur
        "55",  # Rapperswil
        "56",  # Baden
        "61",  # Basel
        "62",  # Olten
        "71",  # St. Gallen
        "81",  # Chur
        "91",  # Ticino
    ]

    def swiss_ahv(self) -> str:
        """Generate a valid Swiss AHV number (social security number).

        Format: 756.XXXX.XXXX.XX
        - 756 is the Swiss country code for SSN
        - 8 random digits
        - 2 check digits (EAN-13)

        Returns:
            Valid AHV number string.
        """
        # Start with Swiss country code for AHV
        prefix = "756"

        # Generate 8 random digits
        middle = "".join([str(self.random_int(0, 9)) for _ in range(8)])

        # Full 12-digit number (without check digits)
        full_number = prefix + middle

        # Calculate EAN-13 check digit
        check = self._ean13_check_digit(full_number)

        # Format: 756.XXXX.XXXX.XX
        return f"{prefix}.{middle[:4]}.{middle[4:]}.{check}"

    def _ean13_check_digit(self, number: str) -> str:
        """Calculate EAN-13 check digit.

        Args:
            number: 12-digit string.

        Returns:
            Two-digit check sum.
        """
        # Calculate first check digit
        weights1 = [1, 3] * 6
        sum1 = sum(int(d) * w for d, w in zip(number, weights1))
        check1 = (10 - (sum1 % 10)) % 10

        # For AHV, we need a second digit
        # Use the first check digit and recalculate
        number_with_check = number + str(check1)
        weights2 = [3, 1] * 6 + [1]
        sum2 = sum(int(d) * w for d, w in zip(number_with_check, weights2))
        check2 = (10 - (sum2 % 10)) % 10

        return f"{check1}{check2}"

    def swiss_phone(self) -> str:
        """Generate a Swiss phone number.

        Format: +41 XX XXX XX XX

        Returns:
            Swiss phone number string.
        """
        area_code = self.random_element(self.AREA_CODES)

        # Generate remaining 7 digits in format XXX XX XX
        remaining = "".join([str(self.random_int(0, 9)) for _ in range(7)])

        return f"+41 {area_code} {remaining[:3]} {remaining[3:5]} {remaining[5:]}"

    def canton_from_city(self, city: str | None = None) -> str:
        """Get canton abbreviation from city name.

        If no city is provided, returns a random canton abbreviation.

        Args:
            city: City name (optional).

        Returns:
            Two-letter canton abbreviation.
        """
        if city and city in self.CITY_TO_CANTON:
            return self.CITY_TO_CANTON[city]

        # Return random canton abbreviation
        return self.random_element(list(self.CANTONS.values()))

    def canton_name(self) -> str:
        """Get a random Swiss canton name.

        Returns:
            Full canton name.
        """
        return self.random_element(list(self.CANTONS.keys()))

    def canton_abbr(self) -> str:
        """Get a random Swiss canton abbreviation.

        Returns:
            Two-letter canton abbreviation.
        """
        return self.random_element(list(self.CANTONS.values()))
