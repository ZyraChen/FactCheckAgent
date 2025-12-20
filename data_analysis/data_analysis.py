#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据集标签分布分析与可视化
使用顶刊级别的图表样式
"""

import json
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from collections import Counter
import pandas as pd
from matplotlib import font_manager
import warnings
from matplotlib.colors import LogNorm
from matplotlib.ticker import PercentFormatter

warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# 设置顶刊风格
sns.set_style("whitegrid")
sns.set_context("paper", font_scale=1.3)
plt.rcParams['figure.dpi'] = 300
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['savefig.bbox'] = 'tight'

# 读取数据
print("正在加载数据集...")
with open('../data/dataset_latest.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"数据集总条数: {len(data)}\n")

# ========== 1. Verdict 分布 - 使用环形图 (Donut Chart) ==========
print("绘制 Verdict 分布图...")

verdict_count = Counter([item['verdict'] for item in data])
verdict_df = pd.DataFrame(verdict_count.items(), columns=['Verdict', 'Count'])
verdict_df = verdict_df.sort_values('Count', ascending=False)

fig, ax = plt.subplots(figsize=(10, 8))

# 颜色方案 - 使用学术风格的配色
colors = ['#E74C3C', '#3498DB', '#95A5A6']
explode = (0.05, 0.02, 0.02)  # 突出最大的部分

wedges, texts, autotexts = ax.pie(
    verdict_df['Count'],
    labels=verdict_df['Verdict'],
    autopct='%1.1f%%',
    startangle=90,
    colors=colors,
    explode=explode,
    textprops={'fontsize': 12, 'weight': 'bold'}
)

# 创建环形图效果
centre_circle = plt.Circle((0, 0), 0.70, fc='white')
fig.gca().add_artist(centre_circle)

# 添加中心文字
ax.text(0, 0, f'Total\n{len(data)}',
        ha='center', va='center', fontsize=20, weight='bold')

# 美化百分比文字
for autotext in autotexts:
    autotext.set_color('white')
    autotext.set_fontsize(11)
    autotext.set_weight('bold')

ax.set_title('Claim Verdict Distribution', fontsize=16, weight='bold', pad=20)
plt.savefig('1_verdict_distribution.png', bbox_inches='tight', dpi=300)
plt.close()
print("✓ Verdict 分布图已保存")

# ========== 2. Error Type 分布 - 使用水平条形图 ==========
print("绘制 Error Type 分布图...")

error_type_count = Counter([item['error_type'] for item in data if item['error_type'] is not None])
error_df = pd.DataFrame(error_type_count.items(), columns=['Error Type', 'Count'])
error_df = error_df.sort_values('Count', ascending=True)

fig, ax = plt.subplots(figsize=(12, 8))

# 使用渐变色
colors = plt.cm.RdYlBu_r(np.linspace(0.3, 0.9, len(error_df)))

bars = ax.barh(error_df['Error Type'], error_df['Count'], color=colors, edgecolor='black', linewidth=0.7)

# 添加数值标签
for i, (bar, count) in enumerate(zip(bars, error_df['Count'])):
    ax.text(count + 0.5, i, f'{count}',
            va='center', ha='left', fontsize=10, weight='bold')

ax.set_xlabel('Frequency', fontsize=13, weight='bold')
ax.set_title('Error Type Distribution', fontsize=16, weight='bold', pad=20)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.grid(axis='x', alpha=0.3, linestyle='--')
plt.savefig('2_error_type_distribution.png', bbox_inches='tight', dpi=300)
plt.close()
print("✓ Error Type 分布图已保存")

# ========== 3. Category 分布 - 使用棒棒糖图 (Lollipop Chart) ==========
print("绘制 Category 分布图...")

category_count = Counter([item['category'] for item in data if item['category'] is not None])
category_df = pd.DataFrame(category_count.items(), columns=['Category', 'Count'])
category_df = category_df.sort_values('Count', ascending=True)

fig, ax = plt.subplots(figsize=(14, 10))

# 棒棒糖图
ax.hlines(y=range(len(category_df)), xmin=0, xmax=category_df['Count'],
          color='#34495E', alpha=0.4, linewidth=2)
ax.plot(category_df['Count'], range(len(category_df)), "o",
        markersize=12, color='#E74C3C', markeredgecolor='white', markeredgewidth=2)

# 添加数值标签
for i, count in enumerate(category_df['Count']):
    ax.text(count + 0.3, i, f'{count}',
            va='center', ha='left', fontsize=9, weight='bold')

ax.set_yticks(range(len(category_df)))
ax.set_yticklabels(category_df['Category'], fontsize=10)
ax.set_xlabel('Frequency', fontsize=13, weight='bold')
ax.set_title('Error Category Distribution (Detailed)', fontsize=16, weight='bold', pad=20)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.grid(axis='x', alpha=0.3, linestyle='--')
plt.savefig('3_category_distribution.png', bbox_inches='tight', dpi=300)
plt.close()
print("✓ Category 分布图已保存")

# ========== 4. Topic 分布 - 使用旭日图风格的条形图 ==========
print("绘制 Topic 分布图...")

topic_count = Counter([item['topic'] for item in data if item['topic'] is not None])
topic_df = pd.DataFrame(topic_count.items(), columns=['Topic', 'Count'])
topic_df = topic_df.sort_values('Count', ascending=False)

fig, ax = plt.subplots(figsize=(12, 8))

# 使用渐变色彩映射
colors = plt.cm.Spectral(np.linspace(0.2, 0.9, len(topic_df)))

bars = ax.bar(topic_df['Topic'], topic_df['Count'], color=colors,
              edgecolor='black', linewidth=1.2, alpha=0.8)

# 添加数值标签
for bar, count in zip(bars, topic_df['Count']):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width() / 2., height + 0.5,
            f'{count}', ha='center', va='bottom', fontsize=11, weight='bold')

ax.set_ylabel('Frequency', fontsize=13, weight='bold')
ax.set_title('Topic Distribution', fontsize=16, weight='bold', pad=20)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.xticks(rotation=45, ha='right')
ax.grid(axis='y', alpha=0.3, linestyle='--')
plt.savefig('4_topic_distribution.png', bbox_inches='tight', dpi=300)
plt.close()
print("✓ Topic 分布图已保存")

# ========== 5. Verdict vs Error Type 热力图 ==========
print("绘制 Verdict vs Error Type 热力图...")

# 创建交叉表
verdict_error_data = []
for item in data:
    if item['error_type'] is not None:
        verdict_error_data.append({
            'verdict': item['verdict'],
            'error_type': item['error_type']
        })

if verdict_error_data:
    df_cross = pd.DataFrame(verdict_error_data)
    cross_tab = pd.crosstab(df_cross['error_type'], df_cross['verdict'])

    fig, ax = plt.subplots(figsize=(10, 8))

    # 使用红蓝色映射
    sns.heatmap(cross_tab, annot=True, fmt='d', cmap='RdYlBu_r',
                cbar_kws={'label': 'Count'}, linewidths=0.5, linecolor='gray',
                square=True, ax=ax)

    ax.set_title('Verdict vs Error Type Heatmap', fontsize=16, weight='bold', pad=20)
    ax.set_xlabel('Verdict', fontsize=13, weight='bold')
    ax.set_ylabel('Error Type', fontsize=13, weight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.savefig('5_verdict_errortype_heatmap.png', bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Verdict vs Error Type 热力图已保存")

# ========== 6. Topic vs Error Type 热力图 ==========
print("绘制 Topic vs Error Type 热力图...")

topic_error_data = []
for item in data:
    if item['error_type'] is not None and item['topic'] is not None:
        topic_error_data.append({
            'topic': item['topic'],
            'error_type': item['error_type']
        })

if topic_error_data:
    df_topic_error = pd.DataFrame(topic_error_data)
    cross_tab_topic = pd.crosstab(df_topic_error['topic'], df_topic_error['error_type'])

    fig, ax = plt.subplots(figsize=(14, 10))

    sns.heatmap(cross_tab_topic, annot=True, fmt='d', cmap='YlOrRd',
                cbar_kws={'label': 'Count'}, linewidths=0.5, linecolor='gray',
                ax=ax)

    ax.set_title('Topic vs Error Type Heatmap', fontsize=16, weight='bold', pad=20)
    ax.set_xlabel('Error Type', fontsize=13, weight='bold')
    ax.set_ylabel('Topic', fontsize=13, weight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.savefig('6_topic_errortype_heatmap.png', bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Topic vs Error Type 热力图已保存")


# ========== 7. Topic vs Verdict 热力图 ==========
print("绘制 Topic vs Verdict 热力图...")

topic_error_data = []
for item in data:
    if item['verdict'] is not None and item['topic'] is not None:
        topic_error_data.append({
            'topic': item['topic'],
            'verdict': item['verdict']
        })

if topic_error_data:
    df_topic_error = pd.DataFrame(topic_error_data)
    cross_tab_topic = pd.crosstab(df_topic_error['topic'], df_topic_error['verdict'])

    fig, ax = plt.subplots(figsize=(14, 10))

    sns.heatmap(cross_tab_topic, annot=True, fmt='d', cmap='YlOrRd',
                cbar_kws={'label': 'Count'}, linewidths=0.5, linecolor='gray',
                ax=ax)

    ax.set_title('Topic vs Verdict Heatmap', fontsize=16, weight='bold', pad=20)
    ax.set_xlabel('Verdict', fontsize=13, weight='bold')
    ax.set_ylabel('Topic', fontsize=13, weight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.savefig('6_topic_verdict_heatmap.png', bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Topic vs Verdict 热力图已保存")
# ========== 7. 综合仪表盘 ==========
print("绘制综合仪表盘...")

fig = plt.figure(figsize=(20, 12))
gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

# 7.1 Verdict 饼图
ax1 = fig.add_subplot(gs[0, 0])
wedges, texts, autotexts = ax1.pie(
    verdict_df['Count'],
    labels=verdict_df['Verdict'],
    autopct='%1.1f%%',
    colors=['#E74C3C', '#3498DB', '#95A5A6'],
    startangle=90
)
ax1.set_title('Verdict', fontsize=14, weight='bold')

# 7.2 Error Type 条形图
ax2 = fig.add_subplot(gs[0, 1:])
error_df_top = error_df.sort_values('Count', ascending=False).head(6)
colors_error = plt.cm.RdYlBu_r(np.linspace(0.3, 0.9, len(error_df_top)))
ax2.barh(error_df_top['Error Type'], error_df_top['Count'], color=colors_error)
ax2.set_xlabel('Count', fontsize=11, weight='bold')
ax2.set_title('Top Error Types', fontsize=14, weight='bold')
ax2.grid(axis='x', alpha=0.3)

# 7.3 Topic 条形图
ax3 = fig.add_subplot(gs[1, :])
topic_df_sorted = topic_df.sort_values('Count', ascending=False)
colors_topic = plt.cm.Spectral(np.linspace(0.2, 0.9, len(topic_df_sorted)))
bars = ax3.bar(topic_df_sorted['Topic'], topic_df_sorted['Count'], color=colors_topic, alpha=0.8)
for bar, count in zip(bars, topic_df_sorted['Count']):
    height = bar.get_height()
    ax3.text(bar.get_x() + bar.get_width() / 2., height + 0.3,
             f'{count}', ha='center', va='bottom', fontsize=9)
ax3.set_ylabel('Count', fontsize=11, weight='bold')
ax3.set_title('Topic Distribution', fontsize=14, weight='bold')
plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')
ax3.grid(axis='y', alpha=0.3)

# 7.4 热力图
ax4 = fig.add_subplot(gs[2, :])
if verdict_error_data:
    df_cross_small = pd.DataFrame(verdict_error_data)
    cross_tab_small = pd.crosstab(df_cross_small['error_type'], df_cross_small['verdict'])
    sns.heatmap(cross_tab_small, annot=True, fmt='d', cmap='RdYlBu_r',
                cbar_kws={'label': 'Count'}, linewidths=0.5, ax=ax4, square=False)
    ax4.set_title('Verdict vs Error Type', fontsize=14, weight='bold')
    ax4.set_xlabel('Verdict', fontsize=11, weight='bold')
    ax4.set_ylabel('Error Type', fontsize=11, weight='bold')
    plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45, ha='right')

fig.suptitle('Dataset Label Distribution Dashboard', fontsize=18, weight='bold', y=0.98)
plt.savefig('7_comprehensive_dashboard.png', bbox_inches='tight', dpi=300)
plt.close()
print("✓ 综合仪表盘已保存")
# ========== 7. Topic vs Verdict 热力图（改进版：百分比 + 对数计数） ==========
print("绘制 Topic vs Verdict 热力图（百分比 + 对数计数）...")

topic_verdict_rows = []
for item in data:
    if item.get('verdict') is not None and item.get('topic') is not None:
        topic_verdict_rows.append({
            'topic': item['topic'],
            'verdict': item['verdict']
        })

if topic_verdict_rows:
    df_topic_verdict = pd.DataFrame(topic_verdict_rows)
    cross_tab_topic = pd.crosstab(df_topic_verdict['topic'], df_topic_verdict['verdict'])

    # ---- 7.1 行归一化（每个 Topic 内比例）----  ✅ 推荐主图
    cross_tab_pct = cross_tab_topic.div(cross_tab_topic.sum(axis=1), axis=0).fillna(0)

    fig, ax = plt.subplots(figsize=(14, 10))
    sns.heatmap(
        cross_tab_pct,
        annot=True,
        fmt='.1%',
        cmap='YlOrRd',
        cbar_kws={'label': 'Row % (P(verdict | topic))'},
        linewidths=0.5,
        linecolor='gray',
        ax=ax
    )
    ax.set_title('Topic vs Verdict Heatmap (Row-normalized %)', fontsize=16, weight='bold', pad=20)
    ax.set_xlabel('Verdict', fontsize=13, weight='bold')
    ax.set_ylabel('Topic', fontsize=13, weight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.savefig('7_topic_verdict_heatmap_rowpct.png', bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Topic vs Verdict 百分比热力图已保存: 7_topic_verdict_heatmap_rowpct.png")

    # ---- 7.2 原始计数（对数色阶）----  ✅ 用于同时展示规模
    fig, ax = plt.subplots(figsize=(14, 10))
    topic_order = [
        'Environment',
        'Economy',
        'Society',
        'Health',
        'Policy',
        'Entertainment',
        'Culture',
        'Science',
        'Sports',
        'Politics'
    ]
    verdict_order = [
        'Supported',
        'Refuted',
        'Not Enough Evidence'
    ]
    cross_tab_topic = cross_tab_topic.reindex(
        index=topic_order,
        columns=verdict_order
    )
    sns.heatmap(
        cross_tab_topic,
        annot=True,
        fmt='d',
        cmap='YlOrRd',
        norm=LogNorm(),  # 关键：对数色阶，减少“碾压感”
        cbar_kws={'label': 'Count (Log scale)'},
        linewidths=0.5,
        linecolor='gray',
        ax=ax
    )
    ax.set_title('Topic vs Verdict Heatmap (Counts, Log-scaled)', fontsize=16, weight='bold', pad=20)
    ax.set_xlabel('Verdict', fontsize=13, weight='bold')
    ax.set_ylabel('Topic', fontsize=13, weight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.savefig('7_topic_verdict_heatmap_logcount.png', bbox_inches='tight', dpi=300)
    plt.close()
    print("✓ Topic vs Verdict 对数计数热力图已保存: 7_topic_verdict_heatmap_logcount.png")

# ========== 8. 生成统计报告 ==========
print("\n生成统计报告...")

report = f"""
{'=' * 60}
数据集标签分布统计报告
{'=' * 60}

数据集概览:
- 总样本数: {len(data)}

1. Verdict 分布:
"""

for verdict, count in verdict_count.most_common():
    percentage = (count / len(data)) * 100
    report += f"   - {verdict}: {count} ({percentage:.1f}%)\n"

report += "\n2. Error Type 分布:\n"
for error_type, count in error_type_count.most_common():
    percentage = (count / sum(error_type_count.values())) * 100
    report += f"   - {error_type}: {count} ({percentage:.1f}%)\n"

report += "\n3. Category 分布 (Top 10):\n"
for category, count in category_count.most_common(10):
    percentage = (count / sum(category_count.values())) * 100
    report += f"   - {category}: {count} ({percentage:.1f}%)\n"

report += "\n4. Topic 分布:\n"
for topic, count in topic_count.most_common():
    percentage = (count / sum(topic_count.values())) * 100
    report += f"   - {topic}: {count} ({percentage:.1f}%)\n"

report += f"\n{'=' * 60}\n"

with open('dataset_analysis_report.txt', 'w', encoding='utf-8') as f:
    f.write(report)

print(report)
print("\n✓ 所有图表已生成完成!")
print("\n生成的图表:")
print("  1. 1_verdict_distribution.png - Verdict环形图")
print("  2. 2_error_type_distribution.png - Error Type水平条形图")
print("  3. 3_category_distribution.png - Category棒棒糖图")
print("  4. 4_topic_distribution.png - Topic柱状图")
print("  5. 5_verdict_errortype_heatmap.png - Verdict vs Error Type热力图")
print("  6. 6_topic_errortype_heatmap.png - Topic vs Error Type热力图")
print("  7. 7_comprehensive_dashboard.png - 综合仪表盘")
print("  8. dataset_analysis_report.txt - 统计报告")