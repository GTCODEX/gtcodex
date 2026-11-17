"""Build step for Vercel: expose the dashboard as CDN-served static assets.

Vercel's Flask preset serves files in ``public/**`` from the CDN. We keep
``static/**`` as the source of truth so the local stdlib server is unchanged.
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
SOURCE = ROOT / "static"
DESTINATION = ROOT / "public"


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    copied = []
    for source_file in sorted(SOURCE.iterdir()):
        if not source_file.is_file():
            continue
        target = DESTINATION / source_file.name
        shutil.copy2(source_file, target)
        copied.append(target.name)

    wanted = set(copied)
    for stale in DESTINATION.iterdir():
        if stale.is_file() and stale.name not in wanted:
            stale.unlink()

    print(f"Copied {len(copied)} static assets into public/: {', '.join(copied)}")


if __name__ == "__main__":
    main()
