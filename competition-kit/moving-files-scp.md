# Moving files between the laptop and the Pi

Everything here is `scp`, run **from the laptop**, in **Git Bash** (not
PowerShell — see the gotchas at the end).

The shape is always the same:

```
scp  <where it is now>  <where it should go>
```

and a remote place is written `pi@raspberrypi:path`.

---

## The four you will actually use

### Send one file to the Pi

```bash
scp src/open_challenge.py pi@raspberrypi:wro2026/
```

The trailing `/` means "into that directory, keep the name". Without it you are
naming the destination file, which is how you accidentally create
`wro2026/open_challenge` with no extension.

### Send a whole folder

```bash
scp -r src/tools pi@raspberrypi:wro2026/
```

`-r` is recursive. Note this puts it at `wro2026/tools`, and if `tools` already
exists it **merges into it**, overwriting same-named files.

### Fetch one file from the Pi

```bash
scp pi@raspberrypi:wro2026/logs/open_log.csv diag/
```

### Fetch everything matching a pattern

```bash
scp "pi@raspberrypi:wro2026/logs/obstacle_*.csv" diag/obs/
```

**Quote the remote pattern.** Unquoted, your laptop's shell tries to expand
`*.csv` locally, finds nothing, and the command fails. Quoted, the `*` reaches
the Pi and expands there.

---

## The project's own shortcuts

You rarely need raw `scp` — the repo has wrappers:

```bash
./sync.sh push          # laptop -> Pi   (src/, tools/, docs/)
./sync.sh pull          # Pi -> laptop
./backup.sh save        # full snapshot of the Pi into backups/
```

> `./sync.sh push` **overwrites** whatever is on the Pi. If you tuned numbers on
> the Pi, `./sync.sh pull` first, or those edits are gone. This has bitten us:
> always check with a diff before pushing.

Check before you overwrite:

```bash
scp pi@raspberrypi:wro2026/obstacle_challenge.py /tmp/theirs.py
diff src/obstacle_challenge.py /tmp/theirs.py
```

---

## Useful variations

| What you want | Command |
|---|---|
| Keep timestamps | `scp -p file pi@raspberrypi:wro2026/` |
| See progress on a big file | `scp -v file pi@raspberrypi:wro2026/` |
| Several files at once | `scp a.py b.py c.py pi@raspberrypi:wro2026/tools/` |
| A file with spaces in the name | `scp "my file.png" pi@raspberrypi:wro2026/` |
| From the Pi's home directory | `pi@raspberrypi:wro2026/...` — paths are relative to `/home/pi` |
| An absolute path on the Pi | `pi@raspberrypi:/boot/firmware/config.txt` |

### Faster for many files: rsync

`scp` re-sends everything. `rsync` sends only what changed:

```bash
rsync -av --progress src/tools/ pi@raspberrypi:wro2026/tools/
```

The **trailing slash on the source matters**: `src/tools/` copies the *contents*
into `tools/`; `src/tools` would create `tools/tools`.

---

## Running something without copying it

Often you do not need to copy at all:

```bash
ssh pi@raspberrypi "cd wro2026 && source .venv/bin/activate && python tools/wall_calib.py cw"
```

And to pull a file straight into a local one:

```bash
ssh pi@raspberrypi "cat wro2026/logs/open_log.csv" > diag/open_log.csv
```

---

## Gotchas on THIS setup

These are all things that have actually gone wrong here.

### 1. Use Git Bash, not PowerShell

PowerShell has its own `scp`, but the quoting differs and remote globs behave
badly. Every command in this repo assumes Git Bash.

### 2. `/tmp` is not the same place in both shells

Git Bash's `/tmp` maps to a Windows temp folder that **Python cannot see** at
that path. So this fails:

```bash
scp pi@raspberrypi:wro2026/file.py /tmp/f.py    # lands in Git Bash's /tmp
python -c "open('/tmp/f.py')"                   # Python: file not found
```

Copy into the repo (e.g. `diag/`) instead, or use a full Windows path.

### 3. The hostname is not always resolvable

Measured on this laptop:

```
raspberrypi        -> works on the hotspot (Windows ICS DNS)
raspberrypi.local  -> FAILS from Git Bash (no mDNS there)
```

and it is intermittent — `scp` has failed with *"Could not resolve hostname
raspberrypi"* seconds after a successful one. If that happens, **just retry**;
it usually works on the second attempt. If it keeps failing, the Pi is off, or
the hotspot is down, or a VPN (ProtonVPN) is hijacking DNS — disconnect it.

Over the direct Ethernet cable, see `new-laptop-setup.md` for the hosts entry.

### 4. Line endings

Windows Git may write CRLF into files. Python does not care, but a **shell
script** with CRLF fails on the Pi with a confusing `bad interpreter` error. If
a `.sh` you copied misbehaves:

```bash
ssh pi@raspberrypi "cd wro2026 && sed -i 's/\r$//' tools/venue_net.sh && chmod +x tools/venue_net.sh"
```

### 5. The executable bit is lost

`scp` from Windows does not carry the executable bit, so a copied `.sh` or tool
arrives non-executable:

```bash
ssh pi@raspberrypi "chmod +x wro2026/*.sh wro2026/tools/*.py"
```

### 6. Do not copy over a running program

If `obstacle_challenge.py` is running and holding the camera and GPIO, copying a
new version does **not** affect the running one — but the next run uses the new
file, so it is easy to think you tested a change you did not. Check first:

```bash
ssh pi@raspberrypi "ps -eo pid,etime,cmd | grep -E 'open_challenge|obstacle_challenge' | grep -v grep"
```

---

## Verifying a copy actually landed

Byte counts and a content compare, ignoring line endings:

```bash
ssh pi@raspberrypi "wc -c < wro2026/open_challenge.py"
wc -c < src/open_challenge.py

diff <(tr -d '\r' < src/open_challenge.py) \
     <(ssh pi@raspberrypi "cat wro2026/open_challenge.py" | tr -d '\r') \
  && echo IDENTICAL
```

An md5 comparison will show a **false difference** if one side has CRLF and the
other LF — strip `\r` from both first, as above.

---

## Where things live on the Pi

```
/home/pi/wro2026/
    open_challenge.py            the two programs
    obstacle_challenge.py
    openchallengejoliancompetetionday.py    your own copy
    run.sh  autostart.sh         what the boot service runs
    robot.py config.py camera.py the older library (tools import these)
    colors.json  camera_settings.json  servo_center.txt   settings, read by name
    tools/                       tuning and diagnostic tools
    tools/scratch/               one-off probes, kept for reference
    logs/                        one timestamped CSV per run
    frames/                      captured images
    old/  docs/  color_check/    archive
    .venv/                       the Python environment - never copy over this
```

> **Never `scp` into `.venv/`** and never `sync.sh push` something that would
> overwrite it. Rebuilding it at a venue with no internet is not possible.
