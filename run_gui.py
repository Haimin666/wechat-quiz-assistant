#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信小程序自动答题助手 - GUI启动脚本
"""

import sys
import os

# 添加src目录到sys.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from gui import main

if __name__ == "__main__":
    main()
