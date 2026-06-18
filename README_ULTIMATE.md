# 🎬 WE.ED.IT ULTIMATE + DATABASE

> **"Musik dirigiert. KI schneidet. Du kreierst."**  
> **"Fortschritt erfolgreich eingefroren. Vorgang beendet."**

**Komplettes AI-Musikvideo-Studio für Ihr Setup:**

- ✅ **Video Clips:** `D:\Oidasheim\NFOs\teST\9zu16` (6241+ entries)
- ✅ **Audio Files:** `D:\Oidasheim\NFOs\teST\snd`
- ✅ **Output:** `./done`
- ✅ **Database:** `weedit_db.json`

---

## 📥 SCHNELLSTART

### 1. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 2. Batch-Verarbeitung starten

```bash
python weedit_ultimate_db.py --batch
```

### 3. Bei Unterbrechung (Ctrl+C) fortsetzen

```bash
python weedit_ultimate_db.py --batch --resume
```

## 🖥️ WINDOWS BENUTZER

Verwenden Sie die `run.bat` Datei für ein einfaches Menü:

```batch
run.bat
```

Wählen Sie:
- **Option 1:** Batch-Verarbeitung starten
- **Option 2:** Fortsetzen nach Unterbrechung
- **Option 3:** Neu beginnen (ohne Fortsetzung)

## 📋 BEFEHLE

| Befehl | Beschreibung |
|--------|-------------|
| `python weedit_ultimate_db.py --batch` | Alle Audiodateien verarbeiten |
| `python weedit_ultimate_db.py --batch --resume` | Fortsetzen (Standard) |
| `python weedit_ultimate_db.py --batch --no-resume` | Neu beginnen |
| `python weedit_ultimate_db.py --version` | Version anzeigen |
| `python weedit_ultimate_db.py --log-level DEBUG` | Debug-Logging |

## 🗄️ DATENBANK

Die `weedit_db.json` enthält:

- **6241+ Clips** aus `D:\Oidasheim\NFOs\teST\9zu16`
- Audio-Analysen
- Projekt-Historie
- Metadaten

### Atomare Speicherung

Bei Unterbrechung (Ctrl+C) wird die Datenbank automatisch und sicher gespeichert:

```
[!] Setup-Prozess durch Benutzer unterbrochen (Abbruch-Signal)
[*] Sichere aktuellen Datenbank-Stand...
✅ [DB] 6241 analysierte Clips atomar in weedit_db.json gesichert.
[+] Fortschritt erfolgreich eingefroren. Beendet.
```

## 🎯 FEATURES

### ✨ 9D Semantic Vector Space

Jeder Clip wird in einem 9-dimensionalen Raum positioniert:

- **Genre** (5D): Hip-Hop, Pop, Electronic, Rock, Soul
- **Mood** (3D): Happy, Intense, Calm
- **Motion** (1D): 0.0 (static) to 1.0 (dynamic)

### 🎬 Beat-Aligned Segmentation

Videos werden automatisch zu den Beats der Musik geschnitten:

- BPM Detection
- Beat Grid Generation
- Energy-based Effect Selection

### 🎨 Hip-Hop Visual Profiling

Erkennt visuelle Hip-Hop-Elemente automatisch:

- Gold/Bling Detection (Farbe)
- Neon/Glow Analysis (Beleuchtung)
- Edge/Contrast Detection (Komposition)
- Graffiti/Street Elements (Textur)

### 📊 Batch Processing mit Resume

- Verarbeite alle Audiodateien nacheinander
- Automatische Fortsetzung bei Unterbrechung
- Progress Tracking alle 10 Dateien
- Fehlerbehandlung für jede Datei

### 💾 Atomic Database Saves

- Sichere Fortschritt bei Ctrl+C
- Keine Datenbeschädigungen
- Atomare Schreibvorgänge mit temp-Dateien

## 📁 KONFIGURATION

Pfade sind vorkonfiguriert für Ihre Setup:

```python
vidz_dir = r"D:\Oidasheim\NFOs\teST\9zu16"  # Video-Clips
snd_dir  = r"D:\Oidasheim\NFOs\teST\snd"     # Audio-Dateien
done_dir = "./done"                           # Ausgabe
db_path  = "weedit_db.json"                   # Datenbank
```

Überschreiben Sie mit Command-Line-Argumenten:

```bash
python weedit_ultimate_db.py --batch --vidz D:\MyClips --snd D:\MyMusic
```

## ⚠️ FEHLERBEHEBUNG

### "FFmpeg nicht gefunden"

```bash
choco install ffmpeg
```

Oder manuell von https://ffmpeg.org/download.html installieren.

### "Keine Audiodateien gefunden"

- Überprüfen Sie `D:\Oidasheim\NFOs\teST\snd` existiert
- Audiodateien müssen `.mp3` oder `.wav` sein
- Spezifizieren Sie mit `--snd` wenn anders

### "Keine Video-Clips gefunden"

- Überprüfen Sie `D:\Oidasheim\NFOs\teST\9zu16` existiert
- Videodateien müssen `.mp4`, `.mov`, `.avi`, etc. sein
- Spezifizieren Sie mit `--vidz` wenn anders

### "Datenbank beschädigt"

1. Sichern Sie `weedit_db.json.tmp` (backup)
2. Löschen Sie `weedit_db.json`
3. Starten Sie mit `--batch --no-resume` neu

### Debug-Logging

```bash
python weedit_ultimate_db.py --batch --log-level DEBUG
```

Alle Details werden in `weedit_batch.log` gespeichert.

## 📊 LEISTUNG

Typische Verarbeitungszeiten:

| Schritt | Zeit | Notes |
|---------|------|-------|
| **Datenbank laden** | 1-2s | 6241 Clips |
| **Audio-Analyse** | 5-10s | Pro Datei |
| **Video-Rendering** | 30-60s | Pro 3-Min-Song |
| **Gesamt (50 Songs)** | 30-60 Min | Mit Fortsetzung |

## 🔍 MONITORING

Überwachen Sie den Fortschritt:

```bash
# Log-Datei ansehen (Windows)
type weedit_batch.log

# Oder live folgen
findstr /I "erfolg" weedit_batch.log
```

## 📞 SUPPORT

1. **Überprüfen Sie die Log-Datei:** `weedit_batch.log`
2. **Verifizieren Sie die Pfade:**
   - `D:\Oidasheim\NFOs\teST\9zu16` (Clips)
   - `D:\Oidasheim\NFOs\teST\snd` (Audio)
   - `weedit_db.json` (Datenbank)
3. **Alle Abhängigkeiten installiert?**
   ```bash
   pip install -r requirements.txt
   ```

## 📦 DATEISTRUKTUR

```
.
├── weedit_ultimate_db.py        # Haupt-Skript
├── requirements.txt             # Dependencies
├── run.bat                      # Windows-Menü
├── README_ULTIMATE.md           # Diese Datei
├── weedit_db.json               # Datenbank (wird erstellt)
├── weedit_batch.log             # Log-Datei
└── done/                        # Ausgabe-Verzeichnis
    ├── video1_WEEDIT_*.mp4
    ├── video2_WEEDIT_*.mp4
    └── temp_segments/           # Temporäre Dateien
```

## 🎯 WORKFLOW

1. **Starten Sie den Prozess:**
   ```bash
   python weedit_ultimate_db.py --batch
   ```

2. **Der System wird:**
   - ✅ Alle Audio-Dateien finden
   - ✅ Jede Datei analysieren (BPM, Struktur, Genre)
   - ✅ Beat-aligned Timeline generieren
   - ✅ Beste Clips semantisch selektieren
   - ✅ Mit Effects rendern (NORMAL, WOBBLE-ZOOM, SCRATCH-STUTTER)
   - ✅ Final MP4 mit Audio erstellen
   - ✅ Fortschritt in Datenbank speichern

3. **Bei Unterbrechung (Ctrl+C):**
   - ✅ Aktuelle Datenbank wird gespeichert
   - ✅ Fortschritt bleibt erhalten
   - ✅ Später mit `--resume` fortsetzen

4. **Finale Videos sind in `./done/`:**
   ```
   output_Song01_WEEDIT_20260618_143000.mp4
   output_Song02_WEEDIT_20260618_143530.mp4
   ```

## 🚀 OPTIMIERUNGEN

### Schneller Processing

```bash
# Erhöhe Batch-Size für selteneere Speicherung
python weedit_ultimate_db.py --batch --batch-size 20
```

### Mehr Parallelität

```bash
# FFmpeg-Prozesse erhöhen (bei viel RAM)
python weedit_ultimate_db.py --batch --max-processes 8
```

### Weniger Logging (schneller)

```bash
python weedit_ultimate_db.py --batch --log-level WARNING
```

## 📈 STATISTIKEN

Nach Verarbeitung sehen Sie:

```
======================================================================
📊 ZUSAMMENFASSUNG
======================================================================
✅ Erfolgreich: 48
❌ Fehlgeschlagen: 2

📁 Datenbank: 6241 Clips, 50 Audio, 48 Projekte
======================================================================
```

## 🎓 ADVANCED USAGE

### Nur eine Datei testen

```bash
python weedit_ultimate_db.py --snd "D:\test.mp3"
```

### Custom Pfade

```bash
python weedit_ultimate_db.py --batch ^
  --vidz "D:\MyClips" ^
  --snd "D:\MyMusic" ^
  --done "D:\Videos" ^
  --db "custom_db.json"
```

### Neue Datenbank beginnen

```bash
rem Alte DB sichern
move weedit_db.json weedit_db.json.backup

rem Neu starten
python weedit_ultimate_db.py --batch --no-resume
```

---

**Version:** 1.0 Complete  
**Database:** weedit_db.json (6241+ entries)  
**Setup:** D:\Oidasheim\NFOs\teST  
**Last Updated:** June 18, 2026  

> "Musik dirigiert. KI schneidet. Du kreierst."
