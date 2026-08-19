# ==========================================================================
# new-laptop-check.ps1 - is this laptop ready to reach the Pi over Ethernet?
#
#   powershell -ExecutionPolicy Bypass -File .\new-laptop-check.ps1
#
# Read-only by default. To also write the hosts entry that makes the BARE
# name "raspberrypi" work, run it as Administrator with:
#
#   powershell -ExecutionPolicy Bypass -File .\new-laptop-check.ps1 -AddHostsEntry
#
# The Pi needs nothing changed. Its eth0 is in NetworkManager "shared" mode:
# fixed at 192.168.50.1, running its own DHCP server for 192.168.50.10-254.
# ==========================================================================
param(
    [switch]$AddHostsEntry
)

$PI_IP   = "192.168.50.1"
$PI_NAME = "raspberrypi"
$ok = 0
$bad = 0

function Say-Good($m) { Write-Host "  [ OK ]  $m" -ForegroundColor Green; $script:ok++ }
function Say-Bad($m)  { Write-Host "  [FAIL]  $m" -ForegroundColor Red;   $script:bad++ }
function Say-Warn($m) { Write-Host "  [ ?? ]  $m" -ForegroundColor Yellow }
function Section($m)  { Write-Host ""; Write-Host "=== $m ===" -ForegroundColor Cyan }

Write-Host ""
Write-Host "==========================================================="
Write-Host "  SECOND LAPTOP -> RASPBERRY PI OVER ETHERNET"
Write-Host "==========================================================="

# ---------------------------------------------------------------- 1. adapter
Section "1. Is there a working wired adapter?"
$wired = Get-NetAdapter | Where-Object {
    $_.InterfaceDescription -notmatch "Wi-?Fi|Wireless|Bluetooth|Virtual|Loopback|TAP|WAN Miniport|Hyper-V|VirtualBox|WireGuard"
}
if ($wired) {
    foreach ($a in $wired) {
        Write-Host ("     {0,-22} {1,-14} {2}" -f $a.Name, $a.Status, $a.InterfaceDescription)
    }
    $usable = $wired | Where-Object { $_.Status -eq "Up" -or $_.Status -eq "Disconnected" }
    if ($usable) {
        Say-Good "a wired adapter exists (Disconnected just means no cable yet)"
    } else {
        Say-Bad "wired adapters exist but none are usable - check Device Manager"
    }
} else {
    Say-Bad "NO wired adapter at all. This is what stopped the first laptop."
    Write-Host "          A USB-to-Ethernet adapter fixes it. Buy one that works" -ForegroundColor Yellow
    Write-Host "          without a driver download, or install its driver NOW." -ForegroundColor Yellow
}

# ---------------------------------------------------------------- 2. ssh
Section "2. Is the SSH client installed?"
$sshCmd = Get-Command ssh -ErrorAction SilentlyContinue
if ($sshCmd) {
    Say-Good ("ssh found at " + $sshCmd.Source)
} else {
    Say-Bad "ssh is NOT installed"
    Write-Host "          Fix (as Administrator, needs internet):" -ForegroundColor Yellow
    Write-Host "          Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0" -ForegroundColor Yellow
}

# ---------------------------------------------------------------- 3. address
Section "3. Has the Pi handed this laptop an address?"
$addr = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -like "192.168.50.*" }
if ($addr) {
    Say-Good ("this laptop is " + $addr[0].IPAddress + " on the Pi's cable")
} else {
    $apipa = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
             Where-Object { $_.IPAddress -like "169.254.*" }
    $cableIn = $false
    if ($wired) {
        $cableIn = [bool]($wired | Where-Object { $_.Status -eq "Up" })
    }
    if ($apipa -and $cableIn) {
        Say-Bad "cable is IN but no DHCP reply - self-assigned 169.254.x.x"
        Write-Host "          The Pi is probably still booting, or its eth0 is not" -ForegroundColor Yellow
        Write-Host "          in shared mode. Check with venue_net.sh status." -ForegroundColor Yellow
    } elseif ($apipa) {
        Say-Warn "169.254.x.x on a DISCONNECTED adapter - that is just 'no cable'"
    } else {
        Say-Warn "no 192.168.50.x address - cable not connected, or Pi is off"
    }
    Write-Host "          The wired adapter must be on 'Obtain an IP address" -ForegroundColor Yellow
    Write-Host "          automatically'. A static IP here breaks it." -ForegroundColor Yellow
}

# ---------------------------------------------------------------- 4. reach
Section "4. Can the Pi be reached?"
$pinged = Test-Connection -ComputerName $PI_IP -Count 2 -Quiet -ErrorAction SilentlyContinue
if ($pinged) {
    Say-Good "$PI_IP answers"
} else {
    Say-Warn "$PI_IP does not answer (expected if the Pi is off or unplugged)"
}

foreach ($n in @("$PI_NAME.local", $PI_NAME)) {
    $resolved = $null
    try { $resolved = [System.Net.Dns]::GetHostAddresses($n) } catch { }
    if ($resolved) {
        $ips = ($resolved | ForEach-Object { $_.IPAddressToString } | Select-Object -Unique) -join ", "
        Say-Good "$n resolves to $ips"
    } else {
        if ($n -eq $PI_NAME) {
            Say-Warn "$n does not resolve - this is NORMAL over a direct cable"
            Write-Host "          There is no DNS server on that link to append .local" -ForegroundColor Yellow
            Write-Host "          for you. Re-run this script as Administrator with" -ForegroundColor Yellow
            Write-Host "          -AddHostsEntry to make the bare name work." -ForegroundColor Yellow
        } else {
            Say-Warn "$n does not resolve (Pi off, or mDNS unavailable)"
        }
    }
}

# ---------------------------------------------------------------- 5. hosts
Section "5. The hosts entry for the bare name"
$hosts = "$env:SystemRoot\System32\drivers\etc\hosts"
$already = $false
if (Test-Path $hosts) {
    $already = (Select-String -Path $hosts -Pattern "^\s*$([regex]::Escape($PI_IP))\s+$PI_NAME\b" -Quiet)
}
if ($already) {
    Say-Good "hosts already maps $PI_IP -> $PI_NAME"
} elseif ($AddHostsEntry) {
    $admin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $admin) {
        Say-Bad "-AddHostsEntry needs Administrator. Re-run PowerShell as Admin."
    } else {
        try {
            Add-Content -Path $hosts -Value ("`r`n$PI_IP`t$PI_NAME") -Encoding utf8 -ErrorAction Stop
            Say-Good "added: $PI_IP  $PI_NAME  (ssh pi@$PI_NAME will now work)"
        } catch {
            Say-Bad ("could not write hosts: " + $_.Exception.Message)
        }
    }
} else {
    Say-Warn "not set. Re-run as Administrator with -AddHostsEntry to add it."
    Write-Host "          Safe to hard-code because the Pi's WIRED address is" -ForegroundColor Yellow
    Write-Host "          static. On Wi-Fi the Pi has a different address, so" -ForegroundColor Yellow
    Write-Host "          prefer raspberrypi.local if you use both." -ForegroundColor Yellow
}

# ---------------------------------------------------------------- 6. repo
Section "6. Is the code on this laptop?"
if (Test-Path ".\src\open_challenge.py") {
    Say-Good "repository is here"
} else {
    Say-Warn "run this from inside the cloned repo, or clone it:"
    Write-Host "          git clone https://github.com/jolianjij/Red-Castle-WRO-Future-Engineers-2026.git" -ForegroundColor Yellow
    Write-Host "          Do that NOW - there is no internet at the venue." -ForegroundColor Yellow
}

# ---------------------------------------------------------------- summary
Write-Host ""
Write-Host "==========================================================="
if ($bad -eq 0) {
    Write-Host ("  $ok checks passed, nothing failed.") -ForegroundColor Green
} else {
    Write-Host ("  $ok passed, $bad FAILED - see the red lines above.") -ForegroundColor Red
}
Write-Host ""
Write-Host "  Once the Pi is on and the cable is in:"
Write-Host "      ssh pi@$PI_NAME"
Write-Host "      ssh pi@$PI_NAME `"cd wro2026 && ./tools/venue_net.sh status`""
Write-Host ""
Write-Host "  Only turn the radios off AFTER the wired link is proven:"
Write-Host "      ./tools/venue_net.sh wifi-off"
Write-Host "  It refuses unless the laptop has really taken an address."
Write-Host "==========================================================="
