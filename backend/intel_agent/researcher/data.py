"""Bounded CSV input; no uploaded code or pickle is ever loaded."""
from __future__ import annotations

import csv
import io
from pathlib import Path

import numpy as np

MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS = 10_000
MAX_COLUMNS = 101
LABEL_NAMES = {"label", "target", "y", "anomaly", "is_anomaly", "class"}


def parse_csv(content: bytes):
    if len(content) > MAX_BYTES:
        raise ValueError("CSV 文件不能超过 8 MiB")
    try:
        text = content.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(text)))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValueError("请上传 UTF-8 编码、逗号分隔且带表头的 CSV") from exc
    if not rows:
        raise ValueError("CSV 为空")
    columns = [name.strip() for name in rows[0]]
    if (not all(columns) or len(columns) != len(set(columns))
            or any(len(name) > 200 for name in columns)):
        raise ValueError("CSV 列名须非空、唯一且不超过 200 字符")
    if len(columns) > MAX_COLUMNS:
        raise ValueError("第一版最多支持 100 个特征和 1 个标签列")
    values = [row for row in rows[1:] if any(cell.strip() for cell in row)]
    if not 30 <= len(values) <= MAX_ROWS:
        raise ValueError("CSV 需包含 30 至 10,000 行数据")
    if any(len(row) != len(columns) for row in values):
        raise ValueError("CSV 存在与表头列数不一致的数据行")
    numeric = {}
    for index, name in enumerate(columns):
        try:
            array = np.array([float(row[index]) if row[index].strip() else np.nan
                              for row in values], dtype=float)
        except ValueError:
            continue
        if np.isinf(array).any():
            raise ValueError(f"列 {name} 包含无穷值，请先处理")
        if not np.isnan(array).all():
            numeric[name] = array
    if not numeric:
        raise ValueError("CSV 至少需要一个可用的数值特征列")
    return columns, values, numeric


def describe(content: bytes, dataset_id: str, name: str):
    columns, values, numeric = parse_csv(content)
    suggestion = next((name for name in columns
                       if name.lower() in LABEL_NAMES
                       and name in numeric and set(numeric[name]) == {0.0, 1.0}), None)
    return {"dataset_id": dataset_id, "name": name, "rows": len(values),
            "columns": columns, "numeric_columns": list(numeric),
            "suggested_label": suggestion}


def load_dataset(path: Path, label_column: str | None):
    columns, _, numeric = parse_csv(path.read_bytes())
    label_column = label_column or None
    y = None
    if label_column:
        if label_column not in numeric:
            raise ValueError("标签列不存在或不是数值列；标签须为 0（正常）和 1（异常）")
        labels = numeric[label_column]
        if not np.isfinite(labels).all() or set(labels) != {0.0, 1.0}:
            raise ValueError("标签须同时包含 0（正常）和 1（异常），且不能缺失")
        y = labels.astype(int)
        if min(np.bincount(y)) < 5:
            raise ValueError("每类至少需要 5 条标签，才能分开训练、验证和最终测试")
    # Even when labels are withheld, conventional label fields must not become predictors.
    features = [name for name in numeric if name != label_column and name.lower() not in LABEL_NAMES]
    if not features or len(features) > 100:
        raise ValueError("移除标签后需要 1 至 100 个数值特征")
    ignored = [name for name in columns if name not in features and name != label_column]
    return np.column_stack([numeric[name] for name in features]), y, features, ignored


def demo_csv() -> bytes:
    rng = np.random.default_rng(42)
    X = np.vstack([rng.normal(size=(270, 6)), rng.normal(3, 1.5, size=(30, 6))])
    y = np.r_[np.zeros(270, dtype=int), np.ones(30, dtype=int)]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([f"feature_{i + 1}" for i in range(6)] + ["label"])
    for index in rng.permutation(len(y)):
        writer.writerow([*np.round(X[index], 6), int(y[index])])
    return buffer.getvalue().encode("utf-8")
