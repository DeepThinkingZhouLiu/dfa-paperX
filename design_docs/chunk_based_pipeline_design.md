# Chunk-Based Paper2Graph Pipeline 设计文档

## 1. Pipeline 概览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Chunk-Based P2G Pipeline (MVP)                        │
└─────────────────────────────────────────────────────────────────────────────┘

    用户输入 (target: 论文方法描述/摘要)
                    │
                    ▼
    ┌───────────────────────────────────┐
    │   semantic_constructor_agent      │  合并了 target_analysis
    │   (语义构建 + 意图分析)            │
    └───────────────────────────────────┘
                    │
                    │ semantic_json (chunks, nodes, edges)
                    ▼
    ┌───────────────────────────────────┐
    │   chunk_layout_constructor_agent  │
    │   (全局布局 + chunk内部布局)       │
    └───────────────────────────────────┘
                    │
                    │ chunk_layout_json (bbox + internal_layout)
                    ▼
    ┌───────────────────────────────────┐
    │   chunk_vlm_design_agent          │
    │   (为每个chunk生成VLM prompt)      │
    └───────────────────────────────────┘
                    │
                    │ chunk_vlm_designs (chunk_id -> vlm_prompt)
                    ▼
    ┌───────────────────────────────────┐
    │   chunk_render_agent              │
    │   (并行调用VLM渲染各chunk)         │
    └───────────────────────────────────┘
                    │
                    │ chunk_images (chunk_id -> image_path)
                    ▼
    ┌───────────────────────────────────┐
    │   pptx_composer_agent             │
    │   (组装PPTX + SAM提取nodes)        │
    └───────────────────────────────────┘
                    │
                    ▼
    最终输出: PPTX 文件 (可编辑，nodes已分离)
```

---

## 2. State 扩展字段

在 `Paper2GraphState` 中新增以下字段：

```python
# ==================== Chunk-Based Pipeline 新增字段 ====================

# semantic_constructor_agent 输出
# semantic_json 已存在，复用

# chunk_layout_constructor_agent 输出
chunk_layout_json: Dict[str, Any] = field(default_factory=dict)
# 结构:
# {
#   "canvas": {"width": 1920, "height": 1080},
#   "chunks": [
#     {
#       "chunk_id": "c1",
#       "bbox": {"x": 100, "y": 50, "w": 600, "h": 400},
#       "internal_layout": {
#         "flow_direction": "left_to_right",
#         "nodes": [
#           {"node_id": "n1", "rel_bbox": {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.2}}
#         ]
#       }
#     }
#   ],
#   "inter_chunk_connectors": [
#     {"from_chunk": "c1", "to_chunk": "c2", "type": "arrow"}
#   ]
# }

# chunk_vlm_design_agent 输出
chunk_vlm_designs: Dict[str, Any] = field(default_factory=dict)
# 结构:
# {
#   "c1": {
#     "prompt": "...",
#     "style_config": {...},
#     "expected_elements": ["n1", "n2", ...]
#   }
# }

# chunk_render_agent 输出
chunk_images: Dict[str, Any] = field(default_factory=dict)
# 结构:
# {
#   "c1": {
#     "path": "/path/to/c1.png",
#     "bbox": {"x": 100, "y": 50, "w": 600, "h": 400}
#   }
# }

# pptx_composer_agent 输出 (SAM 提取结果)
extracted_nodes: Dict[str, Any] = field(default_factory=dict)
# 结构:
# {
#   "n1": {
#     "chunk_id": "c1",
#     "bbox_in_chunk": {"x": 50, "y": 30, "w": 150, "h": 80},
#     "bbox_in_canvas": {"x": 150, "y": 80, "w": 150, "h": 80},
#     "mask_path": "/path/to/n1_mask.png",
#     "cropped_path": "/path/to/n1_cropped.png"
#   }
# }
```

---

## 3. 各 Agent 详细设计

### 3.1 semantic_constructor_agent

**职责**: 理解用户意图 + 构建语义结构（合并原 target_analysis 和 semantic_constructor）

**输入**:
- `state.request.target`: 用户的论文方法描述

**输出**:
- `state.semantic_json`: 语义结构

**输出 Schema**:
```json
{
  "title": "Figure title",
  "abstract": "Brief description of the entire figure",
  "chunks": [
    {
      "chunk_id": "c1",
      "title": "Chunk title",
      "summary": "What this chunk represents",
      "semantic_role": "introduction|data_flow|process|branch|output|auxiliary",
      "node_ids": ["n1", "n2", "n3"]
    }
  ],
  "nodes": [
    {
      "node_id": "n1",
      "chunk_id": "c1",
      "node_type": "module|dataset|text_block|annotation|connector|icon",
      "desc": "Detailed description of this element",
      "visual_hint": "rounded_rect|circle|arrow|text|icon"
    }
  ],
  "edges": [
    {
      "edge_id": "e1",
      "from": "n1",
      "to": "n2",
      "edge_type": "data_flow|reference|contains",
      "cross_chunk": false
    }
  ],
  "inter_chunk_relations": [
    {
      "from_chunk": "c1",
      "to_chunk": "c2",
      "relation_type": "sequence|branch|merge",
      "connector_hint": "arrow|dashed_arrow|none"
    }
  ]
}
```

**Chunk 划分原则**:
1. 每个 chunk 是一个"视觉完整"的子图（有明确边界和主题）
2. chunk 数量控制在 **4-6 个**（简单图 3-4，复杂图 5-6）
3. 每个 chunk 包含 **3-8 个 nodes**
4. 线性流程尽量合并为一个 chunk
5. 并行分支分开为不同 chunks
6. 辅助内容（图例、全局注释）单独成 chunk 或标记为 `auxiliary`

---

### 3.2 chunk_layout_constructor_agent

**职责**: 规划全局布局 + chunk 内部元素布局

**输入**:
- `state.semantic_json`: 语义结构

**输出**:
- `state.chunk_layout_json`: 布局信息

**输出 Schema**:
```json
{
  "canvas": {
    "width": 1920,
    "height": 1080,
    "background": "white"
  },
  "global_style": {
    "theme": "scientific_diagram",
    "color_palette": {
      "primary": "#4A90D9",
      "secondary": "#66c2a5",
      "accent": "#fc8d62",
      "neutral": "#808080"
    },
    "font_family": "Arial, sans-serif"
  },
  "chunks": [
    {
      "chunk_id": "c1",
      "bbox": {
        "x": 100,
        "y": 50,
        "w": 600,
        "h": 400
      },
      "internal_layout": {
        "flow_direction": "left_to_right|top_to_bottom|radial",
        "alignment": "center|start|end",
        "nodes": [
          {
            "node_id": "n1",
            "rel_bbox": {
              "x": 0.05,
              "y": 0.1,
              "w": 0.25,
              "h": 0.3
            },
            "z_index": 1
          }
        ]
      }
    }
  ],
  "inter_chunk_connectors": [
    {
      "id": "conn_c1_c2",
      "from_chunk": "c1",
      "to_chunk": "c2",
      "from_anchor": "right",
      "to_anchor": "left",
      "type": "arrow",
      "style": "solid",
      "label": ""
    }
  ]
}
```

**布局约束**:
1. chunks 之间不能重叠
2. 相邻 chunks 间距 >= 20px
3. chunk 内部 nodes 使用归一化坐标 (0~1)
4. nodes 之间间距 >= 0.03 (归一化)
5. 整体利用率目标: 50%~75%

---

### 3.3 chunk_vlm_design_agent

**职责**: 为每个 chunk 生成完整的 VLM 绘图 prompt

**输入**:
- `state.semantic_json`: 语义结构
- `state.chunk_layout_json`: 布局信息

**输出**:
- `state.chunk_vlm_designs`: VLM prompt 设计

**输出 Schema**:
```json
{
  "c1": {
    "prompt": "Create a scientific diagram illustration...",
    "canvas_size": {
      "width": 600,
      "height": 400
    },
    "style_config": {
      "theme": "scientific_diagram",
      "color_scheme": "professional_blue",
      "background": "white"
    },
    "elements": [
      {
        "node_id": "n1",
        "description": "A rounded rectangle module labeled 'LLM Policy'",
        "position_hint": "left-center",
        "size_hint": "medium",
        "style_hint": "module_box with calm_blue fill"
      }
    ],
    "internal_connections": [
      {
        "from": "n1",
        "to": "n2",
        "type": "arrow",
        "label": ""
      }
    ],
    "composition_notes": "Arrange elements in a left-to-right flow..."
  }
}
```

**Prompt 生成原则**:
1. 明确 canvas 尺寸和宽高比
2. 描述每个元素的视觉特征和位置
3. 描述元素之间的连接关系
4. 强调整体风格一致性
5. 添加负面约束（不要什么）

---

### 3.4 chunk_render_agent

**职责**: 并行调用 VLM 渲染各 chunk 图片

**输入**:
- `state.chunk_vlm_designs`: VLM prompt 设计

**输出**:
- `state.chunk_images`: 渲染结果

**输出 Schema**:
```json
{
  "c1": {
    "path": "/output/chunks/c1.png",
    "bbox": {"x": 100, "y": 50, "w": 600, "h": 400},
    "render_status": "success",
    "render_time_ms": 3500
  },
  "c2": {
    "path": "/output/chunks/c2.png",
    "bbox": {"x": 720, "y": 50, "w": 500, "h": 400},
    "render_status": "success",
    "render_time_ms": 2800
  }
}
```

**实现要点**:
1. 并发控制（默认 3-5 并发）
2. 超时处理（默认 180s）
3. 失败重试（最多 2 次）
4. 保存原始图片和处理后图片

---

### 3.5 pptx_composer_agent

**职责**: 组装 PPTX + 使用 SAM 提取 nodes

**输入**:
- `state.chunk_images`: chunk 图片
- `state.chunk_layout_json`: 布局信息
- `state.semantic_json`: 语义结构（用于 node 匹配）

**输出**:
- `state.extracted_nodes`: 提取的 nodes 信息
- `state.pptx_output_path`: PPTX 文件路径

**处理流程**:

```
1. 加载 chunk 图片
       │
       ▼
2. SAM 分割每个 chunk 图片
       │
       │  得到多个 mask 区域
       ▼
3. 匹配 mask 与 semantic_json 中的 nodes
       │
       │  基于位置、大小、描述
       ▼
4. 裁切每个 node 为独立图片
       │
       ▼
5. 创建 PPTX
       │
       │  - 设置 slide 尺寸
       │  - 放置 chunk 背景图（可选）
       │  - 放置各 node 图片
       │  - 添加 inter-chunk 连接线
       ▼
6. 保存 PPTX
```

**SAM Node 提取策略**:

```python
# 伪代码
def extract_nodes_with_sam(chunk_image, semantic_nodes, internal_layout):
    # 1. 使用 SAM 自动分割
    masks = sam_model.generate_masks(chunk_image)

    # 2. 过滤太小或太大的 mask
    valid_masks = filter_by_size(masks, min_area=100, max_area_ratio=0.8)

    # 3. 匹配 mask 与 nodes
    matched = []
    for node in semantic_nodes:
        expected_bbox = internal_layout.get_node_bbox(node.node_id)
        best_mask = find_best_matching_mask(valid_masks, expected_bbox)
        if best_mask:
            matched.append({
                "node_id": node.node_id,
                "mask": best_mask,
                "confidence": compute_iou(best_mask.bbox, expected_bbox)
            })

    # 4. 裁切并保存
    for m in matched:
        cropped = crop_with_mask(chunk_image, m.mask)
        save_image(cropped, f"{node_id}_cropped.png")

    return matched
```

**PPTX 组装策略**:

```python
# 伪代码
def compose_pptx(chunk_images, extracted_nodes, layout_json, output_path):
    prs = Presentation()
    prs.slide_width = Inches(layout_json.canvas.width / 96)
    prs.slide_height = Inches(layout_json.canvas.height / 96)

    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank

    # 方案 A: 放置整个 chunk 图片（简单，但不可编辑）
    # for chunk_id, chunk_info in chunk_images.items():
    #     add_picture(slide, chunk_info.path, chunk_info.bbox)

    # 方案 B: 放置提取的 nodes（可编辑）
    for node_id, node_info in extracted_nodes.items():
        add_picture(slide, node_info.cropped_path, node_info.bbox_in_canvas)

    # 添加 inter-chunk 连接线
    for conn in layout_json.inter_chunk_connectors:
        add_connector(slide, conn)

    prs.save(output_path)
```

---

## 4. 数据流示例

```
输入:
  target = "Early Experience paradigm: bridging IL and RL via rollout-based supervision..."

                    │
                    ▼
semantic_constructor_agent
                    │
                    ▼
semantic_json = {
  "chunks": [
    {"chunk_id": "c1", "title": "Data Pipeline", "node_ids": ["n1","n2","n3","n4"]},
    {"chunk_id": "c2", "title": "IWM Branch", "node_ids": ["n5","n6","n7"]},
    {"chunk_id": "c3", "title": "SR Branch", "node_ids": ["n8","n9","n10"]},
    {"chunk_id": "c4", "title": "Output", "node_ids": ["n11","n12"]}
  ],
  "nodes": [...],
  "edges": [...],
  "inter_chunk_relations": [
    {"from_chunk": "c1", "to_chunk": "c2", "relation_type": "branch"},
    {"from_chunk": "c1", "to_chunk": "c3", "relation_type": "branch"},
    {"from_chunk": "c2", "to_chunk": "c4", "relation_type": "merge"},
    {"from_chunk": "c3", "to_chunk": "c4", "relation_type": "merge"}
  ]
}
                    │
                    ▼
chunk_layout_constructor_agent
                    │
                    ▼
chunk_layout_json = {
  "canvas": {"width": 1920, "height": 1080},
  "chunks": [
    {"chunk_id": "c1", "bbox": {"x": 50, "y": 300, "w": 500, "h": 400}, ...},
    {"chunk_id": "c2", "bbox": {"x": 600, "y": 100, "w": 600, "h": 350}, ...},
    {"chunk_id": "c3", "bbox": {"x": 600, "y": 500, "w": 600, "h": 350}, ...},
    {"chunk_id": "c4", "bbox": {"x": 1250, "y": 300, "w": 600, "h": 400}, ...}
  ],
  "inter_chunk_connectors": [...]
}
                    │
                    ▼
chunk_vlm_design_agent
                    │
                    ▼
chunk_vlm_designs = {
  "c1": {"prompt": "Create a data pipeline diagram...", ...},
  "c2": {"prompt": "Create an IWM training branch...", ...},
  "c3": {"prompt": "Create a Self-Reflection branch...", ...},
  "c4": {"prompt": "Create an output module...", ...}
}
                    │
                    ▼
chunk_render_agent (4 次 VLM 调用)
                    │
                    ▼
chunk_images = {
  "c1": {"path": "c1.png", ...},
  "c2": {"path": "c2.png", ...},
  "c3": {"path": "c3.png", ...},
  "c4": {"path": "c4.png", ...}
}
                    │
                    ▼
pptx_composer_agent (SAM 提取 + 组装)
                    │
                    ▼
输出:
  - pptx_output_path = "paper2graph_output.pptx"
  - extracted_nodes = {
      "n1": {"cropped_path": "n1.png", "bbox_in_canvas": {...}},
      ...
    }
```

---

## 5. 与现有 Pipeline 的对比

| 维度 | 现有 Node-Based Pipeline | 新 Chunk-Based Pipeline |
|------|-------------------------|------------------------|
| VLM 调用次数 | 50+ 次 (每个 node) | 4-6 次 (每个 chunk) |
| Token 消耗 | 高 | 低 (约 1/10) |
| 视觉一致性 | 差 (nodes 独立渲染) | 好 (chunk 内统一渲染) |
| 可编辑性 | 好 (每个 node 独立) | 中等 (需 SAM 提取) |
| 跨 chunk 连接 | 需额外处理 | 在 PPTX 阶段添加 |
| 复杂度 | 高 (多 agent) | 中等 (5 个 agent) |

---

## 6. 实现优先级

### Phase 1: MVP (当前)
1. ✅ semantic_constructor_agent (合并 target_analysis)
2. ✅ chunk_layout_constructor_agent
3. ✅ chunk_vlm_design_agent
4. ✅ chunk_render_agent
5. ✅ pptx_composer_agent (基础版，先不做 SAM 提取)

### Phase 2: SAM 集成
1. 集成 SAM 模型
2. 实现 node 提取逻辑
3. 优化 mask-node 匹配算法

### Phase 3: 优化
1. chunk_optimizer_agent (可选)
2. 渲染质量评估和重试
3. 交互式编辑支持

---

## 7. 文件结构

```
dataflow_agent/
├── agentroles/
│   ├── p2g_semantic_constructor_agent.py    # 新增
│   ├── p2g_chunk_layout_constructor_agent.py # 新增
│   ├── p2g_chunk_vlm_design_agent.py        # 新增
│   ├── p2g_chunk_render_agent.py            # 新增
│   └── p2g_pptx_composer_agent.py           # 重构
├── workflow/
│   └── wf_p2g_chunk_pipeline.py             # 新增
├── toolkits/
│   └── sam_extractor/                       # 新增
│       ├── __init__.py
│       └── node_extractor.py
└── promptstemplates/
    └── prompts_repo.py                      # 新增 prompt 模板
```
