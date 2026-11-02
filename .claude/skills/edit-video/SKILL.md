---
name: edit-video
description: Use whenever the user drops or names a video file, or says edit, cut, clip, make a reel/short/TikTok, or "do this one". Asks a short set of multiple-choice questions before any editing, then hands the render to the video-editor subagent.
---

# Edit video (ask first, then edit)

Never start rendering until the questions below are answered. Ask, confirm the plan, then edit.

## 1. Take in the file
- Copy each dropped file into `inbox/` (keep the original where it was). Name: lower-case, no spaces.
- Get basics with one quiet command, nothing else read:
  `ffprobe -v error -show_entries format=duration:stream=width,height -of csv=p=0 inbox/<file>`
- Read `studio-defaults.json` if it exists (the user's last answers).

## 2. Ask (AskUserQuestion, one call, up to 4 questions)
Skip any question the user's message already answers. If `studio-defaults.json` exists, make "Same as last time (<summary>)" the first option of each question.

1. **Where is it going?** Reels/TikTok/Shorts 9:16 (Recommended) · YouTube 16:9 · Both · Square
2. **How long?** Under 30s · 30–60s · 60–90s (Recommended for walkthroughs) · Keep full length
3. **Style?** My usual (content-replicator / last export) · Clone one of my past videos (ask which) · Clean, captions only · Fast cuts and zooms
4. **How many versions?** 1 · 3 different hooks · 5 variations for trial reels

If the answers raise one more decision (which past video to clone, which script from the NightLister Half-Reveal Scripts doc, music or none, CTA), ask it in ONE more AskUserQuestion call. Never more than two rounds.

## 3. Confirm the plan in 3 lines
```
Editing: <file> (<length>s) → <format>, target <length>
Style: <style>; versions: <n>; captions: <on/off>
Hooks/script: <from doc row # / user's words / none>
```
Then start, no further "OK?" unless something is irreversible.

## 4. Edit
- Creative parts stay in the main session: pick takes, write the 1–5 hook lines, check claims against `.claude/skills/content-cloner/targets/nightlister.md`.
- Hand all rendering to the `video-editor` subagent with exact paths and settings. Outputs go to `exports/<name>_<format>[_v#].mp4`.
- Cloning a past video: follow the content-cloner skill.

## 5. Finish
- Report in ≤4 lines: files made, length, what was cut, anything approximated.
- Save this session's answers to `studio-defaults.json` (format, length, style, versions, captions).
- Ask the video-editor to run `python3 tools/cleanup.py`.
