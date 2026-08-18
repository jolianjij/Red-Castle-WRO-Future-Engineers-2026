# Builds other/api-reference.html by INTROSPECTING the real modules, so every
# signature and docstring is the one that actually exists. Regenerate; do not
# hand-edit.
import ast
import html
import io
import os

ROOT = r"C:\Users\jolian\Desktop\WRO Future Engineers 2026"
os.chdir(ROOT)

MODULES = [
    ("robot.py", "robot", "The car: hardware, camera, seeing, control. "
     "Everything below is reached as <code>R.something</code> after "
     "<code>import robot as R</code>."),
    ("obstacle_challenge.py", "obstacle_challenge",
     "The Obstacle Challenge program. Its helpers are worth knowing because a "
     "surprise challenge involving coloured objects will reuse them."),
    ("open_challenge.py", "open_challenge",
     "The Open Challenge program - the simplest complete example of the "
     "three-part shape."),
]


def sig(node):
    a = node.args
    parts = []
    defaults = [None] * (len(a.args) - len(a.defaults)) + list(a.defaults)
    for arg, d in zip(a.args, defaults):
        if arg.arg == "self":
            continue
        if d is None:
            parts.append(arg.arg)
        else:
            try:
                parts.append("%s=%s" % (arg.arg, ast.unparse(d)))
            except Exception:
                parts.append(arg.arg + "=...")
    if a.vararg:
        parts.append("*" + a.vararg.arg)
    if a.kwarg:
        parts.append("**" + a.kwarg.arg)
    return "(" + ", ".join(parts) + ")"


def returns(doc):
    """Pull a 'what it gives back' line out of the docstring if there is one."""
    if not doc:
        return ""
    low = doc.lower()
    for key in ("returns ", "return ", "-> ", "true if", "true when"):
        i = low.find(key)
        if i >= 0:
            frag = doc[i:].split("\n\n")[0].replace("\n", " ")
            return " ".join(frag.split())[:220]
    first = doc.strip().split("\n")[0]
    return first if first.startswith(("(", "[")) else ""


def collect(path):
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    funcs, classes, consts = [], [], []
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and not n.name.startswith("_"):
            funcs.append((n.name, sig(n), ast.get_docstring(n) or ""))
        elif isinstance(n, ast.ClassDef) and not n.name.startswith("_"):
            meths = []
            for m in n.body:
                if isinstance(m, ast.FunctionDef) and (
                        not m.name.startswith("_") or m.name == "__init__"):
                    meths.append((m.name, sig(m), ast.get_docstring(m) or ""))
            classes.append((n.name, ast.get_docstring(n) or "", meths))
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    try:
                        consts.append((t.id, ast.unparse(n.value)[:60]))
                    except Exception:
                        pass
    return funcs, classes, consts


def esc(t):
    return html.escape(str(t))


def para(doc, limit=None):
    """Docstring -> paragraphs, keeping indented blocks as code."""
    if not doc:
        return "<p class='nodoc'>No description.</p>"
    out, buf, code = [], [], []
    for line in doc.split("\n"):
        if line.startswith("    ") and line.strip():
            if buf:
                out.append("<p>%s</p>" % esc(" ".join(buf)))
                buf = []
            code.append(line[4:])
        elif not line.strip():
            if buf:
                out.append("<p>%s</p>" % esc(" ".join(buf)))
                buf = []
            if code:
                out.append("<pre>%s</pre>" % esc("\n".join(code)))
                code = []
        else:
            if code:
                out.append("<pre>%s</pre>" % esc("\n".join(code)))
                code = []
            buf.append(line.strip())
    if buf:
        out.append("<p>%s</p>" % esc(" ".join(buf)))
    if code:
        out.append("<pre>%s</pre>" % esc("\n".join(code)))
    return "".join(out[:limit] if limit else out)


P = []
add = P.append
add('''<title>Red Castle API Reference</title>
<style>
:root{--ground:#FAFAF9;--surface:#fff;--sunk:#F0F0EE;--ink:#16181A;--muted:#61686E;
--line:#E3E4E2;--accent:#7A4FBF;--sig:#0B6E5F;--warn:#A8620C;
--mono:ui-monospace,"Cascadia Mono",Consolas,"SF Mono",Menlo,monospace;
--sans:system-ui,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
--ground:#0C0D0F;--surface:#141619;--sunk:#1A1D20;--ink:#E8EAEC;--muted:#98A0A6;
--line:#24272B;--accent:#B48CF0;--sig:#5FCFB8;--warn:#E0A552}}
:root[data-theme="dark"]{--ground:#0C0D0F;--surface:#141619;--sunk:#1A1D20;
--ink:#E8EAEC;--muted:#98A0A6;--line:#24272B;--accent:#B48CF0;--sig:#5FCFB8;--warn:#E0A552}
*{box-sizing:border-box}
body{background:var(--ground);color:var(--ink);font-family:var(--sans);font-size:15.5px;
line-height:1.6;margin:0}
.wrap{max-width:1180px;margin:0 auto;padding:0 24px 90px;display:grid;
grid-template-columns:230px minmax(0,1fr);gap:44px;align-items:start}
@media(max-width:940px){.wrap{grid-template-columns:minmax(0,1fr);gap:0}nav.toc{display:none}}
header.top{grid-column:1/-1;padding:60px 0 30px;border-bottom:2px solid var(--ink)}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;
color:var(--accent);margin:0 0 14px}
h1{font-size:clamp(2.1rem,5vw,3.2rem);line-height:1.04;letter-spacing:-.03em;margin:0 0 16px}
.standfirst{color:var(--muted);max-width:64ch;margin:0 0 24px;font-size:1.08rem}
nav.toc{position:sticky;top:24px;padding-top:44px;font-size:13px}
nav.toc a{display:block;color:var(--muted);text-decoration:none;padding:3px 8px;
border-left:2px solid transparent}
nav.toc a:hover,nav.toc a:focus-visible{color:var(--ink);border-left-color:var(--accent)}
nav.toc .grp{font-family:var(--mono);font-size:10px;letter-spacing:.13em;text-transform:uppercase;
color:var(--accent);margin:16px 0 4px;padding-left:8px}
main{padding-top:44px;min-width:0}
section{margin-bottom:46px;scroll-margin-top:20px}
h2{font-size:1.7rem;letter-spacing:-.02em;margin:0 0 4px}
h2 .m{font-family:var(--mono);font-size:.62em;color:var(--muted);display:block}
.lede{color:var(--muted);max-width:70ch;margin:0 0 20px}
.item{background:var(--surface);border:1px solid var(--line);border-radius:7px;
padding:14px 16px;margin:10px 0;scroll-margin-top:20px}
.item .name{font-family:var(--mono);font-size:.95rem;font-weight:600;color:var(--sig)}
.item .args{font-family:var(--mono);font-size:.9rem;color:var(--muted)}
.item p{margin:8px 0 0;font-size:.93rem;max-width:74ch}
.item p.nodoc{color:var(--muted);font-style:italic}
.item pre{font-family:var(--mono);font-size:12px;background:var(--sunk);padding:9px 11px;
border-radius:5px;overflow-x:auto;margin:8px 0;white-space:pre}
.ret{display:block;margin-top:8px;font-size:.86rem;color:var(--muted);
border-left:2px solid var(--accent);padding-left:9px}
.ret b{color:var(--ink);font-weight:600}
.cls{border-left:3px solid var(--accent)}
.meth{margin-left:18px;border-left:2px solid var(--line)}
.scroll{overflow-x:auto;margin:14px 0;border:1px solid var(--line);border-radius:6px;
background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:13px;min-width:420px}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--line)}
thead th{font-family:var(--mono);font-size:10px;letter-spacing:.11em;text-transform:uppercase;
color:var(--muted);background:var(--sunk);font-weight:500}
tbody tr:last-child td{border-bottom:0}
td.n{font-family:var(--mono);white-space:nowrap}
code{font-family:var(--mono);font-size:.87em;background:var(--sunk);padding:.1em .32em;border-radius:3px}
pre.cmd{font-family:var(--mono);font-size:12.5px;background:var(--sunk);border:1px solid var(--line);
border-radius:6px;padding:12px 14px;overflow-x:auto;max-width:74ch}
.note{background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--warn);
border-radius:0 6px 6px 0;padding:13px 15px;margin:16px 0;max-width:74ch;font-size:.93rem}
footer{grid-column:1/-1;border-top:1px solid var(--line);padding-top:18px;color:var(--muted);font-size:13px}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
</style>
<div class="wrap">
<header class="top">
<p class="eyebrow">WRO 2026 Future Engineers &middot; Team The Red Castle</p>
<h1>Everything you can call</h1>
<p class="standfirst">Every function, class and method in the car&rsquo;s code &mdash;
what it takes, what it gives back. Generated by reading the source, so a signature
here is the signature that exists.</p>
</header>
<nav class="toc" aria-label="Contents">
<div class="grp">Start here</div>
<a href="#start">The shape of a program</a>
<a href="#recipes">Common recipes</a>''')

data = []
for fn, mod, blurb in MODULES:
    funcs, classes, consts = collect(os.path.join("src", fn))
    data.append((fn, mod, blurb, funcs, classes, consts))
    add('<div class="grp">%s</div>' % esc(fn))
    for n, _, _ in funcs:
        add('<a href="#%s-%s">%s()</a>' % (mod, n, esc(n)))
    for c, _, _ in classes:
        add('<a href="#%s-%s">%s</a>' % (mod, c, esc(c)))

add('</nav>\n<main>')

add('''<section id="start">
<h2>The shape of a program</h2>
<p class="lede">Both challenges are the same three parts. A new one is a copy
with a different <code>decide()</code>.</p>
<pre class="cmd">import robot as R

# 1. TUNABLES ................ numbers at the top, nothing else to edit

# 2. decide(view, ...) ....... one frame in, one steering decision out.
#                              No hardware, no camera - pure arithmetic,
#                              so tools/test_logic.py can drive it.

# 3. main() .................. LOOK -> THINK -> ACT
button = R.Button()
cam    = R.open_camera()
button.wait_for_start("My Challenge")
R.motor(70)
while True:
    view = R.look(cam)                  # LOOK   everything measured
    d    = decide(view)                 # THINK  one decision
    R.servo(d.steer); R.motor(speed)    # ACT
    if button.stop_pressed(): break
R.motor(0); R.shutdown(); cam.close()</pre>

<p><strong>Sign conventions hold everywhere.</strong> Getting these wrong is the
most common way a new challenge misbehaves:</p>
<pre class="cmd">steering    0 = straight,  POSITIVE = RIGHT,  NEGATIVE = LEFT
direction  +1 = clockwise,      -1 = counter-clockwise
wall        a FRACTION 0..1 of the image.  BIGGER = CLOSER.</pre>

<h3>What <code>R.look()</code> gives you</h3>
<div class="scroll"><table>
<thead><tr><th>field</th><th>type</th><th>meaning</th></tr></thead>
<tbody>
<tr><td class="n">view.left</td><td class="n">float 0..1</td><td>how much of the LEFT half is wall. Bigger = closer.</td></tr>
<tr><td class="n">view.right</td><td class="n">float 0..1</td><td>the same for the right half</td></tr>
<tr><td class="n">view.front</td><td class="n">float 0..1</td><td>the same straight ahead. High means a corner.</td></tr>
<tr><td class="n">view.blue</td><td class="n">float 0..1</td><td>blue corner line in the bottom band</td></tr>
<tr><td class="n">view.orange</td><td class="n">float 0..1</td><td>orange corner line in the bottom band</td></tr>
<tr><td class="n">view.hsv</td><td class="n">ndarray</td><td>the HSV image, for your own colour work</td></tr>
<tr><td class="n">view.proc</td><td class="n">ndarray</td><td>the BGR image, for saving annotated frames</td></tr>
</tbody></table></div>
</section>

<section id="recipes">
<h2>Common recipes</h2>
<p class="lede">The handful of things a surprise challenge almost always needs.</p>

<h3>Is there a lot of some colour, and where?</h3>
<pre class="cmd">n   = R.color_count(view.hsv, "red")                    # pixels, whole frame
f   = R.color_count(view.hsv, "red", as_fraction=True)  # 0.0 .. 1.0
lf  = R.color_count(view.hsv, "red", "left",  as_fraction=True)
rf  = R.color_count(view.hsv, "red", "right", as_fraction=True)
steer = 20.0 if lf &gt; rf else -20.0     # turn away from whichever side has more</pre>
<div class="note"><strong>Compare fractions, not counts.</strong> A raw count
depends on how big the region is, so comparing two differently sized regions by
count is a mistake that looks fine until it is not.</div>

<h3>Find an object, not just pixels</h3>
<pre class="cmd">blobs = R.color_blobs(view.hsv, "green", min_area=70, tall_only=True)
if blobs:
    area, cx, cy, x, y, w, h = blobs[0]      # biggest first
    steer = (cx - 160) * 0.2                 # steer toward it</pre>
<p><code>tall_only</code> keeps only objects taller than they are wide &mdash;
which is what separates a standing sign from a line, a marking, or a patch of
floor.</p>

<h3>Do not hit anything</h3>
<pre class="cmd">escape = R.wall_emergency(view.left, view.right, outer, direction)
if escape is not None:
    return Decision(escape, "emergency")     # ALWAYS the first rung</pre>

<h3>Save the frames that mattered</h3>
<pre class="cmd">rec = R.FrameRecorder()                       # clears frames/ at the start
rec.moment(view, "found-the-thing", t,
           lines=["area %d" % area],
           boxes=[(x, y, w, h, (0,255,0), "target")])
rec.write_index()                             # frames/00-WHAT-HAPPENED.txt</pre>
</section>''')

for fn, mod, blurb, funcs, classes, consts in data:
    add('<section id="%s"><h2><span class="m">%s</span>%s</h2><p class="lede">%s</p>'
        % (mod, esc(fn), esc(mod), blurb))
    for n, s_, doc in funcs:
        r = returns(doc)
        add('<div class="item" id="%s-%s"><span class="name">%s</span>'
            '<span class="args">%s</span>%s%s</div>'
            % (mod, n, esc(n), esc(s_), para(doc),
               ('<span class="ret"><b>gives back</b> %s</span>' % esc(r)) if r else ""))
    for c, cdoc, meths in classes:
        add('<div class="item cls" id="%s-%s"><span class="name">class %s</span>%s</div>'
            % (mod, c, esc(c), para(cdoc)))
        for mn, ms, mdoc in meths:
            r = returns(mdoc)
            label = "%s(...)" % c if mn == "__init__" else "%s.%s" % (c, mn)
            add('<div class="item meth"><span class="name">%s</span>'
                '<span class="args">%s</span>%s%s</div>'
                % (esc(label), esc(ms), para(mdoc, limit=3),
                   ('<span class="ret"><b>gives back</b> %s</span>' % esc(r)) if r else ""))
    if consts:
        add('<div class="scroll"><table><thead><tr><th>constant</th>'
            '<th>value</th></tr></thead><tbody>')
        for k, v in consts[:40]:
            add("<tr><td class='n'>%s</td><td class='n'>%s</td></tr>" % (esc(k), esc(v)))
        add("</tbody></table></div>")
    add("</section>")

add('''</main>
<footer>Generated from <code>src/</code> by <code>other/build-api-reference.py</code>.
Regenerate after changing the code rather than editing this page.</footer>
</div>''')

out = "\n".join(P)
io.open("other/api-reference.html", "w", encoding="utf-8", newline="\n").write(out)
print("wrote other/api-reference.html (%d chars)" % len(out))
