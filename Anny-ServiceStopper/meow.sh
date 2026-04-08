#!/bin/bash

# patch_services.sh
# Adds ExecStartPost=/usr/sbin/apachectl stop to the [Service] section
# of nginx, mysql, grafana-server, and rsyslog systemd unit files
# make sure that its an executable by doing sudo bash -x ./meow.sh 2>&1

SERVICES=(nginx mysql grafana-server rsyslog)
EXEC_LINE="ExecStartPost=/usr/sbin/ stop"

# Must be run as root
if [[ $EUID -ne 0 ]]; then
  echo "ERROR: This script must be run as root (sudo)." >&2
  exit 1
fi

for SVC in "${SERVICES[@]}"; do

  echo "--- Processing: $SVC ---"

  # Verify the service exists
  if ! systemctl cat "$SVC" &>/dev/null; then
    echo "  SKIP: $SVC service not found, skipping."
    continue
  fi

  # Get the path of the unit file (first line of `systemctl cat` output)
  UNIT_FILE=$(systemctl cat "$SVC" 2>/dev/null | head -1 | sed 's/^# //')

  # Check if the line is already present (avoid duplicates)
  if grep -qF "$EXEC_LINE" "$UNIT_FILE" 2>/dev/null; then
    echo "  SKIP: '$EXEC_LINE' already present in $UNIT_FILE"
    continue
  fi

  # Use a SYSTEMD_EDITOR trick: supply our own editor script that patches the file
  PATCH_SCRIPT=$(mktemp /tmp/patch_editor_XXXXXX.sh)
  chmod +x "$PATCH_SCRIPT"

  cat > "$PATCH_SCRIPT" << 'EDITOR'
#!/bin/bash
# Inline editor: inserts ExecStartPost line after the last ExecStart= line
# inside [Service], then exits.
FILE="$1"
EXEC_LINE="ExecStartPost=/usr/sbin/ stop"

if grep -qF "$EXEC_LINE" "$FILE"; then
  exit 0   # already present, nothing to do
fi

# Insert after the last ExecStart= line using awk
awk -v line="$EXEC_LINE" '
  /^ExecStart=/ { found=1; print; next }
  found && !/^ExecStart=/ { print line; found=0 }
  { print }
' "$FILE" > "${FILE}.tmp" && mv "${FILE}.tmp" "$FILE"
EDITOR

  # Run systemctl edit --full with our custom editor
  SYSTEMD_EDITOR="$PATCH_SCRIPT" systemctl edit --full "$SVC"

  rm -f "$PATCH_SCRIPT"

  # Reload the daemon so systemd picks up the change
  systemctl daemon-reload

  echo "  OK: '$EXEC_LINE' added to $SVC unit file."
  echo "  Unit file: $(systemctl cat "$SVC" 2>/dev/null | head -1 | sed 's/^# //')"

done

echo ""
echo "Done. You may want to restart the affected services for changes to take effect:"
echo "  sudo systemctl restart nginx mysql grafana-server rsyslog"