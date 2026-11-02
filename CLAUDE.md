# Content studio

Giordan's video workspace for NightLister and personal-brand content (IG trial reels, TikTok, YouTube Shorts).

## Folders
- `inbox/` raw clips land here
- `work/<clip-name>/` blueprints, transcripts, intermediate files
- `exports/` finished videos, named `<clip-name>_9x16.mp4` / `<clip-name>_16x9.mp4`
- `archive/` raw clips after export (moved by `tools/cleanup.py`)

## When a video is dropped or named
Always use the `edit-video` skill: copy it into `inbox/`, ask the intake questions, confirm the plan, then edit. Never render before the questions are answered.

## Who does what (to keep usage low)
- **Any mechanical video work** — cutting, captions, reframing, loudness, renders, batch exports, cleanup — goes to the `video-editor` subagent (runs on Haiku). Give it paths and settings; don't do the render steps in the main session.
- **The main session** only does the creative part: reading `blueprint.md`, writing `structure.md` / `script.md` / `shots.md`, choosing hooks and best takes, and checking claims.
- For "clone this video" or "make this about NightLister", follow the `content-cloner` skill; its edit steps go to `video-editor`.

## Rules for every session
- Never read full transcripts, `blueprint.json`, ffmpeg output or logs into the conversation. Read `blueprint.md` or `head`/`jq` the one field you need.
- Look at no more than 4 frames per video, scaled to 360 px wide.
- All ffmpeg calls use `-hide_banner -loglevel error`.
- Default transcription model: `tiny`. Use `small` only for the final caption pass.
- After a batch is exported, have `video-editor` run `python3 tools/cleanup.py`.
- Product facts and claims rules: `.claude/skills/content-cloner/targets/nightlister.md`. No income promises, averages only, no "free trial".
