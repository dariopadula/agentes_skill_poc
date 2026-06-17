import unicodedata


def normalize_text(text: str) -> str:
    """Pasa a minúsculas y elimina tildes para simplificar las reglas."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    without_accents = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    )
    return " ".join(without_accents.split())
