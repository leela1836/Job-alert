"""Extract the resume text for pasting into the RESUME_TEXT GitHub secret.

The PDF itself cannot be a secret: base64 of it is around 117 KB and GitHub
caps a single secret at 48 KB. Only the extracted text is ever used for skill
detection, and that is a couple of KB.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from job_alert import DEFAULT_RESUME, read_pdf_text
from models import BASE_DIR

OUTPUT_PATH = BASE_DIR / "resume_text.txt"
SECRET_LIMIT = 48 * 1024


def copy_to_clipboard(text: str) -> bool:
    if sys.platform == "win32" and shutil.which("clip"):
        subprocess.run("clip", input=text.encode("utf-16-le"), check=False)
        return True
    for tool in (["pbcopy"], ["xclip", "-selection", "clipboard"], ["wl-copy"]):
        if shutil.which(tool[0]):
            subprocess.run(tool, input=text.encode("utf-8"), check=False)
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Export resume text for the RESUME_TEXT secret")
    parser.add_argument("--resume", type=Path, default=DEFAULT_RESUME)
    parser.add_argument("--no-clipboard", action="store_true")
    args = parser.parse_args()

    if not args.resume.exists():
        raise SystemExit(f"Resume not found: {args.resume}")

    text = read_pdf_text(args.resume).strip()
    if not text:
        raise SystemExit(f"No text could be extracted from {args.resume.name}")

    OUTPUT_PATH.write_text(text, encoding="utf-8")
    size = len(text.encode("utf-8"))

    print(f"Extracted {len(text)} chars ({size / 1024:.1f} KB) from {args.resume.name}")
    print(f"GitHub secret limit is {SECRET_LIMIT // 1024} KB - "
          f"{'fits' if size < SECRET_LIMIT else 'TOO LARGE'}")
    print(f"Written to {OUTPUT_PATH.name}")

    if not args.no_clipboard and copy_to_clipboard(text):
        print("Copied to clipboard - paste it into the RESUME_TEXT secret")
    else:
        print(f"Open {OUTPUT_PATH.name}, select all, copy, "
              "then paste into the RESUME_TEXT secret")


if __name__ == "__main__":
    main()
