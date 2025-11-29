# PaperGraph JSON Schema v0.2 - VLM 生图增强版

## 设计原则
1. **语义层与视觉层分离**：语义信息（nodes/edges/groups）与视觉描述（description）解耦
2. **多粒度描述**：支持节点级、边级、组级、全局级的描述
3. **VLM 友好**：description 字段包含足够信息供 VLM 生成图像
4. **可扩展性**：保留 MVP 核心字段，description 作为扩展但重要字段

## 核心改进点

### 1. 新增 `description` 字段体系

#### 1.1 Node Description（节点描述）
每个节点需要包含：
- **semantic_description**: 语义描述（用于理解节点含义）
- **visual_description**: 视觉描述（用于 VLM 生图，包含形状、颜色、图标等）
- **context_description**: 上下文描述（节点在整体图中的位置和作用）

```json
{
  "id": "node1",
  "label": "Input Data",
  "type": "data",
  "role": "input",
  "description": {
    "semantic": "Raw input data tensor with shape [B, T, D]",
    "visual": "A rectangular box with rounded corners, light blue background (#E3F2FD), containing text 'Input Data' in dark blue. The box should be positioned on the left side of the diagram.",
    "vlm_prompt": "Create a minimalist rectangular box with rounded corners, light blue background (#E3F2FD), containing the text 'Input Data' in dark blue font. The box should have a subtle shadow and be suitable for a scientific diagram.",
    "context": "This is the starting point of the data flow, positioned at the leftmost side of the diagram"
  }
}
```

#### 1.2 Edge Description（边描述）
每条边需要包含：
- **semantic_description**: 数据流/控制流的语义
- **visual_description**: 箭头样式、路径、方向
- **vlm_prompt**: 用于生成箭头/连接线的提示词

```json
{
  "id": "e1",
  "source": "node1",
  "target": "node2",
  "type": "data",
  "description": {
    "semantic": "Data flows from Input Data to Tokenizer",
    "visual": "A horizontal arrow pointing from left to right, solid line style, dark gray color (#424242), with arrowhead at the end",
    "vlm_prompt": "Draw a horizontal arrow pointing right, solid dark gray line (#424242), connecting two boxes. The arrow should be straight and have a clear arrowhead.",
    "direction": "right",
    "style": {
      "line_type": "solid",
      "color": "#424242",
      "width": 2,
      "arrowhead": "standard"
    }
  }
}
```

#### 1.3 Group Description（组描述）
每个组需要包含：
- **semantic_description**: 组的语义含义
- **visual_description**: 组的视觉边界、背景、布局
- **vlm_prompt**: 用于生成组容器的提示词

```json
{
  "group_id": "grp_input",
  "label": "Input Processing",
  "type": "stage",
  "node_ids": ["node1", "node2"],
  "description": {
    "semantic": "Input processing stage containing data input and tokenization",
    "visual": "A dashed rectangular border with light gray background (#F5F5F5), grouping two nodes horizontally. The border should be subtle and not distract from the content.",
    "vlm_prompt": "Create a subtle dashed rectangular border with light gray background (#F5F5F5) that groups two boxes horizontally. The border should be thin and unobtrusive.",
    "layout": "horizontal"
  }
}
```

### 2. 全局视觉描述（Canvas/Global Description）

在顶层添加全局视觉描述，用于整体风格控制：

```json
{
  "version": "0.2",
  "paper": {...},
  "canvas": {
    "width": 1920,
    "height": 1080,
    "background_color": "#FFFFFF",
    "style": "academic"
  },
  "global_description": {
    "style_guide": "Minimalist academic diagram style with clean lines, professional color palette (blues and grays), consistent spacing",
    "vlm_global_prompt": "Create a clean, professional academic diagram in minimalist style. Use a professional color palette dominated by blues (#1976D2, #E3F2FD) and grays (#424242, #F5F5F5). Maintain consistent spacing and alignment. All elements should be clearly readable and well-organized.",
    "color_palette": {
      "primary": "#1976D2",
      "secondary": "#E3F2FD",
      "text": "#212121",
      "border": "#BDBDBD",
      "background": "#FFFFFF"
    },
    "typography": {
      "font_family": "Arial, sans-serif",
      "font_size_base": 14,
      "font_weight": "normal"
    }
  }
}
```

### 3. 渲染层增强（Render Layer Enhancement）

在 render 层中添加更详细的视觉属性，与 description 配合：

```json
{
  "render": {
    "nodes": [
      {
        "node_id": "node1",
        "bbox": {"x": 100, "y": 200, "width": 150, "height": 80},
        "shape": "rounded_rectangle",
        "style": {
          "fill_color": "#E3F2FD",
          "stroke_color": "#1976D2",
          "stroke_width": 2,
          "corner_radius": 8,
          "opacity": 1.0
        },
        "icon": {
          "type": "generated",
          "prompt": "minimalist data input icon, blue theme",
          "uri": null,
          "position": "left"
        },
        "label": {
          "text": "Input Data",
          "position": "center",
          "style": {"color": "#212121", "font_size": 14}
        },
        "rotation": 0,
        "z_index": 1
      }
    ],
    "edges": [
      {
        "edge_id": "e1",
        "points": [{"x": 250, "y": 240}, {"x": 300, "y": 240}],
        "route": "orthogonal",
        "style": {
          "stroke_color": "#424242",
          "stroke_width": 2,
          "line_type": "solid",
          "arrowhead": {
            "type": "standard",
            "size": 8,
            "fill_color": "#424242"
          }
        },
        "label": null
      }
    ],
    "groups": [
      {
        "group_id": "grp_input",
        "bbox": {"x": 80, "y": 180, "width": 400, "height": 120},
        "style": {
          "border_color": "#BDBDBD",
          "border_width": 1,
          "border_style": "dashed",
          "background_color": "#F5F5F5",
          "background_opacity": 0.3,
          "padding": {"top": 10, "right": 10, "bottom": 10, "left": 10}
        },
        "label": {
          "text": "Input Processing",
          "position": "top-left",
          "style": {"color": "#757575", "font_size": 12}
        }
      }
    ]
  }
}
```

## 完整 JSON Schema v0.2 结构

```json
{
  "version": "0.2",
  "paper": {
    "title": "Transformer-based Model Architecture",
    "arxiv_id": "2301.00001",
    "doi": null
  },
  "canvas": {
    "width": 1920,
    "height": 1080,
    "unit": "px",
    "dpi": 300,
    "background_color": "#FFFFFF"
  },
  "global_description": {
    "style_guide": "Minimalist academic diagram style",
    "vlm_global_prompt": "Create a clean, professional academic diagram...",
    "color_palette": {...},
    "typography": {...}
  },
  "layout": {
    "flow": "left-to-right",
    "algorithm": "dagre",
    "hints": {
      "ranks": [["node1"], ["node2"], ["node3", "node4"], ["node5"], ["node6"]],
      "direction_overrides": {}
    }
  },
  "graph": {
    "nodes": [
      {
        "id": "node1",
        "label": "Input Data",
        "type": "data",
        "role": "input",
        "attrs": {"shape": "[B,T,D]", "dtype": "fp32"},
        "importance": 0.8,
        "level": 0,
        "provenance": {
          "section": "Methods",
          "span_refs": [{"start": 120, "end": 150}],
          "confidence": 0.95
        },
        "description": {
          "semantic": "Raw input data tensor",
          "visual": "Rectangular box with rounded corners, light blue background",
          "vlm_prompt": "Create a minimalist rectangular box...",
          "context": "Starting point of data flow"
        }
      }
    ],
    "edges": [
      {
        "id": "e1",
        "source": "node1",
        "target": "node2",
        "type": "data",
        "label": null,
        "attrs": {},
        "provenance": {...},
        "description": {
          "semantic": "Data flows from Input Data to Tokenizer",
          "visual": "Horizontal arrow pointing right",
          "vlm_prompt": "Draw a horizontal arrow...",
          "direction": "right",
          "style": {
            "line_type": "solid",
            "color": "#424242",
            "width": 2
          }
        }
      }
    ]
  },
  "groups": [
    {
      "group_id": "grp_input",
      "label": "Input Processing",
      "type": "stage",
      "node_ids": ["node1", "node2"],
      "importance": 0.6,
      "layout_hint": {
        "direction": "left-to-right",
        "grid": null,
        "collapse": false,
        "rank": 0
      },
      "description": {
        "semantic": "Input processing stage",
        "visual": "Dashed rectangular border grouping nodes",
        "vlm_prompt": "Create a subtle dashed border...",
        "layout": "horizontal"
      }
    }
  ],
  "render": {
    "nodes": [...],
    "edges": [...],
    "groups": [...],
    "labels": [...],
    "assets": {
      "icons": [...],
      "images": [...]
    }
  },
  "evaluation": {
    "readability": 0.9,
    "logic": 0.95,
    "aesthetics": 0.85,
    "completeness": 0.9,
    "professionalism": 0.92,
    "issues": []
  }
}
```

## 关键设计决策与讨论点

### 讨论点 1: Description 字段的粒度
**问题**: description 应该是一个字符串还是结构化对象？

**方案 A（当前）**: 结构化对象，包含 semantic/visual/vlm_prompt
- 优点：清晰分离不同用途的描述
- 缺点：结构复杂，可能冗余

**方案 B**: 单一 description 字符串 + 可选的 vlm_prompt
- 优点：简单，易于生成
- 缺点：语义和视觉信息混合

**建议**: 采用方案 A，但允许简化版本（只有 vlm_prompt）

### 讨论点 2: VLM Prompt 的生成时机
**问题**: vlm_prompt 应该在哪个 Agent 阶段生成？

**选项**:
1. CEA/DSP: 在语义抽取时就生成基础 prompt
2. MDA: 在视觉设计阶段生成详细 prompt
3. PTA: 专门的 Prompt Template Agent 生成

**建议**: 
- DSP 阶段生成基础 semantic description
- MDA 阶段生成 visual description
- PTA 阶段生成最终的 vlm_prompt（整合所有信息）

### 讨论点 3: 位置信息在 Description 中的表达
**问题**: description 中是否应该包含绝对位置信息？

**当前设计**: description 包含相对位置（如"left side"），绝对位置在 render.bbox 中

**考虑**: 
- description 中的位置应该是语义性的（"left side", "top-right corner"）
- 绝对坐标在 render 层
- 这样便于布局算法调整位置而不影响描述

### 讨论点 4: 多语言支持
**问题**: description 和 vlm_prompt 是否应该支持多语言？

**建议**: 
- vlm_prompt 统一使用英文（VLM 通常对英文理解更好）
- semantic description 可以使用原始语言（中文/英文）
- label 可以支持多语言

### 讨论点 5: Description 的模板化
**问题**: 是否需要定义 description 的模板规则？

**建议**: 定义模板规则，例如：
- Node: "{shape} with {color} background, containing text '{label}'"
- Edge: "{direction} arrow from {source_label} to {target_label}"
- Group: "{border_style} border grouping {count} nodes in {layout} arrangement"

这样可以保证一致性和可预测性。

## 下一步行动建议

1. **确认 description 字段结构**：是否采用 semantic/visual/vlm_prompt 三层结构？
2. **定义模板规则**：为不同类型的节点/边/组定义描述模板
3. **Agent 职责划分**：明确哪个 Agent 负责生成哪部分 description
4. **示例完善**：提供完整的端到端示例 JSON
5. **Schema 验证**：考虑使用 JSON Schema 进行格式验证


