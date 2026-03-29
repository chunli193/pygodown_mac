#!/usr/bin/env python3
"""
macOS 视频下载工具 - VidGrabber
基于 PyQt6 实现，支持 0.5x - 2x 缩放
自动检测并安装所需依赖
"""

import sys
import os
import threading
import subprocess
import glob

REQUIRED_PACKAGES = {
    "PyQt6": "PyQt6",
    "yt-dlp": "yt-dlp",
}


def check_and_install_dependencies():
    """检查并安装所需依赖"""
    missing = []

    for package, import_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name.replace("-", "_"))
            print(f"✓ {package} 已安装")
        except ImportError:
            missing.append(package)
            print(f"✗ {package} 未安装")

    if missing:
        print(f"\n正在安装缺失的依赖: {', '.join(missing)}")
        for package in missing:
            print(f"安装 {package}...")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", package],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print(f"✓ {package} 安装成功")
            except subprocess.CalledProcessError as e:
                print(f"✗ {package} 安装失败: {e}")
                return False
        return True
    return True


def check_brew_package(package_name):
    """检查brew是否安装了指定的包"""
    try:
        result = subprocess.run(
            ["brew", "list", package_name], capture_output=True, text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_ffmpeg():
    """检查ffmpeg是否存在，返回路径或None"""
    import shutil

    if shutil.which("ffmpeg"):
        return shutil.which("ffmpeg")

    common_paths = [
        "/usr/local/bin/ffmpeg",
        "/opt/homebrew/bin/ffmpeg",
        os.path.expanduser("~/anaconda3/bin/ffmpeg"),
        os.path.expanduser("~/miniconda3/bin/ffmpeg"),
    ]

    for path in common_paths:
        if os.path.exists(path):
            return path

    return None


def install_ffmpeg():
    """提示用户安装ffmpeg"""
    print("\n" + "=" * 50)
    print("ffmpeg 未安装或不在PATH中")
    print("=" * 50)
    print("\n推荐安装方式:")
    print("  方式1: 使用 Homebrew (推荐)")
    print("    brew install ffmpeg")
    print("\n  方式2: 使用 Anaconda")
    print("    conda install ffmpeg")
    print("=" * 50)

    if check_brew_package("ffmpeg"):
        print("\n检测到Homebrew已安装ffmpeg，请运行: brew link ffmpeg")
    else:
        print("\n请安装Homebrew后运行:")
        print(
            '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
        )
        print("\n然后运行: brew install ffmpeg")


from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QRadioButton,
    QGroupBox,
    QProgressBar,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QFileDialog,
    QMessageBox,
    QButtonGroup,
    QFrame,
    QSplitter,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QAction, QColor

try:
    import yt_dlp

    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False


class VideoDownloader(QMainWindow):
    """视频下载工具主窗口"""

    BASE_FONT_SIZE = 10
    MIN_SCALE = 0.5
    MAX_SCALE = 2.0

    progress_updated = pyqtSignal(int, str)
    status_updated = pyqtSignal(str)
    fetch_completed = pyqtSignal(str)
    fetch_failed = pyqtSignal(str)
    danmaku_log = pyqtSignal(str)
    danmaku_finished = pyqtSignal(bool, str)
    download_log = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self.scale_factor = 1.0
        self.base_font_size = self.BASE_FONT_SIZE
        self.current_download_title = ""
        self.is_downloading = False
        self.is_fetching = False
        self.ydl = None
        self.download_thread = None
        self.fetch_thread = None

        class YtLogger:
            def __init__(self, parent):
                self.parent = parent

            def _filter_text(self, text):
                if not text:
                    return ""
                return "".join(
                    c for c in text if c.isprintable() or c in "中文中文简体繁体汉字"
                )

            def debug(self, msg):
                if msg.strip():
                    clean_msg = self._filter_text(msg)
                    if clean_msg:
                        self.parent.download_log.emit(clean_msg)

            def warning(self, msg):
                if msg.strip():
                    clean_msg = self._filter_text(msg)
                    if clean_msg:
                        self.parent.download_log.emit(f"[警告] {clean_msg}")

            def error(self, msg):
                if msg.strip():
                    clean_msg = self._filter_text(msg)
                    if clean_msg:
                        self.parent.download_log.emit(f"[错误] {clean_msg}")

        self._yt_logger = YtLogger(self)

        self.init_ui()
        self.set_default_download_path()

        self.progress_updated.connect(self._on_progress_updated)
        self.status_updated.connect(self._on_status_updated)
        self.fetch_completed.connect(self._on_fetch_completed)
        self.fetch_failed.connect(self._on_fetch_failed)
        self.danmaku_log.connect(self._on_danmaku_log)
        self.danmaku_finished.connect(self._on_danmaku_finished)
        self.download_log.connect(self._on_download_log)

    def _on_progress_updated(self, percent, speed):
        """处理进度更新"""
        self.progress_bar.setValue(percent)
        self.status_label.setText(f"下载中... {percent:.1f}% {speed}")
        self.speed_label.setText(f"下载速度: {speed}")
        self.download_speed_label.setText(speed)
        self.update_download_list_item(speed, percent)

    def _on_fetch_completed(self, title):
        """获取视频信息成功"""
        self.video_info_label.setText(f"标题: {title}")
        self.status_label.setText("视频信息获取成功")
        self.status_label.setStyleSheet(
            "color: white; background-color: #333; padding: 5px; border-radius: 3px;"
        )
        self.download_btn.setEnabled(True)
        if "bilibili.com" in self.url_input.text():
            self.danmaku_btn.setEnabled(True)

    def _on_fetch_failed(self, error_msg):
        """获取视频信息失败"""
        self.status_label.setText("获取视频信息失败")
        self.log(f"获取视频信息失败: {error_msg}")

    def _on_danmaku_log(self, message):
        """弹幕下载日志"""
        self.log(message)

    def _on_download_log(self, message):
        """处理下载日志"""
        self.log(message)

    def _on_danmaku_finished(self, success, message):
        """弹幕下载完成"""
        if success:
            self.status_label.setText("弹幕下载成功!")
            self.status_label.setStyleSheet(
                "color: white; background-color: #333; padding: 5px; border-radius: 3px;"
            )
            self.log(message)
        else:
            self.status_label.setText("弹幕下载失败")
            self.log(message)
        self.danmaku_btn.setEnabled(True)

    def _on_status_updated(self, status):
        """处理状态更新"""
        self.status_label.setText(status)
        if "下载" in status or "合并" in status or "转码" in status:
            self.status_label.setStyleSheet(
                "color: white; background-color: #2196F3; padding: 5px; border-radius: 3px;"
            )
        else:
            self.status_label.setStyleSheet(
                "color: white; background-color: #333; padding: 5px; border-radius: 3px;"
            )

    def init_ui(self):
        """初始化UI界面"""
        self.setWindowTitle("PyGoDown - 视频下载器")
        self.setGeometry(100, 100, 600, 400)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        title_label = QLabel("PyGoDown (macOS)")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        url_layout = QVBoxLayout()
        url_label = QLabel("视频URL:")
        url_label.setFont(QFont("", self.base_font_size))
        url_layout.addWidget(url_label)

        self.url_input = QLineEdit()
        self.url_input.setFont(QFont("", self.base_font_size))
        self.url_input.setPlaceholderText("请输入视频链接...")
        self.url_input.textChanged.connect(self.on_url_changed)
        url_layout.addWidget(self.url_input)
        main_layout.addLayout(url_layout)

        path_layout = QVBoxLayout()
        path_label = QLabel("保存路径:")
        path_label.setFont(QFont("", self.base_font_size))
        path_layout.addWidget(path_label)

        path_input_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setFont(QFont("", self.base_font_size))
        path_input_layout.addWidget(self.path_input)

        self.browse_btn = QPushButton("浏览")
        self.browse_btn.setFont(QFont("", self.base_font_size))
        self.browse_btn.clicked.connect(self.browse_folder)
        path_input_layout.addWidget(self.browse_btn)
        path_layout.addLayout(path_input_layout)
        main_layout.addLayout(path_layout)

        ffmpeg_layout = QVBoxLayout()
        ffmpeg_label = QLabel("FFmpeg路径 (可选):")
        ffmpeg_label.setFont(QFont("", self.base_font_size))
        ffmpeg_layout.addWidget(ffmpeg_label)

        ffmpeg_input_layout = QHBoxLayout()
        self.ffmpeg_input = QLineEdit()
        self.ffmpeg_input.setFont(QFont("", self.base_font_size))
        self.ffmpeg_input.setPlaceholderText("自动检测ffmpeg")
        self.ffmpeg_input.setText("")
        ffmpeg_input_layout.addWidget(self.ffmpeg_input)

        self.ffmpeg_browse_btn = QPushButton("浏览")
        self.ffmpeg_browse_btn.setFont(QFont("", self.base_font_size))
        self.ffmpeg_browse_btn.clicked.connect(self.browse_ffmpeg)
        ffmpeg_input_layout.addWidget(self.ffmpeg_browse_btn)
        ffmpeg_layout.addLayout(ffmpeg_input_layout)
        main_layout.addLayout(ffmpeg_layout)

        options_group = QGroupBox("下载选项")
        options_layout = QHBoxLayout()

        format_label = QLabel("格式:")
        format_label.setFont(QFont("", self.base_font_size))
        options_layout.addWidget(format_label)

        self.format_group = QButtonGroup(self)
        self.mp4_radio = QRadioButton("MP4 (视频)")
        self.mp4_radio.setFont(QFont("", self.base_font_size))
        self.mp4_radio.setChecked(True)
        self.mp4_radio.toggled.connect(self.on_format_changed)
        self.format_group.addButton(self.mp4_radio)
        options_layout.addWidget(self.mp4_radio)

        self.mp3_radio = QRadioButton("MP3 (音频)")
        self.mp3_radio.setFont(QFont("", self.base_font_size))
        self.format_group.addButton(self.mp3_radio)
        options_layout.addWidget(self.mp3_radio)

        options_layout.addSpacing(30)

        quality_label = QLabel("视频质量:")
        quality_label.setFont(QFont("", self.base_font_size))
        options_layout.addWidget(quality_label)

        self.quality_combo = QComboBox()
        self.quality_combo.setFont(QFont("", self.base_font_size))
        self.quality_combo.addItems(["原画", "1080p", "720p", "480p", "360p"])
        self.quality_combo.setCurrentText("原画")
        options_layout.addWidget(self.quality_combo)

        options_layout.addStretch()
        options_group.setLayout(options_layout)
        main_layout.addWidget(options_group)

        self.video_info_label = QLabel("请输入视频URL自动获取信息")
        self.video_info_label.setFont(QFont("", self.base_font_size))
        self.video_info_label.setStyleSheet("color: gray;")
        main_layout.addWidget(self.video_info_label)

        btn_layout = QHBoxLayout()

        self.download_btn = QPushButton("开始下载")
        self.download_btn.setFont(QFont("", self.base_font_size))
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self.start_download)
        btn_layout.addWidget(self.download_btn)

        self.danmaku_btn = QPushButton("下载弹幕")
        self.danmaku_btn.setFont(QFont("", self.base_font_size))
        self.danmaku_btn.setEnabled(False)
        self.danmaku_btn.clicked.connect(self.download_danmaku)
        btn_layout.addWidget(self.danmaku_btn)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.setFont(QFont("", self.base_font_size))
        self.clear_btn.clicked.connect(self.clear_all)
        btn_layout.addWidget(self.clear_btn)

        self.zoom_out_btn = QPushButton("缩小")
        self.zoom_out_btn.setFont(QFont("", self.base_font_size))
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        btn_layout.addWidget(self.zoom_out_btn)

        self.zoom_in_btn = QPushButton("放大")
        self.zoom_in_btn.setFont(QFont("", self.base_font_size))
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        btn_layout.addWidget(self.zoom_in_btn)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setFont(QFont("", self.base_font_size))
        self.zoom_label.setMinimumWidth(60)
        btn_layout.addWidget(self.zoom_label)

        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFont(QFont("", self.base_font_size))
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMinimumHeight(25)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #999;
                border-radius: 3px;
                text-align: center;
                min-height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        self.convert_progress_bar = QProgressBar()
        self.convert_progress_bar.setFont(QFont("", self.base_font_size))
        self.convert_progress_bar.setValue(0)
        self.convert_progress_bar.setTextVisible(True)
        self.convert_progress_bar.setMinimumHeight(20)
        self.convert_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #999;
                border-radius: 3px;
                text-align: center;
                min-height: 20px;
            }
            QProgressBar::chunk {
                background-color: #FF9800;
            }
        """)
        self.convert_progress_bar.setVisible(False)
        main_layout.addWidget(self.convert_progress_bar)

        status_layout = QHBoxLayout()

        self.status_label = QLabel("就绪")
        self.status_label.setFont(QFont("", self.base_font_size))
        self.status_label.setStyleSheet(
            "color: white; background-color: #333; padding: 5px; border-radius: 3px;"
        )
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.speed_label = QLabel("")
        self.speed_label.setFont(QFont("", self.base_font_size))
        self.speed_label.setStyleSheet("color: white;")
        status_layout.addWidget(self.speed_label)

        main_layout.addLayout(status_layout)

        list_group = QGroupBox("下载列表")
        list_layout = QVBoxLayout()

        list_btn_layout = QHBoxLayout()

        self.play_btn = QPushButton("播放")
        self.play_btn.setFont(QFont("", self.base_font_size))
        self.play_btn.clicked.connect(self.play_video)
        list_btn_layout.addWidget(self.play_btn)

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setFont(QFont("", self.base_font_size))
        self.refresh_btn.clicked.connect(self.refresh_list)
        list_btn_layout.addWidget(self.refresh_btn)

        self.delete_btn = QPushButton("删除")
        self.delete_btn.setFont(QFont("", self.base_font_size))
        self.delete_btn.clicked.connect(self.delete_file)
        list_btn_layout.addWidget(self.delete_btn)

        self.open_folder_btn = QPushButton("打开文件夹")
        self.open_folder_btn.setFont(QFont("", self.base_font_size))
        self.open_folder_btn.clicked.connect(self.open_folder)
        list_btn_layout.addWidget(self.open_folder_btn)

        list_btn_layout.addStretch()

        self.download_speed_label = QLabel("")
        self.download_speed_label.setFont(QFont("", self.base_font_size))
        self.download_speed_label.setStyleSheet("color: blue;")
        list_btn_layout.addWidget(self.download_speed_label)

        list_layout.addLayout(list_btn_layout)

        self.download_tree = QTreeWidget()
        self.download_tree.setFont(QFont("", self.base_font_size))
        self.download_tree.setHeaderLabels(["文件名", "大小", "速度", "状态"])
        self.download_tree.setColumnWidth(0, 500)
        list_layout.addWidget(self.download_tree)

        list_group.setLayout(list_layout)

        log_group = QGroupBox("下载日志")
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setFont(QFont("Monaco", self.base_font_size))
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        log_group.setLayout(log_layout)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(list_group)
        splitter.addWidget(log_group)
        splitter.setSizes([200, 200])
        main_layout.addWidget(splitter, 1)

    def zoom_out(self):
        new_scale = self.scale_factor * 0.9
        if new_scale >= self.MIN_SCALE:
            self.scale_factor = new_scale
            self.apply_zoom()
            self.log(f"界面缩小: {self.scale_factor * 100:.0f}%")
        else:
            self.status_label.setText(f"已到最小缩放比例 {self.MIN_SCALE * 100:.0f}%")

    def zoom_in(self):
        new_scale = self.scale_factor * 1.1
        if new_scale <= self.MAX_SCALE:
            self.scale_factor = new_scale
            self.apply_zoom()
            self.log(f"界面放大: {self.scale_factor * 100:.0f}%")
        else:
            self.status_label.setText(f"已到最大缩放比例 {self.MAX_SCALE * 100:.0f}%")

    def apply_zoom(self):
        new_size = self.base_font_size * self.scale_factor
        QTimer.singleShot(50, lambda: self._apply_font_size(new_size))
        self.zoom_label.setText(f"{self.scale_factor * 100:.0f}%")

    def _apply_font_size(self, font_size):
        new_font = QFont()
        new_font.setPointSizeF(font_size)
        self.setFont(new_font)
        self._set_widget_font(self, font_size)
        self.update()
        self.repaint()

    def _set_widget_font(self, widget, font_size):
        font = QFont()
        font.setPointSizeF(font_size)
        widget.setFont(font)
        for child in widget.children():
            if isinstance(child, QWidget):
                self._set_widget_font(child, font_size)

    def set_default_download_path(self):
        default_path = os.path.join(os.path.expanduser("~"), "Downloads")
        if os.path.exists(default_path):
            self.path_input.setText(default_path)
            self.output_dir = default_path
            self.refresh_list()

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "选择保存路径", self.path_input.text() or os.path.expanduser("~")
        )
        if folder:
            self.path_input.setText(folder)
            self.output_dir = folder
            self.refresh_list()

    def browse_ffmpeg(self):
        file, _ = QFileDialog.getOpenFileName(
            self,
            "选择ffmpeg",
            self.ffmpeg_input.text() or "/usr/local/bin",
            "Executable (*);;All files (*.*)",
        )
        if file:
            self.ffmpeg_input.setText(file)

    def on_format_changed(self):
        if self.mp4_radio.isChecked():
            self.quality_combo.setEnabled(True)
        else:
            self.quality_combo.setEnabled(False)

    def on_url_changed(self, text):
        url = text.strip()
        if not url:
            self.video_info_label.setText("请输入视频URL自动获取信息")
            self.video_info_label.setStyleSheet("color: gray;")
            self.download_btn.setEnabled(False)
            self.danmaku_btn.setEnabled(False)
            return

        if "youtube.com" in url or "youtu.be" in url or "bilibili.com" in url:
            self.fetch_video_info(url)
            self.danmaku_btn.setEnabled("bilibili.com" in url)

    def fetch_video_info(self, url):
        if not url:
            return

        if not YTDLP_AVAILABLE:
            QMessageBox.critical(
                self, "错误", "yt-dlp未安装，请运行: pip install yt-dlp"
            )
            return

        self.status_label.setText("正在获取视频信息...")
        self.status_label.setStyleSheet(
            "color: white; background-color: #333; padding: 5px; border-radius: 3px;"
        )
        self.log(f"获取视频信息: {url}")

        self.is_fetching = True
        self.fetch_thread = threading.Thread(
            target=self._fetch_video_info_thread, args=(url,)
        )
        self.fetch_thread.daemon = True
        self.fetch_thread.start()

    def _fetch_video_info_thread(self, url):
        try:
            ydl_opts = {
                "quiet": True,
                "logger": self._yt_logger,
                "nocheckcertificate": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.ydl = ydl
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "未知标题")
                self.fetch_completed.emit(title)
                self.status_label.setText("视频信息获取成功")
                self.status_label.setStyleSheet(
                    "color: white; background-color: #333; padding: 5px; border-radius: 3px;"
                )
                self.download_btn.setEnabled(True)
        except Exception as e:
            import traceback

            error_detail = f"{str(e)}\n{traceback.format_exc()}"
            self.fetch_failed.emit(error_detail)
        finally:
            self.is_fetching = False
            self.ydl = None

    def start_download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "错误", "请输入视频URL")
            return

        output_dir = self.path_input.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "错误", "请选择保存路径")
            return

        if not YTDLP_AVAILABLE:
            QMessageBox.critical(
                self, "错误", "yt-dlp未安装，请运行: pip install yt-dlp"
            )
            return

        self.is_downloading = True
        self.download_btn.setEnabled(False)
        self.status_label.setText("正在下载...")
        self.status_label.setStyleSheet(
            "color: white; background-color: #2196F3; padding: 5px; border-radius: 3px;"
        )
        self.progress_bar.setValue(0)
        self.convert_progress_bar.setVisible(False)
        self.convert_progress_bar.setValue(0)

        video_format = "mp4" if self.mp4_radio.isChecked() else "mp3"
        quality = self.quality_combo.currentText()

        self.current_download_title = "获取视频信息..."
        self.refresh_list()

        self.download_thread = threading.Thread(
            target=self.download_video, args=(url, output_dir, video_format, quality)
        )
        self.download_thread.daemon = True
        self.download_thread.start()

    def download_danmaku(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "错误", "请输入视频URL")
            return

        if "bilibili.com" not in url:
            QMessageBox.warning(self, "错误", "弹幕下载仅支持Bilibili视频")
            return

        output_dir = self.path_input.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "错误", "请选择保存路径")
            return

        self.danmaku_btn.setEnabled(False)
        self.status_label.setText("正在下载弹幕...")
        self.status_label.setStyleSheet(
            "color: white; background-color: #2196F3; padding: 5px; border-radius: 3px;"
        )
        self.log(f"下载弹幕 URL: {url}")
        self.log(f"保存目录: {output_dir}")
        self.log("开始下载弹幕...")

        try:
            thread = threading.Thread(
                target=self._download_danmaku_thread, args=(url, output_dir)
            )
            thread.daemon = True
            thread.start()
            self.log("弹幕线程已启动")
        except Exception as e:
            self.log(f"启动线程失败: {e}")
            self.danmaku_btn.setEnabled(True)

    def _download_danmaku_thread(self, url, output_dir):
        try:
            import re
            import urllib.request
            import urllib.error
            import ssl
            import json
            import zlib

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            self.danmaku_log.emit(">>> 线程开始执行")

            self.danmaku_log.emit("正在解析URL...")

            bv_match = re.search(r"BV[\w]+", url)
            if not bv_match:
                bv_match = re.search(r"/video/(BV[\w]+)", url)

            if not bv_match:
                self.danmaku_log.emit("无法识别视频ID，请检查URL格式")
                self.danmaku_finished.emit(False, "无法识别视频ID，请检查URL格式")
                return

            bv_id = (
                bv_match.group(bv_match.lastindex)
                if bv_match.lastindex
                else bv_match.group(0)
            )
            self.danmaku_log.emit(f"BV号: {bv_id}")

            self.danmaku_log.emit("请求B站API...")
            api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bv_id}"

            req = urllib.request.Request(
                api_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.15.3 (KHTML, like Gecko) Version/17.0 Safari/605.15.3",
                    "Referer": "https://www.bilibili.com",
                    "Accept": "application/json",
                },
            )

            try:
                response = urllib.request.urlopen(req, timeout=15, context=ssl_context)
                data = response.read()
            except urllib.error.HTTPError as e:
                self.danmaku_log.emit(f"HTTP错误: {e.code} {e.reason}")
                self.danmaku_finished.emit(False, f"HTTP错误: {e.code}")
                return
            except Exception as e:
                self.danmaku_log.emit(f"网络请求失败: {str(e)}")
                self.danmaku_finished.emit(False, f"网络请求失败: {str(e)}")
                return

            try:
                info = json.loads(data)
            except json.JSONDecodeError as e:
                self.danmaku_log.emit(f"JSON解析失败: {str(e)}")
                self.danmaku_finished.emit(False, f"JSON解析失败: {str(e)}")
                return

            if info.get("code") != 0:
                self.danmaku_log.emit(f"API返回错误: {info.get('message')}")
                self.danmaku_finished.emit(False, f"API错误: {info.get('message')}")
                return

            cid = info["data"]["cid"]
            title = info["data"]["title"]

            self.danmaku_log.emit(f"正在下载弹幕: {title}")

            dm_url = f"https://comment.bilibili.com/{cid}.xml"
            req = urllib.request.Request(
                dm_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.15.3 (KHTML, like Gecko) Version/17.0 Safari/605.15.3",
                    "Referer": "https://www.bilibili.com",
                },
            )

            response = urllib.request.urlopen(req, timeout=30, context=ssl_context)
            raw_data = response.read()

            xml_header = b'<?xml version="1.0" encoding="UTF-8"?>'
            if raw_data.startswith(xml_header):
                compressed_data = raw_data[len(xml_header) :]
            else:
                compressed_data = raw_data

            try:
                decompressed = zlib.decompress(compressed_data, -zlib.MAX_WBITS)
            except:
                try:
                    decompressed = zlib.decompressobj().decompress(compressed_data)
                except:
                    self.danmaku_log.emit("解压失败，尝试直接解码...")
                    decompressed = compressed_data

            content = xml_header.decode("utf-8") + "\n" + decompressed.decode("utf-8")

            safe_title = self.sanitize_filename(title)
            xml_file = os.path.join(output_dir, f"{safe_title}.xml")
            with open(xml_file, "w", encoding="utf-8") as f:
                f.write(content)

            self.danmaku_finished.emit(True, f"弹幕已保存: {xml_file}")

        except Exception as e:
            import traceback

            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            print(f"Danmaku error: {error_msg}")
            self.danmaku_log.emit(f"下载失败: {str(e)}")
            self.danmaku_finished.emit(False, f"弹幕下载错误: {str(e)}")

    def download_video(self, url, output_dir, video_format, quality):
        try:
            quality_map = {
                "原画": "bestvideo+bestaudio/best",
                "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
                "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
                "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best",
                "360p": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best",
            }

            ffmpeg_path = self._check_ffmpeg(self.ffmpeg_input.text().strip())
            ffmpeg_opts = {"ffmpeg_location": ffmpeg_path} if ffmpeg_path else {}

            if video_format == "mp4":
                fmt = quality_map.get(quality, quality_map["原画"])
                ydl_opts = {
                    "outtmpl": f"{output_dir}/%(title)s_%(height)sp.%(ext)s",
                    "format": fmt,
                    "progress_hooks": [self.progress_hook],
                    "overwrites": True,
                    "logger": self._yt_logger,
                    "nocheckcertificate": True,
                    "no_warnings": False,
                    "fragment_retries": 10,
                    "retries": 10,
                }
                ydl_opts.update(ffmpeg_opts)
            else:
                ydl_opts = {
                    "outtmpl": f"{output_dir}/%(title)s.%(ext)s",
                    "format": "bestaudio/best",
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ],
                    "progress_hooks": [self.progress_hook],
                    "overwrites": True,
                    "logger": self._yt_logger,
                    "nocheckcertificate": True,
                    "fragment_retries": 10,
                    "retries": 10,
                }
                ydl_opts.update(ffmpeg_opts)

            QTimer.singleShot(0, lambda: self.log(f"开始下载: {url}"))
            QTimer.singleShot(0, lambda: self.status_label.setText("正在下载..."))
            QTimer.singleShot(
                0, lambda: self.status_label.setStyleSheet("color: white;")
            )

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    self.ydl = ydl
                    info = ydl.extract_info(url, download=True)
                    title = info.get("title", "video")
                    self.current_download_title = title
                    QTimer.singleShot(0, self.refresh_list)

                QTimer.singleShot(0, lambda: self.download_finished(True, "下载完成!"))

            except Exception as e:
                if not self.is_downloading:
                    QTimer.singleShot(
                        0, lambda: self.download_finished(False, "下载已取消")
                    )
                else:
                    import traceback

                    error_detail = f"{str(e)}\n{traceback.format_exc()}"
                    QTimer.singleShot(
                        0, lambda: self.download_finished(False, error_detail)
                    )
            finally:
                self.is_downloading = False
                self.ydl = None
        except Exception as e:
            self.is_downloading = False
            self.ydl = None

    def _check_ffmpeg(self, custom_path=None):
        """检查ffmpeg是否存在"""
        import shutil

        if custom_path and os.path.exists(custom_path):
            if os.path.isfile(custom_path):
                return custom_path
            elif os.path.isdir(custom_path):
                ffmpeg_bin = os.path.join(custom_path, "ffmpeg")
                if os.path.exists(ffmpeg_bin):
                    return custom_path

        if shutil.which("ffmpeg"):
            return shutil.which("ffmpeg")

        common_paths = [
            "/usr/local/bin",
            "/opt/homebrew/bin",
        ]

        for path in common_paths:
            ffmpeg_bin = os.path.join(path, "ffmpeg")
            if os.path.exists(ffmpeg_bin):
                return path

        return None

    def progress_hook(self, d):
        status = d.get("status", "")

        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)

            if total and total > 0:
                percent = (downloaded / total) * 100
            else:
                percent_str = d.get("_percent_str", "").strip().replace("%", "")
                try:
                    percent = float(percent_str) if percent_str else 0
                except:
                    percent = 0

            speed = d.get("_speed_str", "")
            if speed:
                speed = speed.strip()
                speed = "".join(c for c in speed if c.isprintable() or c in "KMGkB./")
            percent_int = int(percent)

            self.progress_updated.emit(percent_int, speed)

        elif status == "finished":
            self.status_updated.emit("正在合并视频...")
            self.progress_updated.emit(100, "")
            QTimer.singleShot(0, lambda: self.convert_progress_bar.setVisible(True))
            QTimer.singleShot(0, lambda: self.convert_progress_bar.setValue(0))

        elif status == "postprocessing":
            progress = d.get("progress", 0)
            if progress:
                percent = int(progress * 100)
                self.status_updated.emit(f"正在转码... {percent}%")
                QTimer.singleShot(
                    0, lambda p=percent: self.convert_progress_bar.setValue(p)
                )
            else:
                self.status_updated.emit("正在转码...")

    def _update_progress_ui(self, percent, speed):
        self.progress_bar.setValue(percent)
        self.status_label.setText(f"下载中... {percent:.1f}% {speed}")
        self.speed_label.setText(f"下载速度: {speed}")
        self.download_speed_label.setText(speed)
        self.update_download_list_item(speed, percent)

    def download_finished(self, success, message):
        self.download_btn.setEnabled(True)
        self.speed_label.setText("")
        self.download_speed_label.setText("")
        self.progress_bar.setValue(0)
        self.convert_progress_bar.setVisible(False)
        self.convert_progress_bar.setValue(0)

        if success:
            self.status_label.setText("下载完成!")
            self.status_label.setStyleSheet(
                "color: white; background-color: #333; padding: 5px; border-radius: 3px;"
            )
            self.log(message)
            self.refresh_list()
        else:
            self.status_label.setText("下载失败")
            self.status_label.setStyleSheet(
                "color: white; background-color: #f44336; padding: 5px; border-radius: 3px;"
            )
            self.log(f"错误: {message}")
            self.refresh_list()

    def root_after(self, delay, func, *args):
        if args:
            QTimer.singleShot(delay, lambda: func(*args))
        else:
            QTimer.singleShot(delay, func)

    def on_download_complete(self, success, message):
        self.download_btn.setEnabled(True)

        if success:
            self.status_label.setText("下载完成!")
            self.status_label.setStyleSheet(
                "color: white; background-color: #333; padding: 5px; border-radius: 3px;"
            )
            self.progress_bar.setValue(100)
            self.log(message)
            QMessageBox.information(self, "成功", message)
            self.refresh_list()
        else:
            self.status_label.setText("下载失败")
            self.status_label.setStyleSheet("color: red;")
            self.log(f"错误: {message}")
            QMessageBox.critical(self, "错误", message)

    def refresh_list(self):
        self.download_tree.clear()

        output_dir = self.path_input.text().strip()
        if not output_dir or not os.path.exists(output_dir):
            return

        video_exts = ["*.mp4", "*.mp3", "*.mkv", "*.webm", "*.flv"]
        for ext in video_exts:
            files = glob.glob(os.path.join(output_dir, ext))
            for f in files:
                filename = os.path.basename(f)
                size = os.path.getsize(f)
                size_str = self.format_size(size)
                item = QTreeWidgetItem([filename, size_str, "", "已完成"])
                item.setForeground(3, Qt.GlobalColor.green)
                self.download_tree.addTopLevelItem(item)

        if hasattr(self, "current_download_title") and self.current_download_title:
            percent = self.progress_bar.value()
            speed_text = self.download_speed_label.text().replace("下载速度: ", "")
            status_text = f"下载中 {percent}%"
            current_item = QTreeWidgetItem(
                [self.current_download_title, f"{percent}%", speed_text, status_text]
            )
            current_item.setForeground(0, Qt.GlobalColor.white)
            current_item.setForeground(1, Qt.GlobalColor.white)
            current_item.setForeground(2, Qt.GlobalColor.white)
            current_item.setForeground(3, Qt.GlobalColor.white)
            self.download_tree.insertTopLevelItem(0, current_item)

    def update_download_list_item(self, speed, percent=0):
        if self.download_tree.topLevelItemCount() > 0:
            item = self.download_tree.topLevelItem(0)
            if item and "下载中" in item.text(3):
                item.setText(1, f"{percent}%")
                item.setText(2, speed)
                item.setText(3, f"下载中 {percent}%")

    def format_size(self, size):
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def play_video(self):
        """播放选中的视频 - macOS版本"""
        current_item = self.download_tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请选择要播放的视频")
            return

        filename = current_item.text(0)
        filepath = os.path.join(self.path_input.text(), filename)

        if not os.path.exists(filepath):
            QMessageBox.critical(self, "错误", "文件不存在")
            return

        subprocess.run(["open", filepath])

    def delete_file(self):
        """删除选中的文件"""
        current_item = self.download_tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请选择要删除的文件")
            return

        filename = current_item.text(0)
        filepath = os.path.join(self.path_input.text(), filename)

        if not os.path.exists(filepath):
            QMessageBox.critical(self, "错误", "文件不存在")
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f'确定要删除文件 "{filename}" 吗？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(filepath)
                self.log(f"已删除: {filename}")
                self.refresh_list()
                QMessageBox.information(self, "成功", "文件已删除")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除失败: {e}")

    def open_folder(self):
        """打开下载文件夹 - macOS版本"""
        folder = self.path_input.text().strip()
        if not folder or not os.path.exists(folder):
            QMessageBox.warning(self, "提示", "请选择有效的保存路径")
            return
        subprocess.run(["open", folder])

    def sanitize_filename(self, filename):
        """清理文件名中的非法字符"""
        import re

        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        filename = filename[:100]
        return filename

    def clear_all(self):
        """清空所有输入并停止下载"""
        self.is_downloading = False
        self.is_fetching = False
        self.ydl = None

        self.url_input.clear()
        self.video_info_label.setText("请输入视频URL自动获取信息")
        self.video_info_label.setStyleSheet("color: gray;")
        self.status_label.setText("就绪")
        self.status_label.setStyleSheet(
            "color: white; background-color: #333; padding: 5px; border-radius: 3px;"
        )
        self.log_text.clear()
        self.download_btn.setEnabled(False)
        self.danmaku_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.convert_progress_bar.setVisible(False)
        self.convert_progress_bar.setValue(0)
        self.log("已停止当前操作")

    def log(self, message):
        """添加日志"""
        self.log_text.append(message)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="PyGoDown 视频下载器")
    parser.add_argument(
        "--skip-deps", action="store_true", help="跳过依赖检查（打包后使用）"
    )
    args, unknown = parser.parse_known_args()

    is_frozen = getattr(sys, "frozen", False)

    print("=" * 50)
    print("PyGoDown - 视频下载器 (macOS版)")
    print("=" * 50)

    if not args.skip_deps and not is_frozen:
        if not check_and_install_dependencies():
            print("\n依赖安装失败，请手动安装后重试")
            sys.exit(1)

        ffmpeg_path = check_ffmpeg()
        if not ffmpeg_path:
            install_ffmpeg()
        else:
            print(f"✓ ffmpeg 已找到: {ffmpeg_path}")
    else:
        if is_frozen:
            print("✓ 打包模式：跳过依赖检查")
        else:
            print("✓ 跳过依赖检查 (--skip-deps)")

    try:
        app = QApplication(sys.argv)

        font = QFont("Helvetica Neue", 10)
        app.setFont(font)

        app.setStyle("Fusion")

        window = VideoDownloader()
        window.show()

        sys.exit(app.exec())
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
