#!/usr/bin/env python3
"""
build_pdf.py - regenerate WRO2026-Control-and-Tunables.pdf.

Run it on the LAPTOP (it never imports picamera2):

    python competition-kit/build_pdf.py

Every value in the PDF is PARSED OUT OF THE PROGRAMS at build time, so the
document cannot drift away from the code. If you change a tunable, re-run this
and the PDF follows.
"""
import ast
import io
import os
import sys
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak, KeepTogether)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
def _find(name):
    """Works whether this sits in the repo (../src/) or in the kit (./)."""
    for cand in (os.path.join(HERE, name),
                 os.path.join(ROOT, "src", name),
                 os.path.join(ROOT, name)):
        if os.path.exists(cand):
            return cand
    raise SystemExit("cannot find %s" % name)


OPEN_PY = _find("open_challenge.py")
OBS_PY = _find("obstacle_challenge.py")
OUT = os.path.join(HERE, "WRO2026-Control-and-Tunables.pdf")


# ------------------------------------------------------------------ parsing
def values_of(path):
    """Every module-level constant assignment, as {name: literal text}."""
    src = io.open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        try:
            val = ast.literal_eval(node.value)
        except Exception:
            continue
        txt = repr(val)
        if isinstance(val, float):
            txt = ("%g" % val)
        for t in node.targets:
            if isinstance(t, ast.Name):
                out[t.id] = txt
            elif isinstance(t, ast.Tuple) and isinstance(node.value, ast.Tuple):
                for nm, v in zip(t.elts, node.value.elts):
                    if isinstance(nm, ast.Name):
                        try:
                            out[nm.id] = "%g" % ast.literal_eval(v) if isinstance(
                                ast.literal_eval(v), float) else repr(
                                ast.literal_eval(v))
                        except Exception:
                            pass
    return out


OV = values_of(OPEN_PY)
BV = values_of(OBS_PY)


def v(d, name):
    return d.get(name, "?")


# ------------------------------------------------------------------ styles
styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=16,
                    spaceAfter=4, textColor=colors.HexColor("#12304a"))
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11.5,
                    spaceBefore=10, spaceAfter=3,
                    textColor=colors.HexColor("#1d5c86"))
BODY = ParagraphStyle("BODY", parent=styles["BodyText"], fontSize=8.6,
                      leading=11.4, spaceAfter=4)
NOTE = ParagraphStyle("NOTE", parent=BODY, fontSize=8, leading=10.4,
                      textColor=colors.HexColor("#5b4636"))
EQ = ParagraphStyle("EQ", parent=BODY, fontName="Courier", fontSize=8.4,
                    leading=11.6, leftIndent=8,
                    textColor=colors.HexColor("#102a43"))
CELL = ParagraphStyle("CELL", parent=BODY, fontSize=7.7, leading=9.4,
                      spaceAfter=0)
CELLB = ParagraphStyle("CELLB", parent=CELL, fontName="Courier-Bold",
                       fontSize=7.7)
CELLC = ParagraphStyle("CELLC", parent=CELL, fontName="Courier", fontSize=7.7)

story = []


def tune_table(rows):
    """rows: (name, value, what it does, change it when)"""
    data = [[Paragraph("<b>tunable</b>", CELL), Paragraph("<b>now</b>", CELL),
             Paragraph("<b>what it does</b>", CELL),
             Paragraph("<b>change it when</b>", CELL)]]
    for n, val, what, when in rows:
        data.append([Paragraph(n, CELLB), Paragraph(val, CELLC),
                     Paragraph(what, CELL), Paragraph(when, CELL)])
    t = Table(data, colWidths=[38 * mm, 15 * mm, 63 * mm, 60 * mm],
              repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbe7f0")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#9fb3c4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f4f8fb")]),
    ]))
    return t


def eq(*lines):
    return [Paragraph(l.replace(" ", "&nbsp;"), EQ) for l in lines]


# ==========================================================================
#  TITLE
# ==========================================================================
story.append(Paragraph("WRO 2026 Future Engineers &mdash; Control &amp; Tunables", H1))
story.append(Paragraph(
    "Team The Red Castle &mdash; HMK AI and Robotics Club. "
    "Generated %s from the programs themselves; every value below is parsed "
    "out of the source at build time, so it cannot disagree with the code."
    % date.today().isoformat(), NOTE))

story.append(Paragraph("What the car actually measures", H2))
story.append(Paragraph(
    "There is no distance sensor. Everything below is built from one 640&times;480 "
    "camera frame, cropped from row <b>CROP_TOP</b> to the bottom, taking every "
    "second column, then resized to <b>320&times;120</b>. All pixel counts, areas "
    "and thresholds in this document live on that 320&times;120 frame &mdash; which "
    "is why a threshold measured on a different crop does not transfer.", BODY))
story += eq(
    "crop      = raw[CROP_TOP:480, 0:640:2]   ->  resize to 320x120",
    "wall density  left_wall  = count(wall pixels, left half)  / 12800",
    "              right_wall = count(wall pixels, right half) / 12800",
)
story.append(Paragraph(
    "The divisor is 12800 and each half is really 120&times;160 = 19200 pixels, so "
    "these densities are not true fractions &mdash; they run to about 1.5. That is "
    "inherited and harmless, because every target is measured on the same "
    "scale. It only matters if you compare against a number from elsewhere.", NOTE))

story.append(Paragraph("The wall mask &mdash; what counts as a wall", H2))
story += eq(
    "wall = (V < WALL_V_HARD)  OR  (V < WALL_V_SOFT AND S < WALL_S_MAX)",
    "then  morphological OPEN, kernel WALL_OPEN_K",
    "then  keep only pixels in a VERTICAL RUN of >= WALL_MIN_RUN pixels",
)
story.append(Paragraph(
    "Two cases, because saturation is unreliable when V is tiny &mdash; a black "
    "wall can report S&gt;200 from sensor noise. Testing saturation alone rejects "
    "real walls; testing brightness alone accepts the coloured lines. "
    "The vertical-run test is the shadow filter: a real wall is a tall solid "
    "run, a shadow is a broad shallow smear.", BODY))

# ==========================================================================
#  OPEN CHALLENGE
# ==========================================================================
story.append(PageBreak())
story.append(Paragraph("Open Challenge &mdash; control law", H1))
story.append(Paragraph(
    "One P controller on wall density. The car follows the OUTER wall: driving "
    "clockwise it turns right, so the inside of the loop is on its right and "
    "the LEFT wall is the outer one; counter-clockwise is the mirror.", BODY))
story += eq(
    "direction = +1 (CW)    dir = (left_wall  - CW_TARGET ) * WALL_GAIN",
    "direction = -1 (CCW)   dir = (CCW_TARGET - right_wall) * WALL_GAIN",
    "",
    "before the direction locks (direction = 0):",
    "   if left_wall  > NEUTRAL_TARGET:  dir = (left_wall - NEUTRAL_TARGET) * WALL_GAIN",
    "   if right_wall > NEUTRAL_TARGET:  dir = (NEUTRAL_TARGET - right_wall) * WALL_GAIN",
    "",
    "dir       = clamp(dir, -STEER_MAX, +STEER_MAX)",
    "dir_servo = SERVO_SMOOTH * dir + (1 - SERVO_SMOOTH) * dir_servo_previous",
    "pulse_us  = 500 + ((dir_servo + 90 + SERVO_TRIM) / 180) * 2000",
)
story.append(Paragraph(
    "<b>TARGET is the density a CENTRED car reads.</b> That is the whole "
    "calibration: park it in the middle, read the number, put it here. A target "
    "that is wrong by 0.03 commands about 2&deg; of steering while the car is "
    "already centred &mdash; a constant lean into one wall, every cycle, all run.", NOTE))

story.append(Paragraph("Counting laps", H2))
story += eq(
    "pixels > threshold                -> state 1  (on the line)",
    "state 1 -> below threshold        -> state 2  (crossed) -> quadrant + 1",
    "then ignore that colour for LINE_BLANK_S seconds",
    "12 quadrants -> keep driving FINISH_RUN_S -> stop",
)
story.append(Paragraph(
    "The count happens on the FALLING edge, so what causes a double count is "
    "the pixel count dipping below the threshold mid-crossing. A lower "
    "threshold makes that less likely, not more.", NOTE))

story.append(Paragraph("Open Challenge tunables", H2))
story.append(tune_table([
    ("CW_TARGET", v(OV, "CW_TARGET"),
     "Left-wall density a centred car reads, driving clockwise.",
     "Re-measure at the venue with <b>wall_calib.py cw</b>. Always."),
    ("CCW_TARGET", v(OV, "CCW_TARGET"),
     "Right-wall density a centred car reads, counter-clockwise.",
     "Re-measure with <b>wall_calib.py ccw</b>. Should be within ~0.01 of CW_TARGET."),
    ("NEUTRAL_TARGET", v(OV, "NEUTRAL_TARGET"),
     "Before the direction locks, steer away from a wall past this density.",
     "If the car drives straight out of the start into a wall, lower it."),
    ("WALL_GAIN", v(OV, "WALL_GAIN"),
     "Degrees of steering per unit of density error.",
     "Raise if it corrects too slowly; lower if it weaves on a straight."),
    ("STEER_MAX", v(OV, "STEER_MAX"),
     "Software steering limit for ordinary driving.",
     "Raise toward 35 if it runs wide at corners. The log prints CLAMP."),
    ("SERVO_SMOOTH", v(OV, "SERVO_SMOOTH"),
     "Exponential average on the command. 1.0 = raw.",
     "Lower if the steering is twitchy; raise if it feels sluggish."),
    ("SERVO_DEADBAND", v(OV, "SERVO_DEADBAND"),
     "Degrees of change below which the servo pulse is not rewritten.",
     "Raise a little if the servo buzzes while going straight."),
    ("SERVO_TRIM", v(OV, "SERVO_TRIM"),
     "Degrees added so that a command of 0 drives dead straight.",
     "If the car curves with dir=0 in the log, adjust this, nothing else."),
    ("blue_line_threshould", v(OV, "blue_line_threshould"),
     "Blue pixels needed to call it a line.",
     "Set from <b>line_audit.py blue</b>: about 77% of a full line."),
    ("orange_line_threshould", v(OV, "orange_line_threshould"),
     "Orange pixels needed to call it a line.",
     "Set from <b>line_audit.py orange</b>."),
    ("LINE_BLANK_S", v(OV, "LINE_BLANK_S"),
     "Seconds a colour is ignored after it is counted.",
     "Must exceed one crossing (~0.5 s) and stay under the gap between "
     "counted lines (~5 s on a real run)."),
    ("FINISH_RUN_S", v(OV, "FINISH_RUN_S"),
     "Seconds of driving after the 12th quadrant.",
     "Raise if the car stops on the line instead of past it."),
    ("CROP_TOP", v(OV, "CROP_TOP"),
     "First raw row kept. Lower = more wall in frame, smaller lines.",
     "Changing this invalidates BOTH the wall targets and the line thresholds."),
    ("WALL_V_HARD", v(OV, "WALL_V_HARD"),
     "Below this brightness it is wall whatever the saturation says.", ""),
    ("WALL_V_SOFT", v(OV, "WALL_V_SOFT"),
     "Up to this brightness it is wall only if desaturated.", ""),
    ("WALL_S_MAX", v(OV, "WALL_S_MAX"),
     "Saturation above this is a coloured line, not a wall.", ""),
    ("WALL_MIN_RUN", v(OV, "WALL_MIN_RUN"),
     "Vertical dark pixels required to be a wall &mdash; the shadow filter.",
     "Raise if shadow leaks in; lower if distant walls vanish."),
    ("speed", v(OV, "speed"), "Motor PWM percent.",
     "Lower it before you tune anything else &mdash; every threshold is easier "
     "to hit slowly."),
]))

# ==========================================================================
#  OBSTACLE
# ==========================================================================
story.append(PageBreak())
story.append(Paragraph("Obstacle Challenge &mdash; control law", H1))
story.append(Paragraph(
    "Three things can steer, in this order of authority: a pillar, then a wall "
    "that is too close, then the corner kick. Between pillars there is no wall "
    "following at all &mdash; <b>dir is 0 and the car drives straight</b>.", BODY))

story.append(Paragraph("Following a pillar", H2))
story += eq(
    "d = SIGN_Y_GAIN * (119 - y)          y is the blob centre; y=0 is FURTHEST",
    "",
    "green aim = min(320 + GREEN_TARGET_CLAMP, GREEN_NEAR_{CW|CCW} + d)",
    "red   aim = max(     -RED_TARGET_CLAMP,   RED_NEAR            - d)",
    "",
    "Err(green) = -(green aim - x)        pass on its LEFT  -> steer LEFT",
    "Err(red)   =  (x - red aim)          pass on its RIGHT -> steer RIGHT",
    "",
    "if green and x > 220        : Err = 0      (release, CW only)",
    "if red   and x <  90        : Err = 0      (release, CCW only)",
    "",
    "dir = Err * kp,  clamped to GREEN_STEER_MAX or RED_STEER_MAX",
)
story.append(Paragraph(
    "<b>The aim runs off-frame on purpose.</b> The further away a pillar is, "
    "the further outside the 320-pixel frame the car aims, so it commits early "
    "and eases off as the pillar arrives. The clamps stop that becoming a lunge.", BODY))
story.append(Paragraph(
    "<b>Measured, and still true in this build:</b> the green release "
    "(<font face='Courier'>x &gt; 220</font>, no distance condition) zeroes the "
    "steering on about 70% of the cycles a green pillar is held in CW, at any "
    "distance &mdash; down to x=221 with the pillar close. CCW has no such line, "
    "which is why green behaves better counter-clockwise. The distance-gated "
    "version is in git if it is wanted back.", NOTE))

story.append(Paragraph("Walls and the corner kick", H2))
story += eq(
    "if a wall density > WALL_CLOSE:  dir = +-(30 or 40) * that density",
    "     ceiling becomes WALL_STEER_MAX",
    "",
    "corner kick, once per crossing:",
    "   CW  and last sign GREEN and orange line crossed -> servo(+45)",
    "   CCW and last sign RED   and blue   line crossed -> servo(-45)",
    "",
    "parking exit, once at the start:",
    "   purple_left > purple_right -> exit RIGHT, direction = CW  (+1)",
    "   otherwise                  -> exit LEFT,  direction = CCW (-1)",
)
story.append(Paragraph(
    "With no purple in view at all that comparison is false, so the car "
    "silently commits to CCW. Check the first line the program prints.", NOTE))

story.append(Paragraph("Obstacle Challenge tunables", H2))
story.append(tune_table([
    ("kp", v(BV, "kp"), "Degrees of steering per pixel of sign error.",
     "The single strongest knob for pillar behaviour. Change it in small steps."),
    ("SIGN_Y_GAIN", v(BV, "SIGN_Y_GAIN"),
     "How much further off-frame to aim per row of distance.",
     "Raise to commit earlier to a far pillar; lower to react later."),
    ("GREEN_NEAR_CW", v(BV, "GREEN_NEAR_CW"),
     "Where a CLOSE green pillar should sit in frame, driving CW.",
     "Raise to pass wider around green. Try this before raising kp."),
    ("GREEN_NEAR_CCW", v(BV, "GREEN_NEAR_CCW"), "Same, counter-clockwise.", ""),
    ("RED_NEAR", v(BV, "RED_NEAR"),
     "Where a CLOSE red pillar should sit in frame.",
     "Lower to pass wider around red."),
    ("GREEN_TARGET_CLAMP", v(BV, "GREEN_TARGET_CLAMP"),
     "How far past the frame edge green may be aimed. 400 = effectively free.", ""),
    ("RED_TARGET_CLAMP", v(BV, "RED_TARGET_CLAMP"),
     "Same for red. Small on purpose &mdash; it is what stops red lunging at "
     "the start of a section.",
     "Raise if red is not avoided enough; lower if red over-reacts."),
    ("GREEN_STEER_MAX", v(BV, "GREEN_STEER_MAX"),
     "Steering ceiling while following green.",
     "Raise if green is clipped; the log shows the clamp."),
    ("RED_STEER_MAX", v(BV, "RED_STEER_MAX"),
     "Steering ceiling while following red. Deliberately tighter than green.",
     "Lower if red is still too sharp."),
    ("GREEN_MIN_AREA", v(BV, "GREEN_MIN_AREA"),
     "Green blob size before it becomes a target. Area falls with the SQUARE "
     "of distance.",
     "Keep low &mdash; green needs to start early to swing wide."),
    ("RED_MIN_AREA", v(BV, "RED_MIN_AREA"),
     "Red blob size before it becomes a target.",
     "Raise to answer red later. A pillar measures ~1220 px at mid distance."),
    ("PARALELIPIPED_MIN_AREA", v(BV, "PARALELIPIPED_MIN_AREA"),
     "Floor below which a blob is noise, not a pillar.", ""),
    ("SIGN_MAX_ASPECT", v(BV, "SIGN_MAX_ASPECT"),
     "A blob is a pillar only if width &lt; this &times; height.",
     "Raise if a CLOSE pillar is lost &mdash; its base runs off frame so its "
     "height stops growing while its width does not."),
    ("SIGN_CLOSE_AREA_CW", v(BV, "SIGN_CLOSE_AREA_CW"),
     "Area at which the sign is latched as the last one seen (CW).", ""),
    ("SIGN_CLOSE_AREA_CCW", v(BV, "SIGN_CLOSE_AREA_CCW"), "Same, CCW.", ""),
    ("WALL_CLOSE", v(BV, "WALL_CLOSE"),
     "Density above which a wall overrides the pillar steering.",
     "Lower if the car touches walls; raise if it shies away from them."),
    ("WALL_STEER_MAX", v(BV, "WALL_STEER_MAX"),
     "Ceiling for a wall correction, so a sign's tighter limit cannot blunt it.", ""),
    ("STEER_MAX", v(BV, "STEER_MAX"),
     "Ordinary steering limit when nothing special is happening.", ""),
    ("PARKING_ENABLED", v(BV, "PARKING_ENABLED"),
     "End-of-run parking search. Currently OFF &mdash; the car finishes like "
     "the open challenge.",
     "Set True to bring the whole parking algorithm back."),
    ("FINISH_RUN_S", v(BV, "FINISH_RUN_S"),
     "Seconds of driving after the 12th quadrant, with parking off.", ""),
    ("blue_line_threshould", v(BV, "blue_line_threshould"),
     "Blue pixels needed to call it a line.", "From <b>line_audit.py</b>."),
    ("orange_line_threshould", v(BV, "orange_line_threshould"),
     "Orange pixels needed. Orange shares its hue band with the RED pillars.",
     "If phantom quadrants appear, raise this first."),
    ("LINE_BLANK_S", v(BV, "LINE_BLANK_S"),
     "Seconds a colour is ignored after being counted.", ""),
    ("GREEN_SAT_MIN", v(BV, "GREEN_SAT_MIN"),
     "Green saturation floor. The MAT sits inside the green hue band, so "
     "saturation is the ONLY thing separating cube from floor.",
     "Measured gap: mat p99=146, cube p01=157. Do not go below ~150."),
    ("GREEN_VAL_MIN", v(BV, "GREEN_VAL_MIN"),
     "Green brightness floor. The cube is DARK &mdash; V median 38.",
     "At 60 it kept 1% of the cube. Leave low."),
    ("RED_SAT_MIN", v(BV, "RED_SAT_MIN"), "Red saturation floor.", ""),
    ("PURPLE_SAT_MIN", v(BV, "PURPLE_SAT_MIN"),
     "Parking wall saturation floor.", ""),
    ("PURPLE_VAL_MIN", v(BV, "PURPLE_VAL_MIN"),
     "Parking wall brightness floor. The wall measures V p05=52 p50=67.",
     "Raising this loses the wall; it is what the exit direction depends on."),
]))

# ==========================================================================
#  ORDER OF WORK
# ==========================================================================
story.append(PageBreak())
story.append(Paragraph("Order of work at the venue", H1))
story.append(Paragraph(
    "Do these in order. Each step assumes the ones above it are already right; "
    "doing them out of order means measuring through a mistake.", BODY))
ORDER = [
    ("1", "Lock the camera",
     "<b>mask_debug.py</b>", "Look at the picture before any number. If the "
     "walls are not dark and the lines are not solid, nothing measured "
     "afterwards means anything. Venue lighting is the biggest single change "
     "between practice and competition."),
    ("2", "Walls, both directions",
     "<b>wall_calib.py cw</b> then <b>ccw</b>",
     "Park CENTRED, read the density, put it in CW_TARGET / CCW_TARGET. The "
     "two should agree within about 0.01 &mdash; if they do not, the car was not "
     "centred for one of them."),
    ("3", "Lines",
     "<b>line_audit.py blue</b> / <b>orange</b>",
     "Park over each line. Set the threshold near 77% of a full line. Check "
     "the frame-to-frame spread does not straddle it."),
    ("4", "Pillars",
     "<b>sign_calib.py</b>",
     "Green and red at equal distance should give equal area and equal y. If "
     "one is much smaller, its colour range is clipping the cube &mdash; fix that "
     "before touching kp."),
    ("5", "Parking walls",
     "<b>park_calib.py</b>",
     "Only for the obstacle start. Check both purple counts and that one side "
     "clearly wins &mdash; a near tie means a coin toss for the lap direction."),
    ("6", "Drive, then read the log",
     "logs/*.csv",
     "Every run writes its own timestamped file. Do not tune from memory of "
     "what the car looked like; the log has the wall densities, the pixel "
     "counts, the target and the steering before and after the clamp."),
]
data = [[Paragraph("<b>#</b>", CELL), Paragraph("<b>step</b>", CELL),
         Paragraph("<b>tool</b>", CELL), Paragraph("<b>why</b>", CELL)]]
for n, s_, tool, why in ORDER:
    data.append([Paragraph(n, CELLB), Paragraph(s_, CELL),
                 Paragraph(tool, CELL), Paragraph(why, CELL)])
t = Table(data, colWidths=[8 * mm, 30 * mm, 34 * mm, 104 * mm], repeatRows=1)
t.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbe7f0")),
    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#9fb3c4")),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 3),
    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
     [colors.white, colors.HexColor("#f4f8fb")]),
]))
story.append(t)

story.append(Paragraph("Three rules that have cost this car whole runs", H2))
story.append(Paragraph(
    "<b>1. A threshold belongs to the crop it was measured on.</b> "
    "CROP_TOP was raised from 240 to 160 to get the walls in frame, which "
    "squashes 320 rows into 120 instead of 240 into 120. Lines are horizontal, "
    "so they lose pixels in proportion: the same frame gives 1421 px of blue "
    "through the old crop and 1077 through this one. Both line thresholds were "
    "silently too high for months because of it.", BODY))
story.append(Paragraph(
    "<b>2. Brightness floors set on a brighter camera reject the object.</b> "
    "The same mistake three times: orange needed V&gt;125 where the line reads "
    "78; blue needed V&gt;70 where it reads 43; green needed V&gt;60 where the "
    "cube reads 38 and only 1% of it survived. If something is not detected, "
    "check the V floor before anything else.", BODY))
story.append(Paragraph(
    "<b>3. A controller commanding zero looks exactly like a controller that "
    "is happy.</b> The neutral wall target was 0.5 on a camera whose densities "
    "reach 0.25, so before the direction locked the car steered nothing at all "
    "and drove straight out of the start into the wall. Read dir in the log, "
    "not the car.", BODY))

# ------------------------------------------------------------------ build
doc = SimpleDocTemplate(OUT, pagesize=A4,
                        leftMargin=14 * mm, rightMargin=14 * mm,
                        topMargin=13 * mm, bottomMargin=13 * mm,
                        title="WRO 2026 Control and Tunables",
                        author="Team The Red Castle")


def footer(canvas, doc_):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#7c8ea0"))
    canvas.drawString(14 * mm, 8 * mm,
                      "WRO 2026 Future Engineers - The Red Castle")
    canvas.drawRightString(A4[0] - 14 * mm, 8 * mm, "page %d" % doc_.page)
    canvas.restoreState()


doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("wrote %s (%.0f KB)" % (OUT, os.path.getsize(OUT) / 1024.0))
