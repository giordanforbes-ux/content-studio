#!/usr/bin/env python3
"""Break a source video into a reusable blueprint: cuts, pacing, speech, beats.

Usage: python3 analyze.py SOURCE_VIDEO OUT_DIR [--no-transcribe] [--model small]
Writes OUT_DIR/blueprint.json, OUT_DIR/blueprint.md and OUT_DIR/frames/*.jpg
"""
import argparse, json, os, re, subprocess, sys


def load_audio_16k(path):
    """Decode audio with ffmpeg (avoids PyAV version issues in faster-whisper)."""
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-ac", "1",
                        "-ar", "16000", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path):
    r = run(["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,width,height,r_frame_rate",
             "-of", "json", path])
    if r.returncode != 0:
        sys.exit(f"ffprobe failed: {r.stderr.strip()}")
    d = json.loads(r.stdout)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), {})
    num, den = (v.get("r_frame_rate", "30/1").split("/") + ["1"])[:2]
    return {
        "duration": float(d["format"]["duration"]),
        "width": v.get("width"), "height": v.get("height"),
        "fps": round(float(num) / float(den or 1), 2),
        "has_audio": any(s["codec_type"] == "audio" for s in d["streams"]),
    }


def scene_cuts(path, threshold):
    r = run(["ffmpeg", "-hide_banner", "-i", path, "-vf",
             f"select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"])
    return [round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def silences(path, noise_db=-35, min_len=0.35):
    r = run(["ffmpeg", "-hide_banner", "-i", path, "-af",
             f"silencedetect=noise={noise_db}dB:d={min_len}", "-vn", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return [(round(s, 2), round(e, 2)) for s, e in zip(starts, ends)]


def loudness(path):
    r = run(["ffmpeg", "-hide_banner", "-i", path, "-af", "ebur128", "-vn", "-f", "null", "-"])
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m else None


def transcribe(path, model_name):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None, "faster-whisper not installed (pip install faster-whisper)"
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segs, _ = model.transcribe(load_audio_16k(path), word_timestamps=True, vad_filter=True,
                              initial_prompt="NightLister, eBay, Whop, Pro plan, Starter plan")
    out = []
    for s in segs:
        out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                    "words": [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)}
                              for w in (s.words or [])]})
    return out, None


def extract_frames(path, times, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    files = []
    for i, t in enumerate(times):
        f = os.path.join(out_dir, f"shot{i + 1:02d}_{t:06.2f}s.jpg")
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(t), "-i", path,
             "-frames:v", "1", "-vf", "scale=360:-2", f])
        if os.path.exists(f):
            files.append(f)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("out_dir")
    ap.add_argument("--scene-threshold", type=float, default=0.3)
    ap.add_argument("--no-transcribe", action="store_true")
    ap.add_argument("--model", default="small")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    info = probe(a.source)
    dur = info["duration"]
    cuts = [c for c in scene_cuts(a.source, a.scene_threshold) if 0.2 < c < dur - 0.2]
    bounds = [0.0] + cuts + [round(dur, 2)]
    shots = [{"n": i + 1, "start": bounds[i], "end": bounds[i + 1],
              "len": round(bounds[i + 1] - bounds[i], 2)} for i in range(len(bounds) - 1)]

    sil = silences(a.source) if info["has_audio"] else []
    lufs = loudness(a.source) if info["has_audio"] else None

    transcript, note = (None, "skipped (--no-transcribe)") if a.no_transcribe or not info["has_audio"] \
        else transcribe(a.source, a.model)

    words = [w for s in (transcript or []) for w in s["words"]]
    speech_time = sum(s["end"] - s["start"] for s in (transcript or []))
    for sh in shots:
        sh["text"] = " ".join(w["w"] for w in words if sh["start"] <= w["s"] < sh["end"])
        sh["words"] = len([w for w in words if sh["start"] <= w["s"] < sh["end"]])

    hook_words = " ".join(w["w"] for w in words if w["s"] < 3.0)
    mids = [round((s["start"] + s["end"]) / 2, 2) for s in shots]
    if len(mids) > 16:  # keep frame count small
        step = len(mids) / 16
        mids = [mids[int(i * step)] for i in range(16)]
    frames = extract_frames(a.source, mids, os.path.join(a.out_dir, "frames"))

    lens = [s["len"] for s in shots]
    bp = {
        "source": os.path.abspath(a.source),
        "video": info,
        "pacing": {
            "shots": len(shots),
            "avg_shot_sec": round(sum(lens) / len(lens), 2),
            "shortest_shot_sec": min(lens), "longest_shot_sec": max(lens),
            "cuts_per_10s": round(len(cuts) / dur * 10, 2),
        },
        "audio": {
            "integrated_lufs": lufs,
            "silences_over_0_35s": len(sil),
            "dead_air_sec": round(sum(e - s for s, e in sil), 2),
        },
        "speech": {
            "transcript_note": note,
            "words": len(words),
            "words_per_min": round(len(words) / (dur / 60), 1) if words else None,
            "speech_share": round(speech_time / dur, 2) if transcript else None,
            "hook_first_3s": hook_words,
        },
        "shots": shots,
        "transcript": transcript,
        "frames": frames,
        "beats": "TO FILL: Claude labels each shot/segment with a role (hook, problem, proof, "
                 "mechanism, demo, objection, CTA) in structure.md after viewing frames",
    }
    with open(os.path.join(a.out_dir, "blueprint.json"), "w") as f:
        json.dump(bp, f, indent=2)

    md = [f"# Blueprint: {os.path.basename(a.source)}", "",
          f"- Length: {dur:.1f}s at {info['width']}x{info['height']}, {info['fps']} fps",
          f"- Shots: {len(shots)}, avg {bp['pacing']['avg_shot_sec']}s, "
          f"{bp['pacing']['cuts_per_10s']} cuts per 10s",
          f"- Loudness: {lufs} LUFS, dead air {bp['audio']['dead_air_sec']}s",
          f"- Words: {len(words)}, {bp['speech']['words_per_min']} wpm"
          + (f" ({note})" if note else ""),
          f"- Hook (first 3s): \"{hook_words}\"", "", "| # | Start | Len | Words | Text |",
          "| --- | --- | --- | --- | --- |"]
    for s in shots:
        md.append(f"| {s['n']} | {s['start']:.1f}s | {s['len']:.1f}s | {s['words']} | {s['text'][:80]} |")
    with open(os.path.join(a.out_dir, "blueprint.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md[:7]))
    print(f"\nWrote {a.out_dir}/blueprint.json, blueprint.md and {len(frames)} frames")


if __name__ == "__main__":
    main()
