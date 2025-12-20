#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改进版数据集可视化 - 处理不均匀分布
"""

import json
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from collections import Counter
import pandas as pd
import warnings

warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False
sns.set_style("whitegrid")
plt.rcParams['figure.dpi'] = 300

# 读取数据
with open('../data/dataset_latest.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"数据集总条数: {len(data)}\n")

# ============ 1. 改进的 Verdict 分布 - 使用百分比标注的条形图 ============
print("绘制改进的 Verdict 分布图...")

verdict_count = Counter([item['verdict'] for item in data])
verdict_df = pd.DataFrame(verdict_count.items(), columns=['Verdict', 'Count'])
verdict_df = verdict_df.sort_values('Count', ascending=False)
verdict_df['Percentage'] = (verdict_df['Count'] / len(data) * 100).round(1)

fig, ax = plt.subplots(figsize=(10, 6))
colors = ['#E74C3C', '#3498DB', '#95A5A6']
bars = ax.bar(verdict_df['Verdict'], verdict_df['Count'], color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)

# 添加百分比和数值标签
for bar, count, pct in zip(bars, verdict_df['Count'], verdict_df['Percentage']):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width() / 2., height + 5,
            f'{count}\n({pct}%)', ha='center', va='bottom', fontsize=12, weight='bold')

ax.set_ylabel('Count', fontsize=13, weight='bold')
ax.set_title('Claim Verdict Distribution', fontsize=16, weight='bold', pad=20)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.grid(axis='y', alpha=0.3, linestyle='--')
plt.tight_layout()
plt.savefig('improved_1_verdict_distribution.png', dpi=300, bbox_inches='tight')
plt.close()
print("✓ 改进的 Verdict 分布图已保存")

# ============ 2. 改进的 Error Type - 使用对数刻度 ============
print("绘制改进的 Error Type 分布图...")

error_type_count = Counter([item['error_type'] for item in data if item['error_type'] is not None])
error_df = pd.DataFrame(error_type_count.items(), columns=['Error Type', 'Count'])
error_df = error_df.sort_values('Count', ascending=True)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

# 左图：普通刻度
colors_grad = plt.cm.RdYlBu_r(np.linspace(0.3, 0.9, len(error_df)))
bars1 = ax1.barh(error_df['Error Type'], error_df['Count'], color=colors_grad, edgecolor='black', linewidth=0.7)
for i, (bar, count) in enumerate(zip(bars1, error_df['Count'])):
    ax1.text(count + 3, i, f'{count}', va='center', ha='left', fontsize=10, weight='bold')
ax1.set_xlabel('Frequency (Linear Scale)', fontsize=12, weight='bold')
ax1.set_title('Error Type Distribution - Linear Scale', fontsize=14, weight='bold')
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)
ax1.grid(axis='x', alpha=0.3, linestyle='--')

# 右图：对数刻度
bars2 = ax2.barh(error_df['Error Type'], error_df['Count'], color=colors_grad, edgecolor='black', linewidth=0.7)
for i, (bar, count) in enumerate(zip(bars2, error_df['Count'])):
    ax2.text(count * 1.15, i, f'{count}', va='center', ha='left', fontsize=10, weight='bold')
ax2.set_xlabel('Frequency (Log Scale)', fontsize=12, weight='bold')
ax2.set_xscale('log')
ax2.set_title('Error Type Distribution - Log Scale', fontsize=14, weight='bold')
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)
ax2.grid(axis='x', alpha=0.3, linestyle='--', which='both')

plt.tight_layout()
plt.savefig('improved_2_error_type_comparison.png', dpi=300, bbox_inches='tight')
plt.close()
print("✓ 改进的 Error Type 对比图已保存")

# ============ 3. 改进的 Category - 分组展示 ============
print("绘制改进的 Category 分布图...")

category_count = Counter([item['category'] for item in data if item['category'] is not None])
category_df = pd.DataFrame(category_count.items(), columns=['Category', 'Count'])
category_df = category_df.sort_values('Count', ascending=False)

# 分为高频、中频、低频三组
high_freq = category_df[category_df['Count'] >= 20]
mid_freq = category_df[(category_df['Count'] >= 10) & (category_df['Count'] < 20)]
low_freq = category_df[category_df['Count'] < 10]

fig, axes = plt.subplots(3, 1, figsize=(14, 12))

# 高频类别
if not high_freq.empty:
    colors_high = plt.cm.Reds(np.linspace(0.5, 0.9, len(high_freq)))
    bars_high = axes[0].barh(high_freq['Category'], high_freq['Count'], color=colors_high, edgecolor='black',
                             linewidth=1)
    for i, (bar, count) in enumerate(zip(bars_high, high_freq['Count'])):
        axes[0].text(count + 2, i, f'{count}', va='center', ha='left', fontsize=11, weight='bold')
    axes[0].set_title('High-Frequency Categories (≥20)', fontsize=13, weight='bold')
    axes[0].set_xlabel('Count', fontsize=11, weight='bold')
    axes[0].spines['top'].set_visible(False)
    axes[0].spines['right'].set_visible(False)
    axes[0].grid(axis='x', alpha=0.3)

# 中频类别
if not mid_freq.empty:
    colors_mid = plt.cm.YlOrBr(np.linspace(0.4, 0.8, len(mid_freq)))
    bars_mid = axes[1].barh(mid_freq['Category'], mid_freq['Count'], color=colors_mid, edgecolor='black', linewidth=1)
    for i, (bar, count) in enumerate(zip(bars_mid, mid_freq['Count'])):
        axes[1].text(count + 0.5, i, f'{count}', va='center', ha='left', fontsize=10, weight='bold')
    axes[1].set_title('Medium-Frequency Categories (10-19)', fontsize=13, weight='bold')
    axes[1].set_xlabel('Count', fontsize=11, weight='bold')
    axes[1].spines['top'].set_visible(False)
    axes[1].spines['right'].set_visible(False)
    axes[1].grid(axis='x', alpha=0.3)

# 低频类别
if not low_freq.empty:
    colors_low = plt.cm.Blues(np.linspace(0.4, 0.8, len(low_freq)))
    bars_low = axes[2].barh(low_freq['Category'], low_freq['Count'], color=colors_low, edgecolor='black', linewidth=1)
    for i, (bar, count) in enumerate(zip(bars_low, low_freq['Count'])):
        axes[2].text(count + 0.3, i, f'{count}', va='center', ha='left', fontsize=9)
    axes[2].set_title('Low-Frequency Categories (<10)', fontsize=13, weight='bold')
    axes[2].set_xlabel('Count', fontsize=11, weight='bold')
    axes[2].spines['top'].set_visible(False)
    axes[2].spines['right'].set_visible(False)
    axes[2].grid(axis='x', alpha=0.3)

plt.tight_layout()
plt.savefig('improved_3_category_grouped.png', dpi=300, bbox_inches='tight')
plt.close()
print("✓ 改进的 Category 分组图已保存")

# ============ 4. 改进的 Topic - 使用百分比堆叠 ============
print("绘制改进的 Topic 分布图...")

topic_count = Counter([item['topic'] for item in data if item['topic'] is not None])
topic_df = pd.DataFrame(topic_count.items(), columns=['Topic', 'Count'])
topic_df = topic_df.sort_values('Count', ascending=False)
topic_df['Percentage'] = (topic_df['Count'] / topic_df['Count'].sum() * 100).round(1)
topic_df['Cumulative'] = topic_df['Percentage'].cumsum()

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

# 左图：条形图 + 百分比
colors_topic = plt.cm.Spectral(np.linspace(0.2, 0.9, len(topic_df)))
bars = ax1.bar(range(len(topic_df)), topic_df['Count'], color=colors_topic, alpha=0.8, edgecolor='black', linewidth=1.2)
ax1.set_xticks(range(len(topic_df)))
ax1.set_xticklabels(topic_df['Topic'], rotation=45, ha='right')
for i, (bar, count, pct) in enumerate(zip(bars, topic_df['Count'], topic_df['Percentage'])):
    height = bar.get_height()
    ax1.text(i, height + 3, f'{count}\n({pct}%)', ha='center', va='bottom', fontsize=9, weight='bold')
ax1.set_ylabel('Count', fontsize=12, weight='bold')
ax1.set_title('Topic Distribution with Percentages', fontsize=14, weight='bold')
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)
ax1.grid(axis='y', alpha=0.3)

# 右图：累积百分比曲线
ax2_twin = ax2.twinx()
bars2 = ax2.bar(range(len(topic_df)), topic_df['Percentage'], color=colors_topic, alpha=0.6, edgecolor='black',
                linewidth=1)
line = ax2_twin.plot(range(len(topic_df)), topic_df['Cumulative'], 'o-', color='red', linewidth=3, markersize=8,
                     label='Cumulative %')
ax2.set_xticks(range(len(topic_df)))
ax2.set_xticklabels(topic_df['Topic'], rotation=45, ha='right')
ax2.set_ylabel('Percentage (%)', fontsize=12, weight='bold', color='black')
ax2_twin.set_ylabel('Cumulative Percentage (%)', fontsize=12, weight='bold', color='red')
ax2.set_title('Topic Distribution - Pareto Analysis', fontsize=14, weight='bold')
ax2_twin.legend(loc='upper left')
ax2.spines['top'].set_visible(False)
ax2_twin.spines['top'].set_visible(False)
ax2.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('improved_4_topic_pareto.png', dpi=300, bbox_inches='tight')
plt.close()
print("✓ 改进的 Topic 帕累托图已保存")

# ============ 5. 改进的热力图 - 使用标准化 ============
print("绘制改进的热力图...")

# Verdict vs Error Type - 带标准化版本
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

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

    # 原始计数
    sns.heatmap(cross_tab, annot=True, fmt='d', cmap='YlOrRd',
                cbar_kws={'label': 'Count'}, linewidths=0.5, linecolor='gray',
                ax=ax1, square=False)
    ax1.set_title('Verdict vs Error Type - Absolute Count', fontsize=14, weight='bold')
    ax1.set_xlabel('Verdict', fontsize=12, weight='bold')
    ax1.set_ylabel('Error Type', fontsize=12, weight='bold')
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # 行标准化（每种错误类型的百分比分布）
    cross_tab_norm = cross_tab.div(cross_tab.sum(axis=1), axis=0) * 100
    sns.heatmap(cross_tab_norm, annot=True, fmt='.1f', cmap='RdYlBu_r',
                cbar_kws={'label': 'Percentage (%)'}, linewidths=0.5, linecolor='gray',
                ax=ax2, square=False, vmin=0, vmax=100)
    ax2.set_title('Verdict vs Error Type - Row-Normalized (%)', fontsize=14, weight='bold')
    ax2.set_xlabel('Verdict', fontsize=12, weight='bold')
    ax2.set_ylabel('Error Type', fontsize=12, weight='bold')
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.tight_layout()
    plt.savefig('improved_5_verdict_error_heatmap.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ 改进的 Verdict vs Error Type 热力图已保存")

# ============ 6. 改进的 Topic vs Error Type 热力图 - 分块显示 ============
print("绘制改进的 Topic vs Error Type 热力图...")

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

    # 使用对数标准化来处理极端值
    cross_tab_log = np.log1p(cross_tab_topic)  # log(x+1) 避免log(0)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 10))

    # 原始数据
    sns.heatmap(cross_tab_topic, annot=True, fmt='d', cmap='YlOrRd',
                cbar_kws={'label': 'Count'}, linewidths=0.5, linecolor='gray',
                ax=ax1)
    ax1.set_title('Topic vs Error Type - Raw Count', fontsize=14, weight='bold')
    ax1.set_xlabel('Error Type', fontsize=12, weight='bold')
    ax1.set_ylabel('Topic', fontsize=12, weight='bold')
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # 对数变换
    sns.heatmap(cross_tab_log, annot=cross_tab_topic.values, fmt='d', cmap='viridis',
                cbar_kws={'label': 'log(Count+1)'}, linewidths=0.5, linecolor='gray',
                ax=ax2)
    ax2.set_title('Topic vs Error Type - Log-Transformed', fontsize=14, weight='bold')
    ax2.set_xlabel('Error Type', fontsize=12, weight='bold')
    ax2.set_ylabel('Topic', fontsize=12, weight='bold')
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.tight_layout()
    plt.savefig('improved_6_topic_error_heatmap.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ 改进的 Topic vs Error Type 热力图已保存")

# ============ 6. 改进的 Topic vs verdict 热力图 - 分块显示 ============
print("绘制改进的 Topic vs verdict 热力图...")

topic_verdict_data = []
for item in data:
    if item['verdict'] is not None and item['topic'] is not None:
        topic_verdict_data.append({
            'topic': item['topic'],
            'verdict': item['verdict']
        })

if topic_verdict_data:
    df_topic_verdict = pd.DataFrame(topic_verdict_data)
    cross_tab_topic = pd.crosstab(df_topic_verdict['topic'], df_topic_verdict['verdict'])

    # 使用对数标准化来处理极端值
    cross_tab_log = np.log1p(cross_tab_topic)  # log(x+1) 避免log(0)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 10))

    # 原始数据
    sns.heatmap(cross_tab_topic, annot=True, fmt='d', cmap='YlOrRd',
                cbar_kws={'label': 'Count'}, linewidths=0.5, linecolor='gray',
                ax=ax1)
    ax1.set_title('Topic vs Verdict - Raw Count', fontsize=14, weight='bold')
    ax1.set_xlabel('Verdict', fontsize=12, weight='bold')
    ax1.set_ylabel('Topic', fontsize=12, weight='bold')
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # 对数变换
    sns.heatmap(cross_tab_log, annot=cross_tab_topic.values, fmt='d', cmap='viridis',
                cbar_kws={'label': 'log(Count+1)'}, linewidths=0.5, linecolor='gray',
                ax=ax2)
    ax2.set_title('Topic vs Verdict - Log-Transformed', fontsize=14, weight='bold')
    ax2.set_xlabel('Verdict', fontsize=12, weight='bold')
    ax2.set_ylabel('Topic', fontsize=12, weight='bold')
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.tight_layout()
    plt.savefig('improved_7_topic_verdict_heatmap.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ 改进的 Topic vs Verdict 热力图已保存")

# ============ 7. 数据分布均匀性分析报告 ============
print("生成数据分布分析报告...")

from scipy.stats import entropy


def calculate_uniformity(counts):
    """计算分布均匀性（使用Shannon熵）"""
    total = sum(counts.values())
    probs = np.array([c / total for c in counts.values()])
    max_entropy = np.log(len(counts))
    actual_entropy = entropy(probs)
    uniformity = actual_entropy / max_entropy if max_entropy > 0 else 0
    return uniformity, actual_entropy, max_entropy


# 计算各标签的均匀性
verdict_uniformity, v_ent, v_max = calculate_uniformity(verdict_count)
error_uniformity, e_ent, e_max = calculate_uniformity(error_type_count)
category_uniformity, c_ent, c_max = calculate_uniformity(category_count)
topic_uniformity, t_ent, t_max = calculate_uniformity(topic_count)

report = f"""
{'=' * 70}
数据分布均匀性分析报告
{'=' * 70}

数据集总量: {len(data)} 条

一、分布均匀性评分 (0-1, 1为完全均匀)
{'─' * 70}
1. Verdict 分布:      {verdict_uniformity:.3f} (熵: {v_ent:.3f} / 最大熵: {v_max:.3f})
2. Error Type 分布:   {error_uniformity:.3f} (熵: {e_ent:.3f} / 最大熵: {e_max:.3f})
3. Category 分布:     {category_uniformity:.3f} (熵: {c_ent:.3f} / 最大熵: {c_max:.3f})
4. Topic 分布:        {topic_uniformity:.3f} (熵: {t_ent:.3f} / 最大熵: {t_max:.3f})

评分说明:
- 0.8-1.0: 分布均匀
- 0.6-0.8: 较为均匀
- 0.4-0.6: 不够均匀
- 0.0-0.4: 严重不均匀

二、不均匀性问题分析
{'─' * 70}

1. Verdict 分布 ({'较为均匀' if verdict_uniformity > 0.6 else '不够均匀' if verdict_uniformity > 0.4 else '严重不均匀'}):
"""

for verdict, count in verdict_count.most_common():
    pct = count / len(data) * 100
    report += f"   - {verdict}: {count} ({pct:.1f}%)\n"

report += f"\n2. Error Type 分布 ({'较为均匀' if error_uniformity > 0.6 else '不够均匀' if error_uniformity > 0.4 else '严重不均匀'}):\n"
max_error = max(error_type_count.values())
min_error = min(error_type_count.values())
report += f"   最大/最小比例: {max_error}/{min_error} = {max_error / min_error:.1f}:1\n"
for error_type, count in error_type_count.most_common():
    pct = count / sum(error_type_count.values()) * 100
    report += f"   - {error_type}: {count} ({pct:.1f}%)\n"

report += f"\n3. Category 分布 ({'较为均匀' if category_uniformity > 0.6 else '不够均匀' if category_uniformity > 0.4 else '严重不均匀'}):\n"
max_cat = max(category_count.values())
min_cat = min(category_count.values())
report += f"   最大/最小比例: {max_cat}/{min_cat} = {max_cat / min_cat:.1f}:1\n"
report += f"   Top 5 类别:\n"
for category, count in category_count.most_common(5):
    pct = count / sum(category_count.values()) * 100
    report += f"   - {category}: {count} ({pct:.1f}%)\n"

report += f"\n4. Topic 分布 ({'较为均匀' if topic_uniformity > 0.6 else '不够均匀' if topic_uniformity > 0.4 else '严重不均匀'}):\n"
max_topic = max(topic_count.values())
min_topic = min(topic_count.values())
report += f"   最大/最小比例: {max_topic}/{min_topic} = {max_topic / min_topic:.1f}:1\n"
for topic, count in topic_count.most_common():
    pct = count / sum(topic_count.values()) * 100
    report += f"   - {topic}: {count} ({pct:.1f}%)\n"

report += f"""
三、建议
{'─' * 70}
"""

suggestions = []

if verdict_uniformity < 0.6:
    suggestions.append("✓ Verdict: 考虑增加少数类别的样本或使用重采样技术")
if error_uniformity < 0.6:
    suggestions.append("✓ Error Type: 数据集在某些错误类型上样本不足，建议扩充")
if category_uniformity < 0.5:
    suggestions.append("✓ Category: 存在严重的长尾分布，建议合并低频类别或重新设计分类体系")
if topic_uniformity < 0.6:
    suggestions.append("✓ Topic: 主题分布不均衡，可能影响模型的泛化能力")

if max_error / min_error > 5:
    suggestions.append(f"✓ Error Type 类别间差异过大（{max_error / min_error:.1f}:1），建议使用类别加权或SMOTE")
if max_topic / min_topic > 5:
    suggestions.append(f"✓ Topic 类别间差异过大（{max_topic / min_topic:.1f}:1），考虑分层采样")

if suggestions:
    for sugg in suggestions:
        report += sugg + "\n"
else:
    report += "✓ 数据分布相对均衡，可直接用于模型训练\n"

report += f"\n{'=' * 70}\n"

with open('distribution_analysis_report.txt', 'w', encoding='utf-8') as f:
    f.write(report)

print(report)

print("\n✅ 所有改进图表已生成!")
print("\n生成的文件:")
print("  1. improved_1_verdict_distribution.png - 带百分比的Verdict分布")
print("  2. improved_2_error_type_comparison.png - Error Type线性/对数对比")
print("  3. improved_3_category_grouped.png - Category分组展示")
print("  4. improved_4_topic_pareto.png - Topic帕累托分析")
print("  5. improved_5_verdict_error_heatmap.png - 标准化热力图")
print("  6. improved_6_topic_error_heatmap.png - 对数变换热力图")
print("  7. distribution_analysis_report.txt - 数据分布均匀性分析报告")