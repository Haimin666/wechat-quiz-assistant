# src/gui.py
import os
import sys
import json
import time
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QGroupBox, QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRect, QPoint, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QMouseEvent

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logger import get_logger
from screenshot import capture_screen
from detector import detect_change
from ocr import image_to_text
from ai_analyzer import analyze_question
from cleanup import cleanup_screenshots

logger = get_logger("gui")


class ClickableImageLabel(QLabel):
    """可点击的图片标签"""
    
    region_selected = pyqtSignal(tuple)
    point_clicked = pyqtSignal(QPoint)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.original_pixmap = None
        self.displayed_pixmap = None
        self.scale_ratio = 1.0
        self.offset_x = 0
        self.offset_y = 0
        
        self.first_point = None
        self.is_selecting = False
        
        self.setMinimumHeight(200)
        self.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 2px dashed #ccc;
                border-radius: 10px;
            }
        """)
    
    def set_screenshot(self, pixmap):
        """设置截图"""
        self.original_pixmap = pixmap
        self.first_point = None
        self.is_selecting = True
        self.update_display()
    
    def update_display(self):
        """更新显示"""
        if self.original_pixmap is None:
            return
        
        # 缩放图片以适应标签
        label_size = self.size()
        self.displayed_pixmap = self.original_pixmap.scaled(
            label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        
        # 计算缩放比例
        self.scale_ratio = self.original_pixmap.width() / self.displayed_pixmap.width()
        
        # 计算偏移（居中显示）
        self.offset_x = (label_size.width() - self.displayed_pixmap.width()) // 2
        self.offset_y = (label_size.height() - self.displayed_pixmap.height()) // 2
        
        self.setPixmap(self.displayed_pixmap)
    
    def mousePressEvent(self, event: QMouseEvent):
        """鼠标点击"""
        if not self.is_selecting or self.original_pixmap is None:
            return
        
        if event.button() == Qt.LeftButton:
            # 转换坐标
            x = int((event.x() - self.offset_x) * self.scale_ratio)
            y = int((event.y() - self.offset_y) * self.scale_ratio)
            
            # 确保在图片范围内
            if 0 <= x < self.original_pixmap.width() and 0 <= y < self.original_pixmap.height():
                point = QPoint(x, y)
                
                if self.first_point is None:
                    # 第一个点
                    self.first_point = point
                    self.update()
                else:
                    # 第二个点，完成选择
                    x1, y1 = self.first_point.x(), self.first_point.y()
                    
                    region_x = min(x1, x)
                    region_y = min(y1, y)
                    region_w = abs(x - x1)
                    region_h = abs(y - y1)
                    
                    if region_w > 20 and region_h > 20:
                        self.region_selected.emit((region_x, region_y, region_w, region_h))
                    
                    self.first_point = None
                    self.is_selecting = False
    
    def paintEvent(self, event):
        """绘制"""
        super().paintEvent(event)
        
        if self.displayed_pixmap is None or self.first_point is None:
            return
        
        painter = QPainter(self)
        
        # 绘制第一个点
        p1 = self.to_widget_pos(self.first_point)
        painter.setPen(QPen(QColor(0, 200, 0), 3))
        painter.setBrush(QColor(0, 200, 0, 100))
        painter.drawEllipse(p1, 8, 8)
        
        # 绘制提示
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 12))
        painter.drawText(p1.x() + 15, p1.y() - 10, "起点 - 请点击右下角")
        
        painter.end()
    
    def to_widget_pos(self, point):
        """将原始图片坐标转换为控件坐标"""
        x = int(point.x() / self.scale_ratio) + self.offset_x
        y = int(point.y() / self.scale_ratio) + self.offset_y
        return QPoint(x, y)
    
    def resizeEvent(self, event):
        """窗口大小改变"""
        super().resizeEvent(event)
        self.update_display()


class AIWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, question_text, api_key, model, base_url, max_tokens=2048, enable_thinking=False):
        super().__init__()
        self.question_text = question_text
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.enable_thinking = enable_thinking
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            if self._cancelled:
                return
            result = analyze_question(
                self.question_text,
                question_type="single",
                api_key=self.api_key,
                model=self.model,
                base_url=self.base_url,
                max_tokens=self.max_tokens,
                enable_thinking=self.enable_thinking,
            )
            if not self._cancelled:
                self.finished.emit(result)
        except Exception:
            logger.exception("AIWorker 执行失败")
            if not self._cancelled:
                self.error.emit("AI分析失败，详见日志")


class ListenThread(QThread):
    screenshot_signal = pyqtSignal(str)
    ocr_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    change_signal = pyqtSignal()
    
    def __init__(self, region, config_path):
        super().__init__()
        self.region = region
        self.config_path = config_path
        self.is_running = True
        self.last_image = None
        self._force_ocr = True  # 首帧/换区域后强制 OCR 一次

    def set_region(self, region):
        """运行时更换区域：原子更新 + 重置基线 + 强制下一帧 OCR。

        不重启线程，避免新旧线程并发竞态。
        """
        self.region = region
        self.last_image = None
        self._force_ocr = True

    def run(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            logger.exception("监听线程读取配置失败: %s", self.config_path)
            return

        interval = config.get("auto_detection", {}).get("interval", 0.5)
        threshold = config.get("auto_detection", {}).get("change_threshold", 0.3)

        while self.is_running:
            try:
                # 每轮取最新区域（支持运行时 set_region，无需重启线程）
                region = self.region
                if region is None:
                    time.sleep(interval)
                    continue

                current_image = capture_screen(region=region)
                self.screenshot_signal.emit(current_image)

                if self._force_ocr:
                    self._force_ocr = False
                    self.status_signal.emit("OCR识别中...")
                    question_text = image_to_text(current_image)
                    if question_text.strip():
                        self.ocr_signal.emit(question_text)
                    else:
                        self.status_signal.emit("未识别到文字")
                elif self.last_image is not None:
                    has_change = detect_change(self.last_image, current_image, threshold)

                    if has_change:
                        self.change_signal.emit()
                        self.status_signal.emit("等待动画完成...")
                        # 微信小程序切题动画较快，等待 0.3s 后直接抓 1 帧稳定图即可
                        time.sleep(0.3)
                        if not self.is_running:
                            continue

                        stable_image = capture_screen(region=region)
                        self.screenshot_signal.emit(stable_image)
                        self.status_signal.emit("OCR识别中...")
                        question_text = image_to_text(stable_image)

                        if question_text.strip():
                            self.ocr_signal.emit(question_text)
                        else:
                            self.status_signal.emit("未识别到文字")

                        # 用稳定帧更新 last_image，避免下一轮用过渡帧重复触发
                        current_image = stable_image

                self.last_image = current_image
                time.sleep(interval)
            except Exception:
                logger.exception("监听线程循环异常")
                self.status_signal.emit("错误，详见日志")
                time.sleep(1)
    
    def stop(self):
        self.is_running = False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.region = None
        self.is_running = False
        self.config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
        self.ai_worker = None
        self.listen_thread = None
        self._selector = None
        self._selector_timer = None
        
        self.init_ui()
        self.load_config()

        # 启动时清理历史截图
        save_path = getattr(self, "save_path", None)
        if save_path:
            cleanup_screenshots(save_path)

        # 若已配置区域，立即启动常驻预览线程（截图+变化检测+OCR），
        # 与「开始」按钮解耦：点开始才真正调 AI 答题。
        if self.region:
            self._ensure_preview_thread()
    
    def init_ui(self):
        self.setWindowTitle("微信小程序自动答题助手")
        self.setMinimumSize(950, 700)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # ========== 工具栏 ==========
        toolbar = QHBoxLayout()
        
        # 选取区域按钮
        self.capture_btn = QPushButton("🔲 选取区域")
        self.capture_btn.setFixedHeight(36)
        self.capture_btn.clicked.connect(self.select_region)
        self.capture_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        toolbar.addWidget(self.capture_btn)

        # 提示标签
        self.tip_label = QLabel("点击「选取区域」，依次点左上角和右下角")
        self.tip_label.setStyleSheet("color: #666; font-size: 12px; padding: 0 10px;")
        toolbar.addWidget(self.tip_label)
        
        toolbar.addStretch()
        
        # 区域信息
        self.region_label = QLabel("未设置")
        self.region_label.setStyleSheet("color: #333; font-size: 12px; font-weight: bold;")
        toolbar.addWidget(self.region_label)
        
        # 开始/停止
        self.start_btn = QPushButton("▶ 开始")
        self.start_btn.setFixedSize(90, 36)
        self.start_btn.clicked.connect(self.toggle_listening)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #388E3C; }
        """)
        toolbar.addWidget(self.start_btn)
        
        # 退出
        self.quit_btn = QPushButton("✕ 退出")
        self.quit_btn.setFixedSize(80, 36)
        self.quit_btn.clicked.connect(self.quit_app)
        self.quit_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #d32f2f; }
        """)
        toolbar.addWidget(self.quit_btn)
        
        main_layout.addLayout(toolbar)
        
        # ========== 截图预览 ==========
        self.image_label = ClickableImageLabel()
        self.image_label.region_selected.connect(self.on_region_selected)
        main_layout.addWidget(self.image_label)
        
        # ========== 下方：OCR + 答案 ==========
        bottom = QSplitter(Qt.Horizontal)
        
        # OCR
        ocr_group = QGroupBox("📝 识别结果")
        ocr_layout = QVBoxLayout()
        self.ocr_text = QTextEdit()
        self.ocr_text.setReadOnly(True)
        self.ocr_text.setPlaceholderText("题目文字...")
        ocr_layout.addWidget(self.ocr_text)
        ocr_group.setLayout(ocr_layout)
        bottom.addWidget(ocr_group)
        
        # 答案
        answer_group = QGroupBox("🤖 答案")
        answer_layout = QVBoxLayout()
        
        self.answer_label = QLabel("等待中")
        self.answer_label.setAlignment(Qt.AlignCenter)
        self.answer_label.setMinimumHeight(60)
        self.answer_label.setStyleSheet("""
            QLabel {
                font-size: 42px;
                font-weight: bold;
                color: #4CAF50;
                background-color: #e8f5e9;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        answer_layout.addWidget(self.answer_label)
        
        self.explanation_text = QTextEdit()
        self.explanation_text.setReadOnly(True)
        self.explanation_text.setPlaceholderText("解析...")
        self.explanation_text.setMaximumHeight(120)
        answer_layout.addWidget(self.explanation_text)
        
        answer_group.setLayout(answer_layout)
        bottom.addWidget(answer_group)
        
        main_layout.addWidget(bottom)
        
        # 状态栏
        self.statusBar().showMessage("就绪")
        
        # 样式
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f5f5; }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 8px;
                font-size: 13px;
            }
        """)
    
    def load_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            self.region = config.get("auto_detection", {}).get("screenshot_region")
            # 截图保存路径（相对路径基于项目根）
            save_path = config.get("screenshot", {}).get("save_path", "./tmp/")
            if not os.path.isabs(save_path):
                save_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), save_path)
            self.save_path = save_path
            if self.region:
                self.region_label.setText(f"{self.region[2]}x{self.region[3]} @ ({self.region[0]},{self.region[1]})")
                self.show_region_preview()
        except Exception:
            logger.exception("加载配置失败: %s", self.config_path)
    
    def save_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            if "auto_detection" not in config:
                config["auto_detection"] = {}
            config["auto_detection"]["screenshot_region"] = self.region
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception:
            logger.exception("保存配置失败: %s", self.config_path)
    
    def select_region(self):
        """启动全屏区域选择器：依次点击左上角、右下角。

        复用项目根 region_select.py 的 RegionSelector：
        - 左键依次点左上角、右下角完成选择
        - 右键重选（支持反复重新选择）
        - ESC 取消
        可重复点击本按钮重新选择。
        """
        try:
            from region_select import RegionSelector
        except Exception:
            logger.exception("加载 region_select.RegionSelector 失败")
            QMessageBox.warning(self, "提示", "区域选择器加载失败，详见日志")
            return

        logger.info("启动区域选择器（左上角→右下角，右键重选，ESC 取消）")
        self._selector = RegionSelector()
        self._selector.show()

        # 使用 QTimer 轮询，避免阻塞 GUI
        self._selector_timer = QTimer(self)
        self._selector_timer.timeout.connect(self._poll_selector)
        self._selector_timer.start(50)

    def _poll_selector(self):
        """轮询区域选择器状态"""
        if not self._selector.isVisible():
            self._selector_timer.stop()
            if self._selector.result_region:
                region = tuple(self._selector.result_region)
                self.on_region_selected(region)
            else:
                self.tip_label.setText("已取消，可重新点击「选取区域」")
                self.statusBar().showMessage("区域选择已取消")
            self._selector = None
            self._selector_timer = None

    def on_region_selected(self, region):
        """区域选择完成"""
        self.region = region
        self.region_label.setText(f"{region[2]}x{region[3]} @ ({region[0]},{region[1]})")
        self.save_config()
        self.tip_label.setText("区域已设置，点击「选取区域」可重新选择")

        # 显示区域预览
        path = capture_screen(region=region)
        pixmap = QPixmap(path)
        scaled = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled)
        self.image_label.is_selecting = False

        self.statusBar().showMessage("区域已设置")
        logger.info("截图区域已设置: %s", region)
        # 区域变更，重启预览线程使用新区域
        self._ensure_preview_thread()
    
    def show_region_preview(self):
        """显示区域预览"""
        if self.region:
            path = capture_screen(region=self.region)
            pixmap = QPixmap(path)
            scaled = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)
            self.image_label.is_selecting = False

    def _ensure_preview_thread(self):
        """确保预览线程在跑；若已在跑则原子更新区域（不重启，避免竞态）。"""
        if self.region is None:
            return
        if self.listen_thread is not None and self.listen_thread.isRunning():
            self.listen_thread.set_region(self.region)
            logger.info("预览区域已更新 region=%s", self.region)
            return
        self.listen_thread = ListenThread(self.region, self.config_path)
        self.listen_thread.screenshot_signal.connect(self.on_screenshot)
        self.listen_thread.ocr_signal.connect(self.on_ocr)
        self.listen_thread.status_signal.connect(lambda x: self.statusBar().showMessage(x))
        self.listen_thread.change_signal.connect(self.on_change)
        self.listen_thread.start()
        logger.info("预览线程已启动 region=%s", self.region)
        self.statusBar().showMessage("预览中（未开始答题）")
    
    def toggle_listening(self):
        if self.is_running:
            self.stop_listening()
        else:
            self.start_listening()
    
    def start_listening(self):
        if self.region is None:
            QMessageBox.warning(self, "提示", "请先选择截图区域！")
            return
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            if not config.get("ai", {}).get("api_key"):
                QMessageBox.warning(self, "提示", "请先配置API密钥！")
                return
        except Exception:
            logger.exception("启动监听前读取配置失败")
            QMessageBox.warning(self, "提示", "读取配置失败，详见日志")
            return
        
        self.is_running = True
        self.start_btn.setText("⏹ 停止")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #d32f2f; }
        """)

        # 确保预览线程在跑（防止异常退出后点开始）
        if not (self.listen_thread and self.listen_thread.isRunning()):
            self._ensure_preview_thread()

        # 立即对当前已识别的题目发起 AI 答题，不必等下一次变化
        current = self.ocr_text.toPlainText().strip()
        if current:
            self.start_ai(current)

        self.statusBar().showMessage("答题中...")
    
    def stop_listening(self):
        # 只关 AI 答题，预览线程保持常驻（继续截图+OCR）
        self.is_running = False

        self.start_btn.setText("▶ 开始")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #388E3C; }
        """)

        self.answer_label.setText("未开始答题")
        self.explanation_text.clear()
        self.statusBar().showMessage("已停止答题（预览中）")
    
    def on_screenshot(self, path):
        pixmap = QPixmap(path)
        scaled = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled)
    
    def on_change(self):
        if self.is_running:
            self.answer_label.setText("...")
            self.explanation_text.clear()
        else:
            self.answer_label.setText("未开始答题")
            self.explanation_text.clear()

    def on_ocr(self, text):
        # 始终显示 OCR 文本（预览）；仅在开始后才调 AI 答题
        self.ocr_text.setText(text)
        if self.is_running:
            self.start_ai(text)
        else:
            self.answer_label.setText("未开始答题")
            self.explanation_text.clear()
    
    def start_ai(self, question_text):
        # 取消旧的AI请求
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.cancel()
            self.ai_worker.wait(5000)  # 等待最多5秒，让线程有机会响应取消

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            api_key = config.get("ai", {}).get("api_key", "")
            model = config.get("ai", {}).get("model", "step-3.7-flash")
            base_url = config.get("ai", {}).get("base_url", "https://api.stepfun.com/v1")
            max_tokens = config.get("ai", {}).get("max_tokens", 2048)
            enable_thinking = config.get("ai", {}).get("enable_thinking", False)

            self.ai_worker = AIWorker(
                question_text, api_key, model, base_url,
                max_tokens=max_tokens, enable_thinking=enable_thinking,
            )
            self.ai_worker.finished.connect(self.on_ai_done)
            self.ai_worker.error.connect(self.on_ai_error)
            self.ai_worker.start()
        except Exception:
            logger.exception("启动 AIWorker 失败")
            self.answer_label.setText("错误")
            self.statusBar().showMessage("AI 启动失败，详见日志")

    def on_ai_error(self, msg):
        self.answer_label.setText("错误")
        self.statusBar().showMessage(msg)
    
    def on_ai_done(self, result):
        self.answer_label.setText(result.get("answer", ""))
        self.explanation_text.setText(result.get("explanation", ""))
    
    def quit_app(self):
        self.is_running = False
        if self.listen_thread:
            self.listen_thread.stop()
            self.listen_thread.wait(2000)  # 等待线程结束
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.cancel()
            self.ai_worker.wait(2000)
        if self._selector_timer:
            self._selector_timer.stop()
        QApplication.quit()
    
    def closeEvent(self, event):
        self.quit_app()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
