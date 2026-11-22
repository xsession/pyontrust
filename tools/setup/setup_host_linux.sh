#!/usr/bin/env bash
# pyontrust host setup (Ubuntu/Debian): packages, USB access and CAN for the bench hardware.
#
#   sudo tools/setup/setup_host_linux.sh [--can-bitrate 500000] [--no-can] [--dry-run]
#
# Idempotent — safe to run again. What it does:
#   1. apt packages: hackrf (tools for HackRF), dfu-util (HackRF/nRF recovery),
#      can-utils (candump/cansend), adb, libusb
#   2. adds the user to 'dialout' (serial: PPK2, nRF dongle) and 'plugdev' (USB devices)
#   3. one udev rule file, /etc/udev/rules.d/60-pyontrust.rules:
#        Nordic (PPK2, nRF52840 dongle + its bootloader), SEGGER J-Link, HackRF (+ DFU mode),
#        Seek Thermal, PEAK PCAN — group plugdev; ModemManager told to ignore Nordic/SEGGER
#        serial ports (its AT-command probing upsets them);
#        CAN interfaces brought up automatically at --can-bitrate when the adapter appears
#   4. reloads udev and re-triggers the attached devices (replugging is not needed)
set -euo pipefail

CAN_BITRATE=500000
CAN=1
DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --can-bitrate) CAN_BITRATE="$2"; shift 2 ;;
    --no-can) CAN=0; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

run() { echo "+ $*"; [ "$DRY" = 1 ] || "$@"; }

if [ "$DRY" = 0 ] && [ "$(id -u)" -ne 0 ]; then
  exec sudo -- "$0" "$@" ${CAN_BITRATE:+--can-bitrate "$CAN_BITRATE"} $([ "$CAN" = 0 ] && echo --no-can)
fi
TARGET_USER="${SUDO_USER:-$(logname 2>/dev/null || echo "$USER")}"
case "$CAN_BITRATE" in (*[!0-9]*|'') echo "bad --can-bitrate: $CAN_BITRATE" >&2; exit 2 ;; esac

echo "== 1/4 packages"
run apt-get update -qq
run env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  hackrf dfu-util can-utils adb libusb-1.0-0

echo "== 2/4 groups for $TARGET_USER"
for g in dialout plugdev; do
  if id -nG "$TARGET_USER" | tr ' ' '\n' | grep -qx "$g"; then
    echo "   already in $g"
  else
    run usermod -aG "$g" "$TARGET_USER"
    echo "   added to $g (takes effect at the next login)"
  fi
done

echo "== 3/4 udev rules"
RULES=/etc/udev/rules.d/60-pyontrust.rules
IP=$(command -v ip || echo /usr/sbin/ip)
TMP=$(mktemp)
cat > "$TMP" <<EOF
# pyontrust bench hardware — written by tools/setup/setup_host_linux.sh (safe to regenerate)

# Nordic Semiconductor: PPK2, nRF52840 dongle (+ Open DFU bootloader 1915:521f)
SUBSYSTEM=="usb", ATTR{idVendor}=="1915", MODE="0660", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="tty", ATTRS{idVendor}=="1915", MODE="0660", GROUP="dialout", ENV{ID_MM_DEVICE_IGNORE}="1"
ATTRS{idVendor}=="1915", ENV{ID_MM_DEVICE_IGNORE}="1"

# SEGGER J-Link (and J-Link OB virtual COM ports)
SUBSYSTEM=="usb", ATTR{idVendor}=="1366", MODE="0660", GROUP="plugdev", TAG+="uaccess"
ATTRS{idVendor}=="1366", ENV{ID_MM_DEVICE_IGNORE}="1"

# HackRF One / Jawbreaker / rad1o, and HackRF in DFU recovery mode (NXP LPC 1fc9:000c)
SUBSYSTEM=="usb", ATTR{idVendor}=="1d50", ATTR{idProduct}=="6089|604b|cc15", MODE="0660", GROUP="plugdev", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="1fc9", ATTR{idProduct}=="000c", MODE="0660", GROUP="plugdev", TAG+="uaccess"

# Seek Thermal
SUBSYSTEM=="usb", ATTR{idVendor}=="289d", MODE="0660", GROUP="plugdev", TAG+="uaccess"

# PEAK-System PCAN
SUBSYSTEM=="usb", ATTR{idVendor}=="0c72", MODE="0660", GROUP="plugdev", TAG+="uaccess"
EOF
if [ "$CAN" = 1 ]; then
  cat >> "$TMP" <<EOF

# CAN adapters: up at ${CAN_BITRATE} bit/s as soon as they appear
ACTION=="add", SUBSYSTEM=="net", KERNEL=="can*", RUN+="$IP link set %k type can bitrate ${CAN_BITRATE}", RUN+="$IP link set %k up"
EOF
fi
if [ "$DRY" = 1 ]; then
  echo "+ would write $RULES:"; sed 's/^/    /' "$TMP"; rm -f "$TMP"
else
  install -m 0644 "$TMP" "$RULES"; rm -f "$TMP"
  echo "   wrote $RULES"
fi

echo "== 4/4 apply"
run udevadm control --reload-rules
run udevadm trigger --subsystem-match=usb --subsystem-match=tty --action=change
if [ "$CAN" = 1 ]; then
  for dev in /sys/class/net/can*; do
    [ -e "$dev" ] || continue
    n=$(basename "$dev")
    if [ "$(cat "$dev/operstate")" != "up" ]; then
      run "$IP" link set "$n" type can bitrate "$CAN_BITRATE"
      run "$IP" link set "$n" up
    fi
    echo "   $n: $(cat "$dev/operstate")"
  done
fi

echo
echo "Done. hackrf_info: $(command -v hackrf_info || echo 'not found')"
echo "Group changes need a new login (until then: sg dialout -c '<command>')."
