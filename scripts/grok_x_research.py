from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path("D:/ai-council")
ENV_PATH = Path(os.environ.get("AI_COUNCIL_ENV", Path.home() / ".config" / "ai-council" / ".env"))
OUT_DIR = ROOT / "artifacts"


def load_env() -> None:
    if not ENV_PATH.exists():
        return
    for raw in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def post_json(url: str, payload: dict, timeout: int = 240) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {os.environ['XAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"error": f"http_{exc.code}", "detail": detail[:2000]}
    except URLError as exc:
        return {"error": "url_error", "detail": str(exc.reason)}
    except TimeoutError:
        return {"error": "timeout"}


def extract_text(value) -> str:
    chunks: list[str] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            node_type = str(node.get("type") or "")
            if node_type in {"output_text", "text"} and isinstance(node.get("text"), str):
                chunks.append(node["text"])
            elif isinstance(node.get("content"), str):
                chunks.append(node["content"])
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value.get("output") if isinstance(value, dict) else value)
    return "\n".join(chunk.strip() for chunk in chunks if chunk.strip())


def run_query(label: str, prompt: str, tool: dict) -> dict:
    payload = {
        "model": os.environ.get("AI_COUNCIL_GROK_X_MODEL", "grok-4.3"),
        "input": [
            {
                "role": "system",
                "content": (
                    "Jesteś Grok/X research operator dla prywatnego AI Council Bartka. "
                    "Szukaj na X, oddziel fakty od hipotez, cytuj/postuj URL-e gdy są dostępne, "
                    "i skupiaj się na funkcjach Poke, sposobie działania, UX, automatyzacjach, integracjach, "
                    "ograniczeniach, kosztach, Apple Messages oraz lekcjach do skopiowania."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "tools": [tool],
        "store": False,
    }
    data = post_json("https://api.x.ai/v1/responses", payload)
    return {
        "label": label,
        "prompt": prompt,
        "tool": tool,
        "text": extract_text(data),
        "raw": data,
    }


def main() -> int:
    load_env()
    if not os.environ.get("XAI_API_KEY"):
        print("missing XAI_API_KEY")
        return 2

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_base = OUT_DIR / f"grok-x-poke-research-{stamp}"
    out_base.mkdir(parents=True, exist_ok=True)

    queries = [
        (
            "official_poke_posts",
            (
                "Zbadaj oficjalne posty X od @interaction o Poke od 2026-03-01 do 2026-06-06. "
                "Wyciągnij: funkcje, kanały, Apple Messages/iMessage, Recipes, onboarding, demo claims, "
                "API/MCP/local machine hints, pricing/monetyzację, latency/reliability claims. "
                "Uwzględnij post/thread/status 2062575428213285352 jeśli znajdziesz."
            ),
            {
                "type": "x_search",
                "allowed_x_handles": ["interaction"],
                "from_date": "2026-03-01",
                "to_date": "2026-06-06",
                "enable_image_understanding": True,
                "enable_video_understanding": True,
            },
        ),
        (
            "founder_team_posts",
            (
                "Zbadaj posty X założycieli/teamu i zaawansowanych użytkowników o Poke. "
                "Szukaj insightów o architekturze, szybkości, Apple Messages approval, Recipes, integracjach, "
                "MCP, local/desktop bridge i realnych use case. Oddziel mocne fakty od komentarzy użytkowników."
            ),
            {
                "type": "x_search",
                "from_date": "2026-03-01",
                "to_date": "2026-06-06",
                "enable_image_understanding": True,
                "enable_video_understanding": True,
            },
        ),
        (
            "user_feedback_and_gaps",
            (
                "Zbadaj X pod kątem opinii użytkowników o Poke: co działa, co nie działa, gdzie są opóźnienia, "
                "jakie są najczęstsze zachwyty i skargi, jakie funkcje ludzie realnie używają. "
                "Na końcu daj lekcje dla prywatnego Telegram/iPhone AI Council."
            ),
            {
                "type": "x_search",
                "from_date": "2026-03-01",
                "to_date": "2026-06-06",
                "enable_image_understanding": True,
                "enable_video_understanding": True,
            },
        ),
    ]

    results = [run_query(label, prompt, tool) for label, prompt, tool in queries]
    (out_base / "raw.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Grok X Research: Poke",
        "",
        f"Created: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "Scope: X Search via xAI Responses API, Poke/Interaction posts and broader user feedback, 2026-03-01..2026-06-06.",
        "",
    ]
    for result in results:
        lines.extend(
            [
                f"## {result['label']}",
                "",
                result.get("text") or f"NO_TEXT_OUTPUT. Raw error/status: {json.dumps(result.get('raw'), ensure_ascii=False)[:1200]}",
                "",
            ]
        )
    report = "\n".join(lines)
    report_path = out_base / "report.md"
    report_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nREPORT_PATH={report_path}")
    print(f"RAW_PATH={out_base / 'raw.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
