"""Chargement de la config, des secrets (.env) et gestion des projets vidéo."""
import json
import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"
IDEAS = ROOT / "ideas"

# Étapes d'un projet, dans l'ordre. Les étapes "a_valider" attendent ton feu vert (commande approve).
STEPS = [
    "donnees",           # données téléchargées
    "script_a_valider",  # script écrit par Gemini, à relire
    "script_valide",
    "voix_ok",
    "video_a_valider",   # vidéo rendue, à regarder
    "pret_a_publier",
    "publie",
]


def load_env():
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def load_config():
    with open(ROOT / "config.toml", "rb") as f:
        return tomllib.load(f)


def project_dir(slug):
    return PROJECTS / slug


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_step(slug):
    f = project_dir(slug) / "status.json"
    return read_json(f)["step"] if f.exists() else None


def set_step(slug, step):
    assert step in STEPS, step
    write_json(project_dir(slug) / "status.json", {"step": step})


def require_step(slug, *allowed):
    step = get_step(slug)
    if step not in allowed:
        raise SystemExit(
            f"[{slug}] étape actuelle : {step}. Cette commande demande : {', '.join(allowed)}."
        )
    return step
