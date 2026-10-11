"""
FFmpeg utilities for CCTV evidence generation.

Responsibilities
----------------
- Locate the configured FFmpeg executable.
- Validate input/output paths.
- Convert generated evidence to H.264 MP4.
- Use an atomic replacement for the final output.
- Prevent an individual FFmpeg failure from corrupting an
  already-existing final evidence file.

This module does NOT:
- consume Redis messages
- create incidents
- publish events
- perform detection
- perform tracking
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_PRESET = "fast"
DEFAULT_CRF = "23"
DEFAULT_PIXEL_FORMAT = "yuv420p"
DEFAULT_PROFILE = "main"
DEFAULT_LEVEL = "3.0"

DEFAULT_TIMEOUT_SECONDS = 300.0


# ============================================================
# FFMPEG DISCOVERY
# ============================================================

def _get_ffmpeg_binary() -> str:
    """
    Resolve the FFmpeg executable.

    Priority:
    1. FFMPEG_BIN environment variable.
    2. ffmpeg available on PATH.
    """
    configured = os.getenv("FFMPEG_BIN", "").strip()

    if configured:
        configured_path = Path(configured)

        if configured_path.exists():
            if configured_path.is_file():
                return str(configured_path)

        resolved = shutil.which(configured)
        if resolved:
            return resolved

        raise RuntimeError(
            f"Configured FFmpeg executable was not found: {configured!r}"
        )

    resolved = shutil.which("ffmpeg")

    if resolved:
        return resolved

    raise RuntimeError(
        "FFmpeg executable was not found. "
        "Install FFmpeg or set FFMPEG_BIN."
    )


def require_ffmpeg() -> str:
    """
    Public FFmpeg availability check.
    """
    return _get_ffmpeg_binary()


# ============================================================
# VALIDATION
# ============================================================

def _validate_input_file(
    path: Path,
    name: str,
) -> None:
    """
    Validate an input file before invoking FFmpeg.
    """
    if not isinstance(path, Path):
        raise TypeError(
            f"{name} must be a pathlib.Path."
        )

    try:
        if not path.exists():
            raise FileNotFoundError(
                f"{name} does not exist: {path}"
            )

        if not path.is_file():
            raise ValueError(
                f"{name} is not a file: {path}"
            )

        if path.stat().st_size <= 0:
            raise ValueError(
                f"{name} is empty: {path}"
            )

    except OSError as exc:
        raise RuntimeError(
            f"Unable to inspect {name}: {path}: {exc}"
        ) from exc


def _prepare_output_path(
    final_path: Path,
) -> None:
    """
    Prepare the parent directory of the final output.
    """
    if not isinstance(final_path, Path):
        raise TypeError(
            "final_path must be a pathlib.Path."
        )

    final_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


def _env_float(
    name: str,
    default: float,
    *,
    minimum: float | None = None,
) -> float:
    """
    Read a floating-point environment variable safely.
    """
    raw = os.getenv(name)

    if raw is None or not raw.strip():
        value = default
    else:
        try:
            value = float(raw)
        except ValueError:
            print(
                f"[FFMPEG] Invalid float for {name}={raw!r}; "
                f"using {default}."
            )
            value = default

    if minimum is not None and value < minimum:
        print(
            f"[FFMPEG] {name}={value} is below minimum "
            f"{minimum}; using {minimum}."
        )
        value = minimum

    return value


FFMPEG_TIMEOUT_SECONDS = _env_float(
    "EVIDENCE_FFMPEG_TIMEOUT_SECONDS",
    DEFAULT_TIMEOUT_SECONDS,
    minimum=1.0,
)


# ============================================================
# CONVERSION
# ============================================================

def convert_to_h264(
    raw_path: Path,
    final_path: Path,
    *,
    preset: str = DEFAULT_PRESET,
    crf: str = DEFAULT_CRF,
) -> Path:
    """
    Convert a generated raw MP4 into H.264 MP4.

    The final file is replaced atomically only after FFmpeg
    successfully completes and the temporary output has been
    validated.

    Returns:
        Path to the final H.264 file.
    """
    _validate_input_file(
        raw_path,
        "raw_path",
    )

    if not isinstance(final_path, Path):
        raise TypeError(
            "final_path must be a pathlib.Path."
        )

    _prepare_output_path(final_path)

    ffmpeg_bin = _get_ffmpeg_binary()

    temp_path = final_path.with_name(
        f"{final_path.stem}_h264_tmp"
        f"_{os.getpid()}.mp4"
    )

    command = [
        ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-i",
        str(raw_path),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        str(preset),
        "-crf",
        str(crf),
        "-pix_fmt",
        DEFAULT_PIXEL_FORMAT,
        "-profile:v",
        DEFAULT_PROFILE,
        "-level:v",
        DEFAULT_LEVEL,
        "-movflags",
        "+faststart",
        str(temp_path),
    ]

    try:
        print(
            f"[FFMPEG] Converting "
            f"{raw_path} -> {final_path}"
        )

        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )

        if not temp_path.exists():
            raise RuntimeError(
                "FFmpeg completed successfully but "
                f"temporary output was not created: {temp_path}"
            )

        if temp_path.stat().st_size <= 0:
            raise RuntimeError(
                "FFmpeg created an empty temporary output: "
                f"{temp_path}"
            )

        os.replace(
            temp_path,
            final_path,
        )

        if not final_path.exists():
            raise RuntimeError(
                "Atomic replacement completed but final "
                f"evidence file is missing: {final_path}"
            )

        if final_path.stat().st_size <= 0:
            raise RuntimeError(
                "Final evidence file is empty: "
                f"{final_path}"
            )

        print(
            f"[FFMPEG] Conversion complete: {final_path}"
        )

        return final_path

    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "FFmpeg conversion timed out after "
            f"{FFMPEG_TIMEOUT_SECONDS:.1f} seconds: "
            f"{raw_path}"
        ) from exc

    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()

        if stderr:
            raise RuntimeError(
                f"FFmpeg conversion failed: {stderr}"
            ) from exc

        raise RuntimeError(
            "FFmpeg conversion failed without diagnostic output."
        ) from exc

    except OSError as exc:
        raise RuntimeError(
            f"Unable to execute FFmpeg: {exc}"
        ) from exc

    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError as cleanup_error:
            print(
                f"[FFMPEG] Temporary-file cleanup failed "
                f"for {temp_path}: {cleanup_error}"
            )


def convert_proof_to_h264(
    raw_path: Path,
    final_path: Path,
    *,
    preset: str = DEFAULT_PRESET,
    crf: str = DEFAULT_CRF,
) -> Path:
    """
    Compatibility wrapper for proof-video conversion.
    """
    return convert_to_h264(
        raw_path,
        final_path,
        preset=preset,
        crf=crf,
    )


__all__ = [
    "convert_to_h264",
    "convert_proof_to_h264",
    "require_ffmpeg",
]
