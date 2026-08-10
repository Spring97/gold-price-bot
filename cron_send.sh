#!/bin/bash
# 黄金价格推送 - cron调用脚本
# 通过cron在每小时的 :00 和 :30 触发
# 脚本会自动判断是否在开市时段，非开市时段自动跳过

# 自动获取脚本所在目录（兼容各种部署路径）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
LOCK_FILE="/tmp/gold_price_bot_cron.lock"

# 防止重复执行（锁文件2分钟内有效）
if [ -f "$LOCK_FILE" ]; then
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK_FILE") ))
    if [ "$LOCK_AGE" -lt 120 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') 上次执行还在进行中(锁文件年龄${LOCK_AGE}秒)，跳过"
        exit 0
    fi
fi

touch "$LOCK_FILE"

# 执行单次推送（脚本内部会判断开市时段）
cd "$SCRIPT_DIR"
$PYTHON main.py --once >> "$SCRIPT_DIR/logs/cron.log" 2>&1

# 清除锁文件
rm -f "$LOCK_FILE"
