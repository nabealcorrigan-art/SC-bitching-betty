#!/usr/bin/env python3
"""
generate_default_sound.py

Creates ``sounds/alert.wav`` – a short 440 Hz sine-wave beep.
Run once after cloning the repository or if you need a fresh default sound.

    python generate_default_sound.py
"""

import math
import os
import struct
import wave

SAMPLE_RATE = 44100
DURATION = 0.6        # seconds
FREQUENCY = 440.0     # Hz  (concert A)
AMPLITUDE = 28000     # 0–32767


def _generate_samples(duration: float, frequency: float,
                      amplitude: int, sample_rate: int) -> bytes:
    """Return raw 16-bit little-endian PCM samples for a sine wave."""
    n_samples = int(duration * sample_rate)
    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        # Simple fade-out envelope to avoid a click at the end.
        env = 1.0 - (i / n_samples)
        value = int(amplitude * env * math.sin(2 * math.pi * frequency * t))
        samples.append(struct.pack("<h", value))
    return b"".join(samples)


def main() -> None:
    out_dir = os.path.join(os.path.dirname(__file__), "sounds")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "alert.wav")

    pcm_data = _generate_samples(DURATION, FREQUENCY, AMPLITUDE, SAMPLE_RATE)

    with wave.open(out_path, "w") as wf:
        wf.setnchannels(1)       # mono
        wf.setsampwidth(2)       # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_data)

    print(f"Created: {out_path}")


if __name__ == "__main__":
    main()
