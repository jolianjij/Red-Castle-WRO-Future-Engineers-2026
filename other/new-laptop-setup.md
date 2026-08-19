# Setting up a SECOND laptop on the Pi's Ethernet cable

The Pi is already configured and needs **nothing changed**. `eth0` runs in
NetworkManager *shared* mode: the Pi holds a fixed address and runs its own
DHCP server on that cable.

| | |
|---|---|
| Pi | `192.168.50.1` — fixed, always there |
| Laptop | `192.168.50.10`–`254` — handed out by the Pi |
| Cable | any normal patch cable (Pi 4 Ethernet is auto-MDIX, no crossover needed) |

So the second laptop needs its wired adapter on **"Obtain an IP address
automatically"**, which is the Windows default. Plug in, wait ~5 seconds, done.

---

## Do this BEFORE the venue, not at it

At the venue there is no internet and no wireless. Everything below that needs
a download must happen while you still have a connection.

### 1. Check the laptop actually has a working Ethernet port

This is the step that failed on the first laptop — the hardware was present but
Windows had no driver for it (`Code 45`, adapter absent from Settings).

```powershell
Get-NetAdapter | Format-Table Name, InterfaceDescription, Status, LinkSpeed
```

You want a row that is clearly a wired NIC (Realtek / Intel / "Ethernet") with
`Status` of `Up` or `Disconnected`. **`Disconnected` is fine** — that just means
no cable. If no wired row appears at all, that laptop cannot do this either, and
a USB-to-Ethernet adapter is the fix (buy one that works without a driver
download, or install its driver in advance).

### 2. Confirm the SSH client is installed

Windows 10/11 ship OpenSSH, but it can be absent on trimmed installs.

```powershell
Get-Command ssh
```

If missing:

```powershell
Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
```

### 3. Install a VNC viewer, if you want the desktop

RealVNC Viewer. Download it now. You connect to `raspberrypi:5900` once the
hosts entry below is in place (or `192.168.50.1:5900`).

### 4. Clone the repository

You will want the code, the tools and the docs on this machine too.

```bash
git clone https://github.com/jolianjij/Red-Castle-WRO-Future-Engineers-2026.git
```

Do this now — at the venue you cannot.

### 5. Make the bare hostname `raspberrypi` work

**MEASURED on this laptop, and it is the opposite of what you would expect:**

```
raspberrypi        -> WORKS    (Windows ICS DNS, while on the hotspot)
raspberrypi.local  -> FAILS    (Git Bash does not do mDNS here)
```

So do not rely on `.local`. Windows' own resolver handles it in PowerShell, but
the Git Bash `ssh` that every tool in this repo uses does not, on this machine.

Over a direct cable there is no DNS server at all and no search domain to append
`.local` for you, so neither name resolves on its own. Because the Pi's address
on that cable is fixed at `192.168.50.1`, one hosts-file line fixes it
permanently:

Open PowerShell **as Administrator**:

```powershell
Add-Content -Path C:\Windows\System32\drivers\etc\hosts -Value "`n192.168.50.1`traspberrypi" -Encoding utf8
```

Then `ssh pi@raspberrypi` works, with no `.local` and no address typed.

> **This entry is for the CABLE, and it breaks Wi-Fi access.** It is safe to
> hard-code only because the Pi's wired address is static. On the hotspot the Pi
> has a different address (192.168.137.x), and this entry would send you to
> 192.168.50.1, which is not reachable without the cable.
>
> So: **add it at the venue, remove it at home.** The script does both:
> `-AddHostsEntry` and `-RemoveHostsEntry`.
>
> At home on the hotspot you do not need it - the bare name already works there
> through Windows' own DNS.

---

## Connecting

```bash
ssh pi@raspberrypi
```

Password, or copy your key across:

```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh pi@raspberrypi "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

If you have no key on the new laptop yet:

```powershell
ssh-keygen -t ed25519
```

---

## What "working" looks like

```powershell
ipconfig | Select-String -Context 4 "Ethernet"
```

The wired adapter should show an address of `192.168.50.x`. **Windows will
label this network "Unidentified" or "No internet access" — that is correct
and expected.** There is no internet on that cable; there is only the Pi.

Then, from the Pi side:

```bash
ssh pi@raspberrypi "cd wro2026 && ./tools/venue_net.sh status"
```

That reports three separate things, each stronger than the last:

- **cable** — a carrier exists. Proves a cable is plugged in, nothing more; a
  router or an idle port raises carrier too.
- **address server** — the Pi's dnsmasq is running.
- **lease** — a real machine asked the Pi for an address and got one. This is
  the only one that proves the laptop is genuinely there.

---

## Turning the radios off at the venue

Only once the wired link is proven:

```bash
./tools/venue_net.sh wifi-off
```

It **refuses** unless the laptop has actually taken an address and answers a
ping. That guard exists because a carrier alone is not evidence, and turning
Wi-Fi off with no real wired path locks you out of the robot completely.

`./tools/venue_net.sh wifi-on` undoes it. If you ever lose both, a screen and
keyboard on the Pi plus `nmcli radio wifi on` recovers it.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| No `192.168.50.x` address | adapter set to a static IP | set it back to automatic |
| No address, adapter shows `169.254.x.x` | no DHCP reply — Pi not booted, or cable in the wrong port | wait for the Pi to finish booting, check the cable |
| `raspberrypi.local` fails | Git Bash does not do mDNS - MEASURED here | use the hosts entry; do not rely on `.local` |
| bare `raspberrypi` fails on the cable | no DNS server on a direct link | add the hosts entry (`-AddHostsEntry`) |
| bare `raspberrypi` fails at home | hosts entry still set from the venue | remove it (`-RemoveHostsEntry`) |
| `ssh: connection refused` | Pi still booting | wait, then retry |
| Works, but you suspect it is going over Wi-Fi | both interfaces are up and mDNS picked the Wi-Fi one | test with `ssh pi@192.168.50.1` explicitly — that address only exists on the cable |
| Windows firewall prompt | new network classified Public | nothing to allow; SSH and VNC are outbound |

## Do not plug this port into a venue network

The Pi is a DHCP server on this cable. On a network that already has one, the
two fight. If you ever need the Pi on a normal network instead:

```bash
sudo nmcli con mod "Wired connection 1" ipv4.method auto
```

and set it back to `shared` afterwards.
