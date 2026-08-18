# Builds other/code-walkthrough.html by pulling REAL source out of src/,
# so the code shown is exactly the code that runs.
import html
import io
import os
import re

ROOT = r"C:\Users\jolian\Desktop\WRO Future Engineers 2026"
os.chdir(ROOT)

SRC = {}
for f in ("config.py", "camera.py", "robot.py", "open_challenge.py",
          "obstacle_challenge.py"):
    SRC[f] = io.open(os.path.join("src", f), encoding="utf-8").read()


def block(fname, start, end=None, dedent=False):
    """Pull source from `start` up to `end` (exclusive), or to a dedent."""
    s = SRC[fname]
    i = s.index(start)
    if end:
        j = s.index(end, i + 1)
    else:
        j = len(s)
    out = s[i:j].rstrip()
    return out


def func(fname, name):
    """Extract one top-level def/class by name, to the next top-level statement."""
    s = SRC[fname]
    m = re.search(r"^(def %s\(|class %s[\(:])" % (re.escape(name), re.escape(name)),
                  s, re.M)
    if not m:
        raise SystemExit("not found: %s in %s" % (name, fname))
    i = m.start()
    m2 = re.search(r"^(?:def |class |# =====)", s[i + 1:], re.M)
    j = i + 1 + m2.start() if m2 else len(s)
    return s[i:j].rstrip()


def method(fname, cls, name):
    """Extract one method out of a class."""
    s = SRC[fname]
    ci = s.index("class %s" % cls)
    m = re.search(r"^    def %s\(" % re.escape(name), s[ci:], re.M)
    i = ci + m.start()
    m2 = re.search(r"^    def ", s[i + 1:], re.M)
    m3 = re.search(r"^(?:class |def )", s[i + 1:], re.M)
    ends = [x.start() for x in (m2, m3) if x]
    j = i + 1 + min(ends) if ends else len(s)
    return s[i:j].rstrip()


def code(src, lang="python"):
    return '<pre class="code"><code>%s</code></pre>' % html.escape(src)


P = []
add = P.append

add('''<title>Red Castle Code Walkthrough</title>
<style>
:root{
  --ground:#F7F7F6; --surface:#FFFFFF; --sunk:#EFEFEE; --ink:#14171A;
  --muted:#5F6A70; --line:#E2E4E3; --accent:#1F7A5A; --accent-soft:#E6F2ED;
  --key:#8A4FBF; --str:#B0562A; --com:#7B858B; --num:#2F6FD0;
  --ok:#1F7A5A; --warn:#A8720C; --stop:#BE3A31;
  --mono:ui-monospace,"Cascadia Mono","Cascadia Code",Consolas,"SF Mono",Menlo,monospace;
  --sans:system-ui,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --ground:#0D1112; --surface:#141819; --sunk:#1A1F21; --ink:#E6EAEA;
  --muted:#98A3A7; --line:#242A2C; --accent:#4FC79B; --accent-soft:#10241D;
  --key:#C89BF0; --str:#E0996A; --com:#78868C; --num:#7BAEF5;
  --ok:#4FC79B; --warn:#E0AC4F; --stop:#F0736A;
}}
:root[data-theme="dark"]{
  --ground:#0D1112; --surface:#141819; --sunk:#1A1F21; --ink:#E6EAEA;
  --muted:#98A3A7; --line:#242A2C; --accent:#4FC79B; --accent-soft:#10241D;
  --key:#C89BF0; --str:#E0996A; --com:#78868C; --num:#7BAEF5;
  --ok:#4FC79B; --warn:#E0AC4F; --stop:#F0736A;
}
*{box-sizing:border-box}
body{background:var(--ground);color:var(--ink);font-family:var(--sans);
 font-size:16px;line-height:1.62;margin:0;-webkit-font-smoothing:antialiased}
.wrap{max-width:1240px;margin:0 auto;padding:0 24px 96px;display:grid;
 grid-template-columns:212px minmax(0,1fr);gap:44px;align-items:start}
@media (max-width:940px){.wrap{grid-template-columns:minmax(0,1fr);gap:0}nav.toc{display:none}}
header.top{grid-column:1/-1;padding:64px 0 34px;border-bottom:2px solid var(--ink)}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.16em;
 text-transform:uppercase;color:var(--accent);margin:0 0 16px}
h1{font-size:clamp(2.2rem,5.5vw,3.5rem);line-height:1.03;letter-spacing:-.03em;
 font-weight:700;margin:0 0 18px;text-wrap:balance}
.standfirst{font-size:1.12rem;color:var(--muted);max-width:64ch;margin:0 0 28px}
.facts{display:flex;flex-wrap:wrap;border-top:1px solid var(--line);padding-top:18px}
.fact{padding-right:32px;margin-right:32px;border-right:1px solid var(--line)}
.fact:last-child{border-right:0;margin-right:0;padding-right:0}
.fact dt{font-family:var(--mono);font-size:10px;letter-spacing:.14em;
 text-transform:uppercase;color:var(--muted);margin:0 0 3px}
.fact dd{margin:0;font-weight:600;font-size:.95rem;font-variant-numeric:tabular-nums}
nav.toc{position:sticky;top:26px;padding-top:46px;font-size:13px}
nav.toc ol{list-style:none;margin:0;padding:0}
nav.toc li{margin-bottom:1px}
nav.toc a{display:block;color:var(--muted);text-decoration:none;padding:5px 8px;
 border-left:2px solid transparent;transition:color .12s,border-color .12s}
nav.toc a:hover,nav.toc a:focus-visible{color:var(--ink);border-left-color:var(--accent)}
nav.toc .grp{font-family:var(--mono);font-size:10px;letter-spacing:.13em;
 text-transform:uppercase;color:var(--accent);margin:18px 0 5px;padding-left:8px}
main{padding-top:46px;min-width:0}
section{margin-bottom:60px;scroll-margin-top:22px}
h2{font-size:clamp(1.45rem,3vw,1.9rem);letter-spacing:-.022em;line-height:1.15;
 margin:0 0 4px;text-wrap:balance}
h2 .fn{font-family:var(--mono);font-size:.62em;color:var(--accent);
 display:block;margin-bottom:7px;letter-spacing:0}
.lede{color:var(--muted);max-width:68ch;margin:0 0 22px}
h3{font-size:1.02rem;margin:30px 0 7px;letter-spacing:-.006em;text-wrap:balance}
h3 code{font-size:.94em}
p{max-width:70ch;margin:0 0 14px}
ul,ol{max-width:70ch;padding-left:20px}li{margin-bottom:5px}
a{color:var(--accent)}strong{font-weight:650}
code{font-family:var(--mono);font-size:.875em;background:var(--sunk);
 padding:.1em .34em;border-radius:3px}
pre.code{font-family:var(--mono);font-size:12.5px;line-height:1.55;
 background:var(--surface);border:1px solid var(--line);border-radius:7px;
 padding:15px 17px;overflow-x:auto;margin:14px 0;tab-size:4}
pre.code code{background:none;padding:0;font-size:inherit;white-space:pre}
pre.cmd{font-family:var(--mono);font-size:13px;background:var(--sunk);
 border:1px solid var(--line);border-radius:6px;padding:12px 15px;
 overflow-x:auto;margin:14px 0;max-width:74ch}
.note{background:var(--surface);border:1px solid var(--line);
 border-left:3px solid var(--accent);border-radius:0 6px 6px 0;
 padding:15px 17px;margin:20px 0;max-width:74ch}
.note.bug{border-left-color:var(--stop)}
.note .tag{font-family:var(--mono);font-size:10px;letter-spacing:.14em;
 text-transform:uppercase;color:var(--accent);display:block;margin-bottom:6px}
.note.bug .tag{color:var(--stop)}
.note p{margin:0;font-size:.94rem}.note p+p{margin-top:8px}
.note pre{font-family:var(--mono);font-size:12px;background:var(--sunk);
 padding:8px 10px;border-radius:4px;overflow-x:auto;margin:8px 0;white-space:pre}
.scroll{overflow-x:auto;margin:18px 0;border:1px solid var(--line);
 border-radius:6px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:440px}
th,td{text-align:left;padding:9px 13px;border-bottom:1px solid var(--line);vertical-align:top}
thead th{font-family:var(--mono);font-size:10px;letter-spacing:.12em;
 text-transform:uppercase;color:var(--muted);font-weight:500;background:var(--sunk);white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
td.n,th.n{font-family:var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
.filehdr{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;
 border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:18px}
.filehdr .nm{font-family:var(--mono);font-size:1.05rem;font-weight:600}
.filehdr .meta{font-family:var(--mono);font-size:11px;color:var(--muted)}
.pill{font-family:var(--mono);font-size:10px;letter-spacing:.08em;text-transform:uppercase;
 padding:2px 8px;border-radius:99px;border:1px solid var(--line);color:var(--muted)}
.pill.run{border-color:var(--accent);color:var(--accent)}
footer{grid-column:1/-1;border-top:1px solid var(--line);padding-top:20px;
 color:var(--muted);font-size:13px}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:2px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>

<div class="wrap">
<header class="top">
  <p class="eyebrow">WRO 2026 Future Engineers &middot; Team The Red Castle</p>
  <h1>Every line, and why it is there</h1>
  <p class="standfirst">A complete walkthrough of the code that drives the car.
  Each excerpt below is pulled straight out of <code>src/</code>, so what you
  read here is exactly what runs on the Pi.</p>
  <dl class="facts">
    <div class="fact"><dt>Files</dt><dd>5</dd></div>
    <div class="fact"><dt>Programs you run</dt><dd>2</dd></div>
    <div class="fact"><dt>Offline tests</dt><dd>102</dd></div>
    <div class="fact"><dt>Bugs found this pass</dt><dd>3</dd></div>
  </dl>
</header>

<nav class="toc" aria-label="Contents">
<ol>
  <div class="grp">Orientation</div>
  <li><a href="#shape">The shape of it</a></li>
  <li><a href="#review">This review&rsquo;s findings</a></li>
  <div class="grp">Settings</div>
  <li><a href="#config">config.py</a></li>
  <li><a href="#camera">camera.py</a></li>
  <div class="grp">robot.py</div>
  <li><a href="#hw">Hardware &amp; button</a></li>
  <li><a href="#vision">Vision</a></li>
  <li><a href="#laps">Direction &amp; laps</a></li>
  <li><a href="#control">Control laws</a></li>
  <li><a href="#manoeuvres">Manoeuvres</a></li>
  <div class="grp">Programs</div>
  <li><a href="#open">open_challenge.py</a></li>
  <li><a href="#obstacle">obstacle_challenge.py</a></li>
  <div class="grp">Proving it</div>
  <li><a href="#tools">Tools &amp; tests</a></li>
</ol>
</nav>

<main>''')

# ---------------------------------------------------------------- shape
add('''
<section id="shape">
<h2>The shape of it</h2>
<p class="lede">Five files. Two of them are programs; the rest is support.</p>

<div class="scroll"><table>
<thead><tr><th>File</th><th>Role</th><th></th></tr></thead>
<tbody>
<tr><td class="n">open_challenge.py</td><td>Three laps, empty track</td><td><span class="pill run">run this</span></td></tr>
<tr><td class="n">obstacle_challenge.py</td><td>Three laps, traffic signs, parking exit</td><td><span class="pill run">run this</span></td></tr>
<tr><td class="n">robot.py</td><td>The car: hardware, camera, seeing, control laws</td><td><span class="pill">library</span></td></tr>
<tr><td class="n">config.py</td><td>Every number shared by both challenges</td><td><span class="pill">settings</span></td></tr>
<tr><td class="n">camera.py</td><td>Camera set-up and locked exposure</td><td><span class="pill">settings</span></td></tr>
</tbody></table></div>

<p>Both programs have the <strong>same three parts, in the same order</strong>.
Learn them once and the surprise challenge is a copy-and-edit job:</p>

<div class="scroll"><table>
<thead><tr><th class="n">Part</th><th>What it is</th><th>Why it is separate</th></tr></thead>
<tbody>
<tr><td class="n">1. TUNABLES</td><td>A block of numbers at the top</td><td>Nothing outside it should ever need editing at a venue.</td></tr>
<tr><td class="n">2. decide()</td><td>One frame in, one steering decision out</td><td>Touches no hardware and no camera, so the whole brain runs on a laptop in under a second.</td></tr>
<tr><td class="n">3. main()</td><td>LOOK &rarr; THINK &rarr; ACT, repeatedly</td><td>Identical in both programs, so a new challenge barely changes it.</td></tr>
</tbody></table></div>

<p>Sign conventions hold <em>everywhere</em>, and a lot of the code&rsquo;s
simplicity comes from them being consistent:</p>
<pre class="cmd">steering    0 = straight,  POSITIVE = RIGHT,  NEGATIVE = LEFT
direction  +1 = clockwise,     -1 = counter-clockwise
wall        a FRACTION of the image, 0..1.  BIGGER = CLOSER.</pre>
<p>Because <code>+1</code> already means &ldquo;steer right&rdquo;, several
manoeuvres reduce to <code>direction &times; angle</code> &mdash; one number
answers both &ldquo;which way round the track&rdquo; and &ldquo;which way to
turn the wheels&rdquo;.</p>
</section>
''')

# ---------------------------------------------------------------- review
add('''
<section id="review">
<h2>This review&rsquo;s findings</h2>
<p class="lede">Three real bugs, all found by reading the code against its own claims.</p>

<div class="note bug"><span class="tag">Bug 1 &middot; fixed</span>
<p><strong>The car drove during the &ldquo;stationary&rdquo; measurement.</strong>
The parking exit averages 8 frames because the car is still &mdash; the only
unblurred frames in the run. But the settle phase returned
<code>PARK_SPEED</code>, so the car rolled forward at 45&nbsp;% throughout,
defeating the entire justification. The live dryrun showed it plainly:</p>
<pre>0: park-look  steer=+0.0  speed=45     &larr; before
0: park-look  steer=+0.0  speed= 0     &larr; after</pre>
<p>The settle phase now commands <strong>speed 0</strong>.</p></div>

<div class="note bug"><span class="tag">Bug 2 &middot; fixed</span>
<p><strong>The lap timer never started when the direction was set from
outside.</strong> <code>laps.direction = X</code> skips
<code>_lock_direction()</code>, leaving <code>_last_count_t</code> at
<code>0.0</code>. Since <code>elapsed = now - 0.0</code> is then the machine&rsquo;s
entire uptime, the lockout looked permanently expired and the <em>first</em>
line crossing counted with no debounce &mdash; a car starting beside a line
would begin one quadrant ahead and stop a corner early.</p>
<p>There is now a <code>set_direction()</code> that cannot be called without
starting the timer, and all three call sites use it.</p></div>

<div class="note bug"><span class="tag">Bug 3 &middot; fixed</span>
<p><strong>A forced direction and the parking lot could contradict each
other.</strong> With <code>FORCE_DIRECTION = 1</code> but a lot measuring CCW,
the car would exit <em>left</em> and then race <em>clockwise</em> &mdash; worse
than either choice alone. The exit now obeys an already-known direction instead
of measuring.</p></div>
</section>
''')

# ---------------------------------------------------------------- config
add('''
<section id="config">
<div class="filehdr"><span class="nm">config.py</span>
<span class="meta">shared settings &middot; imports nothing</span></div>
<p class="lede">Every number both challenges share. It imports nothing, so it is
safe to edit under pressure.</p>

<h3>Pins and steering</h3>
''' + code(block("config.py", "SERVO_PIN = 13", "# ---- START / STOP BUTTON")) + '''
<p>Two steering limits, and the difference matters. <code>STEER_MAX</code> is
what normal driving uses; <code>STEER_MECH_MAX</code> is what the linkage can
physically reach. Only deliberate manoeuvres &mdash; the corner kick, the
parking exit &mdash; are allowed between them, and nothing may ever exceed the
second.</p>
''' + code(block("config.py", "STOP_FLIP_DELAY = 0.3", "SERVO_MIN_DUTY")) + '''

<h3>What counts as a wall</h3>
<p>This is the most consequential block in the file. A plain
&ldquo;dark&rdquo; test also catches the coloured lines and the mat&rsquo;s
printed dots.</p>
''' + code(block("config.py", "WALL_V_HARD = 32", "# MAGENTA COUNTS AS A WALL")) + '''

<h3>Corner-line thresholds</h3>
''' + code(block("config.py", "LINE_FRACTION_ORANGE", "# DIRECTION is decided")) + '''
<p>Two separate thresholds, because the two lines are not equally visible.
Orange is a warm colour on a warm mat and fades with distance; blue
over-triggers on bluish background. A single shared threshold is unfair to
orange, and that unfairness reversed a real run&rsquo;s direction.</p>
</section>
''')

# ---------------------------------------------------------------- camera
add('''
<section id="camera">
<div class="filehdr"><span class="nm">camera.py</span>
<span class="meta">sensor set-up</span></div>
<p class="lede">Opens the camera with everything locked, so the image does not
drift mid-run.</p>
<p>Three decisions carry the weight here:</p>
<ul>
<li><strong>Full-FOV sensor mode.</strong> The <code>raw={"size": FULL_FOV}</code>
line forces the uncropped 1296&times;972 mode. Without it the driver silently
picks a cropped mode and the lens loses much of its ~120&deg; view.</li>
<li><strong>Auto-exposure and auto-white-balance are switched OFF</strong> and
replaced with fixed values from <code>camera_settings.json</code>. Auto anything
means the colour thresholds shift under the car as it drives.</li>
<li><strong>No autofocus.</strong> The OV5647 is fixed focus &mdash; which is a
feature: the previous camera&rsquo;s autofocus kept locking onto the background
instead of the track.</li>
</ul>
''' + code(block("camera.py", "    tf = Transform(", "    return")) + '''
</section>
''')

# ---------------------------------------------------------------- hardware
add('''
<section id="hw">
<div class="filehdr"><span class="nm">robot.py</span>
<span class="meta">part 1 of 5 &middot; hardware</span></div>
<p class="lede">Pins, PWM, and the one button.</p>

<h3><code>servo()</code> &mdash; with a raisable ceiling</h3>
''' + code(func("robot.py", "servo")) + '''
<p>The <code>limit</code> argument exists for exactly one reason: the corner
kick and parking exit deliberately ask for more lock than normal driving. It
raises the ceiling for a single call and still cannot exceed the linkage.</p>

<h3><code>motor()</code> &mdash; the one that protects the hardware</h3>
''' + code(func("robot.py", "motor")) + '''
<div class="note"><span class="tag">Why the stop-and-settle is here</span>
<p>Flipping the motor straight from forward to reverse sends a reverse voltage
spike back into the regulator and kills it. So <code>motor()</code> detects the
flip itself and forces a coast first. Putting it here rather than in the calling
code means <em>no</em> caller can get it wrong &mdash; there is no path to a
direct reversal.</p></div>

<h3><code>Button</code> &mdash; start and emergency stop, one control</h3>
''' + code(method("robot.py", "Button", "wait_for_start")) + '''
''' + code(method("robot.py", "Button", "stop_pressed")) + '''
<p>Both are <strong>edge triggered</strong> and debounced, so one physical press
is one event however long you hold it. The hold-off after starting is what stops
you <em>releasing</em> the start press and having that read as a stop.</p>
</section>
''')

# ---------------------------------------------------------------- vision
add('''
<section id="vision">
<div class="filehdr"><span class="nm">robot.py</span>
<span class="meta">part 2 of 5 &middot; vision</span></div>
<p class="lede">Turning a picture into seven numbers.</p>

<h3><code>wall_mask()</code> &mdash; the two-case rule</h3>
''' + code(func("robot.py", "wall_mask")) + '''
<div class="note"><span class="tag">Measured &middot; why both cases are needed</span>
<p>Testing brightness alone accepts the blue and orange corner lines as walls
&mdash; which biased the steering on every single frame and was the real cause
of a control bug we hunted for weeks.</p>
<p>But testing saturation alone is worse: HSV saturation is numerically
unstable when brightness is low, so a genuinely black wall can report
<code>S &gt; 200</code> from sensor noise. A saturation-only test discarded
<strong>99&nbsp;%</strong> of a real nose-to-wall frame.</p></div>

<h3><code>wall_readings()</code> and <code>front_reading()</code> &mdash; distance without a distance sensor</h3>
''' + code(func("robot.py", "wall_readings")) + '''
''' + code(func("robot.py", "front_reading")) + '''
<p>The car never measures distance. It measures how much of the picture a wall
<em>fills</em>: nearer wall, more pixels. Every &ldquo;distance&rdquo; constant
in this project is really a density, which is why they all have to be
re-measured whenever the camera, its mounting, or the lighting changes.</p>

<h3><code>line_counts()</code> &mdash; and where it looks</h3>
''' + code(func("robot.py", "line_counts")) + '''
<p>Restricting the search to the bottom band is a <em>geometric</em> fix, not a
colour one: corner lines are painted on the mat, so they physically cannot
appear high in the frame. Searching the whole image let bluish background at
rows 0&ndash;13 trigger a false blue line on 41&nbsp;% of frames in one run.</p>

<h3><code>look()</code> &mdash; the whole world in one call</h3>
''' + code(func("robot.py", "look")) + '''
<p>This is why every loop starts with a single readable line. <code>View</code>
carries the five measurements plus both images, so <code>decide()</code> can do
its own colour work when it needs to.</p>
</section>
''')

# ---------------------------------------------------------------- laps
add('''
<section id="laps">
<div class="filehdr"><span class="nm">robot.py</span>
<span class="meta">part 3 of 5 &middot; direction and laps</span></div>
<p class="lede">Which way round, and how many corners so far.</p>

<h3>Reading a line crossing exactly once</h3>
''' + code(method("robot.py", "LapTracker", "_line_edges")) + '''
<p>State 0 is absent, 1 present, 2 the falling edge &mdash; the moment the
crossing is <em>over</em>. Acting on the falling edge, plus a lockout in
<strong>seconds</strong>, is what makes one physical line produce one count.</p>
<div class="note"><span class="tag">Measured &middot; why seconds, not frames</span>
<p>The original guard was 10 cycles. At 30&nbsp;fps that is 0.33&nbsp;s, and a
mask flickering above and below threshold turned one physical crossing into
<strong>36</strong> counted crossings in a 45&nbsp;s run. Every debounce in this
codebase is now a wall-clock timer, so none of them change with frame rate.</p></div>

<h3>Deciding the direction &mdash; by confidence, not pixels</h3>
''' + code(block("robot.py", "        # ---------------- PHASE 1", "        # ---------------- corner detection")) + '''
<div class="note"><span class="tag">Measured &middot; a CW run read as CCW</span>
<pre>raw pixels       blue 0.030  &gt;  orange 0.025   &rarr; wrong
own thresholds   blue 0.86x  &lt;  orange 2.08x   &rarr; right</pre>
<p>Comparing raw counts favours whichever colour the camera happens to see more
easily. Dividing each by <em>its own</em> threshold makes them comparable. And
if both look convincing at once, the car waits for a clearer frame rather than
locking a direction it can never undo.</p></div>

<h3><code>set_direction()</code> &mdash; the fix from this review</h3>
''' + code(method("robot.py", "LapTracker", "set_direction")) + '''
</section>
''')

# ---------------------------------------------------------------- control
add('''
<section id="control">
<div class="filehdr"><span class="nm">robot.py</span>
<span class="meta">part 4 of 5 &middot; control laws</span></div>

<h3><code>OuterWallFollower</code> &mdash; follow one wall, not the middle</h3>
''' + code(method("robot.py", "OuterWallFollower", "steer")) + '''
<div class="note"><span class="tag">Measured &middot; why centring failed</span>
<p>A centring controller drove into every corner. Approaching one,
<em>both</em> halves of the image darken together, so <code>left - right</code>
goes to zero &mdash; the error vanishes exactly when the car most needs to turn.
The single-wall law behaves the opposite way: the wall ahead raises the outer
reading, which steers into the turn. Corners need no dedicated code at all.</p>
<p>The <code>direction == 0</code> branch matters too: before the direction is
known, the car centres. That is safe whichever way the track runs, whereas
guessing a side is not.</p></div>

<h3><code>wall_emergency()</code> &mdash; the highest priority in both programs</h3>
''' + code(func("robot.py", "wall_emergency")) + '''
<div class="note bug"><span class="tag">Measured &middot; an override that caused the crash</span>
<p>The first version ramped up from zero. Just past the threshold it produced
<strong>&minus;0.8&deg;</strong> while the wall follower wanted
<strong>&minus;17&deg;</strong> &mdash; so the &ldquo;emergency&rdquo; seized
control and steered the car <em>into</em> the wall. It now starts at half lock
and is floored by the normal command, so it can never be the weaker choice.</p>
<p>The latch matters too: with both walls close, left and right densities
crossing each other made the escape direction flip between frames and the car
twitched in place instead of escaping.</p></div>

<h3><code>apply_bias()</code> &mdash; and where it must not go</h3>
''' + code(func("robot.py", "apply_bias")) + '''
</section>
''')

# ---------------------------------------------------------------- manoeuvres
add('''
<section id="manoeuvres">
<div class="filehdr"><span class="nm">robot.py</span>
<span class="meta">part 5 of 5 &middot; manoeuvres</span></div>
<p class="lede">Three open-loop moves. Each is time-boxed, because none of them
can see whether it has finished.</p>

<h3><code>TurnSequencer</code> &mdash; the scripted corner</h3>
''' + code(method("robot.py", "TurnSequencer", "update")) + '''
<p>Fired by <em>crossing the corner line</em>, because the line proves the car
is physically at the corner &mdash; far more reliable than waiting for a tuned
wall fraction. The clock is only a maximum; the turn exits as soon as the way
ahead is clear.</p>

<h3><code>CornerKick</code> &mdash; getting out of a corner cleanly</h3>
''' + code(method("robot.py", "CornerKick", "maybe_fire")) + '''
<div class="scroll"><table>
<thead><tr><th>Direction</th><th>Corner turns</th><th>Inner wall</th><th>Sign that pushes you inward</th><th>Kick</th></tr></thead>
<tbody>
<tr><td class="n">CW</td><td>right</td><td>right</td><td>red</td><td class="n">30&deg; right</td></tr>
<tr><td class="n">CCW</td><td>left</td><td>left</td><td>green</td><td class="n">30&deg; left</td></tr>
</tbody></table></div>
<p>The rule is one idea: <em>the sign that shoved you toward the inside is the
one that needs a big turn to recover.</em> Both trigger colours are constructor
arguments, so the opposite convention is a one-line change.</p>

<h3><code>ParkingExit</code> &mdash; the way out decides the lap direction</h3>
''' + code(method("robot.py", "ParkingExit", "update")) + '''
<div class="note"><span class="tag">Measured &middot; why black is excluded</span>
<p>Counting black wall alongside magenta cancels the measurement. The magenta
wall <em>occludes</em> the black wall behind it, so the blocked side shows
<strong>less</strong> black, while the open side looks across the track at the
far outer wall and shows more:</p>
<pre>magenta   L 0.60   R 0.05    &rarr; left is blocked
wall      L 0.40   R 0.95    &rarr; says the opposite
sum       L 1.00   R 1.00    &rarr; an exact tie</pre>
<p>The two signals are anti-correlated. Magenta alone is the honest one.</p></div>
</section>
''')

# ---------------------------------------------------------------- open
add('''
<section id="open">
<div class="filehdr"><span class="nm">open_challenge.py</span>
<span class="meta">program 1 &middot; three laps, empty track</span>
<span class="pill run">run this</span></div>

<h3>The brain</h3>
''' + code(func("open_challenge.py", "decide")) + '''
<p>Three rungs, and the order is the whole design. The emergency outranks
everything because touching a wall ends the run. The scripted turn outranks
lane keeping because during a corner the wall readings mean something different.
Lane keeping is what happens the rest of the time.</p>

<h3>The loop</h3>
''' + code(block("open_challenge.py", "            # ---------------- LOOK", "            # ---------------- RECORD")) + '''
<p>Four steps, in the same order every frame. Note that the corner line firing
the turn happens in the <em>loop</em>, not in <code>decide()</code>: crossing a
line is an event, and <code>decide()</code> only ever answers about the present
frame.</p>
</section>
''')

# ---------------------------------------------------------------- obstacle
add('''
<section id="obstacle">
<div class="filehdr"><span class="nm">obstacle_challenge.py</span>
<span class="meta">program 2 &middot; signs, parking exit</span>
<span class="pill run">run this</span></div>

<h3>Finding a sign</h3>
''' + code(func("obstacle_challenge.py", "find_sign")) + '''
<p>The aspect test does the heavy lifting. A traffic sign is a standing block,
so it is always taller than it is wide &mdash; which rejects the corner lines,
mat markings and most stray pixels without any extra tuning.</p>

<h3>Passing it, without knowing how far away it is</h3>
''' + code(func("obstacle_challenge.py", "sign_error")) + '''
<p>We never estimate distance. We push the sign toward one side of the
<em>frame</em>, and the car ends up on the correct side of it in the world. The
target slides further out as the sign gets nearer, so the car commits harder the
closer it gets rather than clipping the corner of it.</p>

<h3>The full ladder</h3>
''' + code(func("obstacle_challenge.py", "decide")) + '''

<h3>Recording which signs were passed</h3>
''' + code(method("obstacle_challenge.py", "PassLogger", "_commit")) + '''
<div class="note"><span class="tag">Two bugs this had</span>
<p><code>_last_t</code> started at <code>0.0</code>, which blocked the very
first commit &mdash; it now starts at <code>-1e9</code>. And the cooldown
originally blocked <em>different</em> signs instead of only repeats, so a green
following a red was swallowed. Both were found by replaying a real run&rsquo;s
log offline.</p></div>
</section>
''')

# ---------------------------------------------------------------- tools
add('''
<section id="tools">
<div class="filehdr"><span class="nm">tools/</span>
<span class="meta">proving it before it drives</span></div>

<pre class="cmd">python tools/test_logic.py    # 102 assertions, laptop only, no Pi
python tools/dryrun.py        # both programs, live camera, motor untouched</pre>

<p><code>test_logic.py</code> stubs <code>RPi.GPIO</code> and
<code>picamera2</code> so the real classes import on a laptop, then drives them
with synthetic numbers. <strong>Every bug described in this document has a test
pinning it</strong>, so none of them can return quietly.</p>

<div class="note bug"><span class="tag">Why this exists</span>
<p>A build once shipped with a <code>NameError</code> on a live code path
because it had only been checked with <code>py_compile</code>. Compiling proves
a file parses. It does not prove the code runs.</p></div>

<div class="scroll"><table>
<thead><tr><th>Tool</th><th>What it is for</th></tr></thead>
<tbody>
<tr><td class="n">test_logic.py</td><td>The whole brain, offline. Run before every deploy.</td></tr>
<tr><td class="n">dryrun.py</td><td>Both programs against the real camera, motor never touched.</td></tr>
<tr><td class="n">tune_colors.py</td><td>Venue recalibration: camera, then every colour, then overlap checks. Headless.</td></tr>
<tr><td class="n">tune_walls.py</td><td><code>--detector</code> re-derives what a wall is; plain calibrates density &harr; cm.</td></tr>
<tr><td class="n">button_test.py</td><td>Confirms the button wiring and that one press is one event.</td></tr>
<tr><td class="n">venue_net.sh</td><td>Wired-only networking; refuses to disable Wi-Fi unless the cable is live.</td></tr>
<tr><td class="n">servo_center.py</td><td>Finds the steering trim.</td></tr>
</tbody></table></div>

<p>Every run also writes a CSV row per frame. Nearly every number quoted in this
document and in the field manual came out of one of those logs.</p>
</section>
''')

add('''
</main>
<footer>Team The Red Castle &middot; HMK AI and Robotics Club.
Code excerpts generated directly from <code>src/</code> &mdash; if the source
changes, regenerate rather than editing this page by hand.</footer>
</div>
''')

out = "\n".join(P)
io.open("other/code-walkthrough.html", "w", encoding="utf-8", newline="\n").write(out)
print("wrote other/code-walkthrough.html  (%d chars)" % len(out))
