"""Synthetic QR delivery-scene frame generator.

Generates a frame-by-frame simulation of a robot's camera approaching a
patient's wristband QR code and then a kit's QR code, with the kinds of
degradation a real camera feed would have: hand-held camera shake,
changing distance (QR growing as the robot gets closer), a changing
viewing angle, brief occlusion (something briefly blocking the code), and
brightness/sensor noise. No real camera footage or personal data is used
or required -- everything here is synthetically rendered.

This module only produces in-memory frames (`numpy.ndarray`) plus
per-frame ground-truth metadata; it does not do any video file I/O --
see `generate_synthetic_video.py` for the CLI that encodes these frames
to an .mp4 and writes the metadata alongside it. Keeping the two separate
means the frame-generation logic (and its ground truth) can be unit
tested directly, and the PR6 evaluation benchmark can reuse it without
needing to decode a video file at all.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np
import qrcode


@dataclass
class SceneConfig:
    patient_id: str = "PATIENT_A_ROOM_203"
    kit_id: str = "KIT_TOILETING_A"
    frame_size: int = 480
    fps: int = 15
    seconds_per_code: float = 3.0
    # Distance: QR box_size (px per QR "module") interpolates min -> max
    # as the robot approaches, simulating the code growing in-frame.
    min_box_size: int = 3
    max_box_size: int = 14
    # Hand-held/robot-vibration jitter, in pixels.
    shake_px: int = 6
    # Max viewing-angle perspective skew, in pixels of corner displacement.
    max_skew_px: int = 14
    # Fraction of frames, within each code's phase, that have something
    # briefly occluding part of the code.
    occlusion_fraction: float = 0.15
    occlusion_size_frac: float = 0.35
    # Brightness multiplier range (1.0 = unchanged).
    min_brightness: float = 0.55
    max_brightness: float = 1.35
    noise_sigma: float = 10.0
    seed: int = 0

    @property
    def frames_per_code(self) -> int:
        return max(1, round(self.fps * self.seconds_per_code))

    @property
    def total_frames(self) -> int:
        return self.frames_per_code * 2


@dataclass
class FrameInfo:
    frame_index: int
    phase: str  # "patient" | "kit"
    qr_value: str
    occluded: bool
    box_size: int
    brightness: float


def _render_qr(data: str, box_size: int) -> np.ndarray:
    """Renders `data` as a black-on-white QR, returned as a BGR image."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    arr = np.array(img)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _paste_centered(canvas: np.ndarray, patch: np.ndarray, dx: int, dy: int) -> None:
    """Pastes `patch` onto `canvas`, centered and offset by (dx, dy), clipped
    to the canvas bounds."""
    ch, cw = canvas.shape[:2]
    ph, pw = patch.shape[:2]
    x0 = (cw - pw) // 2 + dx
    y0 = (ch - ph) // 2 + dy

    src_x0, src_y0 = max(0, -x0), max(0, -y0)
    dst_x0, dst_y0 = max(0, x0), max(0, y0)
    w = min(pw - src_x0, cw - dst_x0)
    h = min(ph - src_y0, ch - dst_y0)
    if w <= 0 or h <= 0:
        return
    canvas[dst_y0 : dst_y0 + h, dst_x0 : dst_x0 + w] = patch[
        src_y0 : src_y0 + h, src_x0 : src_x0 + w
    ]


def _apply_perspective_skew(img: np.ndarray, skew_px: float, rng: np.random.Generator) -> np.ndarray:
    """Warps the four corners of `img` by up to `skew_px` to simulate a
    changing viewing angle."""
    h, w = img.shape[:2]
    src = np.float32([[0, 0], [w, 0], [0, h], [w, h]])  # type: ignore[arg-type]
    jitter = rng.uniform(-skew_px, skew_px, size=(4, 2)).astype(np.float32)
    dst = src + jitter
    matrix = cv2.getPerspectiveTransform(src, dst)  # type: ignore[call-overload]
    return cv2.warpPerspective(img, matrix, (w, h), borderValue=(255, 255, 255))


def _apply_occlusion(img: np.ndarray, size_frac: float, rng: np.random.Generator) -> np.ndarray:
    """Draws an opaque gray rectangle over part of the image."""
    h, w = img.shape[:2]
    ow, oh = int(w * size_frac), int(h * size_frac)
    x0 = rng.integers(0, max(1, w - ow))
    y0 = rng.integers(0, max(1, h - oh))
    out = img.copy()
    cv2.rectangle(out, (x0, y0), (x0 + ow, y0 + oh), (90, 90, 90), thickness=-1)
    return out


def _apply_brightness(img: np.ndarray, factor: float) -> np.ndarray:
    out = img.astype(np.float32) * factor
    return np.clip(out, 0, 255).astype(np.uint8)


def _apply_noise(img: np.ndarray, sigma: float, rng: np.random.Generator) -> np.ndarray:
    if sigma <= 0:
        return img
    noise = rng.normal(0, sigma, size=img.shape)
    out = img.astype(np.float32) + noise
    return np.clip(out, 0, 255).astype(np.uint8)


def generate_frames(config: SceneConfig):
    """Yields (frame, FrameInfo) pairs for the full synthetic scene.

    Phase 1 ("patient"): `config.patient_id` QR approaching the camera.
    Phase 2 ("kit"): `config.kit_id` QR approaching the camera.
    Deterministic for a given `config.seed`.
    """
    rng = np.random.default_rng(config.seed)
    phases = [("patient", config.patient_id), ("kit", config.kit_id)]
    frame_index = 0

    for phase_name, value in phases:
        n = config.frames_per_code
        occluded_flags = rng.random(n) < config.occlusion_fraction

        for i in range(n):
            t = i / max(1, n - 1)
            box_size = round(config.min_box_size + t * (config.max_box_size - config.min_box_size))

            qr_img = _render_qr(value, box_size)
            qr_img = _apply_perspective_skew(qr_img, config.max_skew_px * (1 - 0.5 * t), rng)

            canvas = np.full((config.frame_size, config.frame_size, 3), 255, dtype=np.uint8)
            shake_x = int(config.shake_px * math.sin(frame_index * 0.9) + rng.integers(-2, 3))
            shake_y = int(config.shake_px * math.cos(frame_index * 0.7) + rng.integers(-2, 3))
            _paste_centered(canvas, qr_img, shake_x, shake_y)

            occluded = bool(occluded_flags[i])
            if occluded:
                canvas = _apply_occlusion(canvas, config.occlusion_size_frac, rng)

            brightness = float(
                (config.min_brightness + config.max_brightness) / 2
                + (config.max_brightness - config.min_brightness) / 2 * math.sin(frame_index * 0.15)
            )
            canvas = _apply_brightness(canvas, brightness)
            canvas = _apply_noise(canvas, config.noise_sigma, rng)

            info = FrameInfo(
                frame_index=frame_index,
                phase=phase_name,
                qr_value=value,
                occluded=occluded,
                box_size=box_size,
                brightness=brightness,
            )
            yield canvas, info
            frame_index += 1
