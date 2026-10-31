"""Transcripción con faster-whisper + medición de tiempo, dispositivo real y pico de VRAM."""
import json
import os
import threading
import time
from pathlib import Path

from faster_whisper import WhisperModel

_MODELS: dict[tuple, WhisperModel] = {}


def load_model(size: str, device: str, compute_type: str) -> WhisperModel:
    if os.getenv("FORCE_CPU") == "1":
        device = "cpu"
    key = (size, device, compute_type)
    if key not in _MODELS:
        _MODELS[key] = WhisperModel(size, device=device, compute_type=compute_type)
    return _MODELS[key]


class VramMonitor:
    """Muestrea la memoria usada en la GPU 0 cada 50 ms y guarda el pico (MiB)."""

    def __init__(self, interval: float = 0.05):
        self.interval = interval
        self.baseline_mib = self.peak_mib = None
        self._stop = threading.Event()
        self._thread = None
        try:
            import pynvml

            pynvml.nvmlInit()
            self._nvml = pynvml
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self.gpu_name = pynvml.nvmlDeviceGetName(self._handle)
        except Exception:
            self._nvml = None
            self.gpu_name = None

    def _used_mib(self) -> float:
        return self._nvml.nvmlDeviceGetMemoryInfo(self._handle).used / 2**20

    def _loop(self):
        while not self._stop.is_set():
            self.peak_mib = max(self.peak_mib, self._used_mib())
            time.sleep(self.interval)

    def __enter__(self):
        if self._nvml:
            self.baseline_mib = self.peak_mib = self._used_mib()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc):
        if self._thread:
            self._stop.set()
            self._thread.join()


def transcribe(audio_path: Path, size: str, device: str, compute_type: str,
               language: str = "es", beam_size: int = 5,
               hotwords: str | None = None, initial_prompt: str | None = None) -> dict:
    """hotwords se antepone a cada ventana de 30 s; initial_prompt solo a la primera (faster-whisper 1.1.1)."""
    with VramMonitor() as vram:
        t0 = time.perf_counter()
        model = load_model(size, device, compute_type)
        load_s = time.perf_counter() - t0

        t1 = time.perf_counter()
        segments, info = model.transcribe(str(audio_path), language=language, beam_size=beam_size,
                                          hotwords=hotwords, initial_prompt=initial_prompt)
        segments = list(segments)  # el generador es perezoso: aquí ocurre la inferencia
        transcribe_s = time.perf_counter() - t1

    return {
        "audio": audio_path.name,
        "model": size,
        "requested_device": device,
        # Lo que reporta CTranslate2 en tiempo de ejecución, no lo que pedimos
        "runtime_device": model.model.device,
        "compute_type": compute_type,
        "hotwords": hotwords,
        "initial_prompt": initial_prompt,
        "gpu_name": vram.gpu_name,
        "vram_peak_mib": vram.peak_mib,
        "vram_delta_mib": (vram.peak_mib - vram.baseline_mib) if vram.peak_mib else None,
        "audio_duration_s": info.duration,
        "load_s": load_s,
        "transcribe_s": transcribe_s,
        "rtf": transcribe_s / info.duration if info.duration else None,
        "text": " ".join(s.text.strip() for s in segments),
        "segments": [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments],
    }


def cache_path(cache_dir: Path, audio_stem: str, size: str, device: str, compute_type: str,
               variant: str | None = None) -> Path:
    suffix = f"__{variant}" if variant else ""
    return cache_dir / f"{audio_stem}__{size}__{device}__{compute_type}{suffix}.json"


def load_cached(path: Path) -> dict | None:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def save_cached(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
