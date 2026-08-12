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
MOTOR_IN1 = 23          # L9110S A-IA : PWM here = FORWARD
MOTOR_IN2 = 24          # L9110S A-IB : PWM here = REVERSE
SERVO_HZ = 50
MOTOR_HZ = 1000

STOP_FLIP_DELAY = 0.3   # s to coast before reversing (protects the regulator)
STEER_MAX = 20          # deg - max steering deviation from centre
SERVO_MIN_DUTY = 2.5    # duty at 0 deg
SERVO_MAX_DUTY = 12.5   # duty at 180 deg

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
WALL_EMERGENCY = 0.34   # wall this close -> push away hard
CENTER_DEADBAND = 0.03  # ignore tiny left-right differences (anti-jitter)
WALL_KP = 45.0
WALL_KD = 18.0

# ==========================================================================
# FREE-SPACE / FOLLOW-THE-GAP METHOD  (method "B")
# ==========================================================================
# For each column we scan UP from the bottom and find the mat->wall boundary.
# free[x] = PROC_H - boundary_row  ->  BIG = open road, SMALL = wall close.
FREE_MIN_RUN = 6        # a wall must be >= this many consecutive dark rows.
                        # This is what stops the mat's dotted lines being read
                        # as a wall. Raise it if dots/marks cause false walls.
FREE_SMOOTH = 9         # moving-average width over columns (noise smoothing)
FREE_EDGE_IGNORE = 10   # ignore this many columns at each edge (fisheye is
                        # worst there)

GAP_OPEN_FRAC = 0.55    # a column counts as "open" if free >= this * PROC_H
GAP_MIN_WIDTH = 12      # a gap narrower than this many columns is not drivable
GAP_KP = 26.0           # steering gain on the gap-centre error
GAP_BLOCKED_FRAC = 0.35 # if the best free value is below this * PROC_H the way
                        # ahead is blocked -> commit to the locked turn direction

# ==========================================================================
# CORNERS / LAP COUNTING
# ==========================================================================
FRONT_COLS = 0.40       # centre fraction of width treated as "ahead"
FRONT_ROWS = 0.55       # upper fraction of ROI treated as "ahead"
FRONT_ENTER = 0.45      # front fill this high -> a corner is here
FRONT_EXIT = 0.22       # front cleared below this -> corner finished
CORNER_TOTAL = 0.55     # left+right fill meaning a wall is AHEAD (density method)

MIN_CORNER_CYCLES = 6   # must be in the corner this long before it counts
MAX_CORNER_CYCLES = 90  # safety: never stay stuck in a corner
CORNER_DEBOUNCE = 25    # min CYCLES between two counted corners

# TIME-based guard: a real corner cannot physically happen twice within this
# many seconds. This is the reliable one - cycle counts change with frame rate,
# seconds do not. Raise it if one corner gets counted twice; lower it if a
# genuine corner is missed because it came too soon after the previous one.
CORNER_MIN_INTERVAL_S = 1.2
CORNER_MAX_INTERVAL_S = 25.0   # if no corner for this long, something is wrong
                               # (logged as a warning, does not stop the run)

QUADRANTS_PER_RUN = 12  # 12 corners = 3 laps
FINISH_EXTRA_CYCLES = 60   # keep driving briefly after the last corner
MAX_RUNTIME_S = 90      # SAFETY: hard stop after this long

# ==========================================================================
# COLOURED LINES (direction hint only - NOT required for lap counting)
# ==========================================================================
LINE_FRACTION = 0.020   # a line is "present" above this fraction of the ROI
LINE_DEBOUNCE = 10      # cycles before the same line can trigger again
USE_LINES_FOR_DIRECTION = True   # False = decide direction purely from geometry

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
NAV_METHOD = "gap"      # "gap"     = free-space follow-the-gap (method B)
                        # "density" = KyivRoboMagic wall-density (proven fallback)

FORCE_DIRECTION = 0     # 0 = decide automatically (first line, else first corner)
                        # +1 = force clockwise, -1 = force counter-clockwise
                        # Use this if the judges tell you the run direction.

INVERT_STEERING = False # True if the servo turns the wrong way after a rebuild
INVERT_MOTOR = False    # True if the motor drives backwards after a rewire

DEBUG_EVERY = 15        # print a status line every N cycles (0 = silent)
SAVE_DEBUG_FRAMES = 0   # save an annotated frame every N cycles (0 = off).
                        # Useful to review a bad run; costs ~10ms per save.
