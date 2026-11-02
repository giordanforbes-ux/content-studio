#!/usr/bin/env python3
"""Apply a source blueprint's edit (pacing, punch-ins, captions, loudness) to new footage.

Usage:
  python3 apply_edit.py NEW_FOOTAGE BLUEPRINT_JSON OUT_MP4
      [--format 9x16|16x9] [--no-captions] [--no-cut] [--punch 1.15] [--model small]

Steps: cut dead air -> punch-in zooms at the source's shot rhythm -> reframe ->
-14 LUFS -> word-chunk captions. Writes OUT_MP4 and OUT_MP4.report.json.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile


def load_audio_16k(path):
    """Decode audio with ffmpeg (avoids PyAV version issues in faster-whisper)."""
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-ac", "1",
                        "-ar", "16000", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0


def run(cmd, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"Command failed: {' '.join(cmd[:6])}...\n{r.stderr[-1500:]}")
    return r


def duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    return float(r.stdout.strip())


def speech_segments(path, dur, noise_db=-35, min_gap=0.35, pad=0.08):
    r = run(["ffmpeg", "-hide_banner", "-i", path, "-af",
             f"silencedetect=noise={noise_db}dB:d={min_gap}", "-vn", "-f", "null", "-"], check=False)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    if len(ends) < len(starts):
        ends.append(dur)
    keep, cur = [], 0.0
    for s, e in zip(starts, ends):
        if s - cur > 0.05:
            keep.append((max(0.0, cur - pad), min(dur, s + pad)))
        cur = e
    if dur - cur > 0.05:
        keep.append((max(0.0, cur - pad), dur))
    merged = []
    for a, b in keep:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return merged or [(0.0, dur)]


def ass_time(t):
    h, m = int(t // 3600), int(t % 3600 // 60)
    return f"{h}:{m:02d}:{t % 60:05.2f}"


def write_captions(path, ass_path, w, h, model_name, chunk=3):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return 0, "faster-whisper not installed; captions skipped"
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segs, _ = model.transcribe(load_audio_16k(path), word_timestamps=True, vad_filter=True,
                              initial_prompt="NightLister, eBay, Whop, Pro plan, Starter plan")
    words = [wd for s in segs for wd in (s.words or [])]
    size = int(min(h * 0.04, w * 0.07))
    lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "",
             "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, "
             "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV",
             f"Style: Cap,Arial,{size},&H00FFFFFF,&H00000000,&H80000000,-1,1,{max(3, size // 12)},0,2,"
             f"{int(w * 0.08)},{int(w * 0.08)},{int(h * 0.28)}", "", "[Events]",
             "Format: Layer, Start, End, Style, Text"]
    n = 0
    for i in range(0, len(words), chunk):
        grp = words[i:i + chunk]
        text = " ".join(x.word.strip() for x in grp).upper().replace("NIGHT LISTER", "NIGHTLISTER").replace("{", "").replace("}", "")
        end = grp[-1].end if i + chunk >= len(words) else min(grp[-1].end + 0.15, words[i + chunk].start)
        lines.append(f"Dialogue: 0,{ass_time(grp[0].start)},{ass_time(end)},Cap,{text}")
        n += 1
    with open(ass_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    return n, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("footage")
    ap.add_argument("blueprint")
    ap.add_argument("out")
    ap.add_argument("--format", choices=["9x16", "16x9"], default="9x16")
    ap.add_argument("--no-captions", action="store_true")
    ap.add_argument("--no-cut", action="store_true")
    ap.add_argument("--punch", type=float, default=1.15)
    ap.add_argument("--model", default="small")
    a = ap.parse_args()

    bp = json.load(open(a.blueprint))
    beat = max(1.0, min(8.0, bp["pacing"]["avg_shot_sec"]))
    W, H = (1080, 1920) if a.format == "9x16" else (1920, 1080)
    dur = duration(a.footage)

    segs = [(0.0, dur)] if a.no_cut else speech_segments(a.footage, dur)
    sel = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in segs)
    kept = sum(e - s for s, e in segs)

    # Punch-in on alternate "shots" at the source's average shot length (looks like a cut).
    p = a.punch
    vf = (f"[0:v]select='{sel}',setpts=N/FRAME_RATE/TB,"
          f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,split[base][z];"
          f"[z]scale=iw*{p}:ih*{p},crop={W}:{H}[zoom];"
          f"[base][zoom]overlay=0:0:enable='eq(mod(floor(t/{beat:.2f}),2),1)'[v];"
          f"[0:a]aselect='{sel}',asetpts=N/SR/TB,loudnorm=I=-14:TP=-1.5:LRA=11[a]")

    tmp = tempfile.mkdtemp(prefix="clone_")
    stage1 = os.path.join(tmp, "stage1.mp4")
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", a.footage,
         "-filter_complex", vf, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
         "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", stage1])

    caps, cap_note = 0, "captions off"
    if not a.no_captions:
        ass = os.path.join(tmp, "captions.ass")
        caps, cap_note = write_captions(stage1, ass, W, H, a.model)
        if caps:
            run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", stage1,
                 "-vf", f"ass={ass}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                 "-c:a", "copy", a.out])
    if not caps:
        shutil.move(stage1, a.out)
    shutil.rmtree(tmp, ignore_errors=True)  # don't leave intermediate renders on disk

    out_dur = duration(a.out)
    report = {
        "output": os.path.abspath(a.out),
        "format": f"{W}x{H}",
        "input_sec": round(dur, 2), "output_sec": round(out_dur, 2),
        "dead_air_removed_sec": round(dur - kept, 2),
        "kept_segments": len(segs),
        "punch_in_every_sec": round(beat, 2),
        "source_avg_shot_sec": bp["pacing"]["avg_shot_sec"],
        "caption_chunks": caps, "caption_note": cap_note,
        "target_lufs": -14,
    }
    with open(a.out + ".report.json", "w") as f:
        json.dump(report, f, indent=2)
    # One short line for the model; full details stay in the .report.json file.
    print(f"OK {os.path.basename(a.out)} {report['format']} {report['output_sec']}s "
          f"(cut {report['dead_air_removed_sec']}s dead air, {caps} caption chunks) "
          f"report: {os.path.basename(a.out)}.report.json")


if __name__ == "__main__":
    main()
