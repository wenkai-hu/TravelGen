<!-- model=gemini:gemini-3.5-flash | date=2026-08-05 15:48 | temp=0.7 | run=3 -->
<!-- json_valid=True |  -->

{
  "theme": "杭州西湖宣传片",
  "scenes": [
    {
      "scene_id": 1,
      "location": "西湖苏堤与断桥",
      "time": "清晨",
      "shot_list": [
        {
          "shot_id": 1,
          "duration_s": 8,
          "camera": {"type": "航拍", "movement": "推", "angle": "俯拍"},
          "shot_size": "大远景",
          "subject": "苏堤全貌",
          "background": "朝霞与晨雾",
          "prompt": "航拍镜头缓慢推进，西湖苏堤在晨雾中若隐若现，朝霞将湖面染成金橙色，水面如镜，写实电影质感，高动态范围"
        },
        {
          "shot_id": 2,
          "duration_s": 8,
          "camera": {"type": "摇臂", "movement": "升降", "angle": "平视"},
          "shot_size": "全景",
          "subject": "断桥与近景荷花",
          "background": "朦胧的西湖远山",
          "prompt": "镜头缓缓升起，古朴的断桥横跨湖面，前景是带露水的绿色荷叶与粉色荷花，薄雾环绕，清晨柔和散射光，唯美江南意境"
        }
      ]
    },
    {
      "scene_id": 2,
      "location": "湖心水域",
      "time": "午后",
      "shot_list": [
        {
          "shot_id": 3,
          "duration_s": 10,
          "camera": {"type": "船载拍摄", "movement": "移", "angle": "平视"},
          "shot_size": "中景",
          "subject": "摇鲁木船",
          "background": "波光粼粼的湖面与远处的雷峰塔",
          "prompt": "移动镜头，一艘传统黑色摇橹木船划过清澈碧绿的湖面，荡开层层波纹，远处隐约可见雷峰塔，阳光洒在水面闪烁金光，写实电影色调"
        },
        {
          "shot_id": 4,
          "duration_s": 8,
          "camera": {"type": "三脚架", "movement": "固定", "angle": "俯拍"},
          "shot_size": "特写",
          "subject": "西湖水面与水滴",
          "background": "翠绿的荷叶",
          "prompt": "固定特写镜头，一颗晶莹剔透的水珠在翠绿的荷叶上滚动，背景是碧绿清澈的西湖水，阳光直射，微风吹拂，极高清晰度，微距摄影质感"
        }
      ]
    },
    {
      "scene_id": 3,
      "location": "三潭印月",
      "time": "黄昏",
      "shot_list": [
        {
          "shot_id": 5,
          "duration_s": 10,
          "camera": {"type": "航拍", "movement": "环绕", "angle": "平视"},
          "shot_size": "全景",
          "subject": "三潭石塔",
          "background": "夕阳余晖下的湖面",
          "prompt": "航拍环绕镜头，夕阳洒在三潭印月的三个石塔上，石塔呈现古朴的深灰色，湖面泛着粼粼金色波光，温暖的逆光，电影感色彩"
        }
      ]
    },
    {
      "scene_id": 4,
      "location": "雷峰夕照",
      "time": "日落",
      "shot_list": [
        {
          "shot_id": 6,
          "duration_s": 8,
          "camera": {"type": "航拍", "movement": "拉", "angle": "仰拍"},
          "shot_size": "大远景",
          "subject": "雷峰塔剪影",
          "background": "晚霞与火烧云",
          "prompt": "镜头缓缓向后拉开，五层八角砖木结构的雷峰塔在壮丽的晚霞中呈现完美的剪影，天空中火烧云色彩斑斓，史诗感构图"
        },
        {
          "shot_id": 7,
          "duration_s": 8,
          "camera": {"type": "手持", "movement": "摇", "angle": "平视"},
          "shot_size": "近景",
          "subject": "湖畔游客剪影",
          "background": "落日与雷峰塔",
          "prompt": "镜头从右向左缓缓摇过，湖畔长椅上坐着相互依偎的游客，他们的剪影面向落日，背景中红日渐渐沉入雷峰塔旁，温暖、宁静、治愈的电影质感"
        }
      ]
    }
  ]
}