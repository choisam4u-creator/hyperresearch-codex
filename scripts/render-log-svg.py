#!/usr/bin/env python3
"""실행 로그(stderr 의 `[hpr HH:MM:SS] …` 줄)를 README 용 터미널 그림(SVG)으로 만든다. 외부 도구 없음.

사용: python3 scripts/render-log-svg.py research/logs/<run>.log docs/assets/run.svg [--seconds 24] [--static]
  --seconds N  실제 경과를 N초 애니메이션으로 압축(기본 24). --static 이면 애니메이션 없이 전체를 보여 준다.
"""
import html
import re
import sys
import unicodedata
from pathlib import Path

LINE = re.compile(r"^\[hpr (\d\d):(\d\d):(\d\d)\] (.*)$")
W, PAD, LH, FONT, MAXCELLS = 1120, 18, 19, 13, 84
HOME = re.compile(r"/(?:Users|home)/[^/\s]+/\S*?/(?=research/)")   # 절대 경로의 개인 부분은 지운다


def parse(text: str):
    rows, base = [], None
    for raw in text.splitlines():
        m = LINE.match(raw.rstrip())
        if not m:
            continue
        h, mi, s, body = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
        t = h * 3600 + mi * 60 + s
        base = t if base is None else base
        if t < base:            # 자정 넘김
            t += 86400
        rows.append((t - base, f"{m.group(1)}:{m.group(2)}:{m.group(3)}", body))
    return rows


def color(body: str) -> str:
    if "BLOCKED" in body or "Traceback" in body or " ! " in body:
        return "#ff7b72"
    if "완료 →" in body or "최종 보고서" in body or re.search(r": ok\b", body):
        return "#7ee787"
    if body.lstrip().startswith(("→", "←")):
        return "#79c0ff"
    if "…" in body:
        return "#8b949e"
    if re.match(r"\[\d+/\d+\]", body):
        return "#e6edf3"
    return "#c9d1d9"


def clip(text: str, cells: int = MAXCELLS) -> str:
    used, out = 0, []
    for ch in text:
        used += 2 if unicodedata.east_asian_width(ch) in "WF" else 1
        if used > cells - 1:
            return "".join(out) + "…"
        out.append(ch)
    return text


def render(rows, seconds: float, static: bool) -> str:
    total = max((t for t, _, _ in rows), default=1) or 1
    height = PAD * 2 + 34 + LH * (len(rows) + 1)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}" font-family="SFMono-Regular,Menlo,Consolas,monospace" font-size="{FONT}">',
           f'<rect width="{W}" height="{height}" rx="10" fill="#0d1117"/>',
           '<circle cx="22" cy="20" r="6" fill="#ff5f56"/><circle cx="42" cy="20" r="6" fill="#ffbd2e"/><circle cx="62" cy="20" r="6" fill="#27c93f"/>',
           f'<text x="{W/2}" y="25" text-anchor="middle" fill="#8b949e" font-size="12">hpr run … --preset lean · {total//60}분 {total%60:02d}초 실측</text>']
    y = PAD + 34 + LH
    for i, (t, stamp, body) in enumerate(rows):
        begin = t / total * seconds
        anim = "" if static else f'<set attributeName="opacity" to="1" begin="{begin:.2f}s" fill="freeze"/>'
        op = "1" if static else "0"
        shown = clip(HOME.sub("", body))   # 넘치는 줄은 잘라서 오른쪽이 안 잘리게(한글은 2칸으로 센다)
        out.append(f'<g opacity="{op}">{anim}<text x="{PAD}" y="{y}" fill="#6e7681">[hpr {stamp}]</text>'
                   f'<text x="{PAD + 118}" y="{y}" fill="{color(body)}">{html.escape(shown, quote=True)}</text></g>')
        y += LH
    out.append("</svg>")
    return "\n".join(out)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        sys.exit(__doc__)
    seconds = float(sys.argv[sys.argv.index("--seconds") + 1]) if "--seconds" in sys.argv else 24.0
    rows = parse(Path(args[0]).read_text(encoding="utf-8", errors="replace"))
    if not rows:
        sys.exit("hpr 로그 줄이 없다")
    Path(args[1]).parent.mkdir(parents=True, exist_ok=True)
    Path(args[1]).write_text(render(rows, seconds, "--static" in sys.argv), encoding="utf-8")
    print(f"{args[1]}: {len(rows)}줄, 실측 {rows[-1][0]}초")


if __name__ == "__main__":
    main()
