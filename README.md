# Content studio

Drop a video into Claude Code, answer up to 4 quick questions, get edited reels back. Rendering runs on a cheap Haiku helper so it uses as little of your plan as possible.

## Start
1. `bash setup.sh` (once; installs ffmpeg and the transcriber)
2. Open Claude Code in this folder: `claude`
3. Drag a video in and add a direction, or just "edit this"
4. Answer the questions it asks, then it edits

## What happens
- **edit-video skill:** asks format, length, style and number of versions (skips what you already said, remembers your last answers in `studio-defaults.json`), confirms the plan, then edits.
- **video-editor agent (Haiku):** does every render step and reports back in ≤5 lines.
- **content-cloner skill:** "clone my X video and make it about NightLister".
- **tools/cleanup.py:** clears temp renders and archives raws after export.

## Folders
`inbox/` raw · `work/` in progress · `exports/` finished · `archive/` posted raws

Videos are ignored by git (see `.gitignore`), so the repo stays small.
