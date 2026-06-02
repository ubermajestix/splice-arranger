# Splice Arranger 

A command-line tool that takes a bare-bones Ableton Live session (a loop with stems in Session View) and arranges it into a full house/electronic track structure in Arrangement View.

No dependencies beyond the Python standard library.

## Splice?
Splice, the vast online sample library platform (subscription _not required_), has a feature called Stacks used to quickly build basic musical ideas. This has made creating banger 8-bar loops really easy on my phone. 

However, overcoming the 8-bar loop is one of the hardest problems in music, So, with an ever growing collection of 8-bar loops and endless ideas for improving and arranging those loops, I tried one last time to get a working, arranged, Ableton Live set out of Claude after months of failed attempts with claude-code. To my great surprise, I was able to get Claude Chat to produce a working arranged Ableton Live set and working Python code, this library is the output of that magical chat session. 

This tool _should_ free up my very limited creative time to edit the arrangement, add my own melodies, add fills, chops, effects, and do the fun parts of electronic music production and finish more tracks. 

## Example Track
### Step 1: Splice to Abelton
[Start with a Splice Stack](https://splice.com/sounds/create/share/lo-fi/i-can-give-you-everything/481e566e-7913-40da-b1ea-9a787b4a1bc7) (under the Create tab on desktop), [it's just an 8-bar loop](https://soundcloud.com/dj-macchiato/i_can_give_you_everything_stack_8_bar_loop-1?in=dj-macchiato/sets/splice-arranger-example), and download the Ableton set. As you can see it's just clips in session view, no arrangement. 


<img height="300" alt="Screenshot 2026-06-02 at 12 31 10 PM" src="https://github.com/user-attachments/assets/af4f8ede-f96e-418c-a06e-27cf2c4365a1" />
<img height="300" alt="Screenshot 2026-06-02 at 12 40 35 PM" src="https://github.com/user-attachments/assets/36eef9ed-6ec7-4e7e-afe3-994dcd1d855e" />
<img height="300" alt="Screenshot 2026-06-02 at 12 40 25 PM" src="https://github.com/user-attachments/assets/1303b01f-0923-4dc4-9320-95aa7ccdeec9" />


### Step 2: Python to Arrangement

Run this python script, open and export from Ableton, and you get the [arranged version of your stack.](https://soundcloud.com/dj-macchiato/i_can_give_you_everything_arranged-2?in=dj-macchiato/sets/splice-arranger-example)

<img width="677" height="435" alt="Screenshot 2026-06-02 at 12 53 03 PM" src="https://github.com/user-attachments/assets/1f205a0b-0b71-474f-a82f-fbb74889cb38" />
<img height="300" alt="Screenshot 2026-06-02 at 12 32 46 PM" src="https://github.com/user-attachments/assets/d073ae00-1d2c-4e6c-800b-81997a0e87ad" />
<img height="300" alt="Screenshot 2026-06-02 at 12 32 15 PM" src="https://github.com/user-attachments/assets/af2b9d5f-d491-4e73-ae66-15db4b34a3ae" />


## What it does

Given a zipped `.als` project with a few looped stems, it:

1. Parses the project's BPM, tracks, and clip loop lengths
2. Auto-classifies each stem by role (kick, hats, drums, bass, synth, pad, keys, pluck, vocals, etc.) from clip and track names
3. Places clips in the Arrangement View following a classic drop-structure layout
4. Writes labeled section markers (Intro, Build 1, Drop 1, Breakdown, Build 2, Drop 2, Outro)
5. Packages everything back into a ready-to-open `.zip`

Open the output in Live and the arrangement is there — all stems looping and placed, markers labeled, ready to tweak.

## Requirements

- Python 3.6+
- Ableton Live 11 or later (for opening the output)
- Input project must be a zipped `.als` project with audio stems in Session View slots

## Usage

```bash
python als_arranger.py input.zip
```

Output is written to `input_ARRANGED.zip` in the same directory by default.

## Options

```
positional arguments:
  input_zip             Path to zipped Ableton Live project (.zip)

options:
  -o, --output          Output zip path (default: <name>_ARRANGED.zip)
  --style               Arrangement length: short, standard, extended (default: standard)
  --bpm                 Override BPM (default: read from project)
  --roles               Manually assign roles: role=trackid,role=trackid,...
  --name                Project name used in output filenames
  -v, --verbose         Print full clip-by-clip arrangement plan
  --dry-run             Parse and plan without writing any files
  --list-roles          Show all supported roles and their detection keywords
```

## Arrangement styles

| Style | Structure (bars) | Duration @ 120 BPM |
|---|---|---|
| `short` | 8+16+24+8+8+32+8 | ~3:30 |
| `standard` | 16+16+32+8+8+48+16 | ~4:30 |
| `extended` | 16+32+64+16+16+64+16 | ~7:00 |

## Examples

```bash
# Standard arrangement, inferred output name
python als_arranger.py my_loop.zip

# Extended mix with a custom output path
python als_arranger.py my_loop.zip --style extended -o releases/my_track.zip

# Preview the arrangement plan without writing anything
python als_arranger.py my_loop.zip --dry-run --verbose

# Override BPM if the project has it set wrong
python als_arranger.py my_loop.zip --bpm 128

# Fix a misclassified track (track ID visible in verbose output)
python als_arranger.py my_loop.zip --roles kick=14,hats=13,vocals=18

# See all role keywords used for auto-detection
python als_arranger.py --list-roles
```

## Track role detection

Roles are assigned by scoring clip names and track names against keyword lists. A few examples:

| Role | Sample keywords |
|---|---|
| `kick` | kick, kik, bd, 808 |
| `hats` | hat, hh, hihat, top_loop |
| `drums` | drum_loop, break, groove, stumble |
| `bass` | bass, sub, low_end |
| `arp` | arp, tiger, seq, pulse |
| `pad` | pad, chord, frieden, atmosphere |
| `keys` | piano, electric_piano, ep, rhodes |
| `pluck` | pluck, melody, draw_back |
| `vocals` | vocal, vox, chop, eden |

Run `--list-roles` to see the full keyword list. Use `--roles` to override anything the auto-detection gets wrong.

## Arrangement logic

Tracks are sorted by role priority and staggered into the arrangement:

- **Intro** — lowest-priority tracks only (kick, hats, perc), entering in waves
- **Build 1** — mid-priority layers add in (bass, arp, drums, synth/keys)
- **Drop 1** — all tracks play; vocals/FX enter at the halfway point
- **Breakdown** — atmospheric tracks only (pad, keys, pluck, vocals)
- **Build 2** — kick and hats return first; rest enters at the midpoint
- **Drop 2** — all tracks, extended
- **Outro** — layers peel off in reverse priority; pads and keys tail out last

## Caveats

- Audio clips must be in **Session View slots**, not already arranged
- Only **AudioClip** tracks are processed — MIDI tracks and return tracks are left untouched
- Automation and device settings are preserved as-is; only clip placement changes
- The output `.als` references samples by relative path, so keep the zip structure intact when opening

## License

MIT
