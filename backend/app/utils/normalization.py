from __future__ import annotations

import re


ABBREVIATIONS = {
    "cust": "customer",
    "client": "customer",
    "usr": "user",
    "acct": "account",
    "acc": "account",
    "addr": "address",
    "ph": "phone",
    "qty": "quantity",
    "amt": "amount",
    "num": "number",
    "no": "number",
    "tel": "phone",
    "mob": "mobile",
    "dt": "date",
    "ref": "reference",
    "mail": "email",
    "zip": "postal",
    "dob": "birthdate",
    "nm": "name",
}

SEMANTIC_SYNONYMS = {
    "customer": {"client", "user", "buyer"},
    "identifier": {"id", "key", "reference"},
    "phone": {"mobile", "telephone", "contact"},
    "amount": {"value", "price", "total"},
    "email": {"mail", "email_address", "contact_email"},
    "postal": {"zip", "postcode", "postal_code"},
    "birthdate": {"dob", "date_of_birth", "birthday"},
}

_overlay_abbreviations: dict[str, str] = {}
_overlay_semantic_synonyms: dict[str, set[str]] = {}


def configure_normalization_overrides(
    abbreviations: dict[str, str] | None = None,
    semantic_synonyms: dict[str, set[str]] | None = None,
) -> None:
    global _overlay_abbreviations, _overlay_semantic_synonyms
    _overlay_abbreviations = {key: value for key, value in (abbreviations or {}).items() if key and value}
    _overlay_semantic_synonyms = {
        key: {item for item in values if item}
        for key, values in (semantic_synonyms or {}).items()
        if key
    }


def clear_normalization_overrides() -> None:
    configure_normalization_overrides({}, {})


def abbreviation_map() -> dict[str, str]:
    return {**ABBREVIATIONS, **_overlay_abbreviations}


def semantic_synonym_map() -> dict[str, set[str]]:
    merged = {canonical: set(synonyms) for canonical, synonyms in SEMANTIC_SYNONYMS.items()}
    for canonical, synonyms in _overlay_semantic_synonyms.items():
        merged.setdefault(canonical, set()).update(synonyms)
    return merged


def normalize_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", value).strip().lower()
    tokens = [expand_token(token) for token in cleaned.split() if token]
    return " ".join(tokens)


def tokenize_name(value: str) -> list[str]:
    normalized = normalize_name(value)
    return [token for token in normalized.split() if token]


def expand_token(token: str) -> str:
    return abbreviation_map().get(token, token)


def semantic_token_set(value: str) -> set[str]:
    tokens = set(tokenize_name(value))
    enriched = set(tokens)
    for token in tokens:
        for canonical, synonyms in semantic_synonym_map().items():
            if token == canonical or token in synonyms:
                enriched.add(canonical)
                enriched.update(synonyms)
    return enriched