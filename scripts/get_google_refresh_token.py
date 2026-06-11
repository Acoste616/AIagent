#!/usr/bin/env python3
"""Wygeneruj GOOGLE_REFRESH_TOKEN dla AI Council (Gmail/Calendar/Drive).

Zależność-free (tylko biblioteka standardowa). Uruchom NA SWOIM komputerze
(z przeglądarką). Nie wkleja ani nie loguje sekretów do żadnego modelu.

Krok po kroku:
  1. Google Cloud Console -> nowy projekt.
  2. "APIs & Services" -> Enable APIs: Gmail API (+ Calendar API / Drive API jeśli chcesz).
  3. OAuth consent screen: User type = External; dodaj SIEBIE jako Test user;
     scopes możesz zostawić puste (i tak prosimy o nie w tym skrypcie).
  4. Credentials -> Create credentials -> OAuth client ID ->
     Application type = "Desktop app". Skopiuj Client ID i Client secret.
  5. Uruchom ten skrypt:
        GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... python3 scripts/get_google_refresh_token.py
     (albo bez env — skrypt zapyta). Otworzy się przeglądarka -> zaloguj -> "Allow".
  6. Skrypt wypisze GOOGLE_REFRESH_TOKEN. Wklej trzy linie do .env na hoście:
        GOOGLE_CLIENT_ID=...
        GOOGLE_CLIENT_SECRET=...
        GOOGLE_REFRESH_TOKEN=...

Domyślne scope'y: gmail.compose (tworzenie draftów) + gmail.readonly (read-sync).
Dla Calendar/Drive dopisz w SCOPES poniżej lub ustaw env GOOGLE_OAUTH_SCOPES.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

DEFAULT_SCOPES = (
    "https://www.googleapis.com/auth/gmail.compose "
    "https://www.googleapis.com/auth/gmail.readonly "
    "https://www.googleapis.com/auth/calendar.readonly "
    "https://www.googleapis.com/auth/youtube.readonly"  # L4.107: subskrypcje YT dla Radaru
)
REDIRECT_HOST, REDIRECT_PORT = "localhost", 8765
REDIRECT_URI = f"http://{REDIRECT_HOST}:{REDIRECT_PORT}/"

_code_holder = {}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        _code_holder["code"] = (params.get("code") or [None])[0]
        _code_holder["error"] = (params.get("error") or [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = "OK — wroc do terminala, mozesz zamknac to okno." if _code_holder.get("code") else "Blad autoryzacji."
        self.wfile.write(f"<html><body><h3>{msg}</h3></body></html>".encode())

    def log_message(self, *_):
        pass


def _input(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def main():
    client_id = os.environ.get("GOOGLE_CLIENT_ID") or _input("GOOGLE_CLIENT_ID: ")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET") or _input("GOOGLE_CLIENT_SECRET: ")
    scopes = os.environ.get("GOOGLE_OAUTH_SCOPES", DEFAULT_SCOPES)
    if not client_id or not client_secret:
        print("Brak client_id/secret — przerwano.")
        return 2

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": scopes,
        "access_type": "offline",
        "prompt": "consent",
    })
    print("\nOtwieram przegladarke. Jesli sie nie otworzy, wklej recznie:\n" + auth_url + "\n")
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    server = HTTPServer((REDIRECT_HOST, REDIRECT_PORT), _Handler)
    server.handle_request()  # obsłuż jedno przekierowanie z kodem
    server.server_close()

    if _code_holder.get("error") or not _code_holder.get("code"):
        print("Brak kodu autoryzacji: " + str(_code_holder.get("error")))
        return 1

    data = urllib.parse.urlencode({
        "code": _code_holder["code"],
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode("utf-8")
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        token = json.loads(resp.read().decode("utf-8"))

    refresh = token.get("refresh_token")
    if not refresh:
        print("Nie dostalem refresh_token. Usun dostep aplikacji w https://myaccount.google.com/permissions i sprobuj ponownie (prompt=consent).")
        return 1
    out_path = os.path.expanduser("~/.ai_council_google_creds.env")
    body = (
        f"GOOGLE_CLIENT_ID={client_id}\n"
        f"GOOGLE_CLIENT_SECRET={client_secret}\n"
        f"GOOGLE_REFRESH_TOKEN={refresh}\n"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(body)
    try:
        os.chmod(out_path, 0o600)
    except OSError:
        pass
    print("\n==================== GOTOWE ====================")
    print("Zapisalem 3 klucze do pliku (poza repo, prawa 600):")
    print("  " + out_path)
    print("\nTeraz po prostu napisz do Claude: 'gotowe' — przeniose je na hosta i wlacze Gmail.")
    print("(Nie wklejaj zawartosci tego pliku do czatu.)")
    print("===============================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
