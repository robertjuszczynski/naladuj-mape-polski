"""Lektor z ElevenLabs: jeden plik mp3 na scenę + lektor/durations.json.

Klucz: ~/.config/elevenlabs/key. Głos: ELEVEN_VOICE_ID albo automatycznie
najpopularniejszy polski, męski głos narratora z biblioteki ElevenLabs.
"""

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

B = Path(__file__).resolve().parent
OUT = B.parent / "lektor"
API = "https://api.elevenlabs.io/v1"
MODEL = "eleven_multilingual_v2"
SETTINGS = {"stability": 0.55, "similarity_boost": 0.8, "style": 0.15, "use_speaker_boost": True}


def key():
    k = (Path.home() / ".config/elevenlabs/key").read_text().strip()
    if not k or " " in k:
        sys.exit("W ~/.config/elevenlabs/key nie ma klucza API ElevenLabs.")
    return k


def call(path, k, body=None, raw=False):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"xi-api-key": k, "Content-Type": "application/json", "User-Agent": "aed-video/1.0"},
                                 method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    return data if raw else json.loads(data)


def pick_voice(k):
    if os.environ.get("ELEVEN_VOICE_ID"):
        return os.environ["ELEVEN_VOICE_ID"]
    q = "/shared-voices?language=pl&gender=male&page_size=20&sort=usage_character_count_1y"
    voices = call(q, k).get("voices", [])
    calm = [v for v in voices if (v.get("use_case") or "") in ("narrative_story", "informative_educational", "narration")]
    v = (calm or voices)[0]
    print("głos:", v["name"], v["voice_id"])
    try:
        call("/voices/add/%s/%s" % (v["public_owner_id"], v["voice_id"]), k, {"new_name": "Lektor AED – " + v["name"]})
    except Exception as e:
        print("dodanie do biblioteki pominięte:", e)
    return v["voice_id"]


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout
    return round(float(out.strip()), 3)


def main():
    k = key()
    voice = pick_voice(k)
    script = json.loads((B / "scenariusz.json").read_text())
    OUT.mkdir(exist_ok=True)
    only = [x for x in os.environ.get('ONLY', '').split(',') if x]
    dpath = OUT / 'durations.json'
    durs = json.loads(dpath.read_text()) if only and dpath.exists() else {}
    for i, seg in enumerate(script):
        if only and seg['id'] not in only:
            continue
        body = {"text": seg["tts"], "model_id": MODEL, "voice_settings": SETTINGS,
                "previous_text": script[i - 1]["tts"] if i else None,
                "next_text": script[i + 1]["tts"] if i + 1 < len(script) else None}
        mp3 = OUT / (seg["id"] + ".mp3")
        mp3.write_bytes(call("/text-to-speech/%s?output_format=mp3_44100_128" % voice, k, body, raw=True))
        durs[seg["id"]] = duration(mp3)
        print(seg["id"], durs[seg["id"]], "s")
    (OUT / "durations.json").write_text(json.dumps(durs, indent=1))


if __name__ == "__main__":
    main()
