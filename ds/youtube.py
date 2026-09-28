"""Upload YouTube (API YouTube Data v3). Première exécution : ouvre le navigateur pour autoriser ta chaîne.
Prérequis : client_secret.json (projet Google Cloud, API YouTube Data v3 activée, identifiant OAuth "Application de bureau")."""
from pathlib import Path

from .core import ROOT

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN = ROOT / "token.json"
SECRET = ROOT / "client_secret.json"


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not SECRET.exists():
                raise SystemExit("client_secret.json introuvable : voir la section YouTube du README.")
            creds = InstalledAppFlow.from_client_secrets_file(str(SECRET), SCOPES).run_local_server(port=0)
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def upload(video: Path, thumb: Path, title, description, tags, category, privacy,
           synthetic_voice=True, publish_at=None, lang="fr"):
    from googleapiclient.http import MediaFileUpload

    yt = _service()
    status = {
        "privacyStatus": "private" if publish_at else privacy,
        "selfDeclaredMadeForKids": False,
        # Déclaration "contenu modifié ou synthétique" (voix IA réaliste)
        "containsSyntheticMedia": bool(synthetic_voice),
    }
    if publish_at:
        status["publishAt"] = publish_at  # ex : 2026-10-02T17:00:00+02:00
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags[:15],
            "categoryId": category,
            "defaultLanguage": lang,
            "defaultAudioLanguage": lang,
        },
        "status": status,
    }
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(video), chunksize=-1, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    vid = resp["id"]
    if thumb and thumb.exists():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb))).execute()
        except Exception as e:  # les miniatures perso demandent une chaîne vérifiée
            print(f"  Miniature non appliquée ({e.__class__.__name__}) : vérifie ta chaîne par téléphone.")
    return vid
