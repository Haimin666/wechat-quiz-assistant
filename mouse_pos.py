#!/usr/bin/env python3
"""实时显示鼠标坐标 - 区分逻辑/物理坐标"""

import sys
from PyQt5.QtWidgets import QApplication, QLabel
from PyQt5.QtCore import Qt, QTimer


def main():
    app = QApplication(sys.argv)
    
    label = QLabel()
    label.setFixedSize(320, 80)
    label.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
    label.setStyleSheet("""
        QLabel {
            background-color: rgba(0, 0, 0, 200);
            color: #00FF00;
            font-size: 14px;
            font-weight: bold;
            border-radius: 8px;
            padding: 8px;
        }
    """)
    label.move(50, 50)
    label.show()
    
    desktop = app.desktop()
    
    def update():
        pos = app.desktop().cursor().pos()
        # Qt坐标就是逻辑坐标（screencapture -R使用的）
        x = pos.x()
        y = pos.y()
        # Retina物理坐标 = 逻辑坐标 × 2
        label.setText(
            f"逻辑坐标: X={x}  Y={y}\n"
            f"物理坐标: X={x*2}  Y={y*2}\n"
            f"config填写: [{x},{y},宽,高]"
        )
    
    timer = QTimer()
    timer.timeout.connect(update)
    timer.start(50)
    
    app.exec_()


if __name__ == "__main__":
    main()
