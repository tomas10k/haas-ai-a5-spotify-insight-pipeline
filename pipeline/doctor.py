"""Check setup without ever printing a key. Run: python3 -m pipeline.doctor
Makes at most one tiny Anthropic call (about 20 tokens, a fraction of a cent) and one tiny Jev call."""
import os, sys, platform
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    print(f"python {platform.python_version()} | {platform.system()} {platform.machine()}")
    env = ROOT / ".env"
    print(f".env file present: {env.exists()}")
    try:
        from dotenv import load_dotenv
        load_dotenv(env)
    except ImportError:
        print("python-dotenv not installed: run  pip install -r requirements.txt")
    for k in ("ANTHROPIC_API_KEY", "TYPESAFE_API_KEY"):
        v = os.environ.get(k, "")
        print(f"{k}: {'set (' + str(len(v)) + ' characters)' if v else 'MISSING'}")

    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            r = anthropic.Anthropic().messages.create(
                model="claude-haiku-4-5", max_tokens=5,
                messages=[{"role": "user", "content": "Reply with the word ok."}])
            print(f"Anthropic OK: model={r.model} reply={r.content[0].text!r} usage in/out={r.usage.input_tokens}/{r.usage.output_tokens}")
        except Exception as e:
            print(f"Anthropic FAILED: {type(e).__name__}: {e}")
        try:
            import json as _j
            cfg = _j.loads((ROOT / "config" / "settings.json").read_text())
            ids = [m.id for m in anthropic.Anthropic().models.list(limit=50).data]
            print("Anthropic models on this key:", ", ".join(ids))
            mm = cfg["memo"]["model"]
            from .clients import Runtime, anthropic_call
            rt = Runtime(ROOT / "runs" / "_doctor", 1.0)
            txt, u, _ = anthropic_call(rt, model=mm, max_tokens=cfg["memo"]["max_output_tokens"], system="Answer briefly.",
                                       user="Reply with the word ok.", thinking=cfg["memo"].get("thinking"), effort=cfg["memo"].get("effort"))
            print(f"Memo model OK with memo settings (thinking={cfg['memo'].get('thinking')}, effort={cfg['memo'].get('effort')}): "
                  f"{mm} reply={txt!r} usage in/out={u['input']}/{u['output']}")
        except Exception as e:
            print(f"Memo model check FAILED: {type(e).__name__}: {e}")

    if os.environ.get("TYPESAFE_API_KEY"):
        try:
            from typesafe_sdk import TypeSafeClient, Noul
            r = TypeSafeClient().system_one(state="I love this app",
                                            questions={"positive": Noul(instructions="Is the review positive?")})
            print(f"Jev OK: {r}")
        except Exception as e:
            print(f"Jev FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    sys.exit(main())
