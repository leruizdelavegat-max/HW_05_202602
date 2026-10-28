"""Normalización de números hablados en español: "seis mil quinientos" -> 6500."""
import re
import unicodedata


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


_UNITS = {
    "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20, "veintiun": 21, "veintiuno": 21, "veintiuna": 21,
    "veintidos": 22, "veintitres": 23, "veinticuatro": 24, "veinticinco": 25,
    "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29,
}
_TENS = {
    "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
    "setenta": 70, "ochenta": 80, "noventa": 90,
}
_HUNDREDS = {
    "cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200,
    "trescientos": 300, "trescientas": 300, "cuatrocientos": 400,
    "cuatrocientas": 400, "quinientos": 500, "quinientas": 500,
    "seiscientos": 600, "seiscientas": 600, "setecientos": 700,
    "setecientas": 700, "ochocientos": 800, "ochocientas": 800,
    "novecientos": 900, "novecientas": 900,
}
_SMALL = {**_UNITS, **_TENS, **_HUNDREDS}
_MULTIPLIERS = {"mil": 1_000, "millon": 1_000_000, "millones": 1_000_000}
NUMBER_WORDS = set(_SMALL) | set(_MULTIPLIERS)


def words_to_number(words: list[str]) -> int:
    """Convierte una secuencia de palabras numéricas (sin "y") a entero."""
    total, current = 0, 0
    for raw in words:
        w = strip_accents(raw.lower())
        if w in _SMALL:
            current += _SMALL[w]
        elif w == "mil":
            total += (current or 1) * 1_000
            current = 0
        elif w in ("millon", "millones"):
            total = (total + (current or 1)) * 1_000_000
            current = 0
        else:
            raise ValueError(f"No es una palabra numérica: {raw!r}")
    return total + current


def _is_number_word(token: str) -> bool:
    return strip_accents(token.lower()) in NUMBER_WORDS


def normalize_numbers(text: str) -> str:
    """Reemplaza cada secuencia de números hablados por dígitos, conservando el resto del texto.

    "espero seis mil quinientos soles" -> "espero 6500 soles"
    "treinta y cinco"                  -> "35"   (la "y" solo se une entre decena y unidad)
    """
    tokens = re.findall(r"\w+|\W+", text)
    out, i = [], 0
    while i < len(tokens):
        if not _is_number_word(tokens[i]):
            out.append(tokens[i])
            i += 1
            continue
        run, j = [tokens[i]], i + 1
        while j < len(tokens):
            # tokens[j] es separador; tokens[j+1] la siguiente palabra
            if not tokens[j].isspace() or j + 1 >= len(tokens):
                break
            nxt = tokens[j + 1]
            if _is_number_word(nxt):
                run.append(nxt)
                j += 2
            elif (
                nxt.lower() == "y"
                and strip_accents(run[-1].lower()) in _TENS
                and j + 3 < len(tokens)
                and strip_accents(tokens[j + 3].lower()) in _UNITS
                and _UNITS[strip_accents(tokens[j + 3].lower())] < 10
            ):
                run.append(tokens[j + 3])
                j += 4
            else:
                break
        # "un" / "una" sueltos son artículos ("un puesto"), no números
        if len(run) == 1 and strip_accents(run[0].lower()) in ("un", "una", "uno"):
            out.append(run[0])
        else:
            out.append(str(words_to_number(run)))
        i = j
    return "".join(out)
