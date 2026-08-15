# TravelGen\_v1

# 面向浙江文旅传播的 AIGC 城市短视频自动生成系统

## 系统功能与前后端接口交互方案 V1\.0

---

# 一、项目定位

本系统面向浙江省文旅传播场景，构建一套从：

> 用户需求 → AI策划 → 文案脚本 → 分镜设计 → 多模态生成 → 智能合成 → 成片导出
> 
> 

的 AIGC 城市短视频自动生成系统。

系统重点不是做一个复杂的视频剪辑软件，而是通过 AI 自动完成文旅短视频的主要生产流程，同时保留关键环节的人工调整能力。

核心设计理念：

> **AI自动生成 \+ 用户关键节点干预 \+ Shot级视频生成 \+ 多模态内容融合**
> 
> 

---

# 二、比赛要求对应关系

---

# 三、整体用户流程

系统不采用“一次输入直接生成最终视频”的方式。

而采用分阶段生成：

```Plain Text
用户输入需求
      ↓
① AI创作方案
      ↓
用户修改/确认
      ↓
② AI脚本 + 分镜
      ↓
用户修改/确认
      ↓
③ 分镜图片 + 视频Shot
      ↓
④ AI配音 + 背景音乐
      ↓
⑤ 智能合成
      ↓
成片预览
      ↓
导出
```

其中用户主要在两个地方参与：

### 第一次确认

AI生成：

> 创作方案 \+ 宣传文案
> 
> 

用户可以修改。

### 第二次确认

AI生成：

> 视频脚本 \+ 分镜
> 
> 

用户可以修改某一个 Shot。

确认后再进入实际视频生成。

这样既保证 AI 自动化程度，又避免 AI 一次性生成后用户无法控制。

---

# 四、前端页面设计

整体控制在 5 个主要页面。

## 页面1：创建项目

用户输入：

- 城市/景点

- 场景类型

- 传播主题

- 目标人群

- 视频风格

- 视频时长

- 视频比例

- 补充说明

- 图片素材

---

## 页面2：AI创作方案

展示：

- 视频标题

- 创意概念

- 核心传播点

- 宣传文案

- 视频结构

- 推荐风格

用户可以：

> 编辑 / 重新生成 / 确认方案
> 
> 

---

## 页面3：脚本与分镜

展示：

- 完整视频脚本

- Shot列表

- 每个Shot的画面

- 景别

- 运镜

- 旁白

- 字幕

- 视频Prompt

用户可以：

> 编辑某个Shot / 重新生成某个Shot / 确认分镜
> 
> 

---

## 页面4：生成进度

展示：

```Plain Text
Shot 01   ✓
Shot 02   ✓
Shot 03   生成中
Shot 04   ✓
Shot 05   等待
```

同时展示：

- 配音生成状态

- 音乐生成状态

- 视频生成进度

---

## 页面5：成片预览

展示：

- 最终视频

- 视频时长

- 字幕

- 配音

- 背景音乐

支持：

- 播放

- 重新生成单个Shot

- 导出视频

---

# 五、场景模板

为了满足比赛“至少支持2类典型文旅场景”的要求，第一版建议直接支持 3 类。

对应后面接口1输入参数的"scene\_type" 这部分我的理解是shot生成的引导提示词

## 景区推荐

例如：

> 杭州西湖、乌镇、西塘
> 
> 

内容结构：

```Plain Text
视觉吸引
↓
核心景观
↓
特色体验
↓
文化特色
↓
游客体验
↓
行动召唤
```

---

## 城市形象宣传

例如：

> 杭州城市宣传、宁波城市宣传
> 
> 

内容结构：

```Plain Text
城市航拍
↓
城市地标
↓
自然风光
↓
文化特色
↓
城市生活
↓
城市精神
```

---

## 非遗/文化传播

例如：

> 龙泉青瓷、越剧、传统手工艺
> 
> 

内容结构：

```Plain Text
文化Hook
↓
历史背景
↓
制作/表演过程
↓
文化特色
↓
年轻化表达
↓
文化价值
```

后续可以继续增加：

- 节庆活动

- 校园/城市打卡

但第一版没有必要全部实现。

---

# 六、接口总体设计

第一版建议控制为以下核心接口：

```Plain Text
1. 创建项目 / 生成创作方案
2. 修改/确认创作方案
3. 生成脚本与分镜
4. 修改单个Shot
5. 生成分镜图片与视频
6. 生成配音与音乐
7. 合成最终视频
8. 查询任务状态
```

后端内部可以继续拆分，但前端只与这些统一接口交互。

总的输入和输出

```JSON
{
  "city": "杭州",//传播城市 
  "location": "西湖",//具体地点
  "scene_type": "scenic",//文旅场景 城市形象宣传、景区推荐、节庆活动推广、非遗文化传播、校园/城市打卡视频等

  "theme": "春日西湖旅游宣传",//传播主题

  "audience": "18-35岁年轻游客",//目标人群

  "style": "大气唯美",//视频风格

  "duration_s": 60,//时长要求

  "aspect_ratio": "9:16",//画面比例
  "resolution": "1080p", //画质
    //temperature ai建议不需要前端作为参数输入 后端固定一个生成效果最好的即可 参考了即梦 确实没有这个输入
    //seedance2.0/2.0pro模型感觉也可以做一个选择的输入 看你咋想
  "description": "突出春日西湖风景、年轻人打卡体验",//更详细说明要求
  //参考的图片素材
  "assets":[
    {
      "type": "image",
      "url": "https://..."
    }
    //即梦还有参考音频和视频作为输入 但是我觉得难度和成本有点大了 可以先放着 后续可以考虑加入
  ]
  
}
```

```JSON
// 输出（AI生成管线 → 前端展示）
// 异步任务，包含阶段性输出与最终输出
{
  "task_id": "t_xxx",

  // 当前任务生成状态
  "status": "planning|copywriting|storyboard|generating|audio|composing|done|failed",

  // 当前任务生成进度 可无
  "progress": 0,

  // ===== 阶段性输出 =====

  // AI文旅内容策划结果
  "planning": {},

  // 文旅宣传文案
  "copywriting": {},

  // 视频脚本
  "script": {},

  // 分镜设计结果
  "storyboard": {},

  // 分镜图及视觉素材
  "visual_assets": {},

  // AI配音
  "voice": {},

  // 背景音乐建议/音乐素材
  "music": {},

  // AI生成的视频片段
  "video_clips": {},

  // ===== 系统保障 =====

  // 内容安全、版权合规、素材授权检查结果
  "safety": {},

  // ===== 最终输出 =====

  // 最终短视频成片、预览及导出结果
  "final_video": {}
}
```

---

# 七、接口1：生成AI创作方案

## POST /api/projects

用户填写需求后调用。

### 输入（前端 → 后端）

每个参数需要后端自行

判断类型

是否可以为空

是否为可选\(如画面比例是用户自定义还是seedance有要求\)

\.\.\.\.\.\.\.

重要的可以标注在apifox的参数文档中

```JSON
{
  "city": "杭州",//传播城市 
  "location": "西湖",//具体地点
  "scene_type": "scenic",//文旅场景 城市形象宣传、景区推荐、节庆活动推广、非遗文化传播、校园/城市打卡视频等

  "theme": "春日西湖旅游宣传",//传播主题

  "audience": "18-35岁年轻游客",//目标人群

  "style": "大气唯美",//视频风格

  "duration_s": 60,//时长要求

  "aspect_ratio": "9:16",//画面比例
  "resolution": "1080p", //画质
    //temperature ai建议不需要前端作为参数输入 后端固定一个生成效果最好的即可 参考了即梦 确实没有这个输入
    //seedance2.0/2.0pro模型感觉也可以做一个选择的输入 看你咋想
  "description": "突出春日西湖风景、年轻人打卡体验",//更详细说明要求
  //参考的图片素材
  "assets":[
    {
      "type": "image",
      "url": "https://..."
    }
    //即梦还有参考音频和视频作为输入 但是我觉得难度和成本有点大了 可以先放着 后续可以考虑加入
  ]
  
}
```

### 输出（后端 → 前端）

```JSON
{
"project_id": "p_001",//接口1部分用户输入的存储标识(duration等) 用于后续接口的输入|视频结果存储数据库标识|前端历史创作里的标识
"status": "waiting_confirm",
//旁白文案
"copywriting": "【0-15s】三面云山一面城，6.38平方公里的湖面，盛着一座城最温柔的野心。2011年，西湖文化景观列入世界遗产。\n【15-30s】春风又绿苏堤，那是苏轼用一肩烟雨筑就的长卷；白堤柳色如烟，藏着白居易的江南旧梦。\n【30-45s】断桥边，等一场千年等一回的烟雨；雷峰塔下，夕照为传说镀上金边。\n【45-60s】山不动，水在动；塔不语，风在语。一遇西湖，心上杭州。"
}
```

### 前端操作

用户看到：

> AI旁白文案
> 
> 

可以：

```Plain Text
[编辑]
[重新生成]
[确认方案]
```

---

# 八、接口2：修改/确认创作方案

用户修改方案后提交。

## PUT /api/projects/\{project\_id\}/plan

### 输入

```JSON
//用户微调后最终确定好的旁白文案
{
    "copywriting": "【0-15s】三面云山一面城，6.38平方公里的湖面，盛着一座城最温柔的野心。2011年，西湖文化景观列入世界遗产。\n【15-30s】春风又绿苏堤，那是苏轼用一肩烟雨筑就的长卷；白堤柳色如烟，藏着白居易的江南旧梦。\n【30-45s】断桥边，等一场千年等一回的烟雨；雷峰塔下，夕照为传说镀上金边。\n【45-60s】山不动，水在动；塔不语，风在语。一遇西湖，心上杭州。"
}
```

### 输出

```JSON
{
  "project_id": "p_001",

  "status": "plan_confirmed",

  "plan_id": "plan_001"
}
```

用户确认后进入下一阶段。

---

# 九、接口3：生成视频脚本 \+ 分镜

这是系统的核心接口之一。

## POST /api/projects/\{project\_id\}/storyboard

根据copywriting生成完整视频脚本和分镜。

### 输入

```JSON
{
    "project_id": "p_001",
    "plan_id": "plan_001"
}
```

### 输出

```JSON
{
"project_id": "p_001",

"status": "waiting_storyboard_confirm",

"storyboard": {

    "theme": "杭州西湖宣传片",

    "scenes": [

      {
        "scene_id": 1,

        "location": "西湖湖面",

        "time": "清晨",

        "shot_list": [

          {
            "shot_id": 1,

            "duration_s": 8,

            "camera": {
              "type": "航拍",
              "movement": "推",
              "angle": "俯拍"
            },

            "shot_size": "大远景",

            "subject": "西湖与苏堤全貌",

            "background": "朝霞晨雾",

            "prompt": "电影级航拍大远景，清晨西湖全景与苏堤横贯湖面，轻薄晨雾中朝霞将天际与水面染成淡金色，水面倒影清晰如镜，写实质感，8k分辨率"
          },

          {
            "shot_id": 2,

            "duration_s": 8,

            "camera": {
              "type": "无人机",
              "movement": "移",
              "angle": "平拍"
            },

            "shot_size": "全景",

            "subject": "苏堤春晓",

            "background": "晨雾桃柳",

            "prompt": "电影级无人机平移全景，晨光中苏堤春晓，垂柳轻拂水面桃红点缀，跑者剪影与远处湖心亭，薄雾氤氲于湖面，清新自然光"
          }

        ]
      }

    ]

}
}
实际返回6~8个Scene，10个左右Shot，每个 shot 的 prompt 直接用于视频生成。
```

---

---



# 十一、接口4：修改单个Shot

用户在前端点击某个分镜，例如：

> Shot 03
> 
> 

进行修改视频生成的prompt。

## PUT /api/projects/\{project\_id\}/shots/\{shot\_id\}

### 输入

```JSON
{
"prompt": "电影级摇镜头全景，午后从断桥桥头缓缓摇向白堤，游人漫步于湖光山色间，湖面泛着幽蓝光泽，远山如黛，明亮日光电影色调"
}
```

### 输出

```JSON
{
"project_id": "p_001",

"shot_id": 3,

"status": "updated",

"shot": {
"shot_id": 3,
"duration_s": 7,
"camera": {"type": "地面机位", "movement": "摇", "angle": "平拍"},
"shot_size": "全景",
"subject": "断桥与白堤游人",
"background": "湖光山色",
"prompt": "电影级摇镜头全景，午后从断桥桥头缓缓摇向白堤，游人漫步于湖光山色间，湖面泛着幽蓝光泽，远山如黛，明亮日光电影色调"
}
}
```

前端支持：

```Plain Text
[保存修改]
[重新生成此Shot]
```

---

# 十二、接口5：生成分镜图片 \+ 视频Shot

用户确认分镜以后，开始真正的多模态生成。

## POST /api/projects/\{project\_id\}/generate

### 输入

```JSON
{
"project_id": "p_001",

"shots": [1,2,3,4],

"generate_image": true, //分镜图

"generate_video": true
}
```

### 输出

```JSON
{
  "task_id": "task_001",

  "project_id": "p_001",

  "status": "generating",

  "progress": 0,

  "shots": [
    {
      "shot_id": "shot_01",
      "status": "pending"
    },
    {
      "shot_id": "shot_02",
      "status": "pending"
    }
  ]
}
```

---

# 十三、Shot生成方式

后端内部采用：

```Plain Text
Storyboard
    ↓
Shot Prompt
    ↓
生成分镜图 / Key Frame
    ↓
图片作为视频参考
    ↓
视频模型
    ↓
Video Shot
```

即：

> **先图后视频**
> 
> 

这样可以提高画面可控性和多镜头视觉一致性。

视频模型具体使用哪一家由后端统一决定，例如：

```Plain Text
可灵
即梦
其他视频生成模型
```

前端不需要关心具体模型。

---

# 十四、接口6：查询生成任务

由于图片和视频生成都是异步任务，不能让前端一直等待接口。

## GET /api/tasks/\{task\_id\}

### 输出

```JSON
{
  "task_id": "task_001",

  "status": "generating",

  "progress": 65,

  "shots": [

    {
      "shot_id": "shot_01",
      "status": "completed",

      "image_url": "https://.../shot01.jpg",

      "video_url": "https://.../shot01.mp4"
    },

    {
      "shot_id": "shot_02",
      "status": "completed",

      "image_url": "https://.../shot02.jpg",

      "video_url": "https://.../shot02.mp4"
    },

    {
      "shot_id": "shot_03",
      "status": "generating",

      "progress": 70
    },

    {
      "shot_id": "shot_04",
      "status": "pending"
    }
  ]
}
```

最终：

```JSON
{
  "task_id": "task_001",

  "status": "completed",

  "progress": 100,

  "shots": [
    {
      "shot_id": "shot_01",
      "status": "completed",
      "image_url": "https://...",
      "video_url": "https://..."
    }
  ]
}
```

---

# 十五、Shot级重新生成

这是系统必须保留的功能。

例如：

> Shot 03 人物动作不自然。
> 
> 

不需要重新生成整个60秒视频。

调用：

## POST /api/projects/\{project\_id\}/shots/\{shot\_id\}/regenerate

### 输入

```JSON
{
  "reason": "人物动作不自然",

  "prompt": "人物自然抬头看向夕阳，动作缓慢自然",

  "keep_style": true
}
```

### 输出

```JSON
{
  "task_id": "task_003",

  "shot_id": "shot_03",

  "status": "generating"
}
```

这样能够体现系统的：

> **局部可控生成能力**
> 
> 

也是区别于简单“一键AI视频生成”的重要功能。

---

# 十六、接口7：生成配音与背景音乐

配音和音乐可以在视频Shot生成的同时进行。

## POST /api/projects/\{project\_id\}/audio

### 输入

```JSON
{
  "project_id": "p_001",

  "voice": "",

  "music": ""
}
```

### 输出

```JSON
{
  "task_id": "audio_001",

  "status": "generating",

  "voice": {
    "status": "generating"
  },

  "music": {
    "status": "generating"
  }
}
```

完成后：

```JSON
{
  "task_id": "audio_001",

  "status": "completed",

  "voice_url": "https://.../voice.mp3",

  "music_url": "https://.../music.mp3"
}
```

如果时间有限，背景音乐第一版也可以采用：

> AI推荐 \+ 系统音乐素材库
> 
> 

不一定必须自己训练音乐模型。

---

# 十七、接口8：最终视频合成

当：

```Plain Text
视频Shot
+
配音
+
背景音乐
+
字幕
```

准备完成以后进行最终合成。

## POST /api/projects/\{project\_id\}/render

### 输入

```JSON
{
  "project_id": "p_001",

  "shot_ids": [
    "shot_01",
    "shot_02",
    "shot_03"
  ],

  "voice_url": "https://.../voice.mp3",

  "music_url": "https://.../music.mp3",

  "subtitle": true,

  "resolution": "1080p",

  "aspect_ratio": "9:16"
}
```

### 输出

```JSON
{
  "task_id": "render_001",

  "status": "rendering"
}
```

---

# 十八、最终成片查询

## GET /api/projects/\{project\_id\}/render/status

### 输出

```JSON
{
  "task_id": "render_001",

  "status": "completed",

  "progress": 100,

  "video": {

    "url": "https://.../final.mp4",

    "duration_s": 59.8,

    "resolution": "1080x1920"
  }
}
```

前端进入：

> 成片预览页面
> 
> 

提供：

```Plain Text
[播放]

[重新生成某个Shot]

[导出视频]
```

---

# 十九、内容安全与版权

这一部分不建议第一版做得过于复杂，但一定要有。

## 用户素材授权

上传图片时：

```Plain Text
素材来源：

○ 用户原创
○ 已获得授权
○ 官方公开素材
○ AI生成
```

后端记录：

```JSON
{
  "asset_id": "asset_001",
  "source_type": "user_original",
  "license_confirmed": true
}
```

---

## AI生成内容安全

在最终合成前进行基础检查：

```Plain Text
文本安全
↓
图片/视频安全
↓
最终成片检查
```

如果发现风险：

```JSON
{
  "status": "warning",

  "issues": [
    {
      "type": "content",
      "message": "检测到潜在风险内容"
    }
  ]
}
```

第一版不需要开发复杂的审核后台，可以通过已有模型/API完成。

---

# 二十、浙江文旅特色增强

这是项目区别于普通 AI 视频工具的重要部分。

系统不应该只是：

```Plain Text
用户输入“西湖”
↓
LLM
↓
随便生成
```

而应该增加一个简单的：

> **浙江文旅知识库**
> 
> 

例如保存：

```Plain Text
杭州
 ├─ 西湖
 ├─ 灵隐寺
 ├─ 良渚
 └─ 宋城

嘉兴
 ├─ 乌镇
 └─ 西塘

湖州
 └─ 南浔古镇

金华
 └─ 横店

绍兴
 ├─ 鲁迅故里
 └─ 黄酒文化
```

每个景点保存少量：

- 景点简介

- 历史文化

- 核心特色

- 推荐拍摄元素

- 官方描述

生成文案时：

```Plain Text
用户输入
 ↓
浙江文旅知识检索
 ↓
大模型
 ↓
文案 / 脚本 / 分镜
```

这样可以减少事实错误。

第一版不需要做复杂 RAG。

一个简单的景点 JSON/数据库都可以。

---

# 二十一、视觉一致性

为解决：

> 每个Shot单独生成导致画面风格不一致
> 
> 

在项目创建时生成一个：

```JSON
{
  "style_profile": {

    "visual_style": "电影感、东方美学",

    "color_style": "春日暖色",

    "lighting": "自然光",

    "camera_style": "电影摄影",

    "character_style": "真实人物"
  }
}
```

之后每个Shot都使用：

```Plain Text
全局风格
+
Shot描述
+
参考图片
```

生成。

这样能够体现评分标准中的：

> **风格一致性**
> 
> 

---

# 二十二、AI智能体/工作流

比赛要求鼓励：

> 智能体编排
> 
> 

没有必要真的做一个特别复杂的 Agent 系统。

可以在项目方案中设计为：

```Plain Text
用户需求
                  ↓
           ┌─────────────┐
           │ 文旅策划Agent │
           └──────┬──────┘
                  ↓
           ┌─────────────┐
           │ 脚本分镜Agent │
           └──────┬──────┘
                  ↓
       ┌──────────┼──────────┐
       ↓          ↓          ↓
   图片生成Agent 视频生成Agent 音频Agent
       └──────────┼──────────┘
                  ↓
             剪辑Agent
                  ↓
               成片
```

实际开发时可以由后端用普通工作流实现。

**不需要为了“Agent”这个名词把项目搞复杂。**

---

# 二十三、最终系统结构

```Plain Text
┌───────────────────────────────────────────┐
│              前端 Web 创作平台             │
│                                           │
│  需求输入 → AI方案 → 分镜 → 生成 → 成片    │
└──────────────────┬────────────────────────┘
                   ↓
             统一API接口层
                   ↓
┌───────────────────────────────────────────┐
│               AI内容生产流程               │
│                                           │
│  文旅策划 → 文案 → 脚本 → 分镜             │
│                         ↓                 │
│                  ┌──────┼──────┐          │
│                  ↓      ↓      ↓          │
│                 图片    视频    音频        │
│                  └──────┼──────┘          │
│                         ↓                 │
│                      智能合成              │
└──────────────────┬────────────────────────┘
                   ↓
             成片 / 导出
```

---

# 二十四、核心数据流

整个系统最核心的数据关系：

```Plain Text
Project
   │
   ├── Plan
   │
   ├── Script
   │
   ├── Storyboard
   │      │
   │      ├── Shot 01
   │      ├── Shot 02
   │      ├── Shot 03
   │      └── ...
   │
   ├── Voice
   │
   ├── Music
   │
   └── Final Video
```

其中：

> **Project 是项目主体，Shot 是视频生成的最小单位。**
> 
> 

---

# 二十五、完整Demo流程

比赛现场可以准备一个固定案例：

## 案例：杭州西湖景区推荐

用户输入：

```Plain Text
城市：杭州
景区：西湖
场景：景区推荐
主题：春日西湖
人群：18-35岁年轻游客
风格：清新唯美
时长：60秒
比例：9:16
```

---

## 第一步

点击：

> 开始创作
> 
> 

系统生成：

> AI创作方案 \+ 宣传文案
> 
> 

---

## 第二步

用户修改一句文案：

> “春天的杭州，第一站一定是西湖。”
> 
> 

点击：

> 确认方案
> 
> 

---

## 第三步

系统生成：

> 视频脚本 \+ 10个Shot分镜
> 
> 

用户点击：

> Shot 03
> 
> 

修改画面。

---

## 第四步

点击：

> 开始生成视频
> 
> 

后台并行：

```Plain Text
Shot 01 ✓
Shot 02 ✓
Shot 03 ████░
Shot 04 ✓
...
```

同时生成：

```Plain Text
AI配音
AI音乐
```

---

## 第五步

自动合成：

```Plain Text
10个视频Shot
+
配音
+
音乐
+
字幕
```

得到：

> 60秒竖屏西湖宣传片
> 
> 

---

## 第六步

前端播放：

```Plain Text
[最终成片]

59.8s
1080×1920

[重新生成Shot]
[导出视频]
```

整个Demo完成。

---

# 二十六、第一版开发优先级

考虑到只有两个人，不建议所有功能同时开发。

## P0：必须实现

```Plain Text
✓ 用户需求输入
✓ 至少2个文旅场景
✓ AI文案
✓ AI脚本
✓ AI分镜
✓ 分镜Shot展示
✓ Shot级视频生成
✓ AI配音
✓ 背景音乐
✓ 视频合成
✓ 视频预览
✓ 视频导出
```

这是比赛基本盘。

---

## P1：建议实现

```Plain Text
✓ 用户修改文案
✓ 用户修改Shot
✓ 单Shot重新生成
✓ 浙江文旅知识库
✓ 图片参考素材
✓ 风格一致性
✓ 基础内容安全
✓ 素材授权记录
```

这些可以明显提高比赛完成度。

---

## P2：后续扩展

```Plain Text
○ 时间轴编辑
○ 多版本管理
○ 复杂字幕编辑
○ 多人协作
○ 更复杂Agent
○ 自动传播文案
○ 小红书/抖音标题推荐
○ 多平台视频比例自动适配
○ 更复杂版权管理
```

这些不是当前比赛Demo的核心。

---

# 二十七、最终接口清单

第一版前端真正需要对接的核心接口：

```Plain Text
① POST
/api/projects
生成AI创作方案


② PUT
/api/projects/{project_id}/plan
修改/确认AI方案


③ POST
/api/projects/{project_id}/storyboard
生成脚本+分镜


④ PUT
/api/projects/{project_id}/shots/{shot_id}
修改单个Shot


⑤ POST
/api/projects/{project_id}/generate
批量生成分镜图+视频Shot


⑥ GET
/api/tasks/{task_id}
查询图片/视频生成状态


⑦ POST
/api/projects/{project_id}/audio
生成配音+音乐


⑧ POST
/api/projects/{project_id}/render
合成最终视频


⑨ GET
/api/projects/{project_id}/render/status
查询最终成片状态
```

其中第⑤个接口内部可以由后端拆成：

```Plain Text
图片生成
↓
视频生成
↓
Shot结果汇总
```

前端不需要知道。

---

# 二十八、最终产品定位

这个项目最终不要把自己定义成：

> “AI视频生成网站”
> 
> 

而应该定义为：

> **面向浙江文旅传播的 AIGC 智能短视频制片平台**
> 
> 

核心能力是：

```Plain Text
懂文旅
   ↓
会策划
   ↓
会写文案
   ↓
会做分镜
   ↓
会生成画面
   ↓
会生成视频
   ↓
会配音配乐
   ↓
会自动剪辑
   ↓
最终生成可传播的文旅短视频
```

最终形成：

> **“从一个文旅需求，到一条完整短视频”的自动化生产闭环。**
> 
> 

这比单纯展示某一个 AI 视频模型，更符合本次比赛提出的“完整内容生产链路”和“可复用文旅短视频生成系统”的定位。



