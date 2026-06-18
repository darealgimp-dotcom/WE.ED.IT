#!/usr/bin/env python3
# coding: utf-8
"""
WE.ED.IT ULTIMATE + DATABASE - Complete Batch Processing System
================================================================
AI-driven music video generation with database integration.
Features: 9D vector space, batch processing, resume capability, atomic saves.

Setup:
  - Video Clips: D:\Oidasheim\NFOs\teST\9zu16
  - Audio Files: D:\Oidasheim\NFOs\teST\snd
  - Output: ./done
  - Database: weedit_db.json (6241+ entries)

Usage:
  python weedit_ultimate_db.py --batch              # Process all
  python weedit_ultimate_db.py --batch --resume     # Continue
  python weedit_ultimate_db.py --batch --no-resume  # Restart
  python weedit_ultimate_db.py --snd PATH           # Single file

Vision: "Musik dirigiert. KI schneidet. Du kreierst."
"""

from __future__ import annotations

import os
import sys
import json
import signal
import argparse
import logging
import subprocess
import hashlib
import threading
import shutil
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import tempfile

import numpy as np

# Core imports with fallback
try:
    import cv2
    import librosa
    import eyed3
    from sklearn.decomposition import PCA
    from scipy.spatial.distance import cosine
    import pandas as pd
    HAS_DEPS = True
except ImportError as e:
    print(f"❌ Missing dependency: {e}")
    print("📦 Install: pip install -r requirements.txt")
    sys.exit(1)

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

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class DBConfig:
    """Database and pipeline configuration."""
    vidz_dir: str = r"D:\Oidasheim\NFOs\teST\9zu16"
    snd_dir: str = r"D:\Oidasheim\NFOs\teST\snd"
    done_dir: str = "./done"
    db_path: str = "weedit_db.json"
    batch_size: int = 10
    max_processes: int = 4
    min_free_ram_mb: int = 1524
    min_free_vram_mb: int = 512
    max_analysis_frames: int = 15
    log_level: str = "INFO"
    log_file: str = "weedit_batch.log"

# ============================================================================
# CONSTANTS (9D Vector Space)
# ============================================================================

VECTOR_DIM = 9
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".aac"}

GENRE_KEYWORDS = {
    "genre_hiphop": ["hip", "hop", "hiphop", "rap", "trap", "drill", "grime", "street", "urban"],
    "genre_pop": ["pop", "dance", "edm", "synth", "chart", "bright", "colorful"],
    "genre_electronic": ["electronic", "techno", "house", "trance", "ambient", "abstract", "drone"],
    "genre_rock": ["rock", "metal", "punk", "grunge", "indie", "wide", "dramatic"],
    "genre_soul": ["soul", "rnb", "r&b", "funk", "gospel", "blues", "jazz", "intimate"],
}

MOOD_KEYWORDS = {
    "mood_happy": ["happy", "joy", "euphoric", "upbeat", "positive", "fun", "bright"],
    "mood_intense": ["intense", "dark", "aggressive", "angry", "hard", "fierce", "energetic", "action"],
    "mood_calm": ["calm", "chill", "slow", "soft", "mellow", "smooth", "relax", "static"],
}

SHOT_TAGS = ["wide", "close", "medium", "drone", "pov", "extreme", "aerial"]
MOTION_TAGS = ["pan", "zoom", "orbit", "static", "tracking", "tilt", "dolly", "handheld", "fast", "slow"]
EMOTION_TAGS = list(MOOD_KEYWORDS["mood_happy"]) + list(MOOD_KEYWORDS["mood_intense"]) + list(MOOD_KEYWORDS["mood_calm"])

HIPHOP_COLOR_RANGES = {
    "gold": ([20, 100, 100], [35, 255, 255]),
    "neon": ([80, 150, 150], [140, 255, 255]),
    "red_accent": ([0, 120, 120], [10, 255, 255]),
}

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(config: DBConfig) -> logging.Logger:
    """Configure logging with file and console handlers."""
    logger = logging.getLogger("WE.ED.IT")
    level = getattr(logging, config.log_level.upper(), logging.INFO)
    logger.setLevel(level)
    
    if logger.handlers:
        logger.handlers.clear()
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # File handler
    fh = logging.FileHandler(config.log_file, encoding='utf-8')
    fh.setLevel(level)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    return logger

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class ClipDBEntry:
    """Video clip metadata with semantic vectors."""
    path: str
    name: str
    duration: float
    shot_type: str
    movement: str
    emotion_tags: List[str]
    brightness: float
    motion: float
    hiphop_affinity: float
    dominant_colors: List[List[int]]
    vector: List[float]
    hash: str
    last_used: Optional[str] = None
    use_count: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> ClipDBEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class AudioDBEntry:
    """Audio analysis results."""
    path: str
    title: str
    artist: str
    genre: str
    bpm: float
    duration: float
    beat_times: List[float]
    song_structure: List[Dict]
    drop_timestamps: List[float]
    scratch_zones: List[List[float]]
    rms_energy: List[float]
    semantic_vector: List[float]
    analyzed_at: str
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> AudioDBEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class ProjectDBEntry:
    """Project metadata."""
    audio_path: str
    output_path: str
    viral_score: int
    metrics: Dict[str, float]
    tips: List[str]
    created_at: str
    segments: int
    duration: float
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> ProjectDBEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass
class WEEDITDatabase:
    """Central database container."""
    clips: Dict[str, ClipDBEntry] = field(default_factory=dict)
    audio: Dict[str, AudioDBEntry] = field(default_factory=dict)
    projects: Dict[str, ProjectDBEntry] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'clips': {k: v.to_dict() for k, v in self.clips.items()},
            'audio': {k: v.to_dict() for k, v in self.audio.items()},
            'projects': {k: v.to_dict() for k, v in self.projects.items()},
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> WEEDITDatabase:
        db = cls()
        db.clips = {k: ClipDBEntry.from_dict(v) for k, v in data.get('clips', {}).items()}
        db.audio = {k: AudioDBEntry.from_dict(v) for k, v in data.get('audio', {}).items()}
        db.projects = {k: ProjectDBEntry.from_dict(v) for k, v in data.get('projects', {}).items()}
        db.metadata = data.get('metadata', {})
        return db

# ============================================================================
# DATABASE MANAGER (Atomic Saves)
# ============================================================================

class DatabaseManager:
    """Manages database with atomic saves and interrupt handling."""
    
    def __init__(self, config: DBConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.db = WEEDITDatabase()
        self.temp_db_path = f"{config.db_path}.tmp"
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_interrupt)
        signal.signal(signal.SIGTERM, self._handle_interrupt)
        
        self.load()
    
    def _handle_interrupt(self, signum, frame):
        self.logger.info(f"\n[!] Prozess durch Signal {signum} unterbrochen")
        self.logger.info("[*] Sichere Datenbank...")
        self.save(backup=True)
        self.logger.info(f"✅ {len(self.db.clips)} Clips in {self.config.db_path} gesichert")
        self.logger.info("[+] Fortschritt eingefroren. Beendet.")
        sys.exit(0)
    
    def load(self) -> bool:
        """Load database from JSON file."""
        db_path = Path(self.config.db_path)
        if db_path.exists():
            try:
                with open(db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.db = WEEDITDatabase.from_dict(data)
                self.logger.info(f"✅ [DB] {len(self.db.clips)} Clips geladen")
                return True
            except Exception as e:
                self.logger.error(f"❌ DB-Ladefehler: {e}")
        return False
    
    def save(self, backup: bool = False):
        """Save database atomically."""
        path = self.temp_db_path if backup else self.config.db_path
        try:
            temp_path = f"{path}.tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.db.to_dict(), f, indent=2, ensure_ascii=False)
            if Path(temp_path).exists():
                os.replace(temp_path, path)
            self.logger.info(f"✅ [DB] Gesichert in {path}")
        except Exception as e:
            self.logger.error(f"❌ Speicherfehler: {e}")
    
    def add_clip(self, entry: ClipDBEntry):
        """Add clip to database."""
        self.db.clips[entry.hash] = entry
        self.db.metadata['last_clip_update'] = datetime.now().isoformat()
    
    def add_audio(self, entry: AudioDBEntry):
        """Add audio to database."""
        self.db.audio[entry.path] = entry
        self.db.metadata['last_audio_update'] = datetime.now().isoformat()
    
    def add_project(self, entry: ProjectDBEntry):
        """Add project to database."""
        self.db.projects[entry.output_path] = entry
        self.db.metadata['last_project'] = entry.output_path
        self.db.metadata['total_projects'] = len(self.db.projects)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        return {
            'total_clips': len(self.db.clips),
            'total_audio': len(self.db.audio),
            'total_projects': len(self.db.projects),
            'last_updated': self.db.metadata.get('last_clip_update', 'Nie')
        }

# ============================================================================
# CLIP POOL WITH DATABASE
# ============================================================================

class ClipPoolDB:
    """Video clip pool with 9D vector space."""
    
    def __init__(self, config: DBConfig, db_manager: DatabaseManager, logger: logging.Logger):
        self.config = config
        self.db = db_manager
        self.logger = logger
        self.clips: List[ClipDBEntry] = list(db_manager.db.clips.values())
        self._recently_used: List[str] = []
        self._scan_for_new_clips()
    
    def _scan_for_new_clips(self):
        """Scan for new video files not in database."""
        vidz_path = Path(self.config.vidz_dir)
        if not vidz_path.exists():
            self.logger.warning(f"⚠️  vidz nicht gefunden: {vidz_path}")
            return
        
        video_files = []
        for ext in VIDEO_EXTS:
            video_files.extend(vidz_path.glob(f"**/*{ext}"))
        
        new_count = 0
        for path in video_files:
            file_hash = self._compute_hash(path)
            if not any(c.hash == file_hash for c in self.clips):
                try:
                    entry = self._analyze_clip(path)
                    self.db.add_clip(entry)
                    self.clips.append(entry)
                    new_count += 1
                except Exception as e:
                    self.logger.debug(f"Fehler beim Analysieren von {path}: {e}")
        
        if new_count > 0:
            self.logger.info(f"📈 {new_count} neue Clips hinzugefügt")
            self.db.save()
    
    def _compute_hash(self, path: Path) -> str:
        """Compute file hash for deduplication."""
        stat = path.stat()
        return hashlib.md5(f"{path}{stat.st_mtime}{stat.st_size}".encode()).hexdigest()
    
    def _analyze_clip(self, path: Path) -> ClipDBEntry:
        """Analyze a video clip."""
        path = path.resolve()
        stem = path.stem.lower()
        
        # Parse filename tags
        import re
        words = re.split(r"[\W_]+", stem)
        shot_type = next((w for w in words if w in SHOT_TAGS), "medium")
        movement = next((w for w in words if w in MOTION_TAGS), "static")
        emotion_tags = [w for w in words if w in EMOTION_TAGS]
        
        # Parse NFO file if exists
        nfo_text = ""
        nfo_path = path.with_suffix(".nfo")
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
        brightness, motion, duration, hiphop_affinity, colors = self._evaluate_visual(path)
        
        # Compute 9D vector
        all_text = f"{stem} {nfo_text} {' '.join(emotion_tags)}"
        vector = self._compute_9d_vector(all_text, shot_type, movement, motion, hiphop_affinity)
        
        file_hash = self._compute_hash(path)
        return ClipDBEntry(
            path=str(path), name=path.name, duration=duration,
            shot_type=shot_type, movement=movement, emotion_tags=emotion_tags,
            brightness=brightness, motion=motion, hiphop_affinity=hiphop_affinity,
            dominant_colors=[list(c) for c in colors],
            vector=vector.tolist(), hash=file_hash
        )
    
    def _evaluate_visual(self, path: Path) -> Tuple[float, float, float, float, List]:
        """Extract visual properties from video."""
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return 127.0, 0.0, 0.0, 0.0, []
        
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total / fps if total > 0 else 0.0
        
        if total <= 0:
            cap.release()
            return 127.0, 0.0, duration, 0.0, []
        
        step = max(1, total // self.config.max_analysis_frames)
        brightness_samples = []
        motion_samples = []
        hiphop_scores = []
        prev_gray = None
        sample_frame = None
        
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
        
        colors = self._extract_palette_kmeans(sample_frame) if sample_frame is not None else []
        
        brightness = float(np.mean(brightness_samples)) if brightness_samples else 127.0
        raw_motion = float(np.mean(motion_samples)) if motion_samples else 0.0
        norm_motion = float(np.clip(raw_motion / 30.0, 0.0, 1.0))
        hiphop_affinity = float(np.mean(hiphop_scores)) if hiphop_scores else 0.0
        
        return brightness, norm_motion, duration, hiphop_affinity, colors
    
    def _calculate_hiphop_score(self, frame: np.ndarray, hsv: np.ndarray, gray: np.ndarray) -> float:
        """Calculate hip-hop visual affinity score."""
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
        
        # Contrast
        contrast = np.std(gray)
        if contrast > 60.0:
            score += 0.15
        
        # Edge density
        edges = cv2.Canny(gray, 50, 150)
        edge_ratio = np.sum(edges > 0) / pixel_count
        if 0.08 < edge_ratio < 0.25:
            score += 0.15
        
        return min(score, 1.0)
    
    def _extract_palette_kmeans(self, frame: np.ndarray, k: int = 3) -> List:
        """Extract dominant colors using K-Means."""
        try:
            pixels = frame.reshape((-1, 3)).astype(np.float32)
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
            _, _, centers = cv2.kmeans(pixels, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
            return [(int(c[2]), int(c[1]), int(c[0])) for c in centers]
        except Exception:
            return [(127, 127, 127)]
    
    def _compute_9d_vector(self, text: str, shot_type: str, movement: str, motion: float, hiphop_affinity: float) -> np.ndarray:
        """Compute 9D semantic vector."""
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
        if shot_type == "close":
            vec[6] = max(vec[6], 0.5)
        if shot_type in ["wide", "aerial", "drone"]:
            vec[7] = max(vec[7], 0.5)
        
        # Movement influence
        if movement == "static":
            vec[7] = max(vec[7], 0.4)
        if movement in ["tracking", "handheld", "fast"]:
            vec[6] = max(vec[6], 0.4)
        
        # Motion magnitude [8]
        vec[8] = float(motion)
        
        return vec
    
    def select_best_clip(self, min_duration: float, query_vector: np.ndarray, avoid_reuse: bool = True, cooldown: int = 5) -> Optional[ClipDBEntry]:
        """Select best matching clip using cosine similarity."""
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
                c_vec = np.array(c.vector, dtype=np.float32)
                if np.linalg.norm(q) > 1e-8 and np.linalg.norm(c_vec) > 1e-8:
                    scores.append(float(1.0 - cosine(q, c_vec)))
                else:
                    scores.append(0.0)
            chosen = candidates[int(np.argmax(scores))]
        
        self._recently_used.append(chosen.path)
        return chosen

# ============================================================================
# AUDIO ANALYZER
# ============================================================================

class AudioAnalyzer:
    """Audio analysis with BPM, structure, and semantic vectors."""
    
    def __init__(self, config: DBConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
    
    def analyze(self, audio_path: str) -> AudioDBEntry:
        """Analyze audio file."""
        audio_path = str(Path(audio_path).resolve())
        self.logger.info(f"🎵 Analysiere: {Path(audio_path).name}")
        
        # Extract ID3 tags
        tags = self._extract_id3_tags(audio_path)
        
        # Load audio
        y, sr = librosa.load(audio_path, sr=None)
        duration = len(y) / sr
        
        # Detect BPM and beats
        bpm, beat_times = self._detect_bpm_and_beats(y, sr)
        
        # Compute RMS energy
        rms_energy = self._compute_rms_energy(y, sr)
        
        # Detect song structure
        song_structure, drop_timestamps, scratch_zones = self._detect_song_structure(y, sr, beat_times, rms_energy)
        
        # Semantic vector
        semantic_vector = self._compute_semantic_vector(tags, bpm, rms_energy)
        
        return AudioDBEntry(
            path=audio_path,
            title=tags.get('title', Path(audio_path).stem),
            artist=tags.get('artist', 'Unbekannt'),
            genre=tags.get('genre', 'Unbekannt'),
            bpm=bpm,
            duration=duration,
            beat_times=beat_times,
            song_structure=song_structure,
            drop_timestamps=drop_timestamps,
            scratch_zones=[list(z) for z in scratch_zones],
            rms_energy=rms_energy,
            semantic_vector=semantic_vector,
            analyzed_at=datetime.now().isoformat()
        )
    
    def _extract_id3_tags(self, audio_path: str) -> Dict:
        """Extract ID3 metadata from MP3."""
        try:
            audiofile = eyed3.load(audio_path)
            if audiofile.tag:
                return {
                    'title': audiofile.tag.title or '',
                    'artist': audiofile.tag.artist or 'Unbekannt',
                    'album': audiofile.tag.album or '',
                    'genre': audiofile.tag.genre.name if audiofile.tag.genre else 'Unbekannt',
                    'bpm': audiofile.tag.bpm or 0
                }
        except Exception:
            pass
        
        return {'title': '', 'artist': 'Unbekannt', 'genre': 'Unbekannt', 'bpm': 0}
    
    def _detect_bpm_and_beats(self, y: np.ndarray, sr: int) -> Tuple[float, List[float]]:
        """Detect BPM and beat times."""
        try:
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
            return float(tempo), beat_times
        except Exception:
            # Fallback
            bpm = 120.0
            interval = 60.0 / bpm
            duration = len(y) / sr
            return bpm, [i * interval for i in range(int(duration / interval) + 1)]
    
    def _compute_rms_energy(self, y: np.ndarray, sr: int) -> List[float]:
        """Compute RMS energy per frame."""
        rms = []
        for i in range(0, len(y), 2048):
            frame = y[i:i+2048]
            if len(frame) > 0:
                rms.append(float(np.sqrt(np.mean(frame**2))))
        return rms
    
    def _detect_song_structure(self, y: np.ndarray, sr: int, beat_times: List[float], rms_energy: List[float]) -> Tuple[List[Dict], List[float], List[Tuple]]:
        """Detect song structure sections."""
        structure = []
        drop_timestamps = []
        scratch_zones = []
        
        if not beat_times:
            return structure, drop_timestamps, scratch_zones
        
        # Normalize energy
        rms_norm = [r / max(rms_energy + [0.001]) for r in rms_energy]
        
        # Divide into 6 sections
        beats_per_section = max(1, len(beat_times) // 6)
        section_names = ['intro', 'verse', 'chorus', 'verse', 'drop', 'outro']
        
        for i, name in enumerate(section_names[:min(6, len(beat_times))]):
            s_idx = i * beats_per_section
            e_idx = min((i + 1) * beats_per_section, len(beat_times))
            
            if s_idx >= len(beat_times):
                break
            
            section = {
                'label': name,
                'start': float(beat_times[s_idx]),
                'end': float(beat_times[e_idx - 1] if e_idx > 0 else beat_times[-1]),
                'energy': float(np.mean(rms_norm[s_idx:e_idx]) if e_idx > s_idx else 0)
            }
            structure.append(section)
            
            # Mark drops
            if name == 'drop' or section['energy'] > 0.15:
                drop_timestamps.append(section['start'])
        
        # Detect scratch zones (sharp energy changes)
        for i in range(1, len(rms_norm) - 1):
            if abs(rms_norm[i] - rms_norm[i-1]) > 0.1:
                scratch_zones.append((
                    float(beat_times[i-1] if i-1 < len(beat_times) else 0),
                    float(beat_times[i] if i < len(beat_times) else beat_times[-1])
                ))
        
        return structure, drop_timestamps, scratch_zones
    
    def _compute_semantic_vector(self, tags: Dict, bpm: float, rms_energy: List[float]) -> List[float]:
        """Compute 9D semantic vector from audio."""
        vector = [0.0] * 9
        
        # Genre mapping
        genre = tags.get('genre', 'Unknown').lower()
        genre_map = {
            'hip-hop': 0, 'hip hop': 0, 'rap': 0,
            'pop': 1, 'electronic': 2, 'edm': 2, 'techno': 2, 'house': 2,
            'rock': 3, 'soul': 4, 'r&b': 4, 'rb': 4
        }
        vector[genre_map.get(genre, 0)] = 1.0
        
        # Energy profiling
        avg_energy = np.mean(rms_energy) if rms_energy else 0
        vector[5] = min(1.0, bpm / 140.0) * 0.5 + min(1.0, avg_energy * 10) * 0.5
        vector[6] = min(1.0, bpm / 140.0) * 0.5 + min(1.0, avg_energy * 10) * 0.5
        vector[7] = (1.0 - min(1.0, bpm / 100.0)) * 0.5 + (1.0 - min(1.0, avg_energy * 10)) * 0.5
        vector[8] = min(1.0, bpm / 180.0)
        
        return vector

# ============================================================================
# BATCH PROCESSOR
# ============================================================================

class BatchProcessor:
    """Main batch processing engine."""
    
    STORYBOARD = [
        {"shot_scale": "wide", "movement": "static", "theme": "cityscape"},
        {"shot_scale": "close", "movement": "tracking", "theme": "performance"},
        {"shot_scale": "medium", "movement": "fast", "theme": "action"},
        {"shot_scale": "drone", "movement": "orbit", "theme": "aerial"},
    ]
    
    def __init__(self, config: DBConfig, db_manager: DatabaseManager, clip_pool: ClipPoolDB, logger: logging.Logger):
        self.config = config
        self.db = db_manager
        self.clip_pool = clip_pool
        self.logger = logger
        self.audio_analyzer = AudioAnalyzer(config, logger)
        self._success = 0
        self._failed = 0
        self._failures = []
    
    def run(self, resume: bool = True) -> bool:
        """Execute batch processing."""
        self.logger.info("=" * 70)
        self.logger.info("🎬 WE.ED.IT ULTIMATE - BATCH PROZESSOR")
        self.logger.info("🎵 Musik dirigiert. KI schneidet. Du kreierst.")
        self.logger.info("=" * 70)
        
        # Find audio files
        snd_path = Path(self.config.snd_dir)
        if not snd_path.exists():
            self.logger.error(f"❌ snd nicht gefunden: {snd_path}")
            return False
        
        audio_files = list(snd_path.glob("**/*.mp3")) + list(snd_path.glob("**/*.wav"))
        self.logger.info(f"🎵 Gefunden: {len(audio_files)} Audiodateien")
        
        # Filter if resuming
        if resume:
            processed = set(self.db.db.audio.keys())
            audio_files = [f for f in audio_files if str(f) not in processed]
            self.logger.info(f"📋 {len(audio_files)} übrig (Fortsetzungsmodus)")
        
        if not audio_files:
            self.logger.info("✅ Alle Dateien bereits verarbeitet!")
            return True
        
        # Process each file
        total = len(audio_files)
        for i, audio_path in enumerate(audio_files):
            try:
                self.logger.info(f"\n🎯 [{i+1}/{total}]: {audio_path.name}")
                audio_entry = self.audio_analyzer.analyze(str(audio_path))
                self.db.add_audio(audio_entry)
                
                output = self._create_video(audio_entry, audio_path)
                if output:
                    self.db.add_project(ProjectDBEntry(
                        audio_path=audio_entry.path,
                        output_path=output,
                        viral_score=0,
                        metrics={},
                        tips=[],
                        created_at=datetime.now().isoformat(),
                        segments=0,
                        duration=audio_entry.duration
                    ))
                    self._success += 1
                    self.logger.info(f"✅ Erfolg: {output}")
                else:
                    self._failed += 1
                    self._failures.append(str(audio_path))
                
                if (i + 1) % self.config.batch_size == 0:
                    self.db.save()
            
            except KeyboardInterrupt:
                self.logger.warning("\n[!] Batchvorgang unterbrochen")
                self._handle_interrupt()
                return False
            except Exception as e:
                self._failed += 1
                self._failures.append(str(audio_path))
                self.logger.error(f"❌ Fehler: {e}")
        
        self.db.save()
        self._print_summary()
        return True
    
    def _create_video(self, audio_entry: AudioDBEntry, audio_path: Path) -> Optional[str]:
        """Create music video from audio."""
        self.logger.info(f"   🎬 Erstelle Video: {audio_entry.title}")
        try:
            segments = self._create_timeline(audio_entry)
            if not segments:
                return None
            return self._render_video(segments, str(audio_path))
        except Exception as e:
            self.logger.error(f"   ❌ Fehler: {e}")
            return None
    
    def _create_timeline(self, audio_entry: AudioDBEntry) -> List[Dict]:
        """Create video timeline with beat-aligned segments."""
        segments = []
        
        if not audio_entry.beat_times:
            return segments
        
        for i, beat_time in enumerate(audio_entry.beat_times):
            end_time = audio_entry.beat_times[i + 1] if i + 1 < len(audio_entry.beat_times) else audio_entry.duration
            duration = end_time - beat_time
            
            if duration <= 0.5:
                continue
            
            section = self._get_section(audio_entry, beat_time)
            energy = self._get_energy(audio_entry, beat_time)
            query_vec = self._create_query_vec(audio_entry, beat_time, section)
            
            clip = self.clip_pool.select_best_clip(duration, query_vec)
            if not clip:
                continue
            
            effect = self._determine_effect(audio_entry, beat_time)
            segments.append({
                'start_time': beat_time,
                'end_time': end_time,
                'clip': clip,
                'effect': effect,
                'energy': energy
            })
        
        self.logger.info(f"   ✅ {len(segments)} Segmente")
        return segments
    
    def _get_section(self, audio_entry: AudioDBEntry, time: float) -> str:
        """Get song section for timestamp."""
        for s in audio_entry.song_structure:
            if s['start'] <= time <= s['end']:
                return s['label']
        return 'unknown'
    
    def _get_energy(self, audio_entry: AudioDBEntry, time: float) -> float:
        """Get energy level at timestamp."""
        if not audio_entry.rms_energy:
            return 0.0
        idx = int(time * audio_entry.bpm / 60)
        return audio_entry.rms_energy[idx] if idx < len(audio_entry.rms_energy) else 0.0
    
    def _create_query_vec(self, audio_entry: AudioDBEntry, time: float, section: str) -> np.ndarray:
        """Create query vector for clip selection."""
        vec = np.zeros(9, dtype=np.float32)
        
        # Genre
        genre = audio_entry.genre.lower()
        gmap = {
            'hip-hop': 0, 'hip hop': 0, 'rap': 0,
            'pop': 1, 'electronic': 2, 'edm': 2, 'techno': 2, 'house': 2,
            'rock': 3, 'soul': 4, 'r&b': 4, 'rb': 4
        }
        vec[gmap.get(genre, 0)] = 1.0
        
        # Section-based mood
        energy = self._get_energy(audio_entry, time)
        if section in ['drop', 'chorus'] or energy > 0.15:
            vec[6] = 1.0
        elif section in ['intro', 'outro']:
            vec[7] = 1.0
        else:
            vec[5] = 0.7
            vec[6] = 0.3
        
        vec[8] = min(1.0, energy * 10)
        return vec
    
    def _determine_effect(self, audio_entry: AudioDBEntry, time: float) -> str:
        """Determine effect mode for segment."""
        for zone in audio_entry.scratch_zones:
            if zone[0] <= time <= zone[1]:
                return 'SCRATCH-STUTTER'
        
        if time in audio_entry.drop_timestamps:
            return 'WOBBLE-ZOOM'
        
        if self._get_energy(audio_entry, time) > 0.15:
            return 'WOBBLE-ZOOM'
        
        return 'NORMAL'
    
    def _render_video(self, segments: List[Dict], audio_path: str) -> str:
        """Render final video with FFmpeg."""
        temp_dir = Path(self.config.done_dir) / "temp_segments"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        seg_files = []
        for i, seg in enumerate(segments):
            try:
                out = temp_dir / f"seg_{i:03d}.mp4"
                self._apply_effect(seg['clip'].path, str(out), seg['effect'])
                seg_files.append(str(out))
            except Exception as e:
                self.logger.error(f"Segment {i}: {e}")
        
        if not seg_files:
            return ""
        
        output = Path(self.config.done_dir) / f"{Path(audio_path).stem}_WEEDIT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        output.parent.mkdir(parents=True, exist_ok=True)
        
        list_file = temp_dir / "list.txt"
        with open(list_file, 'w') as f:
            for seg_file in seg_files:
                f.write(f"file '{seg_file}'\n")
        
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'error',
            '-f', 'concat', '-safe', '0',
            '-i', str(list_file),
            '-i', audio_path,
            '-c:v', 'libx264', '-preset', 'fast',
            '-c:a', 'aac', '-b:a', '192k',
            '-shortest',
            str(output)
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=True)
            
            # Cleanup
            for f in seg_files:
                Path(f).unlink(missing_ok=True)
            list_file.unlink(missing_ok=True)
            
            return str(output)
        except Exception as e:
            self.logger.error(f"   ❌ Render-Fehler: {e}")
            return ""
    
    def _apply_effect(self, input_path: str, output_path: str, effect: str):
        """Apply video effects with FFmpeg."""
        scale_filter = "scale=1920:1080:force_original_aspect_ratio=decrease,setsar=1"
        
        if effect == 'NORMAL':
            filter_complex = scale_filter
        elif effect == 'WOBBLE-ZOOM':
            filter_complex = f"{scale_filter},zoompan=z='min(zoom+0.015,1.15)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',fps=30"
        elif effect == 'SCRATCH-STUTTER':
            filter_complex = f"{scale_filter},tmix=frames=3:weights='1|1|1',hue='h=0:0.5*sin(2*PI*t/2)'"
        else:
            filter_complex = scale_filter
        
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'error',
            '-i', input_path,
            '-vf', filter_complex,
            '-c:v', 'libx264', '-preset', 'fast',
            '-an',
            output_path
        ]
        
        subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True)
    
    def _handle_interrupt(self):
        """Handle graceful shutdown."""
        self.logger.info("[+] Fortschritt eingefroren. Beendet.")
        self.db.save(backup=True)
        self._print_summary()
    
    def _print_summary(self):
        """Print processing summary."""
        self.logger.info("\n" + "=" * 70)
        self.logger.info("📊 ZUSAMMENFASSUNG")
        self.logger.info("=" * 70)
        self.logger.info(f"✅ Erfolgreich: {self._success}")
        self.logger.info(f"❌ Fehlgeschlagen: {self._failed}")
        
        if self._failures:
            self.logger.info("\n⚠️  Fehlgeschlagene Dateien:")
            for f in self._failures[:5]:
                self.logger.info(f"   - {f}")
            if len(self._failures) > 5:
                self.logger.info(f"   ... und {len(self._failures) - 5} weitere")
        
        stats = self.db.get_stats()
        self.logger.info(f"\n📁 Datenbank: {stats['total_clips']} Clips, {stats['total_audio']} Audio, {stats['total_projects']} Projekte")
        self.logger.info("=" * 70)

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='WE.ED.IT ULTIMATE + DATABASE',
        epilog="Beispiele:\n  python weedit_ultimate_db.py --batch\n  python weedit_ultimate_db.py --resume"
    )
    parser.add_argument('--vidz', default=None, help='Video-Clips-Verzeichnis')
    parser.add_argument('--snd', default=None, help='Audio-Dateien-Verzeichnis')
    parser.add_argument('--done', default=None, help='Ausgabeverzeichnis')
    parser.add_argument('--db', default='weedit_db.json', help='Datenbankdatei')
    parser.add_argument('--batch', action='store_true', help='Batch-Verarbeitung')
    parser.add_argument('--resume', action='store_true', default=True, help='Fortsetzen')
    parser.add_argument('--no-resume', action='store_true', help='Neu beginnen')
    parser.add_argument('--batch-size', type=int, default=10, help='Speicher alle N Dateien')
    parser.add_argument('--max-processes', type=int, default=4, help='Max FFmpeg-Prozesse')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    parser.add_argument('--version', action='store_true', help='Version')
    
    args = parser.parse_args()
    
    if args.no_resume:
        args.resume = False
    
    if args.version:
        print("WE.ED.IT ULTIMATE + DATABASE v1.0")
        print("Batch-System für D:\\Oidasheim\\NFOs\\teST")
        print("Datenbank: weedit_db.json")
        return
    
    # Setup configuration
    config = DBConfig(
        vidz_dir=args.vidz or r"D:\Oidasheim\NFOs\teST\9zu16",
        snd_dir=args.snd or r"D:\Oidasheim\NFOs\teST\snd",
        done_dir=args.done or "./done",
        db_path=args.db,
        batch_size=args.batch_size,
        max_processes=args.max_processes,
        log_level=args.log_level
    )
    
    # Setup logging
    logger = setup_logging(config)
    
    # Initialize components
    db_manager = DatabaseManager(config, logger)
    clip_pool = ClipPoolDB(config, db_manager, logger)
    
    # Run batch processor
    if args.batch:
        processor = BatchProcessor(config, db_manager, clip_pool, logger)
        success = processor.run(resume=args.resume)
        sys.exit(0 if success else 1)
    else:
        logger.error("Use --batch to run batch processing")
        sys.exit(1)

if __name__ == '__main__':
    main()
