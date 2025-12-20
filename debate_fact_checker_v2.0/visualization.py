"""
论辩图可视化工具
读取argumentation_graph.json并生成可视化HTML
"""
import json
import sys
from pathlib import Path


def generate_html_visualization(graph_data: dict, output_path: str = "graph_visualization.html"):
    """
    生成交互式HTML可视化
    使用vis.js库绘制网络图
    """

    # 提取数据
    evidence_nodes = graph_data.get("evidence_nodes", [])
    attack_edges = graph_data.get("attack_edges", [])

    # 构建节点列表
    nodes_js = []
    for i, node in enumerate(evidence_nodes):
        node_id = node.get("id", f"node_{i}")
        agent = node.get("retrieved_by", "unknown")
        source = node.get("source", "Unknown")
        content = node.get("content", "")[:100] + "..."
        credibility = node.get("credibility", "Medium")
        quality = node.get("quality_score", 0.5)

        # 颜色:Pro=蓝色, Con=红色
        color = "#3498db" if agent == "pro" else "#e74c3c"

        # 大小:根据质量分数
        size = 20 + quality * 30

        # 标签
        label = f"{agent.upper()}\n{source[:20]}"

        # 悬停提示
        title = f"""
<b>{agent.upper()} - {source}</b><br>
可信度: {credibility}<br>
质量: {quality:.2f}<br>
内容: {content}
        """.strip()

        nodes_js.append({
            "id": node_id,
            "label": label,
            "color": color,
            "size": size,
            "title": title,
            "font": {"size": 12, "color": "white"}
        })

    # 构建边列表
    edges_js = []
    for edge in attack_edges:
        attacker = edge.get("attacker_id")
        target = edge.get("target_id")
        strength = edge.get("strength", 0.5)
        rationale = edge.get("rationale", "")

        edges_js.append({
            "from": attacker,
            "to": target,
            "arrows": "to",
            "color": {"color": "#95a5a6", "highlight": "#2c3e50"},
            "width": 1 + strength * 3,
            "title": f"攻击强度: {strength:.2f}<br>{rationale}"
        })

    # 统计信息
    stats = {
        "total_nodes": len(evidence_nodes),
        "pro_nodes": len([n for n in evidence_nodes if n.get("retrieved_by") == "pro"]),
        "con_nodes": len([n for n in evidence_nodes if n.get("retrieved_by") == "con"]),
        "total_edges": len(attack_edges),
        "avg_quality": sum(n.get("quality_score", 0) for n in evidence_nodes) / max(len(evidence_nodes), 1)
    }

    # 生成HTML
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>论辩图可视化</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        #mynetwork {{
            width: 100%;
            height: 600px;
            border: 1px solid #ddd;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .stats {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .stats h2 {{
            margin-top: 0;
            color: #2c3e50;
        }}
        .stat-item {{
            display: inline-block;
            margin-right: 30px;
            padding: 10px 15px;
            background: #ecf0f1;
            border-radius: 5px;
        }}
        .stat-label {{
            color: #7f8c8d;
            font-size: 12px;
        }}
        .stat-value {{
            color: #2c3e50;
            font-size: 24px;
            font-weight: bold;
        }}
        .legend {{
            background: white;
            padding: 15px;
            margin-top: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .legend-item {{
            display: inline-block;
            margin-right: 20px;
        }}
        .legend-color {{
            display: inline-block;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            vertical-align: middle;
            margin-right: 5px;
        }}
    </style>
</head>
<body>
    <div class="stats">
        <h2>📊 论辩图统计</h2>
        <div class="stat-item">
            <div class="stat-label">总证据节点</div>
            <div class="stat-value">{stats['total_nodes']}</div>
        </div>
        <div class="stat-item" style="background: #d4e6f1;">
            <div class="stat-label">正方证据</div>
            <div class="stat-value" style="color: #3498db;">{stats['pro_nodes']}</div>
        </div>
        <div class="stat-item" style="background: #fadbd8;">
            <div class="stat-label">反方证据</div>
            <div class="stat-value" style="color: #e74c3c;">{stats['con_nodes']}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">攻击边</div>
            <div class="stat-value">{stats['total_edges']}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">平均质量</div>
            <div class="stat-value">{stats['avg_quality']:.2f}</div>
        </div>
    </div>

    <div id="mynetwork"></div>

    <div class="legend">
        <h3>图例</h3>
        <div class="legend-item">
            <span class="legend-color" style="background: #3498db;"></span>
            <span>正方证据 (Pro)</span>
        </div>
        <div class="legend-item">
            <span class="legend-color" style="background: #e74c3c;"></span>
            <span>反方证据 (Con)</span>
        </div>
        <div class="legend-item">
            <span>节点大小 = 质量分数</span>
        </div>
        <div class="legend-item">
            <span>边宽度 = 攻击强度</span>
        </div>
        <div class="legend-item">
            <span>鼠标悬停查看详情</span>
        </div>
    </div>

    <script type="text/javascript">
        // 创建节点和边的数据
        var nodes = new vis.DataSet({json.dumps(nodes_js, ensure_ascii=False)});
        var edges = new vis.DataSet({json.dumps(edges_js, ensure_ascii=False)});

        // 创建网络
        var container = document.getElementById('mynetwork');
        var data = {{
            nodes: nodes,
            edges: edges
        }};

        var options = {{
            physics: {{
                enabled: true,
                barnesHut: {{
                    gravitationalConstant: -8000,
                    centralGravity: 0.3,
                    springLength: 150,
                    springConstant: 0.04,
                    damping: 0.09
                }},
                stabilization: {{
                    iterations: 200
                }}
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 100
            }},
            nodes: {{
                shape: 'dot',
                font: {{
                    size: 12,
                    color: 'white'
                }},
                borderWidth: 2,
                borderWidthSelected: 4
            }},
            edges: {{
                smooth: {{
                    type: 'continuous',
                    roundness: 0.5
                }}
            }}
        }};

        var network = new vis.Network(container, data, options);

        // 点击节点显示详细信息
        network.on("click", function(params) {{
            if (params.nodes.length > 0) {{
                var nodeId = params.nodes[0];
                var node = nodes.get(nodeId);
                alert("节点详情:\\n" + node.title.replace(/<br>/g, "\\n").replace(/<b>|<\\/b>/g, ""));
            }}
        }});
    </script>
</body>
</html>
    """

    # 保存HTML
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ 可视化已生成: {output_path}")
    print(f"📊 统计信息:")
    print(f"   - 总节点: {stats['total_nodes']} (Pro: {stats['pro_nodes']}, Con: {stats['con_nodes']})")
    print(f"   - 攻击边: {stats['total_edges']}")
    print(f"   - 平均质量: {stats['avg_quality']:.2f}")

    return output_path


def print_text_summary(graph_data: dict):
    """打印文本格式的论辩图摘要"""
    evidence_nodes = graph_data.get("evidence_nodes", [])
    attack_edges = graph_data.get("attack_edges", [])

    print("\n" + "=" * 80)
    print("论辩图结构")
    print("=" * 80)

    # 按轮次和Agent分组
    pro_nodes = [n for n in evidence_nodes if n.get("retrieved_by") == "pro"]
    con_nodes = [n for n in evidence_nodes if n.get("retrieved_by") == "con"]

    print(f"\n【正方证据】共 {len(pro_nodes)} 个")
    for i, node in enumerate(pro_nodes, 1):
        print(f"\n{i}. ID: {node.get('id')}")
        print(f"   来源: {node.get('source')}")
        print(f"   可信度: {node.get('credibility')} | 质量: {node.get('quality_score', 0):.2f}")
        print(f"   内容: {node.get('content', '')[:150]}...")

    print(f"\n{'=' * 80}")
    print(f"【反方证据】共 {len(con_nodes)} 个")
    for i, node in enumerate(con_nodes, 1):
        print(f"\n{i}. ID: {node.get('id')}")
        print(f"   来源: {node.get('source')}")
        print(f"   可信度: {node.get('credibility')} | 质量: {node.get('quality_score', 0):.2f}")
        print(f"   内容: {node.get('content', '')[:150]}...")

    print(f"\n{'=' * 80}")
    print(f"【攻击关系】共 {len(attack_edges)} 条")
    for i, edge in enumerate(attack_edges, 1):
        attacker_id = edge.get('attacker_id')
        target_id = edge.get('target_id')
        strength = edge.get('strength', 0)
        rationale = edge.get('rationale', '')

        print(f"\n{i}. {attacker_id} → {target_id}")
        print(f"   强度: {strength:.2f}")
        print(f"   理由: {rationale}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    # 使用示例
    if len(sys.argv) > 1:
        graph_file = sys.argv[1]
    else:
        graph_file = "output/argumentation_graph.json"

    if not Path(graph_file).exists():
        print(f"❌ 文件不存在: {graph_file}")
        print(f"使用方法: python visualize_graph.py [graph.json路径]")
        sys.exit(1)

    print(f"📂 读取论辩图: {graph_file}")

    with open(graph_file, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    # 打印文本摘要
    print_text_summary(graph_data)

    # 生成HTML可视化
    html_file = graph_file.replace(".json", ".html")
    generate_html_visualization(graph_data, html_file)

    print(f"\n✨ 完成! 在浏览器中打开 {html_file} 查看交互式可视化")