from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "frontend"
PUBLIC = ROOT / "public"


def main():
    shutil.copytree(SOURCE, PUBLIC, dirs_exist_ok=True)
    print("Copied frontend assets to the Vercel public directory.")


if __name__ == "__main__":
    main()
