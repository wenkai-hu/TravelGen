// 与后端 backend/constants.py 保持一致的前端枚举（改后端时记得同步这里）
// 场景类型：首页卡片选择器的数据源（6 类，覆盖比赛要求 ≥2 类）
export const SCENE_TYPES = [
  { value: '城市形象宣传', emoji: '🏙️', desc: '航拍地标，城市气质' },
  { value: '景区推荐', emoji: '🏞️', desc: '核心景观与特色体验' },
  { value: '节庆活动推广', emoji: '🎉', desc: '节庆氛围与行动召唤' },
  { value: '非遗文化传播', emoji: '🪡', desc: '传统技艺的年轻表达' },
  { value: '打卡视频', emoji: '📍', desc: '年轻人爱分享的机位' },
  { value: '其他', emoji: '✨', desc: '自由主题创作' },
]

export const ASPECT_RATIOS = ['9:16', '16:9', '1:1']
export const RESOLUTIONS = ['720p', '1080p']
export const VIDEO_MODELS = ['seedance-2.0', 'seedance-2.0-pro']

// 时长：与后端 schemas.py Field(60, ge=15, le=120) 对齐
export const DURATION_RANGE = { min: 15, max: 120, default: 60 }

export const DEFAULT_AUDIENCE = '18-35岁年轻游客'
export const DEFAULT_STYLE = '大气唯美'
