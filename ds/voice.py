"""Voix off : Edge-TTS (gratuit) avec horodatage mot par mot pour les sous-titres,
ou voix enregistrée par toi (mode manuel)."""
import asyncio
import json
import re
import subprocess


def audio_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


async def _edge(text, voice, rate, mp3_path):
    import edge_tts

    words = []
    comm = edge_tts.Communicate(text, voice=voice, rate=rate, boundary="WordBoundary")
    with open(mp3_path, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                words.append({"start": start, "end": start + chunk["duration"] / 1e7, "text": chunk["text"]})
    return words


def generate_edge(text, voice, rate, mp3_path, words_path):
    words = asyncio.run(_edge(text, voice, rate, mp3_path))
    if not words:
        raise RuntimeError("Edge-TTS n'a renvoyé aucun horodatage : mets à jour edge-tts (pip install -U edge-tts).")
    # Edge-TTS ne renvoie pas la ponctuation : on la raccroche depuis le texte d'origine
    tokens = re.sub(r"\s+([?!:;»])", r"\1", text).split()
    ti = 0
    for w in words:
        for j in range(ti, min(ti + 4, len(tokens))):
            if re.sub(r"\W", "", tokens[j]).lower().startswith(re.sub(r"\W", "", w["text"]).lower()[:3]):
                w["text"] = tokens[j]
                ti = j + 1
                break
    words_path.write_text(json.dumps(words, ensure_ascii=False, indent=1), encoding="utf-8")
    return words


def even_words(text, duration):
    """Mode manuel : répartit les mots uniformément (moins précis, mais suffisant)."""
    tokens = re.sub(r"\s+([?!:;»])", r"\1", text).split()
    usable = max(duration - 0.3, 1.0)
    weights = [len(t) + 2 for t in tokens]
    total, t, words = sum(weights), 0.15, []
    for tok, wgt in zip(tokens, weights):
        d = usable * wgt / total
        words.append({"start": t, "end": t + d, "text": tok})
        t += d
    return words


def chunk_words(words, max_words=3, max_chars=22):
    """Regroupe les mots en sous-titres de 1 à 3 mots, coupés à la ponctuation."""
    chunks, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        text = " ".join(x["text"] for x in cur)
        nxt = words[i + 1] if i + 1 < len(words) else None
        cut = (
            len(cur) >= max_words
            or len(text) >= max_chars
            or re.search(r"[.,!?;:]$", w["text"])
            or (nxt and nxt["start"] - w["end"] > 0.35)
            or nxt is None
        )
        if cut:
            chunks.append({"start": cur[0]["start"], "end": cur[-1]["end"], "text": text})
            cur = []
    # chaque sous-titre reste affiché jusqu'au suivant
    for a, b in zip(chunks, chunks[1:]):
        a["end"] = max(a["end"], min(b["start"], a["end"] + 0.6))
    return chunks
