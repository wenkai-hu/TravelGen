<!-- model=gemini:gemini-3.5-flash | date=2026-08-05 15:48 | temp=0.7 | run=2 -->
<!-- json_valid=True |  -->

{
  "theme": "杭州西湖宣传片",
  "scenes": [
    {
      "scene_id": 1,
      "location": "西湖苏堤",
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
          "subject": "西湖全景与苏堤",
          "background": "晨雾与朝霞",
          "prompt": "Aerial drone shot pushing in, panoramic view of West Lake and Su Causeway wrapped in morning mist, warm golden sunrise glowing on the calm jade-green water, highly detailed, photorealistic, 8k resolution"
        },
        {
          "shot_id": 2,
          "duration_s": 8,
          "camera": {
            "type": "摇臂",
            "movement": "移",
            "angle": "平拍"
          },
          "shot_size": "中景",
          "subject": "木质摇橹船与荷花",
          "background": "波光粼粼的湖面",
          "prompt": "Slow tracking shot of a traditional wooden rowing boat gliding through blooming pink lotus flowers and green lily pads on West Lake, soft morning sunlight, misty background, cinematic lighting"
        }
      ]
    },
    {
      "scene_id": 2,
      "location": "白堤与断桥",
      "time": "上午",
      "shot_list": [
        {
          "shot_id": 3,
          "duration_s": 9,
          "camera": {
            "type": "手持",
            "movement": "跟",
            "angle": "平拍"
          },
          "shot_size": "全景",
          "subject": "白堤漫步的游客与垂柳",
          "background": "断桥残雪石桥",
          "prompt": "Gimbal tracking shot walking along the Bai Causeway, green weeping willows swaying in the light breeze, the ancient stone Broken Bridge in the background, bright afternoon sunlight, clear blue sky, vibrant colors"
        }
      ]
    },
    {
      "scene_id": 3,
      "location": "雷峰塔",
      "time": "傍晚",
      "shot_list": [
        {
          "shot_id": 4,
          "duration_s": 9,
          "camera": {
            "type": "固定三脚架",
            "movement": "固定",
            "angle": "平拍"
          },
          "shot_size": "全景",
          "subject": "夕阳下的雷峰塔",
          "background": "晚霞与远山",
          "prompt": "Stationary shot of the iconic Leifeng Pagoda, a five-story octagonal brick and wood tower with yellow walls and red railings, standing against a fiery orange sunset, silhouettes of mountains, glowing reflection on the calm lake surface"
        },
        {
          "shot_id": 5,
          "duration_s": 7,
          "camera": {
            "type": "摇臂",
            "movement": "升降",
            "angle": "仰拍"
          },
          "shot_size": "特写",
          "subject": "雷峰塔飞檐风铃",
          "background": "金色夕阳",
          "prompt": "Jib crane shot rising up to a close-up of a bronze wind chime hanging from the eaves of Leifeng Pagoda, golden hour sunset light shining through, dust motes dancing in the light, shallow depth of field, realistic textures"
        }
      ]
    },
    {
      "scene_id": 4,
      "location": "三潭印月",
      "time": "夜晚",
      "shot_list": [
        {
          "shot_id": 6,
          "duration_s": 10,
          "camera": {
            "type": "航拍",
            "movement": "环绕",
            "angle": "平拍"
          },
          "shot_size": "全景",
          "subject": "三潭印月石塔",
          "background": "月光下的湖面",
          "prompt": "Cinematic orbit shot of the Three Pools Mirroring the Moon, three hollow stone pagodas in the dark water illuminated under a bright full moon night, golden lantern light glowing from inside the pagodas, shimmering water reflections, mystical and serene atmosphere"
        },
        {
          "shot_id": 7,
          "duration_s": 9,
          "camera": {
            "type": "轨道",
            "movement": "拉",
            "angle": "俯拍"
          },
          "shot_size": "近景",
          "subject": "湖面月影波光",
          "background": "深蓝色夜空与远山阴影",
          "prompt": "Camera pulling back from the rippling lake surface reflecting the bright full moon, soft focus on the dark silhouette of the distant hills, tranquil night, hyper-realistic water physics, 4k"
        }
      ]
    }
  ]
}