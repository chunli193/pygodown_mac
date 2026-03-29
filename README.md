# PyGoDown
> 基于 Python + 极速解析的一站式视频下载工具

![Version](https://img.shields.io/badge/版本-v1.0.1-blue)
[![Platform macOS](https://img.shields.io/badge/平台-macOS-0099FF?logo=apple&logoColor=white)](https://192.168.4.115:3200/用户名/ffmpeg-installer/releases)

---

## 🔹 核心支持平台
- ✅ YouTube
- ✅ Bilibili（哔哩哔哩）

---

## 🔹 核心下载功能
### 下载模式
- 支持**单个视频**精准下载
- 支持**视频合集 / 播放列表**批量下载

### 画质选择
- 自由选择分辨率：360p-1080P / 2K（依视频源支持）
- 可自动匹配最高可用画质

### 格式支持
- 视频格式：MP4、MKV、WebM 等主流格式
- 音频格式：MP3、M4A、FLAC（纯音频提取）
- 自动完成音视频合并

---

## 🔹 基础特性
- ✅ 支持下载 Bilibili 弹幕文件（**后续考虑转 ASS 字幕**）
- ✅ 高速下载，无速度限制
- ✅ 运行平台：**Windows 优先支持**，macOS / Linux 后续规划
- ✅ FFmpeg 支持：**手动指定 / 自动识别** 二选一

---

## 📖 项目定位
**PyGoDown = Python + Go Fast + Download**

做一款**稳定开箱即用**视频下载工具。



>安装方法 拖入 **Applications** 即可
遇到打开闪退 根据需求 执行 下面命令

```
# 移除隔离属性
sudo xattr -r -d com.apple.quarantine /Applications/pygodown_v1.0.1_mac.app

# 允许任何来源
sudo spctl --master-disable

# 恢复安全设置
sudo spctl --master-enable
```