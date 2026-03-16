#!/usr/bin/env python3
"""
Test Data Generator for PII Masker

Generates multilingual test data files (~100KB each) with embedded PII
for validating the anonymization/deanonymization pipeline.

Usage:
    python test/scripts/generate_test_data.py
    python test/scripts/generate_test_data.py --output-dir test/data/input
    python test/scripts/generate_test_data.py --size 50000  # 50KB per file
"""

import argparse
import json
import os
import random
import string
from pathlib import Path
from typing import Any


class TestDataGenerator:
    """Generates synthetic test data with embedded PII."""

    def __init__(self, templates_dir: str = "test/data/pii_templates"):
        self.templates_dir = Path(templates_dir)
        self.templates = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """Load all PII templates."""
        template_files = [
            "names", "locations", "contacts", "addresses",
            "companies", "credentials", "financial", "dates", "medical"
        ]

        for name in template_files:
            path = self.templates_dir / f"{name}.json"
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    self.templates[name] = json.load(f)

    def _random_digits(self, length: int) -> str:
        """Generate random digits."""
        return "".join(random.choices(string.digits, k=length))

    def _random_letters(self, length: int) -> str:
        """Generate random uppercase letters."""
        return "".join(random.choices(string.ascii_uppercase, k=length))

    def generate_name(self, lang: str) -> str:
        """Generate a full name."""
        names = self.templates.get("names", {}).get(lang, {})
        first_male = names.get("first_names_male", ["John"])
        first_female = names.get("first_names_female", ["Jane"])
        last = names.get("last_names", ["Smith"])

        if random.random() > 0.5:
            first = random.choice(first_male)
        else:
            first = random.choice(first_female)

        return f"{first} {random.choice(last)}"

    def generate_email(self, lang: str, name: str = None) -> str:
        """Generate an email address."""
        contacts = self.templates.get("contacts", {}).get(lang, {})
        domains = contacts.get("email_domains", ["example.com"])
        patterns = contacts.get("email_patterns", ["{first}.{last}@{domain}"])

        if name:
            parts = name.lower().split()
            first = parts[0] if parts else "user"
            last = parts[-1] if len(parts) > 1 else "name"
        else:
            first = self._random_letters(1).lower() + self._random_digits(3)
            last = self._random_letters(5).lower()

        pattern = random.choice(patterns)
        domain = random.choice(domains)

        return pattern.format(
            first=first,
            last=last,
            first_initial=first[0] if first else "x",
            last_initial=last[0] if last else "x",
            numbers=self._random_digits(4),
            domain=domain
        )

    def generate_phone(self, lang: str) -> str:
        """Generate a phone number."""
        contacts = self.templates.get("contacts", {}).get(lang, {})
        formats = contacts.get("phone_formats", ["+1 555-{area}-{number}"])
        area_codes = contacts.get("area_codes", ["212", "310"])

        fmt = random.choice(formats)
        area = random.choice(area_codes)

        return fmt.format(
            area=area,
            exchange=self._random_digits(3),
            number=self._random_digits(7),
            group1=self._random_digits(2),
            group2=self._random_digits(2),
            group3=self._random_digits(2),
            group4=self._random_digits(2),
            mobile=self._random_digits(2)
        )

    def generate_address(self, lang: str) -> str:
        """Generate a postal address."""
        addresses = self.templates.get("addresses", {}).get(lang, {})
        locations = self.templates.get("locations", {}).get(lang, {})

        street_types = addresses.get("street_types", ["Street"])
        street_names = addresses.get("street_names", ["Main"])
        cities = locations.get("cities", ["City"])

        number = random.randint(1, 9999)
        street_type = random.choice(street_types)
        street_name = random.choice(street_names)
        city = random.choice(cities)
        postal = self._random_digits(5)

        return f"{number} {street_name} {street_type}, {city}, {postal}"

    def generate_company(self, lang: str) -> str:
        """Generate a company name."""
        companies = self.templates.get("companies", {}).get(lang, {})
        prefixes = companies.get("prefixes", ["Global"])
        suffixes = companies.get("suffixes", ["Solutions"])
        types = companies.get("company_types", ["Inc."])

        return f"{random.choice(prefixes)} {random.choice(suffixes)} {random.choice(types)}"

    def generate_credit_card(self) -> str:
        """Generate a credit card number."""
        cards = self.templates.get("financial", {}).get("credit_cards", {})
        card_types = ["visa", "mastercard", "amex", "discover"]
        card_type = random.choice(card_types)

        card_info = cards.get(card_type, {})
        examples = card_info.get("examples", ["4111111111111111"])

        return random.choice(examples)

    def generate_iban(self, lang: str) -> str:
        """Generate an IBAN."""
        ibans = self.templates.get("financial", {}).get("iban", {})
        lang_ibans = ibans.get(lang, ibans.get("en", {}))
        examples = lang_ibans.get("examples", ["GB82WEST12345698765432"])

        return random.choice(examples)

    def generate_ssn(self, lang: str) -> str:
        """Generate a social security number."""
        credentials = self.templates.get("credentials", {}).get(lang, {})
        examples = credentials.get("examples", {}).get("ssns", ["123-45-6789"])

        return random.choice(examples)

    def generate_username(self, lang: str) -> str:
        """Generate a username."""
        credentials = self.templates.get("credentials", {}).get(lang, {})
        examples = credentials.get("examples", {}).get("usernames", ["user123"])

        return random.choice(examples)

    def generate_employee_id(self, lang: str) -> str:
        """Generate an employee ID."""
        credentials = self.templates.get("credentials", {}).get(lang, {})
        examples = credentials.get("examples", {}).get("employee_ids", ["EMP-12345"])

        return random.choice(examples)

    def generate_medical_record(self, lang: str) -> str:
        """Generate a medical record number."""
        medical = self.templates.get("medical", {}).get(lang, {})
        examples = medical.get("examples", {}).get("mrns", ["MRN-12345678"])

        return random.choice(examples)

    def generate_date(self, lang: str) -> str:
        """Generate a date."""
        dates = self.templates.get("dates", {}).get(lang, {})
        examples = dates.get("examples", ["01/01/1990"])

        return random.choice(examples)

    def generate_passport(self, lang: str) -> str:
        """Generate a passport number."""
        credentials = self.templates.get("credentials", {}).get(lang, {})
        examples = credentials.get("examples", {}).get("passports", ["A12345678"])

        return random.choice(examples)

    def _get_sentence_templates(self, lang: str) -> list[str]:
        """Get sentence templates for a language."""
        templates = {
            "en": [
                "The patient {name} was admitted on {date} with medical record number {medical_record}.",
                "Please contact {name} at {email} or call {phone} for more information.",
                "The shipment was sent to {address} by our logistics team.",
                "Employee {employee_id}, {name}, works at {company} headquarters.",
                "The customer's credit card number is {credit_card} with IBAN {iban}.",
                "Social Security Number: {ssn}. Passport: {passport}.",
                "Username: {username}. Registered on {date}.",
                "The conference will be held at {company}'s main office, organized by {name}.",
                "For billing inquiries, email {email} or contact {phone}.",
                "Patient {name} (MRN: {medical_record}) was discharged on {date}.",
                "The contract was signed by {name} representing {company}.",
                "Delivery address: {address}. Contact person: {name}, Phone: {phone}.",
                "Account holder: {name}. SSN: {ssn}. Username: {username}.",
                "The report was prepared by {name} (Employee ID: {employee_id}).",
                "Payment received from {company}. Reference: {iban}. Date: {date}.",
            ],
            "de": [
                "Der Patient {name} wurde am {date} mit der Patientennummer {medical_record} aufgenommen.",
                "Bitte kontaktieren Sie {name} unter {email} oder rufen Sie {phone} an.",
                "Die Sendung wurde an {address} von unserem Logistik-Team geschickt.",
                "Mitarbeiter {employee_id}, {name}, arbeitet bei {company}.",
                "Die Kreditkartennummer des Kunden lautet {credit_card} mit IBAN {iban}.",
                "Sozialversicherungsnummer: {ssn}. Reisepass: {passport}.",
                "Benutzername: {username}. Registriert am {date}.",
                "Die Konferenz findet im Hauptbüro von {company} statt, organisiert von {name}.",
                "Bei Rechnungsfragen schreiben Sie an {email} oder kontaktieren Sie {phone}.",
                "Patient {name} (PN: {medical_record}) wurde am {date} entlassen.",
                "Der Vertrag wurde von {name} im Namen von {company} unterzeichnet.",
                "Lieferadresse: {address}. Kontaktperson: {name}, Telefon: {phone}.",
                "Kontoinhaber: {name}. SV-Nummer: {ssn}. Benutzername: {username}.",
                "Der Bericht wurde von {name} (Mitarbeiter-ID: {employee_id}) erstellt.",
                "Zahlung erhalten von {company}. Referenz: {iban}. Datum: {date}.",
            ],
            "fr": [
                "Le patient {name} a été admis le {date} avec le numéro de dossier médical {medical_record}.",
                "Veuillez contacter {name} à {email} ou appeler le {phone} pour plus d'informations.",
                "L'expédition a été envoyée à {address} par notre équipe logistique.",
                "L'employé {employee_id}, {name}, travaille au siège de {company}.",
                "Le numéro de carte de crédit du client est {credit_card} avec l'IBAN {iban}.",
                "Numéro de sécurité sociale : {ssn}. Passeport : {passport}.",
                "Nom d'utilisateur : {username}. Inscrit le {date}.",
                "La conférence aura lieu au bureau principal de {company}, organisée par {name}.",
                "Pour les questions de facturation, envoyez un email à {email} ou contactez le {phone}.",
                "Le patient {name} (DMP : {medical_record}) a été libéré le {date}.",
                "Le contrat a été signé par {name} représentant {company}.",
                "Adresse de livraison : {address}. Personne de contact : {name}, Téléphone : {phone}.",
                "Titulaire du compte : {name}. Numéro de sécurité sociale : {ssn}. Nom d'utilisateur : {username}.",
                "Le rapport a été préparé par {name} (ID employé : {employee_id}).",
                "Paiement reçu de {company}. Référence : {iban}. Date : {date}.",
            ],
            "it": [
                "Il paziente {name} è stato ricoverato il {date} con numero di cartella clinica {medical_record}.",
                "Si prega di contattare {name} all'indirizzo {email} o chiamare {phone} per maggiori informazioni.",
                "La spedizione è stata inviata a {address} dal nostro team logistico.",
                "Il dipendente {employee_id}, {name}, lavora presso la sede di {company}.",
                "Il numero di carta di credito del cliente è {credit_card} con IBAN {iban}.",
                "Codice fiscale: {ssn}. Passaporto: {passport}.",
                "Nome utente: {username}. Registrato il {date}.",
                "La conferenza si terrà presso la sede principale di {company}, organizzata da {name}.",
                "Per domande sulla fatturazione, inviare un'email a {email} o contattare {phone}.",
                "Il paziente {name} (FC: {medical_record}) è stato dimesso il {date}.",
                "Il contratto è stato firmato da {name} per conto di {company}.",
                "Indirizzo di consegna: {address}. Persona di contatto: {name}, Telefono: {phone}.",
                "Intestatario del conto: {name}. Codice fiscale: {ssn}. Nome utente: {username}.",
                "Il rapporto è stato preparato da {name} (ID dipendente: {employee_id}).",
                "Pagamento ricevuto da {company}. Riferimento: {iban}. Data: {date}.",
            ],
            "es": [
                "El paciente {name} fue ingresado el {date} con número de historia clínica {medical_record}.",
                "Por favor contacte a {name} en {email} o llame al {phone} para más información.",
                "El envío fue enviado a {address} por nuestro equipo de logística.",
                "El empleado {employee_id}, {name}, trabaja en la sede de {company}.",
                "El número de tarjeta de crédito del cliente es {credit_card} con IBAN {iban}.",
                "Número de seguridad social: {ssn}. Pasaporte: {passport}.",
                "Nombre de usuario: {username}. Registrado el {date}.",
                "La conferencia se celebrará en la oficina principal de {company}, organizada por {name}.",
                "Para consultas de facturación, envíe un correo a {email} o contacte al {phone}.",
                "El paciente {name} (HC: {medical_record}) fue dado de alta el {date}.",
                "El contrato fue firmado por {name} en representación de {company}.",
                "Dirección de entrega: {address}. Persona de contacto: {name}, Teléfono: {phone}.",
                "Titular de la cuenta: {name}. Número de seguridad social: {ssn}. Nombre de usuario: {username}.",
                "El informe fue preparado por {name} (ID de empleado: {employee_id}).",
                "Pago recibido de {company}. Referencia: {iban}. Fecha: {date}.",
            ],
        }
        return templates.get(lang, templates["en"])

    def generate_sentence(self, lang: str) -> str:
        """Generate a single sentence with embedded PII."""
        template = random.choice(self._get_sentence_templates(lang))

        # Generate all PII types
        name = self.generate_name(lang)

        return template.format(
            name=name,
            email=self.generate_email(lang, name),
            phone=self.generate_phone(lang),
            address=self.generate_address(lang),
            company=self.generate_company(lang),
            credit_card=self.generate_credit_card(),
            iban=self.generate_iban(lang),
            ssn=self.generate_ssn(lang),
            passport=self.generate_passport(lang),
            username=self.generate_username(lang),
            employee_id=self.generate_employee_id(lang),
            medical_record=self.generate_medical_record(lang),
            date=self.generate_date(lang),
        )

    def generate_paragraph(self, lang: str, sentences: int = 5) -> str:
        """Generate a paragraph with multiple sentences."""
        return " ".join(self.generate_sentence(lang) for _ in range(sentences))

    def generate_text(self, lang: str, target_size_bytes: int = 100000) -> str:
        """Generate text of approximately target size."""
        paragraphs = []
        current_size = 0

        while current_size < target_size_bytes:
            paragraph = self.generate_paragraph(lang, sentences=random.randint(3, 7))
            paragraphs.append(paragraph)
            current_size += len(paragraph.encode("utf-8"))

        return "\n\n".join(paragraphs)


def main():
    parser = argparse.ArgumentParser(
        description="Generate multilingual test data for PII Masker"
    )
    parser.add_argument(
        "--templates-dir",
        default="test/data/pii_templates",
        help="Directory containing PII templates",
    )
    parser.add_argument(
        "--output-dir",
        default="test/data/input",
        help="Output directory for generated files",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=100000,
        help="Target size in bytes per file (default: 100KB)",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        default=["en", "de", "fr", "it", "es"],
        help="Languages to generate (default: all)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )

    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    generator = TestDataGenerator(args.templates_dir)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for lang in args.languages:
        print(f"Generating {lang} test data...")
        text = generator.generate_text(lang, args.size)

        output_file = output_dir / f"{lang}_sample.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(text)

        actual_size = output_file.stat().st_size
        print(f"  Created {output_file} ({actual_size:,} bytes)")

    print("\nDone!")


if __name__ == "__main__":
    main()
