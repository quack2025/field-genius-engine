"""Country detection from phone number prefix.

Covers LATAM + ES + US. Uses longest-prefix-match so +506 (Costa Rica)
wins over +5 and +51 (Peru) wins over +5.
"""

from __future__ import annotations


# (prefix, iso_code, display_name)
_PREFIXES: list[tuple[str, str, str]] = [
    # Central America (3-digit codes go first via sort below)
    ("+502", "GT", "Guatemala"),
    ("+503", "SV", "El Salvador"),
    ("+504", "HN", "Honduras"),
    ("+505", "NI", "Nicaragua"),
    ("+506", "CR", "Costa Rica"),
    ("+507", "PA", "Panamá"),
    # South America 3-digit
    ("+591", "BO", "Bolivia"),
    ("+593", "EC", "Ecuador"),
    ("+595", "PY", "Paraguay"),
    ("+598", "UY", "Uruguay"),
    # 2-digit
    ("+51", "PE", "Perú"),
    ("+52", "MX", "México"),
    ("+53", "CU", "Cuba"),
    ("+54", "AR", "Argentina"),
    ("+55", "BR", "Brasil"),
    ("+56", "CL", "Chile"),
    ("+57", "CO", "Colombia"),
    ("+58", "VE", "Venezuela"),
    # Europe + NANP
    ("+34", "ES", "España"),
    ("+1", "US", "Estados Unidos"),
]

# Longest prefix first so matching stops at the most specific entry.
_PREFIXES.sort(key=lambda x: -len(x[0]))


def detect_country(phone: str) -> tuple[str, str] | None:
    """Return (iso_code, display_name) for a phone number, or None if unknown.

    Accepts phone with or without leading '+'. Tolerates 'whatsapp:' prefix.
    """
    if not phone:
        return None
    p = phone.strip().replace("whatsapp:", "").strip()
    if not p:
        return None
    if not p.startswith("+"):
        p = "+" + p
    for prefix, iso, name in _PREFIXES:
        if p.startswith(prefix):
            return iso, name
    return None
