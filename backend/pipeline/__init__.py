# -*- coding: utf-8 -*-
"""pipeline 包：导入即把 urllib 切到直连。

Windows 的“系统代理”（Clash 之类的一键开关）写在注册表里，urllib 默认照单全收，
而 curl 只读环境变量、不读注册表 —— 于是同一台机器上出现 curl 通、Python 报
SSL: UNEXPECTED_EOF_WHILE_READING。本管线只连国内端点（方舟 / 千帆 / bcebos），
绕代理只会把请求打坏，所以进程内统一直连。

ponytail: 全局直连。将来若要下载用户提供的境外图片 URL，再改成按 host 判断是否走代理。
"""
import urllib.request

urllib.request.install_opener(
    urllib.request.build_opener(urllib.request.ProxyHandler({})))
