"""WER y CER con la misma normalización para referencia e hipótesis."""
import re

import jiwer

from engine.numbers import normalize_numbers, strip_accents


def normalize_text(text: str, numbers: bool = True) -> str:
    text = text.lower()
    if numbers:
        text = normalize_numbers(text)
    text = strip_accents(text)
    text = re.sub(r"(?<=\d)[.,](?=\d{3}\b)", "", text)  # 6.500 -> 6500
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def wer_cer(reference: str, hypothesis: str, numbers: bool = True) -> dict:
    ref, hyp = normalize_text(reference, numbers), normalize_text(hypothesis, numbers)
    return {"wer": jiwer.wer(ref, hyp), "cer": jiwer.cer(ref, hyp)}
