#!/usr/bin/env python3
"""
als_arranger.py — Auto-arrange a bare Ableton Live session into a full track structure.

Usage:
    python als_arranger.py input.zip [options]

Examples:
    python als_arranger.py my_loop.zip
    python als_arranger.py my_loop.zip -o arranged.zip --style extended --verbose
    python als_arranger.py my_loop.zip --bpm 128 --duration 5.5
    python als_arranger.py my_loop.zip --roles kick=14,hats=13,bass=12
"""

import argparse
import copy
import gzip
import os
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Track roles and classification
# ─────────────────────────────────────────────────────────────────────────────

ROLES = [
    "kick",       # bare kick drum
    "snare",      # snare / clap
    "hats",       # hi-hats / cymbals
    "perc",       # percussion loops (non-full-drum)
    "drums",      # full drum loop
    "bass",       # bass line
    "arp",        # arpeggiated / rhythmic synth
    "synth",      # synth / lead
    "pad",        # pad / chord
    "keys",       # piano / electric piano / keys
    "pluck",      # pluck melody
    "vocals",     # vocals / vocal chops
    "fx",         # FX / riser / sweep
    "other",      # unclassified
]

# Keywords scored per role (case-insensitive)
ROLE_KEYWORDS: Dict[str, List[str]] = {
    "kick":   ["kick", "kik", "bd ", "bass_drum", "bassdrum", "808"],
    "snare":  ["snare", "snr", "clap", "rim"],
    "hats":   ["hat", "hh", "hihat", "hi_hat", "top_loop", "cymbal", "open_hat", "closed_hat"],
    "perc":   ["perc", "percussion", "conga", "bongo", "shaker", "tamb", "clave"],
    "drums":  ["drum_loop", "drum loop", "break", "beat", "groove", "stumble", "panther",
               "jupiter", "loop_group", "full_kit"],
    "bass":   ["bass", "sub", "low_end", "lowend", "808bass"],
    "arp":    ["arp", "arpegg", "tiger", "seq", "pulse", "stab"],
    "synth":  ["synth", "lead", "mono", "saw", "square", "buzz"],
    "pad":    ["pad", "chord", "frieden", "atmosphere", "atmo", "wash", "ambient", "string"],
    "keys":   ["piano", "keys", "electric_piano", "ep_", "_ep_", "organ", "rhodes", "wurli"],
    "pluck":  ["pluck", "melody", "draw_back", "pizz", "mallet"],
    "vocals": ["vocal", "vox", "voice", "sing", "chop", "eden", "acap"],
    "fx":     ["fx", "riser", "sweep", "impact", "downlifter", "uplifter", "noise"],
}

# Arrangement priority: lower = enters earlier in the track
ROLE_PRIORITY: Dict[str, int] = {
    "kick":   1,
    "hats":   2,
    "snare":  2,
    "perc":   3,
    "bass":   4,
    "arp":    4,
    "drums":  5,
    "synth":  5,
    "pad":    6,
    "keys":   6,
    "pluck":  6,
    "fx":     7,
    "vocals": 8,
    "other":  5,
}

# Whether a role appears only in full drops (not intro or builds)
DROP_ONLY_ROLES = {"vocals", "fx"}

# Whether a role plays in breakdowns
BREAKDOWN_ROLES = {"pad", "keys", "pluck", "vocals", "synth"}


@dataclass
class TrackInfo:
    id: str
    name: str
    clip_name: str
    loop_len: float          # beats
    role: str = "other"
    role_score: int = 0
    source_clip_el: object = None
    track_el: object = None


# ─────────────────────────────────────────────────────────────────────────────
# Arrangement structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Section:
    name: str
    start: int   # beats
    end: int     # beats

    @property
    def length(self) -> int:
        return self.end - self.start

    @property
    def start_bar(self) -> int:
        return self.start // 4 + 1

    @property
    def end_bar(self) -> int:
        return self.end // 4


STYLE_CONFIGS = {
    # style: (bars_intro, bars_build1, bars_drop1, bars_break, bars_build2, bars_drop2, bars_outro)
    "short":    (8,  16, 24,  8,  8, 32,  8),   # ~3:30 @ 120 BPM
    "standard": (16, 16, 32,  8,  8, 48, 16),   # ~4:30 @ 120 BPM
    "extended": (16, 32, 64, 16, 16, 64, 16),   # ~7:00 @ 120 BPM
}


def build_sections(style: str) -> List[Section]:
    bars = STYLE_CONFIGS[style]
    names = ["Intro", "Build 1", "Drop 1", "Breakdown", "Build 2", "Drop 2", "Outro"]
    sections = []
    cursor = 0
    for name, bar_count in zip(names, bars):
        beats = bar_count * 4
        sections.append(Section(name, cursor, cursor + beats))
        cursor += beats
    return sections


# ─────────────────────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────────────────────

def find_als_in_zip(zip_path: str) -> Tuple[str, str]:
    """Extract zip to temp dir, return (temp_dir, als_path)."""
    tmp = tempfile.mkdtemp(prefix="als_arranger_")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(tmp)

    als_files = list(Path(tmp).rglob("*.als"))
    if not als_files:
        shutil.rmtree(tmp)
        raise ValueError("No .als file found in zip")
    if len(als_files) > 1:
        # Prefer the one not in a backup/tmp folder
        primary = [f for f in als_files
                   if "backup" not in str(f).lower() and "tmp" not in str(f).lower()]
        als_files = primary if primary else als_files

    return tmp, str(als_files[0])


def load_als(als_path: str):
    """Load and decompress .als → (root_element, raw_xml_str)."""
    with gzip.open(als_path, "rb") as f:
        content = f.read().decode("utf-8")
    root = ET.fromstring(content)
    return root


def classify_role(track_name: str, clip_name: str) -> Tuple[str, int]:
    """Return (role, confidence_score) based on keyword matching."""
    text = (track_name + " " + clip_name).lower().replace("-", "_")
    scores: Dict[str, int] = {r: 0 for r in ROLES}

    for role, keywords in ROLE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[role] += 2 if kw in clip_name.lower() else 1

    best_role = max(scores, key=lambda r: scores[r])
    best_score = scores[best_role]

    # Disambiguation: bass vs kick (both contain "bass")
    if best_role == "bass" and "kick" in text:
        best_role = "kick"

    return (best_role if best_score > 0 else "other"), best_score


def parse_project(root) -> Tuple[float, List[TrackInfo]]:
    """Parse BPM and all audio tracks from the LiveSet."""
    liveset = root.find("LiveSet")
    tracks_el = liveset.find("Tracks")

    # BPM
    bpm_el = root.find(".//Tempo/Manual")
    bpm = float(bpm_el.get("Value")) if bpm_el is not None else 120.0

    tracks = []
    for t in tracks_el:
        tid = t.get("Id")
        tname_el = t.find(".//Name/EffectiveName")
        tname = tname_el.get("Value") if tname_el is not None else f"Track {tid}"

        ms = t.find(".//MainSequencer")
        if ms is None:
            continue
        csl = ms.find("ClipSlotList")
        if csl is None:
            continue
        clip_el = csl.find(".//AudioClip")
        if clip_el is None:
            continue

        name_el = clip_el.find("Name")
        clip_name = name_el.get("Value") if name_el is not None else ""

        loop = clip_el.find("Loop")
        loop_end = float(loop.find("LoopEnd").get("Value")) if loop is not None else 8.0

        role, score = classify_role(tname, clip_name)

        tracks.append(TrackInfo(
            id=tid,
            name=tname,
            clip_name=clip_name,
            loop_len=loop_end,
            role=role,
            role_score=score,
            source_clip_el=clip_el,
            track_el=t,
        ))

    return bpm, tracks


# ─────────────────────────────────────────────────────────────────────────────
# Arrangement planning
# ─────────────────────────────────────────────────────────────────────────────

Clip = Tuple[str, int, int]  # (track_id, start_beat, end_beat)


def plan_arrangement(tracks: List[TrackInfo], sections: List[Section]) -> List[Clip]:
    """
    Generate (track_id, start, end) clip placements based on track roles
    and the section structure.

    Logic:
    - Sort tracks by priority (kick first, vocals last)
    - Intro:     lowest-priority tracks only; stagger entries every 4 bars
    - Build 1:   mid-priority tracks enter; stagger last few late
    - Drop 1:    everything except vocals and fx
    - Drop 1+:   vocals / fx enter halfway through drop 1
    - Breakdown: pad/keys/melody/vocals only
    - Build 2:   same as build 1 but compressed
    - Drop 2:    everything
    - Outro:     peel back layer by layer
    """
    intro   = sections[0]
    build1  = sections[1]
    drop1   = sections[2]
    brkdown = sections[3]
    build2  = sections[4]
    drop2   = sections[5]
    outro   = sections[6]

    # Sort tracks by role priority
    sorted_tracks = sorted(tracks, key=lambda t: ROLE_PRIORITY.get(t.role, 5))

    clips: List[Clip] = []

    def add(tid: str, start: int, end: int):
        if start < end:
            clips.append((tid, start, end))

    # ── INTRO ─────────────────────────────────────────────────────────────────
    # Stagger entries: tracks enter every quarter of the intro
    intro_tiers = [t for t in sorted_tracks
                   if ROLE_PRIORITY.get(t.role, 5) <= 3 and t.role not in DROP_ONLY_ROLES]
    stagger = max(4, intro.length // max(len(intro_tiers), 1))
    stagger = (stagger // 4) * 4  # snap to bar boundary

    for i, t in enumerate(intro_tiers):
        entry = intro.start + min(i * stagger, intro.length // 2)
        entry = (entry // 4) * 4  # bar-snap
        add(t.id, entry, intro.end)

    # ── BUILD 1 ───────────────────────────────────────────────────────────────
    # Low-priority tracks carry over; mid-priority stagger in
    build1_early = [t for t in sorted_tracks
                    if ROLE_PRIORITY.get(t.role, 5) <= 3 and t.role not in DROP_ONLY_ROLES]
    build1_late  = [t for t in sorted_tracks
                    if 4 <= ROLE_PRIORITY.get(t.role, 5) <= 6 and t.role not in DROP_ONLY_ROLES]

    for t in build1_early:
        add(t.id, build1.start, build1.end)

    late_stagger = max(4, build1.length // max(len(build1_late) + 1, 2))
    late_stagger = (late_stagger // 4) * 4
    for i, t in enumerate(build1_late):
        entry = build1.start + i * late_stagger
        entry = (entry // 4) * 4
        add(t.id, entry, build1.end)

    # ── DROP 1 ────────────────────────────────────────────────────────────────
    drop_only = [t for t in sorted_tracks if t.role in DROP_ONLY_ROLES]
    non_drop  = [t for t in sorted_tracks if t.role not in DROP_ONLY_ROLES]

    for t in non_drop:
        add(t.id, drop1.start, drop1.end)

    # Drop-only tracks enter halfway through drop 1
    drop1_mid = drop1.start + (drop1.length // 2)
    drop1_mid = (drop1_mid // 4) * 4
    for t in drop_only:
        add(t.id, drop1_mid, drop1.end)

    # ── BREAKDOWN ─────────────────────────────────────────────────────────────
    breakdown_tracks = [t for t in sorted_tracks if t.role in BREAKDOWN_ROLES]
    for t in breakdown_tracks:
        add(t.id, brkdown.start, brkdown.end)

    # ── BUILD 2 ───────────────────────────────────────────────────────────────
    # Kick/hats enter immediately; others stagger in the second half
    build2_early = [t for t in sorted_tracks
                    if ROLE_PRIORITY.get(t.role, 5) <= 2 and t.role not in DROP_ONLY_ROLES]
    build2_late  = [t for t in sorted_tracks
                    if 3 <= ROLE_PRIORITY.get(t.role, 5) <= 6 and t.role not in DROP_ONLY_ROLES]

    for t in build2_early:
        add(t.id, build2.start, build2.end)

    # Remaining tracks enter at the halfway point of build 2
    build2_mid = build2.start + (build2.length // 2)
    build2_mid = (build2_mid // 4) * 4
    for t in build2_late:
        add(t.id, build2_mid, build2.end)

    # Breakdown melody carries into build 2
    for t in breakdown_tracks:
        if t not in build2_early + build2_late:
            add(t.id, build2.start, build2.end)

    # ── DROP 2 ────────────────────────────────────────────────────────────────
    for t in sorted_tracks:
        add(t.id, drop2.start, drop2.end)

    # ── OUTRO ─────────────────────────────────────────────────────────────────
    # Peel off layers: drums/bass drop first, melodic sustain, then silence
    outro_q1 = outro.start + (outro.length * 3 // 4)
    outro_q1 = (outro_q1 // 4) * 4
    outro_q2 = outro.start + (outro.length * 1 // 2)
    outro_q2 = (outro_q2 // 4) * 4

    for t in sorted_tracks:
        prio = ROLE_PRIORITY.get(t.role, 5)
        if prio >= 7:                            # fx / vocals: short
            add(t.id, outro.start, outro_q2)
        elif prio >= 5:                          # drums / full groove
            add(t.id, outro.start, outro_q1)
        elif prio >= 3:                          # bass / perc
            add(t.id, outro.start, outro_q1)
        else:                                    # kick, hats, pads → longer tail
            add(t.id, outro.start, outro.end)

    return clips


# ─────────────────────────────────────────────────────────────────────────────
# Writing
# ─────────────────────────────────────────────────────────────────────────────

def make_arr_clip(track: TrackInfo, start: int, end: int, clip_id: int):
    """Deep-copy session clip, adjust for arrangement placement."""
    clip = copy.deepcopy(track.source_clip_el)
    length = end - start

    clip.set("Time", str(start))
    clip.set("Id", str(clip_id))

    # Remove stale CurrentStart/CurrentEnd if present
    for tag in ["CurrentStart", "CurrentEnd"]:
        el = clip.find(tag)
        if el is not None:
            clip.remove(el)

    # Insert correct absolute CurrentStart / CurrentEnd
    color_el = clip.find("ColorIndex")
    insert_pos = list(clip).index(color_el) + 1 if color_el is not None else 0

    cs = ET.Element("CurrentStart")
    cs.set("Value", str(start))
    ce = ET.Element("CurrentEnd")
    ce.set("Value", str(end))
    clip.insert(insert_pos, cs)
    clip.insert(insert_pos + 1, ce)

    # Loop: loop the original sample region, OutMarker = total clip length
    loop = clip.find("Loop")
    if loop is not None:
        loop.find("LoopStart").set("Value", "0")
        loop.find("LoopEnd").set("Value", str(float(track.loop_len)))
        loop.find("OutMarker").set("Value", str(float(length)))
        loop.find("LoopOn").set("Value", "true")

    # Small crossfades
    fades = clip.find("Fades")
    if fades is not None:
        for fade_tag in ["FadeInLength", "FadeOutLength"]:
            f = fades.find(fade_tag)
            if f is not None:
                f.set("Value", "0.5")

    return clip


def clear_arrangement(root):
    """Remove any existing arrangement clips from all tracks."""
    for t in root.find(".//Tracks"):
        ms = t.find(".//MainSequencer")
        if ms is None:
            continue
        sample = ms.find("Sample")
        if sample is None:
            continue
        arr_auto = sample.find("ArrangerAutomation")
        if arr_auto is None:
            arr_auto = ET.SubElement(sample, "ArrangerAutomation")
        events = arr_auto.find("Events")
        if events is None:
            ET.SubElement(arr_auto, "Events")
        else:
            for child in list(events):
                events.remove(child)


def write_clips(root, tracks: List[TrackInfo], clips: List[Clip]):
    """Insert arrangement clips into the correct track Events elements."""
    track_map = {t.id: t for t in tracks}
    clip_id_counter = [6000]
    placed = 0

    for (tid, start, end) in clips:
        track = track_map.get(tid)
        if track is None:
            continue
        t_el = track.track_el
        ms = t_el.find(".//MainSequencer")
        if ms is None:
            continue
        events = ms.find("Sample/ArrangerAutomation/Events")
        if events is None:
            continue

        clip_el = make_arr_clip(track, start, end, clip_id_counter[0])
        clip_id_counter[0] += 1
        events.append(clip_el)
        placed += 1

    return placed


def write_locators(root, sections: List[Section]):
    """Write section markers using the correct <Locator> tag."""
    liveset = root.find("LiveSet")
    locators_container = liveset.find("Locators")
    if locators_container is None:
        return

    locators_inner = locators_container.find("Locators")
    if locators_inner is None:
        locators_inner = ET.SubElement(locators_container, "Locators")

    for child in list(locators_inner):
        locators_inner.remove(child)

    for i, section in enumerate(sections):
        loc = ET.SubElement(locators_inner, "Locator", Id=str(i))
        ET.SubElement(loc, "LomId", Value="0")
        ET.SubElement(loc, "Time", Value=str(section.start))
        ET.SubElement(loc, "Name", Value=section.name)
        ET.SubElement(loc, "Annotation", Value="")
        ET.SubElement(loc, "IsSongStart", Value="false")


def save_als(root, out_path: str):
    """Write modified XML back as gzip-compressed .als."""
    out_xml = ET.tostring(root, encoding="unicode")
    if not out_xml.startswith("<?xml"):
        out_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + out_xml
    with gzip.open(out_path, "wb") as f:
        f.write(out_xml.encode("utf-8"))


def package_output(tmp_dir: str, new_als_path: str, original_als_path: str,
                   out_zip: str, project_name: str):
    """
    Build output zip:
    - new .als file
    - all original Samples folders
    - Ableton Project Info
    """
    original_project_dir = str(Path(original_als_path).parent)
    out_project_dir = os.path.join(tmp_dir, f"{project_name} [Ableton Live project]")
    os.makedirs(out_project_dir, exist_ok=True)

    # Copy samples
    for subdir in ["Samples", "Ableton Project Info"]:
        src = os.path.join(original_project_dir, subdir)
        dst = os.path.join(out_project_dir, subdir)
        if os.path.exists(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)

    # Copy new als
    als_dest = os.path.join(out_project_dir, f"{project_name}.als")
    shutil.copy2(new_als_path, als_dest)

    # Zip
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root_dir, dirs, files in os.walk(out_project_dir):
            for file in files:
                abs_path = os.path.join(root_dir, file)
                rel_path = os.path.relpath(abs_path, tmp_dir)
                zf.write(abs_path, rel_path)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_role_overrides(roles_str: str) -> Dict[str, str]:
    """Parse 'kick=14,hats=13,bass=12' into {track_id: role}."""
    overrides = {}
    if not roles_str:
        return overrides
    for pair in roles_str.split(","):
        pair = pair.strip()
        if "=" not in pair:
            continue
        role, tid = pair.split("=", 1)
        overrides[tid.strip()] = role.strip().lower()
    return overrides


def duration_str(total_beats: int, bpm: float) -> str:
    total_sec = total_beats / bpm * 60
    mins = int(total_sec // 60)
    secs = int(total_sec % 60)
    return f"{mins}:{secs:02d}"


def print_section_table(sections: List[Section], bpm: float):
    print(f"\n{'Section':<14} {'Bars':>10} {'Beats':>12} {'Time':>8}")
    print("─" * 48)
    for s in sections:
        bar_range = f"{s.start_bar}–{s.end_bar}"
        beat_range = f"{s.start}–{s.end}"
        dur = duration_str(s.length, bpm)
        print(f"  {s.name:<12} {bar_range:>10} {beat_range:>12} {dur:>8}")
    total = sections[-1].end
    print("─" * 48)
    print(f"  {'TOTAL':<12} {'':>10} {str(total)+' beats':>12} {duration_str(total, bpm):>8}\n")


def print_track_table(tracks: List[TrackInfo]):
    print(f"\n{'ID':>4}  {'Track Name':<20} {'Role':<10} {'Loop':>6}  {'Clip Name'}")
    print("─" * 78)
    for t in tracks:
        loop_str = f"{int(t.loop_len)}b"
        print(f"  {t.id:>4}  {t.name[:20]:<20} {t.role:<10} {loop_str:>6}  {t.clip_name[:38]}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Auto-arrange an Ableton Live session zip into a full track structure.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Styles:
  short      ~3:30  (8+16+24+8+8+32+8 bars)
  standard   ~4:30  (16+16+32+8+8+48+16 bars)  [default]
  extended   ~7:00  (16+32+64+16+16+64+16 bars)

Role overrides (--roles):
  Specify role=track_id pairs to manually assign roles.
  Example: --roles kick=14,hats=13,bass=12,synth=15

Available roles:
  kick, snare, hats, perc, drums, bass, arp, synth, pad, keys, pluck, vocals, fx
        """
    )
    parser.add_argument("input_zip", nargs="?",
                        help="Path to zipped Ableton Live project (.zip)")
    parser.add_argument("-o", "--output",
                        help="Output zip path (default: <name>_ARRANGED.zip)")
    parser.add_argument("--style", choices=["short", "standard", "extended"],
                        default="standard",
                        help="Arrangement style (default: standard)")
    parser.add_argument("--bpm", type=float,
                        help="Override BPM (default: read from project)")
    parser.add_argument("--roles", default="",
                        help="Manual role assignments: role=id,role=id,...")
    parser.add_argument("--name",
                        help="Project name for output file (default: inferred from zip)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print detailed arrangement plan")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and plan without writing output")
    parser.add_argument("--list-roles", action="store_true",
                        help="Print available roles and exit")

    args = parser.parse_args()

    if args.list_roles:
        print("\nAvailable track roles:")
        for role in ROLES:
            kws = ROLE_KEYWORDS.get(role, [])
            print(f"  {role:<10} — keywords: {', '.join(kws[:5])}")
        print()
        return

    # ── Validate input ────────────────────────────────────────────────────────
    if not args.input_zip:
        parser.print_help()
        sys.exit(1)

    if not os.path.exists(args.input_zip):
        print(f"❌  File not found: {args.input_zip}", file=sys.stderr)
        sys.exit(1)

    if not args.input_zip.lower().endswith(".zip"):
        print("❌  Input must be a .zip file", file=sys.stderr)
        sys.exit(1)

    # Infer project name
    zip_stem = Path(args.input_zip).stem
    project_name = args.name or f"{zip_stem} ARRANGED"
    out_zip = args.output or str(Path(args.input_zip).parent / f"{project_name}.zip")

    print(f"\n🎛  ALS Arranger")
    print(f"   Input  : {args.input_zip}")
    print(f"   Style  : {args.style}")
    print(f"   Output : {out_zip}")

    # ── Extract and parse ─────────────────────────────────────────────────────
    tmp_dir = None
    try:
        print("\n⏳  Extracting project…")
        tmp_dir, als_path = find_als_in_zip(args.input_zip)
        print(f"   Found  : {Path(als_path).name}")

        root = load_als(als_path)
        bpm, tracks = parse_project(root)

        if args.bpm:
            bpm = args.bpm
            print(f"   BPM    : {bpm} (overridden)")
        else:
            print(f"   BPM    : {bpm}")

        if not tracks:
            print("❌  No audio tracks with clips found in project", file=sys.stderr)
            sys.exit(1)

        # Apply manual role overrides
        role_overrides = parse_role_overrides(args.roles)
        if role_overrides:
            for t in tracks:
                if t.id in role_overrides:
                    new_role = role_overrides[t.id]
                    if new_role in ROLES:
                        print(f"   Override: Track {t.id} '{t.name}' → {new_role}")
                        t.role = new_role
                    else:
                        print(f"⚠️   Unknown role '{new_role}' for track {t.id}, ignoring")

        print(f"\n📋  Detected {len(tracks)} tracks:")
        print_track_table(tracks)

        # ── Build sections ────────────────────────────────────────────────────
        sections = build_sections(args.style)
        total_beats = sections[-1].end

        print(f"📐  Arrangement structure ({args.style}):")
        print_section_table(sections, bpm)

        # ── Plan clips ────────────────────────────────────────────────────────
        clips = plan_arrangement(tracks, sections)
        print(f"🎵  Planned {len(clips)} clip placements")

        if args.verbose:
            track_map = {t.id: t for t in tracks}
            print(f"\n{'Track':<22} {'Section':<14} {'Bars':>10}")
            print("─" * 50)
            for (tid, start, end) in clips:
                t = track_map.get(tid)
                tname = f"{t.name[:16]} [{t.role}]" if t else tid
                bar_s = start // 4 + 1
                bar_e = end // 4
                # Find which section this is in
                sec_name = next(
                    (s.name for s in sections if s.start <= start < s.end), "?"
                )
                print(f"  {tname:<20} {sec_name:<14} {str(bar_s)+'-'+str(bar_e):>10}")
            print()

        if args.dry_run:
            print("🔍  Dry run complete — no files written.")
            return

        # ── Write output ──────────────────────────────────────────────────────
        print("✏️   Building arrangement…")
        clear_arrangement(root)
        placed = write_clips(root, tracks, clips)
        write_locators(root, sections)

        # Save modified .als to temp location
        out_als_tmp = os.path.join(tmp_dir, "arranged.als")
        save_als(root, out_als_tmp)

        print(f"   Placed {placed} clips across {len(tracks)} tracks")

        # Package zip
        print("📦  Packaging output…")
        package_output(tmp_dir, out_als_tmp, als_path, out_zip, project_name)

        size_mb = os.path.getsize(out_zip) / 1_000_000
        print(f"\n✅  Done! → {out_zip}  ({size_mb:.1f} MB)")
        print(f"   Duration: ~{duration_str(total_beats, bpm)} @ {bpm} BPM\n")

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌  Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    finally:
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)


if __name__ == "__main__":
    main()
