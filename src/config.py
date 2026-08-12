#!/usr/bin/env python3
"""
config.py - EVERY tunable number for the car, in one place.

At the competition you should only ever need to edit THIS file (plus the
generated colors.json / servo_center.txt / camera_settings.json).
Nothing here imports anything, so it is safe to edit under pressure.

Sign conventions used everywhere:
    steering : 0 = straight, POSITIVE = RIGHT, NEGATIVE = LEFT
    speed    : -100..100, positive = forward
    direction: +1 = clockwise (turns right), -1 = counter-clockwise (turns left)
"""

# ==========================================================================
# HARDWARE PINS (BCM)
# ==========================================================================
SERVO_PIN = 13          # steering servo
MOTOR_IN1 = 24          # L9110S A-IA : PWM here = FORWARD
MOTOR_IN2 = 23          # L9110S A-IB : PWM here = REVERSE
SERVO_HZ = 50
MOTOR_HZ = 1000

STOP_FLIP_DELAY = 0.3   # s to coast before reversing (protects the regulator)
STEER_MAX = 20          # deg - SOFTWARE steering limit actually used when driving.
                        # The Ackermann linkage reaches 35 deg mechanically, but the
                        # car is run at 20 for stability at full speed.
SERVO_MIN_DUTY = 2.5    # duty at 0 deg
SERVO_MAX_DUTY = 12.5   # duty at 180 deg

# DRIFT TRIM - added to every DRIVING steering command (not to servo() itself,
# so centring the wheels at shutdown still centres them).
#   NEGATIVE = push LEFT      POSITIVE = push RIGHT
# MEASURED: across four runs the car always sat closer to the RIGHT wall
# (right density 0.094/0.027/0.062/0.162 vs left 0.027/0.017/0.023/0.018) even
# though the controller was already commanding LEFT on average. Steering
# direction and centre were verified correct by hand, so this is a residual
# mechanical/alignment pull. Make it MORE negative if it still drifts right,
# less negative (toward 0) if it now hugs the left wall.
STEER_BIAS = -4.0

# ==========================================================================
# SPEEDS
# ==========================================================================
CRUISE_OPEN = 100       # base speed, Open Challenge (%)
CRUISE_OBSTACLE = 100   # base speed, Obstacle Challenge (%)
SPEED_CORNER_CUT = 0.5  # how much to slow at full steering (0.5 = half speed)
MIN_SPEED = 35          # never command less than this while driving (%)

# ==========================================================================
# IMAGE / ROI
# ==========================================================================
CAM_W, CAM_H = 640, 480 # camera output
ROI_TOP = 160           # rows above this are background clutter -> ignored
PROC_W, PROC_H = 320, 160   # processing buffer size
BLUR_KSIZE = 5          # median blur before HSV (0/1 = off) - kills sensor noise

# ==========================================================================
# WALL DENSITY METHOD  (KyivRoboMagic style - the proven fallback)
# ==========================================================================
WALL_TARGET = 0.14      # outer-wall fill when nicely positioned
WALL_EMERGENCY = 0.28   # wall this close -> push away hard (was 0.34; lowered so
                        # the escape begins before the car is already against it)
CENTER_DEADBAND = 0.03  # ignore tiny left-right differences (anti-jitter)
WALL_KP = 200.0         # MEASURED: left/right densities on this camera run
WALL_KD = 50.0          # 0.03-0.09, not the ~0.5 the old gains assumed, so the
                        # controller was ~5x too soft to hold a line.

# ==========================================================================
# FREE-SPACE / FOLLOW-THE-GAP METHOD  (method "B")
# ==========================================================================
# For each column we scan UP from the bottom and find the mat->wall boundary.
# free[x] = PROC_H - boundary_row  ->  BIG = open road, SMALL = wall close.
FREE_MIN_RUN = 6        # a wall must be >= this many consecutive dark rows.
                        # This is what stops the mat's dotted lines being read
                        # as a wall. Raise it if dots/marks cause false walls.
FREE_SMOOTH = 9         # moving-average width over columns (noise smoothing)
FREE_EDGE_IGNORE = 20   # ignore this many columns at each edge (the fisheye is
                        # worst there and can see PAST a wall at the extremes)

GAP_OPEN_FRAC = 0.80    # a column counts as "open" if free >= this * PROC_H.
                        # MEASURED on the field: a wall 25 cm ahead scores 0.74,
                        # 40 cm scores 0.82, clear track scores 0.94. 0.80 puts
                        # the cut between "wall at 25-30 cm" and "clear".
GAP_MIN_WIDTH = 60      # a gap narrower than this many columns is NOT drivable.
                        # The car is ~20 cm wide, so a real opening occupies a
                        # big fraction of the frame. MEASURED: with this at 12 a
                        # 12-px fisheye sliver at the frame edge was mistaken for
                        # an opening and produced a +23 deg steer into a wall.
GAP_KP = 80.0           # steering gain on the gap-centre error.
                        # MEASURED: at 26 the largest correction produced in a
                        # whole run was 6.9 deg out of 35 available, and 61% of
                        # frames steered less than 2 deg - far too weak.
GAP_BLOCKED_FRAC = 0.35 # if the best free value is below this * PROC_H the way
                        # ahead is blocked -> commit to the locked turn direction

# ==========================================================================
# OUTER-WALL METHOD  ("outer")  <-- the approach proven by the strongest
# camera-only teams (KyivRoboMagic 2024 international final, Maverick 2025).
# ==========================================================================
# ONE reference, ONE error term: the distance to the OUTER wall.
#   clockwise        -> the outer wall is on the LEFT
#   counter-clockwise-> the outer wall is on the RIGHT
# The inner walls are randomised each round, so they are never referenced at all.
# There is no gap threshold and no front-wall threshold to tune.
OUTER_TARGET = 0.14     # desired outer-wall fill. Bigger = hug the outer wall
                        # closer. This is the ONLY position setpoint.
OUTER_KP = 160.0        # proportional gain on (outer - OUTER_TARGET)
OUTER_KD = 45.0         # derivative gain, damps the weave
OUTER_DEADBAND = 0.02   # ignore tiny errors so it runs straight

# CORNER = a scripted turn TRIGGERED BY THE LINE, not by a tuned wall threshold.
# Crossing the driving-direction line means we are physically at the corner, so
# the turn timing is deterministic instead of depending on a front-wall fraction.
TURN_DURATION_S = 1.1   # how long to hold full lock through a 90 deg corner
TURN_LOCK_FRAC = 1.0    # fraction of STEER_MAX to use during the turn

# ==========================================================================
# CORNERS / LAP COUNTING
# ==========================================================================
FRONT_COLS = 0.40       # centre fraction of width treated as "ahead"
FRONT_ROWS = 0.55       # upper fraction of ROI treated as "ahead"
# MEASURED front values head-on to a wall: 0.15 far, 0.40 at 40 cm, 0.54 at 25 cm.
# 'front' separates distance far better than left+right, so corner detection uses it.
FRONT_ENTER = 0.30      # front fill this high -> a corner is here.
                        # 0.38 fired at ~40 cm which was too late at full speed -
                        # the car reached the wall before the turn developed.
                        # 0.30 fires further out (~55-60 cm) so the turn starts early.
FRONT_EXIT = 0.20       # front cleared below this -> corner finished
CORNER_TOTAL = 0.55     # left+right fill meaning a wall is AHEAD (density method)

MIN_CORNER_CYCLES = 6   # must be in the corner this long before it counts
MAX_CORNER_CYCLES = 90  # safety: never stay stuck in a corner
CORNER_DEBOUNCE = 25    # min CYCLES between two counted corners

# TIME-based guard: a real corner cannot physically happen twice within this
# many seconds. This is the reliable one - cycle counts change with frame rate,
# seconds do not. Raise it if one corner gets counted twice; lower it if a
# genuine corner is missed because it came too soon after the previous one.
CORNER_MIN_INTERVAL_S = 2.5    # (steering-corner guard, geometry side)

# THE LAP TIMER. After a quadrant is counted, NO further count is allowed until
# this many seconds have passed - and the timer RESTARTS on every count. A lap
# quadrant therefore needs BOTH: a line crossing AND an expired timer.
LAP_COUNT_LOCKOUT_S = 2.5
CORNER_MAX_INTERVAL_S = 25.0   # if no corner for this long, something is wrong
                               # (logged as a warning, does not stop the run)

QUADRANTS_PER_RUN = 12  # 12 corners = 3 laps (reference)

# STOP RULE: finish after this many counted quadrants AND once the lap timer has
# expired - so the car keeps driving through the last segment and comes to rest
# in the start/finish section instead of halting on the line itself.
STOP_AFTER_QUADRANT = 11
FINISH_EXTRA_CYCLES = 60   # keep driving briefly after the last corner
MAX_RUNTIME_S = 90      # SAFETY: hard stop after this long

# ==========================================================================
# COLOURED LINES (direction hint only - NOT required for lap counting)
# ==========================================================================
# The corner lines are painted on the MAT, so they can only appear in the LOWER
# part of the frame. Searching the whole ROI let bluish WALL/background pixels in
# the top corners trigger the blue line: measured 41% of a run above threshold,
# with the pixels sitting at rows 0-13 (the very top). Restricting the search to
# the bottom band removes that class of false positive geometrically, without
# depending on colour tuning at all.
LINE_ROWS = 0.45        # only the BOTTOM 45% of the ROI is searched for lines
LINE_FRACTION = 0.020   # a line is "present" above this fraction of the line band

# TIME lockout: once a line has been READ ONCE, that colour is ignored for this
# many seconds. This is what stops one physical crossing being counted many
# times. It MUST be in seconds, not cycles - the old 10-cycle debounce was only
# 0.33 s at 30 fps, so a flickering mask produced 36 "crossings" in a 45 s run.
LINE_LOCKOUT_S = 2.5    # a line cannot be read again for this long
LINE_DEBOUNCE = 10      # (legacy cycle guard, kept as a secondary floor)
# SENSOR FUSION. Both signals run together and cross-check each other:
#   geometry (front wall)  - always available, never depends on colour tuning
#   colour lines           - the official WRO cue (orange=CW, blue=CCW)
# Direction: whichever arrives first locks it, the second CONFIRMS or warns.
# Corners:   EITHER may raise one; the time guard means it is still counted once.
USE_LINES_FOR_DIRECTION = True   # False = decide direction purely from geometry
USE_LINES_FOR_CORNERS = True     # lines DO count corners - each crossing is read
                                 # ONCE thanks to the LINE_LOCKOUT_S timer above.
GEOM_DIR_MIN_DIFF = 0.08         # |left-right| must exceed this before the wall
                                 # geometry is allowed an opinion on direction.
                                 # MEASURED: head-on to a corner the two halves
                                 # read 0.26 vs 0.22 (diff 0.04) - too symmetric
                                 # to mean anything, and it produced a confident
                                 # but arbitrary guess that fought the line cue.

# ==========================================================================
# OBSTACLE CHALLENGE - traffic signs
# ==========================================================================
PILLAR_MIN_AREA = 120       # min contour area in the PROC buffer
PILLAR_MIN_ASPECT = 1.1     # height/width must exceed this (signs are tall)
PILLAR_SIDE_MARGIN = 0.18   # red -> aim sign to x=0.18*W, green -> 0.82*W
PILLAR_KP = 90.0
PILLAR_SPEED = 60           # speed while passing a sign (%)
PILLAR_MEMORY_CYCLES = 12   # keep steering for a sign this long after losing it

# ==========================================================================
# OBSTACLE CHALLENGE - parking
# ==========================================================================
PARK_STOP_AREA = 9000   # magenta area at which we are parked
PARK_SPEED = 30
PARK_KP = 90.0

# ==========================================================================
# COMPETITION SPECIAL CASES
# Flip these at the venue without touching any logic.
# ==========================================================================
NAV_METHOD = "outer"    # "outer"   = outer-wall PD + line-triggered turn (PROVEN)
                        # "gap"     = free-space follow-the-gap
                        # "density" = KyivRoboMagic wall-density fallback
                        # "density" = KyivRoboMagic wall-density (proven fallback)

FORCE_DIRECTION = 0     # 0 = auto-detect from the first line seen (+ geometry)
                        # +1 = force clockwise, -1 = force counter-clockwise
                        # Use this if the judges tell you the run direction.

INVERT_STEERING = False # True if the servo turns the wrong way after a rebuild
INVERT_MOTOR = False    # True if the motor drives backwards after a rewire

DEBUG_EVERY = 15        # print a status line every N cycles (0 = silent)
SAVE_DEBUG_FRAMES = 0   # save an annotated frame every N cycles (0 = off).
                        # Useful to review a bad run; costs ~10ms per save.
