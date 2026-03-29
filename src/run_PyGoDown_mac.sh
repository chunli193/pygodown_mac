#!/bin/bash

# PyGoDown 启动脚本 (macOS)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/pygodown_v1.0.0_mac.py"

echo "========================================"
echo "PyGoDown - 视频下载器 (macOS)"
echo "========================================"

# 检查Python3
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3，请先安装 Python"
    exit 1
fi

# 检查并安装依赖
echo ""
echo "[1/3] 检查依赖..."

check_package() {
    python3 -c "import $1" 2>/dev/null
}

if ! check_package "PyQt6"; then
    echo "正在安装 PyQt6..."
    pip3 install PyQt6
fi

if ! check_package "yt_dlp"; then
    echo "正在安装 yt-dlp..."
    pip3 install yt-dlp
fi

# 检查ffmpeg
echo ""
echo "[2/3] 检查 ffmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "警告: ffmpeg 未安装"
    echo ""
    echo "请运行以下命令安装:"
    echo "  brew install ffmpeg"
    echo ""
    read -p "是否继续启动? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
else
    echo "✓ ffmpeg 已安装"
fi

# 启动程序
echo ""
echo "[3/3] 启动程序..."
echo "========================================"
echo ""

cd "$SCRIPT_DIR"
python3 "$PYTHON_SCRIPT"
