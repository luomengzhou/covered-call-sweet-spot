"""Synchronize generated HTML viewers with their Markdown sources.

Run from the repository root:

    .venv/bin/python theory/_sync_docs.py
    .venv/bin/python theory/_sync_docs.py --check
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent


def derivation_html(template: str, markdown: str, *, lang: str, title: str) -> str:
    out = re.sub(r'<html lang="[^"]+">', f'<html lang="{lang}">', template, count=1)
    out = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", out, count=1)
    encoded = json.dumps(markdown, ensure_ascii=False)
    pattern = r"const md = .*?;\nmarked\.setOptions"
    replacement = f"const md = {encoded};\nmarked.setOptions"
    out, count = re.subn(pattern, replacement, out, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError("could not locate derivation Markdown payload")
    return out


def comparative_html(template: str, markdown: str) -> str:
    pattern = (
        r'(<script type="text/(?:plain|markdown)" id="md-source">\n)'
        r"(.*?)"
        r"(\n\s*</script>)"
    )
    out, count = re.subn(
        pattern,
        lambda m: m.group(1) + markdown.rstrip("\n") + m.group(3),
        template,
        count=1,
        flags=re.DOTALL,
    )
    if count != 1:
        raise RuntimeError("could not locate comparative-statics Markdown payload")
    return out


def expected_outputs() -> dict[Path, str]:
    en_md = (HERE / "00_theory_derivation_en.md").read_text()
    zh_md = (HERE / "00_theory_derivation_zh.md").read_text()
    comp_md = (HERE / "00_theory_comparative_statics.md").read_text()

    en_path = HERE / "00_theory_derivation_en.html"
    en_template = en_path.read_text()
    comp_path = HERE / "00_theory_comparative_statics.html"
    comp_template = comp_path.read_text()

    en_html = derivation_html(
        en_template,
        en_md,
        lang="en",
        title="Covered Call — Full Theoretical Derivation",
    )
    zh_html = derivation_html(
        en_html,
        zh_md,
        lang="zh-CN",
        title="备兑看涨期权——完整理论推导",
    )
    return {
        en_path: en_html,
        HERE / "00_theory_derivation_zh.html": zh_html,
        comp_path: comparative_html(comp_template, comp_md),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    stale: list[Path] = []
    for path, expected in expected_outputs().items():
        if args.check:
            if not path.exists() or path.read_text() != expected:
                stale.append(path)
        else:
            path.write_text(expected)
            print(f"wrote {path.relative_to(HERE)}")

    if stale:
        for path in stale:
            print(f"STALE {path.relative_to(HERE)}")
        return 1
    if args.check:
        print("Markdown/HTML payloads are synchronized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
