"""Escalera de degradación L0-L3 para las llamadas de la Tarea 2.

L0 original -> L1 compresión tipo WhatsApp (Opus 16 kbps) -> L2 banda telefónica 8 kHz
-> L3 ruido blanco a un SNR fijo. Cada nivel parte del anterior (acumulativo).

Usa PyAV (las librerías de ffmpeg que trae faster-whisper), así que no hace falta ffmpeg instalado.
"""
import io
from pathlib import Path

import av
import numpy as np
import soundfile as sf
from faster_whisper.audio import decode_audio
from scipy.signal import butter, resample_poly, sosfiltfilt


def to_wav(src: Path, dst: Path, sample_rate: int = 16000) -> Path:
    """Cualquier formato (m4a, ogg, mp3, mp4...) -> WAV mono PCM 16 kHz."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    sf.write(dst, decode_audio(str(src), sampling_rate=sample_rate), sample_rate, subtype="PCM_16")
    return dst


def _bitrate(value: str) -> int:
    return int(float(value.lower().rstrip("k")) * 1000) if value.lower().endswith("k") else int(value)


def whatsapp(audio: np.ndarray, sr: int, codec: str = "libopus", bitrate: str = "16k") -> np.ndarray:
    """Codifica a Opus en un .ogg en memoria y lo vuelve a decodificar (como una nota de voz)."""
    buffer = io.BytesIO()
    with av.open(buffer, mode="w", format="ogg") as out:
        stream = out.add_stream(codec, rate=48000)  # Opus solo acepta 8/12/16/24/48 kHz; 48k es lo estándar
        stream.bit_rate = _bitrate(bitrate)
        stream.layout = "mono"
        pcm = (np.clip(audio, -1, 1) * 32767).astype("int16")[None, :]
        frame = av.AudioFrame.from_ndarray(pcm, format="s16", layout="mono")
        frame.sample_rate = sr
        resampler = av.AudioResampler(format=stream.codec_context.format.name, layout="mono", rate=48000)
        for resampled in resampler.resample(frame) + resampler.resample(None):
            for packet in stream.encode(resampled):
                out.mux(packet)
        for packet in stream.encode(None):
            out.mux(packet)
    buffer.seek(0)
    decoded = decode_audio(buffer, sampling_rate=sr)
    return decoded[: len(audio)].astype("float32")


def phone(audio: np.ndarray, sr: int, sample_rate: int = 8000,
          low_hz: int = 300, high_hz: int = 3400) -> np.ndarray:
    """Banda telefónica: pasa-banda 300-3400 Hz, bajada a 8 kHz y vuelta a sr (Whisper espera 16 kHz)."""
    sos = butter(4, [low_hz, high_hz], btype="bandpass", fs=sr, output="sos")
    filtered = sosfiltfilt(sos, audio)
    down = resample_poly(filtered, sample_rate, sr)
    return resample_poly(down, sr, sample_rate).astype("float32")


def add_noise(audio: np.ndarray, snr_db: float, seed: int = 42) -> np.ndarray:
    """Ruido blanco gaussiano con potencia tal que 10*log10(P_señal / P_ruido) = snr_db."""
    rng = np.random.default_rng(seed)
    signal_power = np.mean(audio**2)
    noise_power = signal_power / (10 ** (snr_db / 10))
    noisy = audio + rng.normal(0, np.sqrt(noise_power), size=audio.shape)
    return np.clip(noisy, -1, 1).astype("float32")


def measured_snr_db(clean: np.ndarray, noisy: np.ndarray) -> float:
    noise = noisy[: len(clean)] - clean[: len(noisy)]
    return float(10 * np.log10(np.mean(clean**2) / np.mean(noise**2)))


def build_ladder(wav_path: Path, out_dir: Path, levels: dict) -> dict[str, Path]:
    """Genera out_dir/<nivel>/<audio>.wav para cada nivel y devuelve sus rutas."""
    audio, sr = sf.read(wav_path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    paths = {}
    for name, spec in levels.items():
        kind = spec["type"]
        if kind == "whatsapp":
            audio = whatsapp(audio, sr, spec.get("codec", "libopus"), spec.get("bitrate", "16k"))
        elif kind == "phone":
            audio = phone(audio, sr, spec["sample_rate"], spec["low_hz"], spec["high_hz"])
        elif kind == "noise":
            audio = add_noise(audio, spec["snr_db"], spec.get("seed", 42))
        dst = out_dir / name / f"{wav_path.stem}.wav"
        dst.parent.mkdir(parents=True, exist_ok=True)
        sf.write(dst, audio, sr)
        paths[name] = dst
    return paths
