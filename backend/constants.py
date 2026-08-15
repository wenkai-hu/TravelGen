# -*- coding: utf-8 -*-
"""共享枚举常量（app.py 旧契约与 v1_router V1 接口共用，避免两处漂移）。"""

SCENE_TYPES = ["城市形象宣传", "景区推荐", "节庆活动推广", "非遗文化传播", "打卡视频", "其他"]
ASPECT_RATIOS = ["9:16", "16:9", "1:1"]
RESOLUTIONS = ["720p", "1080p"]
VIDEO_MODELS = ["seedance-2.0", "seedance-2.0-pro"]

# V1 文档 scene_type 英文示例 → 落库中文枚举（TravelGen_v1.md §六 "scenic" 等）
SCENE_TYPE_ALIASES = {
    "scenic": "景区推荐",
    "city": "城市形象宣传",
    "city_image": "城市形象宣传",
    "heritage": "非遗文化传播",
    "intangible_cultural_heritage": "非遗文化传播",
    "festival": "节庆活动推广",
    "check_in": "打卡视频",
    "other": "其他",
}
