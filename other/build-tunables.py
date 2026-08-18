# Builds other/tunables.html - every knob, what it does, and which way to move
# it. Current values are READ FROM THE SOURCE, so the page cannot drift.
import ast
import html
import io
import os
import re

ROOT = r"C:\Users\jolian\Desktop\WRO Future Engineers 2026"
os.chdir(ROOT)


def values(path):
    out = {}
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    for n in tree.body:
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    try:
                        out[t.id] = ast.unparse(n.value)
                    except Exception:
                        out[t.id] = "?"
    return out


CFG = values("src/config.py")
OBS = values("src/obstacle_challenge.py")
OPN = values("src/open_challenge.py")


def v(name, *srcs):
    """The current value. When the two challenges disagree, show BOTH - one
    number would be a lie about the other file."""
    found = []
    for s in srcs:
        if s and name in s:
            t = s[name]
            found.append(t if len(t) < 30 else t[:27] + "...")
    if not found:
        return "—"
    if len(found) > 1 and found[0] != found[1]:
        return "open %s / obs %s" % (found[0], found[1])
    return found[0]


def esc(t):
    return html.escape(str(t))


# name, where, what it does, raise it when, lower it when
GROUPS = [
 ("Where the car drives", "The racing line, and how hard it holds it.", [
  ("LANE_DISTANCE_CM", OPN, OBS,
   "How far from the OUTER wall to drive, in centimetres. Converted to a density "
   "by the measured slope, so this is the one distance you set in real units.",
   "you want a wider, safer line",
   "the track is tight or it keeps meeting the inner wall"),
  ("OUTER_KP", CFG, None,
   "How hard it steers back toward the target line. Degrees per unit of density error.",
   "it drifts off line and is slow to come back",
   "it weaves or oscillates down a straight"),
  ("OUTER_KD", CFG, None,
   "Damping. Reacts to how fast the error is CHANGING, which is what settles a weave.",
   "it overshoots and hunts around the line",
   "steering feels twitchy or jerky"),
  ("OUTER_DEADBAND", CFG, None,
   "Errors smaller than this are treated as zero, so the car stops chasing noise.",
   "it fidgets constantly while basically on line",
   "it sits off-line and never corrects"),
  ("STEER_BIAS", CFG, None,
   "Mechanical drift trim, added to lane keeping only. NEGATIVE pushes LEFT. "
   "It is deliberately NOT applied to corners or manoeuvres, which need the full range.",
   "it consistently drifts right (make it more negative)",
   "it now hugs the left wall (toward 0)"),
 ]),
 ("Not hitting things", "The escape, and the one number that decides when it fires.", [
  ("WALL_EMERGENCY", CFG, None,
   "The density at which the escape takes over completely. Bigger number = closer wall. "
   "This is the single most safety-critical value in the car.",
   "it panics far from walls and drives erratically",
   "it gets too close before reacting"),
  ("STEER_MAX", CFG, None,
   "The steering limit used in normal driving. Manoeuvres may exceed it deliberately.",
   "it cannot get round corners",
   "it is unstable at speed"),
  ("STEER_MECH_MAX", CFG, None,
   "The linkage's REAL limit. Nothing may ever exceed this. Not a tuning knob — "
   "a physical fact about the car. Changing it beyond the true limit will stall the servo.",
   "you rebuilt the steering with more travel",
   "you rebuilt it with less"),
  ("SIGN_WALL_GUARD", OBS, None,
   "Where the sign steering starts fading as it aims at a wall, as a fraction of "
   "WALL_EMERGENCY. The sign law has no idea walls exist; this is what stops it "
   "driving into one to place a pillar. 1.0 disables it.",
   "signs are being missed because it gives up too early",
   "it still steers into walls chasing signs"),
 ]),
 ("Which way round the track", "Get this wrong and the whole run is lost.", [
  ("LINE_FRACTION_ORANGE", CFG, None,
   "How much orange must be in the bottom band to count as the orange line. "
   "Orange is the FAINT one — warm colour on a warm mat — so its bar sits low.",
   "the mat or a warm object is triggering orange",
   "real orange crossings are being missed"),
  ("LINE_FRACTION_BLUE", CFG, None,
   "The same for blue. Blue OVER-triggers on bluish background and mat cast, so its "
   "bar sits much higher. Measured on this car: real crossings peak ≥0.114, "
   "background noise ≤0.084.",
   "blue is triggering on the mat (the usual fault)",
   "real blue crossings are being missed"),
  ("LINE_DIR_MIN_RATIO", CFG, None,
   "How decisively one colour must beat the other before the direction locks. Below "
   "this the frame is called ambiguous and it waits for a clearer one.",
   "the direction is sometimes decided wrongly",
   "it never manages to decide at all"),
  ("LINE_ROWS", CFG, None,
   "How much of the bottom of the image is searched for lines. The lines are painted "
   "on the mat, so anything higher up cannot be one. A GEOMETRIC filter — it works "
   "without depending on colour tuning at all.",
   "lines are seen too late",
   "background above the mat is triggering a line"),
  ("LINE_LOCKOUT_S", CFG, None,
   "After a line is read, that colour is ignored for this long. In SECONDS, never "
   "frames: the old 10-frame guard was 0.33 s and turned one crossing into 36.",
   "one crossing is counted several times",
   "two genuinely close corners are being merged"),
 ]),
 ("Corners", "Turning, and getting out cleanly.", [
  ("FRONT_TURN_BACKUP", CFG, None,
   "How blocked the way ahead must be before geometry forces a turn without a line. "
   "The safety net for a missed corner line.",
   "it turns too eagerly on straights",
   "it drives into corners when a line is missed"),
  ("KICK_ANGLE", OBS, None,
   "The fixed hard turn out of a corner, in degrees. May exceed STEER_MAX — that is "
   "the point — but is capped at STEER_MECH_MAX, so a bigger number here silently "
   "does nothing past that.",
   "it cuts corners",
   "it swings too wide"),
  ("KICK_TIME_S", OBS, None,
   "How long that kick is held. NOT MEASURED — this is still an estimate; nobody has "
   "timed how fast this car rotates.",
   "it does not come round far enough",
   "it over-rotates"),
  ("KICK_SIGN_CW", OBS, None,
   "Which sign colour arms the kick when running clockwise. Depends on which side the "
   "sign pushed the car toward, so it flips with direction.",
   "—", "swap with KICK_SIGN_CCW if the kick fires at the wrong corners"),
 ]),
 ("Traffic signs", "Green and red are tuned SEPARATELY, and genuinely need to be.", [
  ("GREEN_MIN_AREA", OBS, None,
   "Smallest green blob that counts as a sign. Measured on a real run: green arrives "
   "at a MEDIAN AREA of 186 px against red's 718, so the two are not interchangeable.",
   "it chases distant green specks",
   "it notices green signs too late"),
  ("RED_MIN_AREA", OBS, None, "The same for red.",
   "it chases distant red specks", "it notices red signs too late"),
  ("GREEN_MIN_ASPECT", OBS, None,
   "height ÷ width. A standing sign is taller than it is wide; this is what rejects "
   "lines, markings and patches of floor. 1.0 means simply 'taller than wide'.",
   "floor patches or lines are being called signs",
   "real signs are being rejected as too wide"),
  ("GREEN_TARGET_X", OBS, None,
   "The image column a GREEN sign is pushed toward. Centre is 160, so >160 drives the "
   "sign right and the car passes on its LEFT. Further from 160 = a wider berth.",
   "it passes too close to green",
   "it swings too far out around green"),
  ("RED_TARGET_X", OBS, None,
   "The same for red, but <160 so the car passes on its RIGHT.",
   "—", "further from 160 for a wider berth"),
  ("GREEN_KP", OBS, None,
   "How hard it steers per unit of sign error. Saturates to full lock quickly if high.",
   "it reacts too slowly to green", "it slams to full lock at every green"),
  ("SIGN_HOLD_S", OBS, None,
   "After the last sighting, how long before lane keeping may resume. Stops the wall "
   "follower dragging the car back across a pass it is halfway through.",
   "it abandons passes halfway",
   "it drives blind too long after each sign"),
  ("SIGN_STEER_HOLD_S", OBS, None,
   "Of that hold, how long it keeps STEERING as the sign commanded before running "
   "straight. The remainder is straight-line driving with NO lane keeping — only the "
   "wall escape catches it, so a big gap between these two is time spent driving blind.",
   "it stops steering too early mid-pass",
   "it keeps turning after it has cleared the sign"),
 ]),
 ("The parking lot", "One measurement that answers two questions.", [
  ("PARK_START", OBS, None,
   "Whether the run begins inside the magenta lot. Also adds +1 to the stop quadrant, "
   "because no line crossing is spent determining the direction.",
   "—", "set False if starting on the track"),
  ("PARK_MIN_MAGENTA", OBS, None,
   "How much magenta one side needs before the car will trust the measurement. Below "
   "it, the car REFUSES to guess and leaves the direction to the corner lines — which "
   "is right, because a wrong direction ruins the run.",
   "it guesses from too little evidence",
   "it refuses when it really is in the lot"),
  ("PARK_INVERT", OBS, None,
   "One-line venue fix. WHICH side is blocked is measured reliably; whether 'blocked "
   "on the left' means clockwise is a fact about your track's layout that the code "
   "cannot check.",
   "—", "set True if it reads the lot correctly but leaves the wrong way"),
  ("PARK_ANGLE", OBS, None,
   "Steering lock while pulling out. Capped at STEER_MECH_MAX, so anything above that "
   "silently does nothing.",
   "the exit is too wide", "it clips the lot wall on the way out"),
  ("PARK_USE_WALL", OBS, None,
   "Count black wall as well as magenta when deciding. OFF: magenta alone is the "
   "direct signal, since the lot is DEFINED by magenta whereas black is every wall "
   "on the track.",
   "—", "on only if magenta's margin is marginal and the wall's is not"),
  ("MAGENTA_IS_WALL", CFG, None,
   "The STARTING value only. It changes during a run: magenta is the LOT while leaving "
   "(so the escape does not fight the exit) and becomes a WALL the moment the car is "
   "out, for the rest of the run.",
   "—", "—"),
 ]),
 ("Speed and finishing", "", [
  ("CRUISE", OPN, OBS,
   "Straight-line speed, in percent. Falls automatically with steering.",
   "for a faster lap", "if it cannot hold the line, or corners badly"),
  ("SPEED_CORNER_CUT", CFG, None,
   "How much of that speed is given up at full steering. 0.5 = half speed.",
   "it is unstable in corners", "corners are costing too much time"),
  ("MIN_SPEED", CFG, None,
   "Never command less than this while driving — below it the motor stalls rather "
   "than crawling.",
   "it stalls in tight corners", "it is too fast through them"),
  ("STOP_AFTER_QUADRANT", OPN, OBS,
   "Corners counted before stopping. 12 corners = 3 laps. Stopping at 11 plus a coast "
   "leaves the car resting in the start section instead of halting on a line.",
   "it stops short", "it does an extra corner"),
  ("STOP_EXTRA_S", OPN, OBS,
   "How long it keeps driving past that last counted corner. Separate from the lap "
   "debounce on purpose — they mean different things.",
   "it stops too early in the section", "it overruns"),
 ]),
]

P = []
add = P.append
add('''<title>Red Castle Tunables</title>
<style>
:root{--ground:#FBFAF8;--surface:#fff;--sunk:#F1EFEB;--ink:#191715;--muted:#6A6560;
--line:#E5E2DC;--accent:#B4542A;--up:#1F7A4D;--down:#9C3A2E;
--mono:ui-monospace,"Cascadia Mono",Consolas,"SF Mono",Menlo,monospace;
--sans:system-ui,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){
--ground:#100F0D;--surface:#191714;--sunk:#201D19;--ink:#EDE9E3;--muted:#A19A92;
--line:#2A2621;--accent:#F0885A;--up:#5CC98D;--down:#F0796A}}
:root[data-theme="dark"]{--ground:#100F0D;--surface:#191714;--sunk:#201D19;
--ink:#EDE9E3;--muted:#A19A92;--line:#2A2621;--accent:#F0885A;--up:#5CC98D;--down:#F0796A}
*{box-sizing:border-box}
body{background:var(--ground);color:var(--ink);font-family:var(--sans);font-size:15.5px;
line-height:1.6;margin:0}
.wrap{max-width:1120px;margin:0 auto;padding:0 24px 90px}
header.top{padding:58px 0 28px;border-bottom:2px solid var(--ink);margin-bottom:34px}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;
color:var(--accent);margin:0 0 14px}
h1{font-size:clamp(2.1rem,5vw,3.2rem);line-height:1.04;letter-spacing:-.03em;margin:0 0 16px}
.standfirst{color:var(--muted);max-width:62ch;margin:0 0 8px;font-size:1.08rem}
h2{font-size:1.45rem;letter-spacing:-.02em;margin:38px 0 4px}
.lede{color:var(--muted);margin:0 0 14px;max-width:70ch}
.scroll{overflow-x:auto;margin:12px 0;border:1px solid var(--line);border-radius:7px;
background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:720px}
th,td{text-align:left;padding:10px 13px;border-bottom:1px solid var(--line);vertical-align:top}
thead th{font-family:var(--mono);font-size:10px;letter-spacing:.11em;text-transform:uppercase;
color:var(--muted);background:var(--sunk);font-weight:500;white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
td.k{font-family:var(--mono);font-weight:600;white-space:nowrap;font-size:12.5px}
td.v{font-family:var(--mono);white-space:nowrap;font-variant-numeric:tabular-nums;
color:var(--accent);font-weight:600}
td.up{color:var(--up);font-size:12.5px}
td.dn{color:var(--down);font-size:12.5px}
code{font-family:var(--mono);font-size:.87em;background:var(--sunk);padding:.1em .32em;border-radius:3px}
pre.cmd{font-family:var(--mono);font-size:12.5px;background:var(--sunk);border:1px solid var(--line);
border-radius:6px;padding:12px 14px;overflow-x:auto;max-width:76ch}
.note{background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--accent);
border-radius:0 6px 6px 0;padding:14px 16px;margin:18px 0;max-width:76ch;font-size:.94rem}
.note b{color:var(--ink)}
footer{border-top:1px solid var(--line);padding-top:18px;margin-top:40px;color:var(--muted);font-size:13px}
</style>
<div class="wrap">
<header class="top">
<p class="eyebrow">WRO 2026 Future Engineers &middot; Team The Red Castle</p>
<h1>Every number you can change</h1>
<p class="standfirst">What each tunable does, the value it is set to right now,
and which way to move it when the car misbehaves. Values are read from the
source, so this page cannot drift from the car.</p>
</header>

<div class="note"><b>Change one number. Run. Read the log. Repeat.</b>
Changing two things and running once tells you nothing about either &mdash; and
almost every number here was originally set by a measurement, so guessing at a
replacement usually undoes one.</div>
''')

for title, lede, rows in GROUPS:
    add("<h2>%s</h2>" % esc(title))
    if lede:
        add('<p class="lede">%s</p>' % esc(lede))
    add('<div class="scroll"><table><thead><tr><th>name</th><th>now</th>'
        '<th>what it does</th><th>raise it when</th><th>lower it when</th>'
        "</tr></thead><tbody>")
    for name, s1, s2 in [(r[0], r[1], r[2]) for r in rows]:
        pass
    for r in rows:
        name, s1, s2, what, up, down = r
        add('<tr><td class="k">%s</td><td class="v">%s</td><td>%s</td>'
            '<td class="up">%s</td><td class="dn">%s</td></tr>'
            % (esc(name), esc(v(name, s1, s2 or {})), esc(what), esc(up), esc(down)))
    add("</tbody></table></div>")

add('''
<h2>How to tune the wall parameters</h2>
<p class="lede">These are the ones people get wrong, because two different
things both sound like &ldquo;the wall setting&rdquo;.</p>

<div class="note"><b>There are two separate layers, and tuning the wrong one
changes nothing.</b><br>
<b>1. What COUNTS as a wall</b> &mdash; <code>WALL_V_HARD</code>,
<code>WALL_V_SOFT</code>, <code>WALL_S_MAX</code>. Brightness and saturation
cuts. <b>These do NOT use a colour range.</b> Tuning the &ldquo;black&rdquo;
colour looks exactly like retuning the walls and changes nothing that drives
the car.<br>
<b>2. HOW CLOSE a wall is</b> &mdash; <code>OUTER_TARGET</code>,
<code>WALL_EMERGENCY</code>. Densities: what fraction of the picture the wall
fills. These are meaningless until layer 1 is right.</div>

<h3>Step 1 &mdash; what counts as a wall</h3>
<pre class="cmd">python tools/tune_walls.py --detector</pre>
<p>It asks for three samples: the black wall, bare mat, and a coloured line. It
then places the thresholds <em>in the gap</em> between the wall's brightness and
the mat's. If those two overlap it refuses to write anything &mdash; that means
the room is too dim for any threshold to separate them, and the fix is light,
not numbers. Results go to <code>wall_settings.json</code>, which
<code>robot.py</code> loads automatically.</p>

<h3>Step 2 &mdash; centimetres to density</h3>
<pre class="cmd">python tools/tune_walls.py</pre>
<p>The car never measures distance &mdash; it measures how much of the picture a
wall <em>fills</em>. This parks it at several known distances, fits a straight
line through the readings, and prints the exact constants to paste in.</p>
<p><b>Measure from the SIDE OF THE CAR</b> to the wall, at camera height, with
the car <b>parallel</b> to the wall. Parallel matters more than exact: at an
angle the camera sees a wedge of wall and reads high, which quietly corrupts
the fit.</p>
<pre class="cmd">python tools/tune_walls.py --live    # watch the numbers while you move the car</pre>

<div class="note"><b>Re-run step 2 after step 1, every time.</b> Changing what
counts as a wall changes every density measured against it, so the old
centimetre mapping is silently wrong.</div>

<h3>How to know it worked</h3>
<div class="scroll"><table>
<thead><tr><th>check</th><th>good</th><th>bad</th></tr></thead>
<tbody>
<tr><td><code>tune_walls.py --live</code>, car parallel at 40&nbsp;cm</td>
<td>reads close to <code>OUTER_TARGET</code></td><td>far off &rarr; refit</td></tr>
<tr><td>the fit's rms error</td><td>below ~0.008</td>
<td>above &rarr; the car was not parallel at one distance</td></tr>
<tr><td>a run log's <code>mode</code> column</td><td><code>wall</code> under ~15% of frames</td>
<td>40% &rarr; it is fighting the track, not driving it</td></tr>
<tr><td><code>WALL_EMERGENCY</code> vs <code>OUTER_TARGET</code></td>
<td>emergency clearly higher</td><td>equal or lower &rarr; the fit is wrong</td></tr>
</tbody></table></div>

<footer>Generated from <code>src/</code> by
<code>other/build-tunables.py</code>. Regenerate after changing the code rather
than editing this page.</footer>
</div>''')

out = "\n".join(P)
io.open("other/tunables.html", "w", encoding="utf-8", newline="\n").write(out)
print("wrote other/tunables.html (%d chars)" % len(out))
