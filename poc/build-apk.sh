#!/usr/bin/env bash
# 一键打包 Android Demo APK 并准备好待装。
# 用法：./build-apk.sh           # 编 + 拷贝到 /tmp/autoluyin-apk/
#       ./build-apk.sh --install # 加上 adb install 到当前连接的手机
#       ./build-apk.sh --serve   # 加上 HTTP server 让手机浏览器下载

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANDROID_DIR="$SCRIPT_DIR/android"
STAGING_DIR="/tmp/autoluyin-apk"
APK_NAME="autoluyin-demo-$(date +%Y%m%d-%H%M).apk"

# Android SDK 路径自动探测
export ANDROID_HOME="${ANDROID_HOME:-/opt/homebrew/share/android-commandlinetools}"
if [[ ! -d "$ANDROID_HOME" ]]; then
    echo "❌ ANDROID_HOME 不存在：$ANDROID_HOME"
    echo "   先装：brew install --cask android-commandlinetools"
    exit 1
fi
export PATH="$ANDROID_HOME/platform-tools:$PATH"

echo "==> 编译 APK ..."
cd "$ANDROID_DIR"
./gradlew --quiet assembleDebug

SRC_APK="$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk"
if [[ ! -f "$SRC_APK" ]]; then
    echo "❌ 编译失败，找不到 $SRC_APK"
    exit 1
fi

mkdir -p "$STAGING_DIR"
# 清理同名/历史版本，避免堆积
rm -f "$STAGING_DIR"/autoluyin-demo-*.apk "$STAGING_DIR"/app-debug.apk
cp "$SRC_APK" "$STAGING_DIR/$APK_NAME"
cp "$SRC_APK" "$STAGING_DIR/app-debug.apk"  # 固定文件名，方便 URL 引用

SIZE=$(du -h "$STAGING_DIR/$APK_NAME" | awk '{print $1}')
echo
echo "✅ 打包完成（$SIZE）"
echo "   $STAGING_DIR/$APK_NAME"
echo "   $STAGING_DIR/app-debug.apk  （固定别名）"

# Mac 内网 IP（过滤回环和虚拟网卡）
LAN_IP=$(ifconfig | awk '/inet / && $2 != "127.0.0.1" && $2 !~ /^198\.18\./ {print $2; exit}')

case "${1:-}" in
    --install)
        echo
        echo "==> adb install ..."
        if ! adb devices | grep -q "device$"; then
            echo "❌ 没检测到已授权的设备"
            echo "   小米手机：开发者选项 → USB 调试 + USB 调试（安全设置）"
            echo "   插 USB → 弹窗选 \"始终允许\""
            exit 1
        fi
        adb install -r "$STAGING_DIR/app-debug.apk"
        echo "✅ 已装机"
        ;;

    --serve)
        echo
        echo "==> 局域网 HTTP 下载："
        echo "   手机浏览器访问  http://$LAN_IP:8088/app-debug.apk"
        echo "   Ctrl+C 停止"
        cd "$STAGING_DIR" && python3 -m http.server 8088
        ;;

    *)
        echo
        echo "下一步可选："
        echo "  USB 安装：     ./build-apk.sh --install"
        echo "  局域网下载：   ./build-apk.sh --serve   （手机访问 http://$LAN_IP:8088/app-debug.apk）"
        echo "  手动 adb：     $ANDROID_HOME/platform-tools/adb install $STAGING_DIR/app-debug.apk"
        ;;
esac
