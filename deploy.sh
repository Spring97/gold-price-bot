#!/bin/bash
# ============================================================
#  黄金价格推送机器人 - 一键部署脚本
#  适用于 Linux 服务器（Ubuntu/CentOS/Debian 等）
# ============================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="${1:-/opt/gold_price_bot}"

echo ""
echo "============================================================"
echo "  黄金价格推送机器人 - 一键部署"
echo "============================================================"
echo "  部署目录: $INSTALL_DIR"
echo "============================================================"
echo ""

# 1. 检查 Python
info "步骤 1/5: 检查 Python 环境..."
if command -v python3 &> /dev/null; then
    PYTHON=python3
    PY_VER=$($PYTHON --version 2>&1)
    info "  找到 $PY_VER"
else
    error "  未找到 python3，请先安装 Python 3.6+"
    exit 1
fi

# 2. 安装依赖
info "步骤 2/5: 安装 Python 依赖..."
$PYTHON -m pip install -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null || {
    warn "  pip 安装失败，尝试使用系统包管理器..."
    if command -v apt-get &> /dev/null; then
        apt-get update -qq && apt-get install -y -qq python3-requests
    elif command -v yum &> /dev/null; then
        yum install -y python3-requests
    else
        error "  无法自动安装 requests，请手动执行: pip3 install requests"
        exit 1
    fi
}
info "  依赖安装完成"

# 3. 复制文件到部署目录
info "步骤 3/5: 部署文件到 $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR/logs"
cp "$SCRIPT_DIR"/*.py "$INSTALL_DIR/"
cp "$SCRIPT_DIR/cron_send.sh" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/cron_send.sh"
info "  文件部署完成"

# 4. 测试数据获取
info "步骤 4/5: 测试数据获取..."
cd "$INSTALL_DIR"
$PYTHON main.py --test 2>&1 | tail -8
if [ $? -ne 0 ]; then
    error "  数据获取测试失败，请检查网络连接"
    exit 1
fi

# 5. 设置定时任务
info "步骤 5/5: 配置 cron 定时任务..."

# 安装 cron（如果未安装）
if ! command -v crontab &> /dev/null; then
    warn "  crontab 未安装，正在安装..."
    if command -v apt-get &> /dev/null; then
        apt-get install -y -qq cron
    elif command -v yum &> /dev/null; then
        yum install -y cronie
    fi
fi

# 启动 cron 服务
if command -v systemctl &> /dev/null; then
    systemctl enable cron 2>/dev/null || systemctl enable crond 2>/dev/null || true
    systemctl start cron 2>/dev/null || systemctl start crond 2>/dev/null || true
elif command -v service &> /dev/null; then
    service cron start 2>/dev/null || service crond start 2>/dev/null || true
fi

# 设置 crontab（每小时 :00 和 :30 执行）
CRON_CMD="0,30 * * * * $INSTALL_DIR/cron_send.sh"
( crontab -l 2>/dev/null | grep -v "gold_price_bot" ; echo "$CRON_CMD" ) | crontab -
info "  cron 定时任务已配置: $CRON_CMD"

echo ""
echo "============================================================"
echo "  ✅ 部署完成！"
echo "============================================================"
echo ""
echo "  推送时段（北京时间）:"
echo "    日市: 周一至周五  09:00 - 15:30"
echo "    夜市: 周一至周五  20:00 - 次日 02:30"
echo "    频率: 每半小时 (:00 和 :30)"
echo ""
echo "  常用命令:"
echo "    立即推送:    $PYTHON $INSTALL_DIR/main.py --once --force"
echo "    测试数据:    $PYTHON $INSTALL_DIR/main.py --test"
echo "    查看调度:    $PYTHON $INSTALL_DIR/main.py --schedule"
echo "    守护进程:    $PYTHON $INSTALL_DIR/main.py --daemon"
echo ""
echo "  日志文件:"
echo "    $INSTALL_DIR/logs/gold_bot.log"
echo "    $INSTALL_DIR/logs/cron.log"
echo ""
echo "  查看 cron 配置:"
echo "    crontab -l"
echo ""
echo "  如需使用 systemd 守护进程（可选）:"
echo "    cp $INSTALL_DIR/gold_price_bot.service /etc/systemd/system/"
echo "    # 编辑其中的路径，然后执行:"
echo "    systemctl daemon-reload"
echo "    systemctl enable gold_price_bot"
echo "    systemctl start gold_price_bot"
echo "============================================================"
