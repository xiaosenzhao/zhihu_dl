# zhihu_dl

将知乎收藏夹（答案 / 文章 / 视频）批量导出为带本地图片的 Markdown 文件。

每条内容生成一个独立的 `.md` 文件，附带 YAML front matter（标题、作者、类型、原文链接），图片下载到本地 `images/` 目录并在 Markdown 中以相对路径引用。

## 安装

```bash
cd /path/to/zhihu-dl

# 使用已有 venv
source .venv/bin/activate

# 或新建
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

依赖：`requests`、`markdownify`。

## 准备 Cookie

知乎收藏夹 API 需要登录态。

1. 浏览器登录 `https://www.zhihu.com`。
2. 打开任意页面，按 F12 → Network → 刷新 → 选一个请求 → Request Headers。
3. 复制完整的 `Cookie:` 头部值（不要包含 `Cookie: ` 前缀）。
4. 粘贴到项目根目录的 `cookie.txt`。

Cookie 过期后会收到 `403`，重新复制即可。

## 用法

```bash
# 下载默认收藏夹（id 在脚本里写死为 646316355）
python3 download.py

# 指定收藏夹 id
python3 download.py -c 31888712

# 仅下载前 N 条，便于测试
python3 download.py -c 31888712 --limit 5

# 自定义输出目录
python3 download.py -c 31888712 --out ./my-output

# 使用其他位置的 cookie 文件
python3 download.py --cookie-file /path/to/cookie.txt
```

收藏夹 id 就是收藏夹页面 URL `https://www.zhihu.com/collection/<id>` 中的数字。

### 参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `-c, --collection` | `646316355` | 收藏夹 id |
| `--cookie-file` | `./cookie.txt` | Cookie 文件路径 |
| `--out` | `./output/<id>` | 输出目录 |
| `--limit` | `0`（不限） | 最多下载条数 |

## 输出结构

```
output/<collection_id>/
├── articles/
│   ├── answer_<id>_<标题>.md
│   ├── article_<id>_<标题>.md
│   └── zvideo_<id>_<标题>.md
└── images/
    └── <md5>.jpg
```

每个 `.md` 文件开头是 YAML front matter：

```markdown
---
title: "..."
author: "..."
type: answer
url: https://www.zhihu.com/question/.../answer/...
zhihu_id: 123456
---

# 标题

正文 ...
```

## 支持的内容类型

- `answer` — 回答
- `article` — 专栏文章
- `zvideo` — 视频（只保存描述文本，不下载视频文件）

未识别的类型会跳过并提示。

## 退出码

- `2` — Cookie 文件缺失或为空
- `3` — Cookie 失效（API 返回 403）

## 注意

- 脚本在分页之间 sleep 1s、图片之间 sleep 0.15s，避免触发限频；不要把这些值改得过小。
- 图片以 URL 的 MD5 命名去重，重跑不会重复下载。
- 仅供个人备份自己可见的收藏夹使用。
