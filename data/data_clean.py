import json
import re

def remove_web_tags(text):
    """删除文本中的 [web:数字] 标记"""
    if isinstance(text, str):
        # 使用正则表达式匹配并删除所有 [web:数字] 格式的标记
        return re.sub(r'\[web:\d+\]', '', text)
    return text

def clean_json_data(data):
    """递归清理JSON数据中的所有web标记"""
    if isinstance(data, dict):
        return {key: clean_json_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [clean_json_data(item) for item in data]
    elif isinstance(data, str):
        return remove_web_tags(data)
    else:
        return data

# 读取JSON文件
with open('dataset_latest.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 清理数据
cleaned_data = clean_json_data(data)

# 保存清理后的数据
with open('dataset_latest.json', 'w', encoding='utf-8') as f:
    json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

print("清理完成！")