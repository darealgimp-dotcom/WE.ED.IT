#!/usr/bin/env python3
# coding: utf-8
"""
WE.ED.IT v4.0 - Unified Cinematic Music Video Director
Complete AI-driven music video generation system with intelligent clip selection,
viral scoring, and hardware acceleration.

Vision: "Musik dirigiert. KI schneidet. Du kreierst."
(Music directs. AI cuts. You create.)

Author: darealgimp-dotcom
License: MIT
"""

from __future__ import annotations

import os
import sys
import json
import re
import time
import shutil
import threading
import subprocess
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, List, Dict, Tuple, Optional
from datetime import datetime
import tempfile

import cv2
import numpy as np
from scipy.spatial.distance import cosine
import librosa
import soundfile as sf

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import pynvml
    HAS_NVML = True
except ImportError:
    HAS_NVML = False

try:
    import eyed3
    HAS_EYED3 = True
except ImportError:
    HAS_EYED3 = False

# ============================================================================
# LOGGING SETUP
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============================================================================
# GLOBAL CONSTANTS
# ============================================================================
VECTOR_DIM = 9
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac"}

# Semantic vector mappings
GENRE_KEYWORDS: Dict[str, List[str]] = {
    "genre_hiphop": ["hip", "hop", "hiphop", "rap", "trap", "drill", "grime", "street", "urban"],
    "genre_pop": ["pop", "dance", "edm", "synth", "chart", "bright", "colorful"],
    "genre_electronic": ["electronic", "techno", "house", "trance", "ambient", "abstract", "drone"],
    "genre_rock": ["rock", "metal", "punk", "grunge", "indie", "wide", "dramatic"],
    "genre_soul": ["soul", "rnb", "r&b", "funk", "gospel", "blues", "jazz", "intimate"],
}

MOOD_KEYWORDS: Dict[str, List[str]] = {
    "mood_happy": ["happy", "joy", "euphoric", "upbeat", "positive", "fun", "bright"],
    "mood_intense": ["intense", "dark", "aggressive", "angry", "hard", "fierce", "energetic", "action"],
    "mood_calm": ["calm", "chill", "slow", "soft", "mellow", "smooth", "relax", "static"],
}

SHOT_TAGS = ["wide", "close", "medium", "drone", "pov", "extreme", "aerial"]
MOTION_TAGS = ["pan", "zoom", "orbit", "static", "tracking", "tilt", "dolly", "handheld", "fast", "slow"]
EMOTION_TAGS = list(MOOD_KEYWORDS["mood_happy"]) + list(MOOD_KEYWORDS["mood_intense"]) + list(MOOD_KEYWORDS["mood_calm"])

# Hip-Hop color ranges (HSV)
HIPHOP_COLOR_RANGES = {
    "gold": ([20, 100, 100], [35, 255, 255]),
    "neon": ([80, 150, 150], [140, 255, 255]),
    "red_accent": ([0, 120, 120], [10, 255, 255]),
}


# ============================================================================
# DATA CONTAINERS
# ============================================================================
@dataclass
class ClipMetadata:
    """Video clip metadata with semantic vectors."""
    path: Path
    duration: float
    shot_type: str
    movement: str
    emotion_tags: List[str]
    brightness: float
    motion: float
    hiphop_affinity: float
    dominant_colors: List[Tuple[int, int, int]]
    vector: np.ndarray


@dataclass
class AudioMetadata:
    """Audio analysis results."""
    path: Path
    duration: float
    tempo: float
    beats: np.ndarray
    onset_frames: np.ndarray
    rms_energy: np.ndarray
    song_structure: Dict[str, Any]
    semantic_vector: np.ndarray
    artist: str
    title: str
    genre: str


@dataclass
class Segment:
    """Video segment specification."""
    start_time: float
    end_time: float
    duration: float
    clip: ClipMetadata
    effect_mode: str  # "NORMAL", "WOBBLE-ZOOM", "SCRATCH-STUTTER"
    energy_level: float


# ============================================================================
# RESOURCE GUARD (Memory & VRAM Protection)
# ============================================================================
class ResourceGuard:
    """Safeguards system resources during concurrent processing."""

    def __init__(
        self,
        max_ffmpeg_processes: int = 4,
        min_free_ram_mb: int = 1024,
        min_free_vram_mb: int = 512,
        monitor_vram: bool = True
    ):
        cpu_cores = os.cpu_count() or 4
        self.max_workers = min(max_ffmpeg_processes, max(1, cpu_cores - 1))
        self.min_free_ram = min_free_ram_mb * 1024 * 1024
        self.min_free_vram = min_free_vram_mb * 1024 * 1024
        self.monitor_vram = monitor_vram

        self.semaphore = threading.BoundedSemaphore(self.max_workers)
        self._active_processes: set[subprocess.Popen] = set()
        self._lock = threading.Lock()

        self._nvml_initialized = False
        if self.monitor_vram and HAS_NVML:
            try:
                pynvml.nvmlInit()
                self._nvml_initialized = True
            except Exception:
                pass

        logger.info(f"🛡️  [CLAW-GUARD] Resource pool: {self.max_workers} workers, {min_free_ram_mb}MB RAM floor")

    def get_system_free_ram(self) -> int:
        """Returns free system RAM in bytes."""
        if HAS_PSUTIL:
            return psutil.virtual_memory().available
        try:
            cmd = "wmic OS get FreePhysicalMemory /Value"
            res = subprocess.run(cmd, capture_output=True, text=True, shell=True, check=True)
            for line in res.stdout.split("\n"):
                if "FreePhysicalMemory" in line:
                    kb = int(line.split("=")[1].strip())
                    return kb * 1024
        except Exception:
            pass
        return 2048 * 1024 * 1024

    def get_gpu_free_vram(self) -> int:
        """Returns free GPU VRAM in bytes."""
        if self._nvml_initialized and HAS_NVML:
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                return info.free
            except Exception:
                pass
        return 1024 * 1024 * 1024

    def check_safety_thresholds(self) -> bool:
        """Validates memory thresholds."""
        free_ram = self.get_system_free_ram()
        if free_ram < self.min_free_ram:
            free_mb = round(free_ram / (1024 * 1024))
            logger.warning(f"⚠️  Low RAM: {free_mb}MB available. Pausing...")
            return False

        if self._nvml_initialized:
            free_vram = self.get_gpu_free_vram()
            if free_vram < self.min_free_vram:
                vram_mb = round(free_vram / (1024 * 1024))
                logger.warning(f"⚠️  Low VRAM: {vram_mb}MB available. Pausing...")
                return False

        return True

    def block_until_safe(self, interval_seconds: float = 2.0) -> None:
        """Blocks until memory conditions improve."""
        while not self.check_safety_thresholds():
            time.sleep(interval_seconds)

    def run_safe_subprocess(self, command: List[str], **kwargs) -> subprocess.CompletedProcess:
        """Executes subprocess within semaphore guard."""
        self.block_until_safe()

        with self.semaphore:
            if "stdout" not in kwargs:
                kwargs["stdout"] = subprocess.PIPE
            if "stderr" not in kwargs:
                kwargs["stderr"] = subprocess.PIPE
            if "text" not in kwargs:
                kwargs["text"] = True

            proc = subprocess.Popen(command, **kwargs)

            with self._lock:
                self._active_processes.add(proc)

            try:
                stdout, stderr = proc.communicate()
                returncode = proc.returncode or 0

                if returncode != 0:
                    logger.error(f"❌ Process failed (Code {returncode}): {stderr}")
                    raise RuntimeError(f"Subprocess error: {stderr}")

                return subprocess.CompletedProcess(command, returncode, stdout, stderr)
            finally:
                with self._lock:
                    self._active_processes.discard(proc)

    def terminate_all(self) -> None:
        """Terminates all active child processes."""
        with self._lock:
            for p in self._active_processes:
                try:
                    p.kill()
                    logger.info(f"💀 Terminated process: PID {p.pid}")
                except Exception:
                    pass
            self._active_processes.clear()

    def __del__(self):
        if self._nvml_initialized and HAS_NVML:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass


# ============================================================================
# AUDIO ANALYSIS LAYER
# ============================================================================
class AudioAnalysisLayer:
    """Comprehensive audio analysis with ID3 extraction and semantic vectors."""

    def __init__(self, audio_path: Path):
        self.audio_path = Path(audio_path)
        self.metadata: Optional[AudioMetadata] = None

    def analyze(self) -> AudioMetadata:
        """Performs complete audio analysis."""
        logger.info(f"🎵 Analyzing: {self.audio_path.name}")

        # Load audio
        y, sr = librosa.load(str(self.audio_path), sr=None)
        duration = librosa.get_duration(y=y, sr=sr)

        # Extract ID3 tags
        artist, title, genre = self._extract_id3_tags()

        # Detect tempo and beats
        tempo, beats = self._detect_tempo_and_beats(y, sr)

        # Onset detection
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onset_frames = librosa.onset.onset_detect(onset_env=onset_env, sr=sr)
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)

        # Energy profiling
        rms_energy = librosa.feature.rms(y=y)[0]
        rms_times = librosa.frames_to_time(np.arange(len(rms_energy)), sr=sr)

        # Song structure detection
        song_structure = self._detect_song_structure(y, sr, onset_times, rms_energy)

        # Semantic vector computation
        semantic_vector = self._compute_semantic_vector(genre, title, artist)

        self.metadata = AudioMetadata(
            path=self.audio_path,
            duration=duration,
            tempo=tempo,
            beats=beats,
            onset_frames=onset_frames,
            rms_energy=rms_energy,
            song_structure=song_structure,
            semantic_vector=semantic_vector,
            artist=artist,
            title=title,
            genre=genre
        )

        logger.info(f"🎼 {artist} - {title} | {genre} | {tempo:.0f} BPM | {duration:.1f}s")
        logger.info(f"📊 Sections: {', '.join([s['label'] for s in song_structure['sections']])}")

        return self.metadata

    def _extract_id3_tags(self) -> Tuple[str, str, str]:
        """Extracts ID3 tags from MP3."""
        if not HAS_EYED3 or self.audio_path.suffix.lower() != ".mp3":
            return "Unknown", self.audio_path.stem, "Unknown"

        try:
            audiofile = eyed3.load(str(self.audio_path))
            artist = audiofile.tag.artist or "Unknown"
            title = audiofile.tag.title or self.audio_path.stem
            genre = audiofile.tag.genre.name if audiofile.tag.genre else "Unknown"
            return artist, title, genre
        except Exception:
            return "Unknown", self.audio_path.stem, "Unknown"

    def _detect_tempo_and_beats(self, y: np.ndarray, sr: int) -> Tuple[float, np.ndarray]:
        """Detects tempo and beat positions."""
        try:
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            tempo, beats = librosa.beat.beat_track(onset_env=onset_env, sr=sr)
            beat_times = librosa.frames_to_time(beats, sr=sr)
            return tempo, beat_times
        except Exception as e:
            logger.warning(f"⚠️  Beat detection failed: {e}. Using fallback 95 BPM")
            return 95.0, np.linspace(0, librosa.get_duration(y=y, sr=sr), 20)

    def _detect_song_structure(self, y: np.ndarray, sr: int, onset_times: np.ndarray, rms_energy: np.ndarray) -> Dict[str, Any]:
        """Detects song structure (intro, verse, chorus, bridge, drop, outro)."""
        duration = librosa.get_duration(y=y, sr=sr)

        # Placeholder structure (in real impl, would use beat sync or chroma features)
        intro_dur = min(8.0, duration * 0.1)
        outro_dur = min(6.0, duration * 0.08)
        middle = duration - intro_dur - outro_dur

        sections = [
            {"label": "intro", "start": 0.0, "end": intro_dur, "energy": float(np.mean(rms_energy[:100]))},
            {"label": "verse", "start": intro_dur, "end": intro_dur + middle * 0.3, "energy": float(np.mean(rms_energy[100:200]))},
            {"label": "chorus", "start": intro_dur + middle * 0.3, "end": intro_dur + middle * 0.6, "energy": float(np.mean(rms_energy[200:300]))},
            {"label": "drop", "start": intro_dur + middle * 0.6, "end": duration - outro_dur, "energy": float(np.mean(rms_energy[-200:-100]))},
            {"label": "outro", "start": duration - outro_dur, "end": duration, "energy": float(np.mean(rms_energy[-100:]))},
        ]

        # Detect drops (peaks in energy)
        drops = []
        for i in range(1, len(rms_energy) - 1):
            if rms_energy[i] > np.percentile(rms_energy, 85) and rms_energy[i] > rms_energy[i-1] and rms_energy[i] > rms_energy[i+1]:
                drop_time = librosa.frames_to_time(i, sr=sr)
                drops.append(drop_time)

        return {
            "sections": sections,
            "drops": drops,
            "duration": duration
        }

    def _compute_semantic_vector(self, genre: str, title: str, artist: str) -> np.ndarray:
        """Computes 9D semantic vector from audio metadata."""
        vec = np.zeros(VECTOR_DIM, dtype=np.float32)
        text = f"{genre} {title} {artist}".lower()

        # Genre [0-4]
        for idx, (genre_key, keywords) in enumerate(GENRE_KEYWORDS.items()):
            if any(kw in text for kw in keywords):
                vec[idx] = 1.0

        # Mood [5-7]
        for idx, (mood_key, keywords) in enumerate(MOOD_KEYWORDS.items()):
            if any(kw in text for kw in keywords):
                vec[5 + idx] = 1.0

        # Motion [8]
        vec[8] = 0.5  # Default medium motion for audio

        return vec


# ============================================================================
# VIDEO ANALYSIS LAYER
# ============================================================================
class VideoAnalysisLayer:
    """Video clip pool management with 9D vector space."""

    def __init__(self, pool_dir: Path, max_analysis_frames: int = 15):
        self.pool_dir = Path(pool_dir)
        self.max_frames = max_analysis_frames
        self.clips: List[ClipMetadata] = []
        self._recently_used: List[Path] = []
        self._load_and_analyze()

    def _load_and_analyze(self) -> None:
        """Loads and analyzes all video clips in pool directory."""
        if not self.pool_dir.exists():
            logger.error(f"❌ Clip pool not found: {self.pool_dir}")
            return

        count = 0
        for fname in sorted(os.listdir(self.pool_dir)):
            path = self.pool_dir / fname
            if path.suffix.lower() not in VIDEO_EXTS:
                continue

            resolved = path.resolve()
            if not resolved.exists():
                continue

            try:
                meta = self._analyze_clip(resolved, original_path=path)
                self.clips.append(meta)
                count += 1
            except Exception as e:
                logger.warning(f"⚠️  Skipping {fname}: {e}")

        logger.info(f"📦 [VideoPool] Loaded {count} clips in 9D space")

    def _analyze_clip(self, path: Path, original_path: Optional[Path] = None) -> ClipMetadata:
        """Analyzes a single video clip."""
        disp_path = original_path or path
        stem = disp_path.stem.lower()

        # Parse filename tags
        words = re.split(r"[\W_]+", stem)
        shot_type = next((w for w in words if w in SHOT_TAGS), "medium")
        movement = next((w for w in words if w in MOTION_TAGS), "static")
        emotion_tags = [w for w in words if w in EMOTION_TAGS]

        # Parse NFO metadata
        nfo_text = ""
        nfo_path = disp_path.with_suffix(".nfo")
        if nfo_path.exists():
            try:
                with open(nfo_path, "r", encoding="utf-8") as f:
                    nfo = json.load(f)
                    nfo_text = " ".join(nfo.get("tags", []))
                    if nfo.get("shot_scale"):
                        shot_type = nfo["shot_scale"]
                    if nfo.get("camera_movement"):
                        movement = nfo["camera_movement"]
            except Exception:
                pass

        # Analyze visual properties
        brightness, motion, duration, hiphop_affinity, colors = self._analyze_visual(path)

        # Compute 9D vector
        all_text = f"{stem} {nfo_text} {' '.join(emotion_tags)}"
        vector = self._compute_clip_vector(all_text, shot_type, movement, motion, hiphop_affinity)

        return ClipMetadata(
            path=disp_path,
            duration=duration,
            shot_type=shot_type,
            movement=movement,
            emotion_tags=emotion_tags,
            brightness=brightness,
            motion=motion,
            hiphop_affinity=hiphop_affinity,
            dominant_colors=colors,
            vector=vector
        )

    def _analyze_visual(self, path: Path) -> Tuple[float, float, float, float, List[Tuple[int, int, int]]]:
        """Analyzes visual properties of a clip."""
        cap = cv2.VideoCapture(str(path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total / fps if total > 0 else 0.0

        if total <= 0:
            cap.release()
            return 127.0, 0.0, 0.0, 0.0, [(127, 127, 127)]

        step = max(1, total // self.max_frames)
        brightness_samples = []
        motion_samples = []
        hiphop_scores = []
        prev_gray: Optional[np.ndarray] = None
        sample_frame: Optional[np.ndarray] = None

        for i in range(0, total, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            if sample_frame is None:
                sample_frame = frame.copy()

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            brightness_samples.append(float(np.mean(gray)))

            if prev_gray is not None:
                diff = cv2.absdiff(prev_gray, gray)
                motion_samples.append(float(np.mean(diff)))

            prev_gray = gray
            hiphop_scores.append(self._calculate_hiphop_score(frame, hsv, gray))

        cap.release()

        colors = []
        if sample_frame is not None:
            colors = self._extract_palette_kmeans(sample_frame)

        brightness = float(np.mean(brightness_samples)) if brightness_samples else 127.0
        raw_motion = float(np.mean(motion_samples)) if motion_samples else 0.0
        norm_motion = float(np.clip(raw_motion / 30.0, 0.0, 1.0))
        hiphop_affinity = float(np.mean(hiphop_scores)) if hiphop_scores else 0.0

        return brightness, norm_motion, duration, hiphop_affinity, colors

    def _calculate_hiphop_score(self, frame: np.ndarray, hsv: np.ndarray, gray: np.ndarray) -> float:
        """Calculates hip-hop visual affinity score."""
        h, w = frame.shape[:2]
        pixel_count = h * w
        score = 0.0

        for color_name, (low, up) in HIPHOP_COLOR_RANGES.items():
            mask = cv2.inRange(hsv, np.array(low), np.array(up))
            ratio = np.sum(mask > 0) / pixel_count
            if color_name == "gold":
                score += min(ratio * 10, 0.35)
            elif color_name == "neon":
                score += min(ratio * 8, 0.25)
            elif color_name == "red_accent":
                score += min(ratio * 5, 0.10)

        contrast = np.std(gray)
        if contrast > 60.0:
            score += 0.15

        edges = cv2.Canny(gray, 50, 150)
        edge_ratio = np.sum(edges > 0) / pixel_count
        if 0.08 < edge_ratio < 0.25:
            score += 0.15

        return min(score, 1.0)

    def _extract_palette_kmeans(self, frame: np.ndarray, k: int = 3) -> List[Tuple[int, int, int]]:
        """Extracts dominant colors using K-Means."""
        try:
            pixels = frame.reshape((-1, 3))
            pixels = np.float32(pixels)
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
            _, _, centers = cv2.kmeans(pixels, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
            return [(int(c[2]), int(c[1]), int(c[0])) for c in centers]
        except Exception:
            return [(127, 127, 127)]

    def _compute_clip_vector(self, text: str, shot_type: str, movement: str, motion: float, hiphop_affinity: float) -> np.ndarray:
        """Computes 9D semantic vector for clip."""
        vec = np.zeros(VECTOR_DIM, dtype=np.float32)
        t = text.lower()

        # Genre [0-4]
        for idx, (genre_key, keywords) in enumerate(GENRE_KEYWORDS.items()):
            if any(kw in t for kw in keywords):
                vec[idx] = 1.0

        if hiphop_affinity > 0.4:
            vec[0] = max(vec[0], hiphop_affinity)

        # Mood [5-7]
        for idx, (mood_key, keywords) in enumerate(MOOD_KEYWORDS.items()):
            if any(kw in t for kw in keywords):
                vec[5 + idx] = 1.0

        # Shot type influence
        if shot_type in ("close",):
            vec[6] = max(vec[6], 0.5)
        if shot_type in ("wide", "aerial", "drone"):
            vec[7] = max(vec[7], 0.5)

        # Movement influence
        if movement == "static":
            vec[7] = max(vec[7], 0.4)
        if movement in ("tracking", "handheld", "fast"):
            vec[6] = max(vec[6], 0.4)

        # Motion magnitude [8]
        vec[8] = float(motion)

        return vec

    def select_best_clip(
        self,
        min_duration: float,
        query_vector: np.ndarray,
        avoid_reuse: bool = True,
        cooldown: int = 5
    ) -> ClipMetadata:
        """Selects best matching clip using cosine similarity."""
        cooldown = min(cooldown, max(1, len(self.clips) // 2))

        candidates = [
            c for c in self.clips
            if c.duration >= min_duration
            and (not avoid_reuse or c.path not in self._recently_used[-cooldown:])
        ]

        if not candidates:
            self._recently_used = self._recently_used[cooldown // 2:]
            candidates = [c for c in self.clips if c.duration >= min_duration] or self.clips

        if len(candidates) == 1:
            chosen = candidates[0]
        else:
            q = query_vector.astype(np.float32)
            scores = []
            for c in candidates:
                if np.linalg.norm(q) < 1e-8 or np.linalg.norm(c.vector) < 1e-8:
                    scores.append(0.0)
                else:
                    scores.append(float(1.0 - cosine(q, c.vector)))
            chosen = candidates[int(np.argmax(scores))]

        self._recently_used.append(chosen.path)
        return chosen


# ============================================================================
# DIRECTOR'S CUTTER ENGINE
# ============================================================================
class DirectorsCutterEngine:
    """Intelligent video segmentation and clip selection."""

    def __init__(self, audio: AudioMetadata, clip_pool: VideoAnalysisLayer):
        self.audio = audio
        self.clip_pool = clip_pool

    def generate_segments(self, min_segment_duration: float = 0.5) -> List[Segment]:
        """Generates beat-aligned video segments."""
        logger.info("✂️  [CUTTER] Generating beat-aligned segments...")

        segments: List[Segment] = []
        beat_times = self.audio.beats
        rms_energy = self.audio.rms_energy
        sr = 22050  # librosa default

        for i, beat_time in enumerate(beat_times[:-1]):
            next_beat_time = beat_times[i + 1]
            duration = next_beat_time - beat_time

            if duration < min_segment_duration:
                continue

            # Get energy at this point
            frame_idx = min(int(beat_time * sr / 512), len(rms_energy) - 1)
            energy = float(rms_energy[frame_idx])

            # Determine effect mode
            if energy > 0.08:
                effect_mode = "WOBBLE-ZOOM"
            elif energy > 0.04:
                effect_mode = "NORMAL"
            else:
                effect_mode = "NORMAL"

            # Build query vector based on audio characteristics
            query_vector = self.audio.semantic_vector.copy()
            query_vector[6] += energy  # Boost intensity mood

            # Select clip
            clip = self.clip_pool.select_best_clip(
                min_duration=min_segment_duration,
                query_vector=query_vector,
                avoid_reuse=True
            )

            segments.append(Segment(
                start_time=beat_time,
                end_time=next_beat_time,
                duration=duration,
                clip=clip,
                effect_mode=effect_mode,
                energy_level=energy
            ))

        logger.info(f"🎬 Generated {len(segments)} segments")
        return segments

    def calculate_output_version(self, artist: str, title: str, output_dir: Path) -> str:
        """Generates versioned output filename."""
        base_name = f"Output_{artist}_{title}"
        i = 1
        while (output_dir / f"{base_name}_v{i:03d}.mp4").exists():
            i += 1
        return f"{base_name}_v{i:03d}.mp4"


# ============================================================================
# SVFX EFFECT PROCESSOR
# ============================================================================
class SVFXEffectProcessor:
    """Renders video segments with hardware acceleration."""

    def __init__(self, guard: ResourceGuard):
        self.guard = guard
        self._detect_hardware()

    def _detect_hardware(self) -> None:
        """Detects available GPU and optimization hints."""
        self.gpu_vendor = self._detect_gpu()
        self.hardware_hint = self._get_optimization_hint()

        logger.info(f"🎮 Hardware: {self.gpu_vendor}")
        logger.info(f"💡 {self.hardware_hint}")

    def _detect_gpu(self) -> str:
        """Detects GPU vendor and codec."""
        if HAS_NVML:
            try:
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                name = pynvml.nvmlDeviceGetName(handle)
                pynvml.nvmlShutdown()
                return f"NVIDIA: {name}"
            except Exception:
                pass

        try:
            result = subprocess.run(["rocm-smi", "--showid"], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                return "AMD ROCm detected"
        except Exception:
            pass

        if sys.platform == "darwin":
            return "Apple Silicon (VideoToolbox)"

        return "CPU (libx264)"

    def _get_optimization_hint(self) -> str:
        """Generates hardware-specific optimization hints."""
        if HAS_PSUTIL:
            ram_gb = psutil.virtual_memory().total / (1024**3)
            cpu_cores = os.cpu_count() or 1

            if ram_gb < 8:
                return f"⚠️  Low RAM ({ram_gb:.1f}GB): Use 720p resolution"
            elif ram_gb < 16:
                return f"ℹ️  Moderate RAM ({ram_gb:.1f}GB): Use 1080p resolution"
            else:
                return f"✅ Plenty of RAM ({ram_gb:.1f}GB): 4K capable"

        return "💻 Hardware detection unavailable"

    def render_segment(
        self,
        segment: Segment,
        temp_dir: Path,
        output_res: Tuple[int, int] = (1920, 1080)
    ) -> Path:
        """Renders a single segment with effects applied."""
        # Extract segment from clip
        clip_path = segment.clip.path
        out_path = temp_dir / f"segment_{hash(str(segment.start_time)):08x}.mp4"

        # Build FFmpeg command
        duration = segment.duration
        cmd = [
            "ffmpeg", "-y",
            "-i", str(clip_path),
            "-ss", "0",
            "-t", str(duration),
            "-vf", f"scale={output_res[0]}:{output_res[1]}:force_original_aspect_ratio=decrease,pad={output_res[0]}:{output_res[1]}:(ow-iw)/2:(oh-ih)/2",
        ]

        # Add effects based on mode
        if segment.effect_mode == "WOBBLE-ZOOM":
            cmd[-1] += ",zoompan=z='min(zoom+0.01,1.1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080"
        elif segment.effect_mode == "SCRATCH-STUTTER":
            cmd[-1] += ",fps=30,setpts='if(lt(t\\,0.1)\\,0\\,N/FRAME_RATE/TB)'"

        # Add audio
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            str(out_path)
        ])

        self.guard.run_safe_subprocess(cmd)
        return out_path


# ============================================================================
# VIRAL SCORING ENGINE
# ============================================================================
class ViralScoringEngine:
    """Analyzes output video for virality metrics."""

    def __init__(self, video_path: Path):
        self.video_path = Path(video_path)

    def analyze(self) -> Dict[str, Any]:
        """Analyzes video and computes viral score."""
        logger.info("🎯 Analyzing viral potential...")

        cap = cv2.VideoCapture(str(self.video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        face_cuts = 0
        motion_samples = []
        brightness_samples = []
        prev_gray: Optional[np.ndarray] = None

        step = max(1, frame_count // 100)

        for i in range(0, frame_count, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness_samples.append(float(np.mean(gray)))

            if prev_gray is not None:
                diff = cv2.absdiff(prev_gray, gray)
                motion_samples.append(float(np.mean(diff)))

            # Simple face detection (placeholder)
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
            if len(faces) > 0:
                face_cuts += 1

            prev_gray = gray

        cap.release()

        # Calculate metrics
        duration = frame_count / fps
        avg_cut_duration = (duration / (frame_count // step)) if frame_count > 0 else 1.0
        color_variance = float(np.std(brightness_samples)) if brightness_samples else 0.5
        motion_average = float(np.mean(motion_samples)) / 30.0 if motion_samples else 0.5
        face_ratio = face_cuts / (frame_count // step) if frame_count > 0 else 0.0

        # Compute viral score
        viral_score = (
            (face_ratio * 0.35) * 25 +
            min(1.0 - abs(1.2 - avg_cut_duration) / 1.0, 1.0) * 20 +
            (color_variance / 100.0) * 15 +
            motion_average * 20 +
            0.75 * 20
        )

        viral_score = min(100, max(0, viral_score))

        # Generate improvement tips
        tips = []
        if face_ratio < 0.25:
            tips.append(f"+15 Potential: Increase face cuts from {face_ratio*100:.0f}% to 30%")
        if color_variance < 30:
            tips.append(f"+12 Potential: Boost color variance with more scene variety")
        if motion_average < 0.5:
            tips.append(f"+10 Potential: Increase clip motion and dynamic scenes")

        return {
            "viral_score": int(viral_score),
            "metrics": {
                "face_cuts": round(face_ratio, 2),
                "avg_cut_duration": round(avg_cut_duration, 2),
                "color_variance": round(color_variance, 2),
                "motion_average": round(motion_average, 2),
            },
            "tips": tips
        }


# ============================================================================
# MAIN CINEMATIC DIRECTOR
# ============================================================================
class CinematicDirector:
    """Main orchestration engine for music video generation."""

    def __init__(
        self,
        audio_path: Path,
        clips_dir: Path,
        output_dir: Path,
        max_duration: Optional[float] = None
    ):
        self.audio_path = Path(audio_path)
        self.clips_dir = Path(clips_dir)
        self.output_dir = Path(output_dir)
        self.max_duration = max_duration
        self.guard = ResourceGuard()
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> str:
        """Executes complete music video generation pipeline."""
        logger.info("=" * 70)
        logger.info("🎬 WE.ED.IT v4.0 - Cinematic Music Video Director")
        logger.info("=" * 70)
        logger.info(f"📁 Audio: {self.audio_path}")
        logger.info(f"📁 Clips: {self.clips_dir}")
        logger.info(f"📁 Output: {self.output_dir}")

        try:
            # Stage 1: Audio Analysis
            audio_layer = AudioAnalysisLayer(self.audio_path)
            audio = audio_layer.analyze()

            # Stage 2: Video Analysis
            video_layer = VideoAnalysisLayer(self.clips_dir)
            if not video_layer.clips:
                raise RuntimeError("❌ No video clips found in pool directory")

            # Stage 3: Segmentation
            cutter = DirectorsCutterEngine(audio, video_layer)
            segments = cutter.generate_segments()

            if not segments:
                raise RuntimeError("❌ No segments generated. Check audio file.")

            # Limit duration if specified
            if self.max_duration:
                total_duration = sum(s.duration for s in segments)
                if total_duration > self.max_duration:
                    segments = segments[:int(len(segments) * self.max_duration / total_duration)]

            # Stage 4: Rendering
            logger.info(f"🧬 Rendering {len(segments)} segments with vector matching...")
            svfx = SVFXEffectProcessor(self.guard)
            segment_files = []

            for idx, segment in enumerate(segments, 1):
                logger.info(
                    f"  🎬 [{idx:03d}/{len(segments)}] {segment.start_time:.2f}s → "
                    f"{segment.end_time:.2f}s | FX: {segment.effect_mode} | "
                    f"Clip: {segment.clip.path.name}"
                )
                seg_file = svfx.render_segment(segment, self.temp_dir)
                segment_files.append(seg_file)

            # Stage 5: Assembly
            output_file = self._assemble_video(segment_files, audio)

            # Stage 6: Viral Scoring
            scorer = ViralScoringEngine(output_file)
            viral_data = scorer.analyze()

            # Stage 7: Output
            self._display_results(audio, viral_data, output_file)

            return str(output_file)

        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}")
            raise
        finally:
            # Cleanup
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.guard.terminate_all()

    def _assemble_video(self, segment_files: List[Path], audio: AudioMetadata) -> Path:
        """Assembles segments into final video with audio."""
        logger.info("🎞️  Assembling final video...")

        concat_file = self.temp_dir / "concat.txt"
        with open(concat_file, "w") as f:
            for seg_file in segment_files:
                f.write(f"file '{seg_file.absolute()}'\n")

        cutter = DirectorsCutterEngine(audio, None)
        output_name = cutter.calculate_output_version(audio.artist, audio.title, self.output_dir)
        output_file = self.output_dir / output_name

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c:v", "copy",
            "-i", str(self.audio_path),
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_file)
        ]

        self.guard.run_safe_subprocess(cmd)
        return output_file

    def _display_results(self, audio: AudioMetadata, viral_data: Dict[str, Any], output_file: Path) -> None:
        """Displays final results and statistics."""
        logger.info("=" * 70)
        logger.info(f"🎥 VIRAL SCORE: {viral_data['viral_score']}/100")
        logger.info("")
        logger.info("💡 Improvement Tips:")
        for tip in viral_data['tips'][:3]:
            logger.info(f"   {tip}")
        logger.info("")
        logger.info("📊 Metrics:")
        for key, value in viral_data['metrics'].items():
            logger.info(f"   {key}: {value}")
        logger.info("")
        logger.info(f"⚡ Musikvideo erfolgreich exportiert:")
        logger.info(f"   📁 {output_file}")
        logger.info("")
        logger.info("🎬 Musik dirigiert. KI schneidet. Du kreierst.")
        logger.info("=" * 70)


# ============================================================================
# CLI INTERFACE
# ============================================================================
def main():
    """Command-line interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description="WE.ED.IT v4.0 - AI-Driven Cinematic Music Video Director"
    )
    parser.add_argument("--song", required=True, help="Path to MP3 audio file")
    parser.add_argument("--clips_dir", required=True, help="Path to video clips directory")
    parser.add_argument("--output_dir", default="./output", help="Output directory")
    parser.add_argument("--max_duration", type=float, help="Maximum video duration in seconds")

    args = parser.parse_args()

    director = CinematicDirector(
        audio_path=args.song,
        clips_dir=args.clips_dir,
        output_dir=args.output_dir,
        max_duration=args.max_duration
    )

    director.run()


if __name__ == "__main__":
    main()
