"""WER y CER con la misma normalización para referencia e hipótesis."""
import math
import re

import jiwer
import numpy as np

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


def bootstrap_ci(values, resamples: int = 10000, seed: int = 42, confidence: float = 0.95) -> tuple[float, float, float]:
    """Media y su IC por percentiles, remuestreando los clips con reemplazo."""
    x = np.asarray([v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))], dtype=float)
    if x.size == 0:
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, x.size, size=(resamples, x.size))].mean(axis=1)
    alpha = (1 - confidence) / 2
    return float(x.mean()), float(np.quantile(means, alpha)), float(np.quantile(means, 1 - alpha))


def wilson_ci(successes: int, n: int, confidence: float = 0.95) -> tuple[float, float, float]:
    """Proporción y su IC de Wilson (se comporta bien con n pequeño y p cerca de 0 o 1)."""
    if n == 0:
        return (float("nan"),) * 3
    z = {0.90: 1.6449, 0.95: 1.96, 0.99: 2.5758}[confidence]
    p = successes / n
    center = (p + z**2 / (2 * n)) / (1 + z**2 / n)
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    return p, max(0.0, center - half), min(1.0, center + half)