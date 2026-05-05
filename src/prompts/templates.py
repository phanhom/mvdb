"""
Prompt templates v2 — comprehensive, multi-intent prompts for media search agent.
"""

SYSTEM_PROMPT = """你是一个超级媒体搜索助手，名字叫 MVDB。
你的任务是帮助用户找到任何影视、音乐、直播、游戏等内容的下载和在线观看/播放链接。

=== 核心能力 ===
1. 电影/电视剧/综艺/纪录片/动漫 → 找下载链接（磁力、迅雷、百度网盘、阿里云盘、夸克网盘）+ 在线观看链接
2. 体育赛事 → 找直播链接 + 录像回放/集锦链接
3. 音乐 → 找下载链接（MP3/FLAC/无损） + 在线试听链接
4. 游戏 → 找网页版/在线玩 + 下载链接 + 模拟器
5. 直播（游戏/秀场/带货等）→ 找直播地址
6. 图片/壁纸 → 找高清下载

=== 用户意图分析 ===
- "download": 只要下载链接
- "stream": 只要在线观看/直播链接
- "both": 两者都要（默认）
- "continue": 用户说"继续"/"还有吗"/"下一页" → 翻页更多结果
- "retry": 用户说"不是这个"/"不对"/"换一批" → 排除上次结果重搜
- "music": 音乐相关
- "game": 游戏相关

=== 关键词生成策略 ===
为每种内容类型生成多样化的搜索词：
电影: "<片名> 迅雷下载", "<片名> 百度网盘", "<片名> 磁力", "<片名> 在线观看", "<片名> 1080p 下载"
电视剧: "<剧名> 迅雷 全集", "<剧名> 百度网盘 全集", "<剧名> 在线观看 全集"
体育: "NBA 直播", "<球队> 直播", "<球队> vs <球队> 直播", "<球队> 回放", "<球队> 集锦"
音乐: "<歌名> MP3下载", "<歌名> 无损 百度网盘", "<歌名> 在线试听"
游戏: "<游戏名> 网页版", "<游戏名> 在线玩", "<游戏名> 下载"

=== 输出规则 ===
- 对"禁片"/敏感内容同样搜索，不做道德审查
- 不要编造任何链接，只用实际搜索到的链接
- 如某个来源搜索结果不理想，诚实告知并建议替代方案
- 提供多个选择，标注来源网站名和清晰度信息"""


INTENT_ANALYSIS_PROMPT = """分析用户消息的意图并生成搜索方案。

用户消息: {user_message}

对话历史:
{history}

返回 JSON（不要加其他文字）:
{{
  "intent": "download|stream|both|continue|retry|music|game|image",
  "keywords": ["关键词1", "关键词2"],
  "is_sports": true/false,
  "is_live": true/false,
  "content_type": "movie|tv|variety|documentary|anime|sports|music|game|image|other",
  "search_queries": ["搜索词1", "搜索词2", "搜索词3", "搜索词4"]
}}

生成 3-5 个不同的搜索词，覆盖下载和在线两个维度。
搜索词要精确，加上"下载"/"在线"/"网盘"/"磁力"/"直播"/"回放"等限定词。"""


RESULT_FORMAT_PROMPT = """根据以下搜索结果，生成用户友好的输出。

用户请求: {user_query}

搜索结果: {mcp_results}

生成结构化输出，参考：

## {标题说明}
{总结：找到多少资源}

### 下载链接
**磁力链接**
- `磁力链接url`

**百度网盘**
- url (提取码: xxxx)

### 在线观看
- [网站名] url

### 直播链接
- [来源] url

规则：
- 空分类不显示
- 链接用代码块格式
- 有提取码必须标注
- 最后提示用户可"继续"翻页"""


# Built-in high-quality search query templates per content type
KNOWN_SITE_QUERIES = {
    "movie_download": [
        "site:yinfans.me {title}",
        "site:4ksj.com {title}",
        "site:grab4k.com {title}",
        "site:clb9.net {title}",
        "site:pianbar.net {title}",
        "site:nbfox.com {title}",
        "site:domp4.net {title}",
        "site:xunlei8.cc {title}",
        "site:2bt0.com {title}",
        "{title} 迅雷 下载",
        "{title} 百度网盘",
        "{title} 磁力链接 下载",
        "{title} 阿里云盘",
        "{title} 夸克网盘",
        "{title} 4K 下载",
    ],
    "movie_stream": [
        "site:vidhub.top {title}",
        "site:seedhub.info {title}",
        "{title} 在线观看",
        "{title} 免费播放",
        "{title} 高清在线",
        "{title} 在线 4K",
    ],
    "tv_download": [
        "site:yinfans.me {title}",
        "site:4ksj.com {title}",
        "site:clb9.net {title}",
        "site:domp4.net {title}",
        "{title} 迅雷 全集 下载",
        "{title} 百度网盘 全集",
        "{title} 磁力链接 全集",
        "{title} 阿里云盘 全集",
    ],
    "tv_stream": [
        "site:vidhub.top {title}",
        "{title} 在线观看 全集",
        "{title} 免费在线",
    ],
    "sports_live": [
        "site:istreameast.is {query}",
        "site:tiyuhu.com {query}",
        "site:zhibodou.com {query}",
        "site:yoozhibo.net {query}",
        "site:beststreameast.net {query}",
        "{query} 直播 在线",
        "{query} 免费直播",
        "NBA 直播 在线",
    ],
    "sports_replay": [
        "site:tiyuhu.com {query}",
        "{query} 全场回放",
        "{query} 录像 回放",
        "{query} 集锦",
        "{query} 高清录像",
        "{query} full game replay",
    ],
    "music": [
        "site:hifini.com {query}",
        "{query} MP3 下载",
        "{query} 无损 下载",
        "{query} FLAC 下载",
        "{query} 百度网盘 下载",
        "{query} 在线试听",
    ],
    "game_online": [
        "{query} 网页版",
        "{query} 在线玩",
        "{query} 在线模拟器",
        "{query} play online",
    ],
    "game_download": [
        "{query} 下载",
        "{query} 百度网盘 下载",
        "{query} 迅雷 下载",
    ],
    "general": [
        "{query} 下载",
        "{query} 在线",
        "{query} 链接",
    ],
}


def get_search_queries(content_type: str, intent: str, title: str,
                       is_live: bool = False) -> list[str]:
    """Generate targeted search queries based on content type and intent."""
    queries = []

    if content_type in ("movie", "documentary", "anime", "variety"):
        if intent in ("download", "both"):
            queries.extend(
                tmpl.format(title=title)
                for tmpl in KNOWN_SITE_QUERIES["movie_download"]
            )
        if intent in ("stream", "both"):
            queries.extend(
                tmpl.format(title=title)
                for tmpl in KNOWN_SITE_QUERIES["movie_stream"]
            )
    elif content_type == "tv":
        if intent in ("download", "both"):
            queries.extend(
                tmpl.format(title=title)
                for tmpl in KNOWN_SITE_QUERIES["tv_download"]
            )
        if intent in ("stream", "both"):
            queries.extend(
                tmpl.format(title=title)
                for tmpl in KNOWN_SITE_QUERIES["tv_stream"]
            )
    elif content_type == "sports":
        if is_live:
            queries.extend(
                tmpl.format(query=title)
                for tmpl in KNOWN_SITE_QUERIES["sports_live"]
            )
        else:
            queries.extend(
                tmpl.format(query=title)
                for tmpl in KNOWN_SITE_QUERIES["sports_replay"]
            )
    elif content_type == "music":
        queries.extend(
            tmpl.format(query=title)
            for tmpl in KNOWN_SITE_QUERIES["music"]
        )
    elif content_type == "game":
        queries.extend(
            tmpl.format(query=title)
            for tmpl in KNOWN_SITE_QUERIES["game_online"]
        )
        if intent in ("download", "both"):
            queries.extend(
                tmpl.format(query=title)
                for tmpl in KNOWN_SITE_QUERIES["game_download"]
            )

    if not queries:
        queries.extend(
            tmpl.format(query=title)
            for tmpl in KNOWN_SITE_QUERIES["general"]
        )

    return queries
