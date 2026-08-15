# -*- coding: utf-8 -*-
"""命令行实战测试：python3 test_search.py "关键词" """

import sys

import service


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    keyword = args[0] if args else "考研英语 真题"
    full = "--full" in sys.argv
    print(f"开始测试关键词：{keyword}")
    result, warnings = service.run_full_search(keyword)
    stats = result["stats"]

    lines = []
    lines.append("=" * 70)
    lines.append(f"关键词：{keyword}")
    lines.append(f"总共抓取原始数据：{stats['total_raw']} 条")
    for src, n in stats["per_source"].items():
        lines.append(f"  · {src}：{n} 条")
    if stats.get("fetched_before_filter"):
        lines.append(
            f"核心词过滤：抓取 {stats['fetched_before_filter']} 条，"
            f"丢弃不含核心词的无关结果 {stats['core_filtered']} 条，"
            f"保留 {stats['total_raw']} 条"
        )
    lines.append(f"去重后保留主条目：{stats['main_count']} 条，合并重复：{stats['merged_count']} 条")
    lines.append(f"最终整理成资料组：{stats['cluster_count']} 组")
    lines.append(f"总耗时：{result['elapsed']} 秒")
    if warnings:
        lines.append("抓取警告：")
        for w in warnings:
            lines.append(f"  · {w}")
    lines.append("=" * 70)
    for i, c in enumerate(result["clusters"], 1):
        tags = "、".join(t["name"] for t in c["all_tags"]) or "无"
        lines.append(f"资料组{i}｜共 {c['total']} 条｜合并重复 {c['merged']} 条｜标签：{tags}")
        lines.append(f"  代表标题：{c['rep_title']}")
        if full:
            for item in c["entries"]:
                qt = "、".join(item["quality_tags"]) if item["quality_tags"] else "无"
                lines.append(
                    f"      · [{item['source']}] {item['title']}（质量：{qt}｜{'⭐' * item['stars']}）"
                )
    lines.append("=" * 70)
    cores = (result.get("core_phrase") or "").split("、")
    if cores:
        bad = []
        for c in result["clusters"]:
            for item in c["entries"]:
                if any(core.lower() not in item["title"].lower() for core in cores):
                    bad.append(item["title"])
        lines.append(
            "标题核心词校验：全部通过"
            if not bad
            else f"标题核心词校验：发现 {len(bad)} 条不含核心词，例如：{'；'.join(bad[:3])}"
        )
        lines.append("=" * 70)
    lines.append("带新质量标签/评级的示例条目（最多 8 条，取主条目）：")
    examples = []
    for c in result["clusters"]:
        for item in c["entries"]:
            if item["is_dup"]:
                continue
            if item["quality_tags"]:
                examples.append(item)
    for c in result["clusters"]:
        for item in c["entries"]:
            if item["is_dup"]:
                continue
            if not item["quality_tags"] and item["stars"] != 3 and len(examples) < 8:
                examples.append(item)
    for i, item in enumerate(examples[:8], 1):
        tags = "、".join(item["quality_tags"]) if item["quality_tags"] else "无质量标签"
        lines.append(f"  {i}. [{item['source']}] {item['title']}")
        lines.append(f"     质量标签：{tags} ｜ 评级：{'⭐' * item['stars']}（{item['stars']}/5）")
    if not examples:
        lines.append("  （本次没有命中任何新质量标签的条目）")
    lines.append("=" * 70)
    lines.append("原始抓取结果中排在最前面的 15 条标题：")
    for i, item in enumerate(result["raw_ordered"][:15], 1):
        lines.append(f"  {i}. [{item['source']}] {item['title']}")
    lines.append("=" * 70)

    text = "\n".join(lines)
    print(text)
    with open("test_report.txt", "w", encoding="utf-8") as f:
        f.write(text)
    print("\n已保存 test_report.txt")


if __name__ == "__main__":
    main()
