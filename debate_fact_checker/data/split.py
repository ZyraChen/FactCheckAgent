import json
import os


def split_json_dataset(input_filename, chunk_size=100):
    """
    读取JSON文件，并将其拆分为多个包含指定数量记录的子文件。
    """
    try:
        # 1. 读取原始数据
        with open(input_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"错误：未找到文件 '{input_filename}'。请确保文件位于当前目录下。")
        return
    except json.JSONDecodeError:
        print(f"错误：文件 '{input_filename}' 格式不是有效的 JSON。")
        return

    if not isinstance(data, list):
        print("错误：JSON文件的根元素不是一个列表（List）。")
        return

    total_items = len(data)
    num_chunks = (total_items + chunk_size - 1) // chunk_size  # 计算需要生成的文件数量

    print(f"✅ 成功读取 {input_filename}，总共 {total_items} 条数据。")
    print(f"➡️ 将拆分成 {num_chunks} 个文件，每文件 {chunk_size} 条记录。")

    # 2. 拆分数据并写入新文件
    for i in range(num_chunks):
        start_index = i * chunk_size
        end_index = min((i + 1) * chunk_size, total_items)

        # 提取当前块的数据
        chunk = data[start_index:end_index]

        # 定义输出文件名
        output_filename = f'dataset_part_{i + 1}.json'

        # 写入新的JSON文件
        try:
            with open(output_filename, 'w', encoding='utf-8') as f:
                # 使用 ensure_ascii=False 确保中文正确显示
                # 使用 indent=2 使文件格式更易于阅读
                json.dump(chunk, f, ensure_ascii=False, indent=2)
            print(f"   - 创建文件：{output_filename} (包含 {len(chunk)} 条记录)")
        except IOError as e:
            print(f"写入文件 {output_filename} 失败: {e}")

    print("\n🎉 所有文件拆分完成！")


# --- 运行函数 ---
# 确保这个文件名和您上传的文件名一致
split_json_dataset('dataset_final.json', chunk_size=100)