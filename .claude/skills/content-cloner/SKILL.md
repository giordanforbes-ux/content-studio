---
name: content-cloner
description: Clone the structure, pacing and edit style of one of the user's existing videos and rebuild it for a new target product (default NightLister) — new script, shot list, and an edited 9:16 or 16:9 cut of new footage. Use when the user says "clone this video", "make this one about NightLister", "copy the format of my X video", or "remake this for another product".
---

# Content cloner

Turns a video that already worked into a new video about a different target. It copies the **format** (hook type, beat order, shot rhythm, word count, caption style, loudness), not the words.

Inputs:
- `SOURCE` — a video from the user's own content (any topic or business).
- `TARGET` — a file in `targets/` (default `targets/nightlister.md`).
- `FOOTAGE` — optional new raw footage. Without it, stop after the script and shot list so the user can film.

If the source is someone else's video, clone only the structure and pacing. Never reuse their wording, footage, audio or on-screen graphics.

## Setup (once)
- Needs `ffmpeg`/`ffprobe` and `pip install faster-whisper numpy` (use `--break-system-packages` if pip asks).
- First run downloads the Whisper model. `--model small` is the default; use `--model tiny` on a slow machine.

## Workflow

### 1. Analyze the source
```
python3 .claude/skills/content-cloner/scripts/analyze.py SOURCE work/<name>/
```
This writes `blueprint.json`, `blueprint.md` (shots, pacing, wpm, hook, loudness) and `frames/`.
Then **look at every image in `frames/`** and note what the numbers can't show:
- on-screen text and title style, caption look (font, colour, position)
- framing (face size, B-roll, screen recordings), zooms, transitions, music, emoji or graphics

### 2. Write `structure.md`
Label each shot or sentence with its role: hook, problem, proof, mechanism, demo, objection, CTA. Record for each beat: seconds, word count, purpose, and the visual. Add one line on *why the source worked*. If formula-lab is installed and has stats for this video, pull them in.

Show the user `structure.md` in a few lines and confirm it reads right before writing anything new.

### 3. Retarget the script
Read the TARGET file. Write `script.md` beat by beat, matching the source's:
- beat order and roles
- word count per beat (within about ±15%) and total length
- hook type (e.g. if the source opens with a question, so does the clone)
- CTA position

Rules:
- Use **only facts written in the TARGET file**. If a beat needs a fact that isn't there (a number, a result, a feature), write `[NEED: …]` and ask the user. Never invent stats, prices, results or features.
- Follow the TARGET's claims rules (for NightLister: no income promises, averages only, disclose codes).
- Give 3 hook options for the first beat, each a different hook type.

Also write `shots.md`: for each beat, what to film or screen-record, at what framing, and any on-screen text. Show the user `script.md` + `shots.md` and wait for approval or edits. If no FOOTAGE was given, stop here.

### 4. Edit the new footage
Hand this whole step to the `video-editor` subagent (Haiku) with the footage path, blueprint path and formats. Don't run renders in the main session. It returns a 5-line summary.

If the content-replicator skill is installed, use it for captions, zoom style and hook overlays so the user's house style carries over, and use the blueprint's pacing numbers as its settings. Otherwise:
```
python3 .claude/skills/content-cloner/scripts/apply_edit.py FOOTAGE work/<name>/blueprint.json work/<name>/clone_9x16.mp4
python3 .claude/skills/content-cloner/scripts/apply_edit.py FOOTAGE work/<name>/blueprint.json work/<name>/clone_16x9.mp4 --format 16x9
```
It cuts dead air, adds punch-in zooms at the source's average shot length, reframes, normalizes to -14 LUFS and burns word-chunk captions. Options: `--no-captions`, `--no-cut`, `--punch 1.1`.

Double takes: before running it, transcribe the footage, find repeated or restarted lines, keep the best take (cleanest, most complete; later one if tied), and trim the others with ffmpeg. List what you cut.

### 5. Check before handing over
- Re-run `analyze.py` on the clone with `--no-transcribe` and compare pacing with the source (avg shot length, cuts per 10s, length). Say where it differs.
- Pull 3–4 frames and look at them: captions inside the frame, face not cropped, nothing private visible (buyer names, addresses, order numbers, emails, store IDs). Blur anything that is.
- Check every claim in the captions against the TARGET file.
- Give the user the files plus a short list of anything approximated.

### 6. Log it
If formula-lab is installed, log the clone with tags: `source_video`, `target`, `hook_type`, `beat_order`, `length_sec`, `avg_shot_sec`, so source and clone performance can be compared later.

## Adding another target
Copy `targets/nightlister.md` to `targets/<product>.md` and fill in what it is, plans, audience, mechanism lines, allowed proof, claims rules and CTAs. The skill only says what that file says.

## Files
- `scripts/analyze.py` — blueprint from any video
- `scripts/apply_edit.py` — applies the blueprint's edit to new footage
- `targets/nightlister.md` — NightLister facts, claims rules and CTAs
