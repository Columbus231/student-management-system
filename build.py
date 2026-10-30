from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "frontend"
PUBLIC = ROOT / "public"


def main():
    PUBLIC.mkdir(exist_ok=True)
    shutil.copy2(SOURCE / "index.html", PUBLIC / "index.html")
    for folder in ("css", "js"):
        shutil.copytree(SOURCE / folder, PUBLIC / folder, dirs_exist_ok=True)
    print("Copied frontend assets to the Vercel public directory.")


if __name__ == "__main__":
    main()
