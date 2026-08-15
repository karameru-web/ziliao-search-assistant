# 资料搜索助手（v2）

四个板块：

1. **全网搜索**：B站视频 + B站专栏 + Bing 网页 + 知乎，抓取约 100 条原始结果，
   自动打标签（免费可下 / 引流私信 / 付费购买）、跨平台去重、贪心聚类成资料组；
   资料组内提供 查看原文 / 复制链接 / 下载（文件直链）/ 收藏。
2. **链接评估**：粘贴小红书/知乎/B站等分享链接（可整段粘贴自动识别），
   自动抓取公开内容 + 关键词分析，输出绿/橙/红三档风险提示。
3. **上传评估**：上传 PDF / TXT，自动读取文字并识别资料类型；扫描版 PDF 会提示无法读取。
4. **我的资料**：书架页面，列出已下载（bookshelf/）、收藏的链接和上传的资料。

## 运行方法

```bash
cd kaoyan-search
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

然后浏览器打开 http://127.0.0.1:5000

## 命令行测试

```bash
.venv/bin/python test_search.py "考研英语 真题"
```

## 项目文件

- `crawler.py`：B站 API / Bing 抓取（含 -412 重试、Bing 反爬重试）
- `processor.py`：标签、去重（difflib > 0.8）、聚类（贪心 > 0.5）
- `evaluator.py`：链接提取、链接抓取、关键词评估
- `shelf.py`：bookshelf/ 下载与书架索引管理
- `service.py`：抓取 + 归纳编排
- `app.py`：Flask 入口
- `templates/`：四个板块页面 + 共享导航
