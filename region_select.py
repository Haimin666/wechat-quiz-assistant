#!/usr/bin/env python3
"""区域选择工具 - 点击两点选择区域"""

import sys
from PyQt5.QtWidgets import QApplication, QLabel, QWidget
from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QMouseEvent


class RegionSelector(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("区域选择 - 点击左上角，再点击右下角 | ESC取消")
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |  # 保持在最上层
            Qt.FramelessWindowHint |   # 无边框
            Qt.Tool                    # 不在任务栏显示
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 获取屏幕尺寸并全屏
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        
        # 截全屏
        self.screenshot = self.take_screenshot()
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        
        self.point1 = None
        self.point2 = None
        self.is_selecting = True
        
        self.result_region = None
        
        self.setMouseTracking(True)
    
    def take_screenshot(self):
        """截全屏"""
        import subprocess
        import tempfile
        import os
        
        tmp = os.path.join(tempfile.gettempdir(), "region_select.png")
        subprocess.run(["screencapture", "-x", "-r", tmp], check=True)
        pixmap = QPixmap(tmp)
        return pixmap
    
    def showEvent(self, event):
        """显示时更新缩放"""
        self.update_scale()
        super().showEvent(event)
    
    def update_scale(self):
        """计算缩放比例"""
        if self.screenshot.isNull():
            return
        
        # 窗口尺寸
        w = self.width()
        h = self.height()
        
        # 图片尺寸
        pw = self.screenshot.width()
        ph = self.screenshot.height()
        
        # 缩放比例（保持比例）
        self.scale = min(w / pw, h / ph)
        
        # 居中偏移
        self.offset_x = int((w - pw * self.scale) / 2)
        self.offset_y = int((h - ph * self.scale) / 2)
    
    def resizeEvent(self, event):
        self.update_scale()
        super().resizeEvent(event)
    
    def mousePressEvent(self, event: QMouseEvent):
        """鼠标点击"""
        if not self.is_selecting:
            return

        if event.button() == Qt.LeftButton:
            # 直接使用 widget（逻辑屏幕）坐标 —— 与 screencapture -R 一致。
            # 注意：不能除以 self.scale 转成 pixmap 物理坐标，否则会得到 2x 坐标，
            # 导致 capture_screen 的 screencapture -R 区域偏移/越界、右下角被截断。
            x = max(0, min(event.x(), self.width() - 1))
            y = max(0, min(event.y(), self.height() - 1))

            if self.point1 is None:
                self.point1 = QPoint(x, y)
                self.update()
            else:
                self.point2 = QPoint(x, y)
                # 计算区域（逻辑坐标）
                x1 = min(self.point1.x(), self.point2.x())
                y1 = min(self.point1.y(), self.point2.y())
                x2 = max(self.point1.x(), self.point2.x())
                y2 = max(self.point1.y(), self.point2.y())

                w = x2 - x1
                h = y2 - y1

                if w > 20 and h > 20:
                    self.result_region = (x1, y1, w, h)
                    self.is_selecting = False
                    self.close()  # 直接关闭
                else:
                    self.point1 = None
                    self.point2 = None
                    self.update()

        elif event.button() == Qt.RightButton:
            # 右键取消重选
            self.point1 = None
            self.point2 = None
            self.update()
    
    def keyPressEvent(self, event):
        """ESC取消"""
        if event.key() == Qt.Key_Escape:
            self.result_region = None
            self.close()
    
    def paintEvent(self, event):
        """绘制"""
        painter = QPainter(self)
        
        # 1. 绘制缩放后的截图
        scaled = self.screenshot.scaled(
            int(self.screenshot.width() * self.scale),
            int(self.screenshot.height() * self.scale),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        painter.drawPixmap(self.offset_x, self.offset_y, scaled)
        
        # 2. 半透明遮罩
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        # 3. 绘制已选区域
        if self.point1:
            p1 = self.to_widget_pos(self.point1)
            
            if self.point2:
                p2 = self.to_widget_pos(self.point2)
                rect = QRect(p1, p2).normalized()
                
                # 清除选区内遮罩，显示原图
                painter.setCompositionMode(QPainter.CompositionMode_Clear)
                painter.fillRect(rect, Qt.transparent)
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
                
                # 边框
                painter.setPen(QPen(QColor(0, 255, 0), 3))
                painter.drawRect(rect)
                
                # 坐标信息
                x1 = min(self.point1.x(), self.point2.x())
                y1 = min(self.point1.y(), self.point2.y())
                w = abs(self.point2.x() - self.point1.x())
                h = abs(self.point2.y() - self.point1.y())
                
                painter.setPen(QColor(255, 255, 255))
                painter.setFont(QFont("Arial", 14))
                painter.drawText(rect.x(), rect.y() - 10, f"({x1},{y1}) {w}×{h}")
            else:
                # 第一个点
                painter.setPen(QPen(QColor(0, 255, 0), 3))
                painter.setBrush(QColor(0, 255, 0, 100))
                painter.drawEllipse(p1, 10, 10)
        
        # 4. 提示文字
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Arial", 16))
        if self.point1 is None:
            painter.drawText(20, 30, "请点击题目区域的【左上角】")
        elif self.point2 is None:
            painter.drawText(20, 30, "请点击题目区域的【右下角】 | 右键重选 | ESC取消")
        else:
            painter.drawText(20, 30, "选择完成！")
        
        painter.end()
    
    def to_widget_pos(self, point):
        """控件坐标转控件坐标（point 已是 widget/逻辑坐标，直接返回）。

        早期版本 point 存的是 pixmap 物理坐标，需要 ×scale + offset 换回 widget；
        现在 mousePressEvent 直接存 widget 坐标，故此处为恒等映射。
        """
        return QPoint(point.x(), point.y())


def main():
    app = QApplication(sys.argv)
    selector = RegionSelector()
    selector.show()
    
    # 等待选择完成
    while selector.isVisible():
        app.processEvents()
        import time
        time.sleep(0.01)
    
    if selector.result_region:
        print(f"selected_region = {list(selector.result_region)}")
    else:
        print("cancelled")


if __name__ == "__main__":
    main()
