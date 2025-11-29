# PaperGraph JSON Schema v0.5 — 字段概览

本文档仅说明 PaperGraph v0.5 中各字段的含义，便于标注和下游消费。

## 顶层字段
- `version`: string，schema 版本号，如 "0.5"。
- `canvas`: object，画布尺寸信息：
  - `width`: number，画布宽度。
  - `height`: number，画布高度。
  - `unit`: string，可选，坐标单位，例如 "px"、"pt"。
- `layout_flow`: string，可选，整体布局方向，如 "left-to-right"、"top-to-bottom"。
- `chunks`: array，语义块列表。
- `nodes`: array，图中所有节点元素。
- `edges`: array，节点之间的连线。
- `positions`: object，布局结果（chunk/node 的 bbox 等）。
- `style_sheet`: 渲染相关设置。

## `chunks[]` 语义块
- `chunk_id`: string，语义块 ID，在文档内唯一。
- `title`: string，可选，语义块标题。
- `title_bbox`: object，可选，chunk中title在画布上的大致bbox `{ x, y, w, h }`，使用绝对坐标。
- `summary`: string，该块要表达的主要内容的自然语言概述。
- `node_ids`: string[]，属于该块的节点 ID 列表（如 ["n1","n2",...]）。
- `bbox`: object，可选，此语义块在画布上的大致bbox `{ x, y, w, h }`，使用绝对坐标。

## `nodes[]` 节点
- `node_id`: string，节点 ID，在文档内唯一，如 "n1","n2"。
- `node_type`: string，节点类型，常见枚举：
  - "text_block": 文本块（标题、正文、说明等）。
  - "shape": 模块框/流程框等形状。
  - "image_placeholder": 图片或子图占位。
  - "table_placeholder": 表格占位。
  - "annotation": 注释、备注、脚注等说明性元素。
- `chunk_id`: string，所属语义块 ID，对应某个 `chunk_id`。
- `desc`: string，可选，对该节点的自然语言描述（框内文字或简要说明）。
- `bbox`: object，可选，节点在画布中的位置与大小 `{ x, y, w, h }`，使用 `canvas.unit` 对应的绝对坐标。
- `render_method`: string，可选，该节点的渲染方式：
  - "vlm": 通过 VLM 生成图标/图像。
  - "pptx": 使用 PPTX 原生图形/文本框。
- `vlm_prompt`: string，可选，当 `render_method = "vlm"` 时，用于生成该节点资产的提示语。

## `edges[]` 边
- `edge_id`: string，边 ID，在文档内唯一，推荐如 "e1","e2"。
- `from`: string，起点节点 ID，对应某个 `node_id`。
- `to`: string，终点节点 ID，对应某个 `node_id`。

## `positions` 布局结果
- `positions.chunks`: array，可选，每个语义块的几何信息：
  - `chunk_id`: string，对应语义层中的 `chunk_id`。
  - `bbox`: object，此语义块在画布上的包围盒 `{ x, y, w, h }`。
- `positions.nodes`: array，可选，每个节点的几何信息：
  - `node_id`: string，对应语义层中的 `node_id`。
  - `bbox`: object，该节点在画布上的包围盒 `{ x, y, w, h }`。

## `style_sheet` 渲染
- `global_theme`: string，整张图的全局风格描述，如 "NeurIPS-style clean diagram with light background"。
- `node_styles`: object，从 `node_id` 到渲染配置的映射：
  - key: `node_id`（如 "n1"），value 为：
    - `render_method`: string，可选，节点渲染方式："vlm" 或 "pptx"。
    - `vlm_prompt`: string，可选，当使用 VLM 渲染时，表示该节点的vlm生图prompt。


---
## 示例（简化示意，仅展示核心字段）

```json
{
  "version": "0.5",
  "canvas": {"width": 1920, "height": 1080, "unit": "px"},
  "layout_flow": "left-to-right",

  "chunks": [
    {
      "chunk_id": "c1",
      "title": "Training Pipeline",
      "title_bbox": {"x": 672,  "y": 54, "w": 576, "h": 86},
      "summary": "Overall training pipeline for the proposed model.",
      "node_ids": ["n1", "n2", "n3", "n4", "n5"]
    }
  ],

  "nodes": [
    {
      "node_id": "n1",
      "node_type": "text_block",
      "chunk_id": "c1",
      "desc": "Training Pipeline"
    },
    {
      "node_id": "n2",
      "node_type": "shape",
      "chunk_id": "c1",
      "desc": "Raw Data"
    },
    {
      "node_id": "n3",
      "node_type": "shape",
      "chunk_id": "c1",
      "desc": "Encoder"
    },
    {
      "node_id": "n4",
      "node_type": "shape",
      "chunk_id": "c1",
      "desc": "Predictions"
    },
    {
      "node_id": "n5",
      "node_type": "annotation",
      "chunk_id": "c1",
      "desc": "We freeze encoder weights during fine-tuning."
    }
  ],

  "edges": [
    {"edge_id": "e1", "from": "n2", "to": "n3"},
    {"edge_id": "e2", "from": "n3", "to": "n4"}
  ],

  "positions": {
    "chunks": [
      {"chunk_id": "c1", "bbox": {"x": 96, "y": 36,  "w": 1728, "h": 972}}
    ],
    "nodes": [
      {"node_id": "n1", "bbox": {"x": 672,  "y": 54,  "w": 576, "h": 86}},
      {"node_id": "n2",    "bbox": {"x": 192,  "y": 324, "w": 384, "h": 129}},
      {"node_id": "n3", "bbox": {"x": 768,  "y": 324, "w": 384, "h": 129}},
      {"node_id": "n4",   "bbox": {"x": 1344, "y": 324, "w": 384, "h": 129}},
      {"node_id": "n5",  "bbox": {"x": 768,  "y": 540, "w": 576, "h": 129}}
    ]
  },

  "style_sheet": {
    "global_theme": "NeurIPS-style clean diagram with light background and minimal colors.",
    "node_styles": {
      "n1": {"render_method": "pptx"},
      "n2":    {"render_method": "vlm", "vlm_prompt": "Icon of raw dataset or CSV file."},
      "n3": {"render_method": "vlm", "vlm_prompt": "Neural network block representing encoder."},
      "n4":   {"render_method": "vlm", "vlm_prompt": "Output predictions icon."},
      "n5":  {"render_method": "pptx"}
    }
  }
}
```


---

## v0.5 相对 v0.4 的主要变化小结

- 移除：
  - `groups` 结构（及其在 `positions.groups` 中的几何信息）。
  - `Annotation` 独立类型；其语义统一收敛到 `nodes` 中的 `node_type = "annotation"`。
  - `PortHint` / `PortPose` 以及端口级别的几何信息与连线端点指定。
  - 较复杂的 `style_sheet.rules` 与细粒度 Compositor 样式字段。

- 简化：
  - `edges` 仅保留 `{ edge_id, from, to, edge_type?, metadata? }`，将几何信息交给 `positions.edges` 或前端直连。
  - 美学层仅保留若干 VLM prompt 与轻量 hints，不再要求详尽的颜色/字体/线型控制。

- 保留但弱化：
  - `chunks` 仍用于表达语义块，但不再与 `groups` 叠加，仅通过 `node.chunk_id` 建立简单关系。
  - `positions` 仍存在，主要记录 chunks/nodes 的 bbox（绝对坐标）。

- 新增/规范：
  - 明确 `node_type` 核心枚举集合：`text_block`, `shape`, `image_placeholder`, `table_placeholder`, `annotation`。
  - 推荐统一使用与 `canvas.unit` 一致的绝对坐标系，方便与 PPTX 等渲染坐标对齐。

该简化版本旨在：
- 降低标注与模型预测的任务难度（特别是从图片回推 JSON）。
- 保留论文图中最关键的结构信息（节点 + 边 + 粗粒度块 + 少量语义角色）。
- 为后续在 `paperX` 与 `workflow_design` 中的 pipeline 实现与评测提供一个稳定且易用的中间表示。