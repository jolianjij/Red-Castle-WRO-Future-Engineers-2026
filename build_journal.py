#!/usr/bin/env python3
"""
build_journal.py — build the printable Engineering Journal.

WRO 2026 rules (Appendix C.2) expect BOTH:
  * a structured Engineering Journal (PDF or similar), and
  * a well-organised GitHub repository,
and §7 requires a HARD COPY at the international final.

This merges README.md + ENGINEERING-JOURNAL.md into one print-optimised HTML
document. Open it in a browser and use  File > Print > Save as PDF  to produce
Engineering-Journal.pdf, then print that for the hard copy.

    python build_journal.py

Only needs the `markdown` package (pip install markdown). Mermaid diagrams are
rendered by mermaid.js from a CDN, so be online the first time you print.
"""
import os
import re
import sys

try:
    import markdown
except ImportError:
    sys.exit("Missing dependency:  pip install markdown")

ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCES = ["README.md", "ENGINEERING-JOURNAL.md"]
OUT = os.path.join(ROOT, "Engineering-Journal.html")

CSS = """
@page { size: A4; margin: 16mm 14mm; }
* { box-sizing: border-box; }
body {
  font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 10.5pt; line-height: 1.5; color: #14181d;
  max-width: 190mm; margin: 0 auto; padding: 10mm;
}
h1 { font-size: 21pt; color: #a41d24; border-bottom: 3px solid #a41d24;
     padding-bottom: 6px; margin-top: 0; }
h2 { font-size: 15pt; color: #a41d24; margin-top: 22px;
     border-bottom: 1px solid #ddd; padding-bottom: 4px; page-break-after: avoid; }
h3 { font-size: 12pt; margin-top: 16px; page-break-after: avoid; }
h4 { font-size: 11pt; margin-top: 12px; page-break-after: avoid; }
p, li { orphans: 3; widows: 3; }
table { border-collapse: collapse; width: 100%; margin: 10px 0;
        font-size: 9pt; page-break-inside: avoid; }
th, td { border: 1px solid #c8ccd2; padding: 5px 7px; text-align: left;
         vertical-align: top; }
th { background: #f1f3f5; font-weight: 600; }
code { background: #f4f5f7; padding: 1px 4px; border-radius: 3px;
       font-family: Consolas, "Courier New", monospace; font-size: 9pt; }
pre { background: #f7f8fa; border: 1px solid #e2e5e9; border-radius: 4px;
      padding: 9px; overflow-x: auto; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 8.5pt; }
blockquote { border-left: 4px solid #a41d24; background: #fbf7f7;
             margin: 10px 0; padding: 8px 14px; page-break-inside: avoid; }
img { max-width: 100%; height: auto; page-break-inside: avoid; }
.cover { text-align: center; padding: 45mm 0 30mm; page-break-after: always; }
.cover img { max-width: 135mm; }
.cover h1 { border: none; font-size: 27pt; margin: 18px 0 6px; }
.cover .sub { font-size: 13pt; color: #444; }
.cover .meta { margin-top: 26mm; font-size: 11pt; color: #555; line-height: 1.9; }
.docbreak { page-break-before: always; }
.mermaid { text-align: center; page-break-inside: avoid; margin: 12px 0; }
a { color: #a41d24; text-decoration: none; }
@media print { a { color: #14181d; } body { padding: 0; } }
"""

COVER = """
<div class="cover">
  <img src="other/team-logo.jpg" alt="Team The Red Castle">
  <h1>Engineering Journal</h1>
  <div class="sub">WRO 2026 &mdash; Future Engineers (Self-Driving Cars)</div>
  <div class="meta">
    <b>Team The Red Castle</b><br>
    HMK AI and Robotics Club<br><br>
    Coach: Ahmad Kalthom<br>
    Jolian Wassof &middot; Omar Shammout &middot; Louay Rashwan<br><br>
    Repository:<br>
    github.com/jolianjij/Red-Castle-WRO-Future-Engineers-2026
  </div>
</div>
"""


def convert(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        text = f.read()
    html = markdown.markdown(
        text, extensions=["tables", "fenced_code", "attr_list", "sane_lists"]
    )
    # hand mermaid blocks to mermaid.js instead of showing them as code
    html = re.sub(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        lambda m: '<div class="mermaid">%s</div>' % _unescape(m.group(1)),
        html,
        flags=re.S,
    )
    return html


def _unescape(s):
    return (s.replace("&amp;", "&").replace("&lt;", "<")
             .replace("&gt;", ">").replace("&quot;", '"'))


def main():
    parts = []
    for i, src in enumerate(SOURCES):
        if not os.path.exists(os.path.join(ROOT, src)):
            print(f"  ! skipping missing {src}")
            continue
        cls = ' class="docbreak"' if i else ""
        parts.append(f"<section{cls}>\n{convert(src)}\n</section>")
        print(f"  + {src}")

    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Engineering Journal — Team The Red Castle — WRO 2026 Future Engineers</title>
<style>{CSS}</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>mermaid.initialize({{startOnLoad:true, theme:'neutral'}});</script>
</head><body>
{COVER}
{"".join(parts)}
</body></html>"""

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(doc)

    print(f"\nBuilt: {OUT}")
    print("Open it in a browser, then File > Print > Save as PDF (A4, background graphics ON).")


if __name__ == "__main__":
    main()
