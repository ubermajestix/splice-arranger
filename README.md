# Splice Arranger 

A command-line tool that takes a bare-bones Ableton Live session (a loop with stems in Session View) and arranges it into a full house/electronic track structure in Arrangement View.

No dependencies beyond the Python standard library.

## Splice?
Splice, the vast online sample library platform (subscription _not required_), has a feature called Stacks used to quickly build basic musical ideas. This has made creating banger 8-bar loops really easy on my phone. 

However, overcoming the 8-bar loop is one of the hardest problems in music, So, with an ever growing collection of 8-bar loops and endless ideas for improving and arranging those loops, I tried one last time to get a working, arranged, Ableton Live set out of Claude after months of failed attempts with claude-code. To my great surprise, I was able to get Claude Chat to produce a working arranged Ableton Live set and working Python code, this library is the output of that magical chat session. 

This tool _should_ free up my very limited creative time to edit the arrangement, add my own melodies, add fills, chops, effects, and do the fun parts of electronic music production and finish more tracks. 

## Example Track
[Start with a Splice Stack](https://splice.com/sounds/create/share/lo-fi/i-can-give-you-everything/481e566e-7913-40da-b1ea-9a787b4a1bc7) (under the Create tab on desktop), [it's just an 8-bar loop](https://soundcloud.com/dj-macchiato/i_can_give_you_everything_stack_8_bar_loop-1?in=dj-macchiato/sets/splice-arranger-example), download the Ableton set, run this tool, open and export from Ableton, and you get the [arranged version of your stack.](https://soundcloud.com/dj-macchiato/i_can_give_you_everything_arranged-2?in=dj-macchiato/sets/splice-arranger-example)

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

### A Real Example
The examples linked in the top of this README were created using this exact flow. 

Create a Stack on Splice. It's [just a repeating 8-bar loop.](https://soundcloud.com/dj-macchiato/i_can_give_you_everything_stack_8_bar_loop-1?in=dj-macchiato/sets/splice-arranger-example)

Download the .als file, requires using credits for any unpurchased samples used in the Stack. 

For this example I used the project `"i can give you everything [Ableton Live project].zip"` unmodifed from Splice's export.

**Run the arranger:**

```bash
python als_arranger.py "i can give you everything  [Ableton Live project].zip" --dry-run --verbose
```

**Output:**

```
🎛  ALS Arranger
   Input  : examples/i can give you everything  [Ableton Live project].zip
   Style  : standard
   Output : examples/i can give you everything  [Ableton Live project] ARRANGED.zip

⏳  Extracting project…
   Found  : i can give you everything.als
   BPM    : 100.0

📋  Detected 7 tracks:

  ID  Track Name           Role         Loop  Clip Name
──────────────────────────────────────────────────────────────────────────────
    18  Bass                 bass          32b  AU_MJH_70_electric_bass_loop_princess_
    17  FX                   pad           32b  SO_SRB_85_atmosphere_reminisce
    16  Drums                other         16b  NH_IAR_84_drum_destroy
    15  Drums                perc          16b  SO_LO_84_drum_loop_perc_dirty_amp_dist
    14  Vocals               vocals        32b  OS_VC_80_vocal_full_sunset_Fm
    13  Guitar               other         32b  ZEN_DUST_87_guitar_electric_closeby_Fm
    12  Chords               keys          32b  SO_NT_100_piano_martinique_lofi_Fmin

📐  Arrangement structure (standard):

Section              Bars        Beats     Time
────────────────────────────────────────────────
  Intro              1–16         0–64     0:38
  Build 1           17–32       64–128     0:38
  Drop 1            33–64      128–256     1:16
  Breakdown         65–72      256–288     0:19
  Build 2           73–80      288–320     0:19
  Drop 2           81–128      320–512     1:55
  Outro           129–144      512–576     0:38
────────────────────────────────────────────────
  TOTAL                      576 beats     5:45

🎵  Planned 38 clip placements

Track                  Section              Bars
──────────────────────────────────────────────────
  Drums [perc]         Intro                1-16
  Drums [perc]         Build 1             17-32
  Bass [bass]          Build 1             17-32
  Drums [other]        Build 1             19-32
  Guitar [other]       Build 1             21-32
  FX [pad]             Build 1             23-32
  Chords [keys]        Build 1             25-32
  Drums [perc]         Drop 1              33-64
  Bass [bass]          Drop 1              33-64
  Drums [other]        Drop 1              33-64
  Guitar [other]       Drop 1              33-64
  FX [pad]             Drop 1              33-64
  Chords [keys]        Drop 1              33-64
  Vocals [vocals]      Drop 1              49-64
  FX [pad]             Breakdown           65-72
  Chords [keys]        Breakdown           65-72
  Vocals [vocals]      Breakdown           65-72
  Drums [perc]         Build 2             77-80
  Bass [bass]          Build 2             77-80
  Drums [other]        Build 2             77-80
  Guitar [other]       Build 2             77-80
  FX [pad]             Build 2             77-80
  Chords [keys]        Build 2             77-80
  Vocals [vocals]      Build 2             73-80
  Drums [perc]         Drop 2             81-128
  Bass [bass]          Drop 2             81-128
  Drums [other]        Drop 2             81-128
  Guitar [other]       Drop 2             81-128
  FX [pad]             Drop 2             81-128
  Chords [keys]        Drop 2             81-128
  Vocals [vocals]      Drop 2             81-128
  Drums [perc]         Outro             129-140
  Bass [bass]          Outro             129-140
  Drums [other]        Outro             129-140
  Guitar [other]       Outro             129-140
  FX [pad]             Outro             129-140
  Chords [keys]        Outro             129-140
  Vocals [vocals]      Outro             129-136

🔍  Dry run complete — no files written.
```

Then run without --dry-run to create the arranged version.

Unzip the new arranged version and open the set in Ableton. You will likely have to locate the referenced files in the media explorer. 

Switch to arrangement view, enable arrangement mode, cmd+a, cmd+l, cmd+r (select all, loop, export) and you end up with [a basic arrangement that sounds like this.](https://soundcloud.com/dj-macchiato/i_can_give_you_everything_arranged-2?in=dj-macchiato/sets/splice-arranger-example) This audio is the unmodified export from this tool, no changes to the arrangement or plugins added.

Add your magic

...

Profit!

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
