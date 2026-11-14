#!/bin/bash
# Install the UPS HAT (E) monitor. Run on the Pi:  sudo bash install.sh
# Enables I2C, installs python3-smbus and i2c-tools, and starts the syntaxlab-ups service.
# Settings (thresholds, dry run) go in /etc/default/syntaxlab-ups; see syntaxlab-ups.py.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"

echo "== Enabling I2C"
raspi-config nonint do_i2c 0
modprobe i2c-dev || true

echo "== Installing packages"
apt-get install -y python3-smbus i2c-tools

echo "== Installing the monitor"
install -m 0755 "$here/syntaxlab-ups.py" /usr/local/bin/syntaxlab-ups.py
install -m 0644 "$here/syntaxlab-ups.service" /etc/systemd/system/syntaxlab-ups.service
if [ ! -f /etc/default/syntaxlab-ups ]; then
  printf '%s\n' \
    '# Overrides for syntaxlab-ups (see /usr/local/bin/syntaxlab-ups.py).' \
    '# UPS_SHUTDOWN_PERCENT=10' \
    '# UPS_DRY_RUN=1' > /etc/default/syntaxlab-ups
fi
systemctl daemon-reload
systemctl enable syntaxlab-ups
systemctl restart syntaxlab-ups   # picks up a new version when run again

echo "== Checks"
i2cdetect -y 1 | sed -n '1p;4p'   # the HAT answers at 0x2d
python3 /usr/local/bin/syntaxlab-ups.py status
systemctl --no-pager --lines 5 status syntaxlab-ups
