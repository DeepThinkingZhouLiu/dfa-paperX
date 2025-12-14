# Design Document

## Overview

本设计文档描述了Paper2GraphX布局生成系统的优化方案。当前系统通过多个agent协作生成科研论文方法图的布局,包括语义构建(Semantic Constructor)、chunk布局规划(Chunk Layout Planner)和node布局规划(Node Layout Planner)三个主要阶段。

优化的核心目标是:
1. 减少生成的chunk数量,使其更符合科研绘图的常见范式(3-7个chunks)
2. 简化网格结构,从当前的5x3或更复杂配置简化为2x2、2x3、3x3等常见配置
3. 确保node的bbox具有合理的宽高比(0.3-3.0),避免过于细长的bbox导致VLM渲染内容无法适配
4. 通过prompt优化和后处理验证,提高布局质量

## Architecture

### Current Architecture

```
User Target
    ↓
[P2gTargetAnalystAgent]
    ↓ (enriched_description)
[P2gSemanticConstructorAgent]
    ↓ (semantic_json: chunks, nodes, edges)
[P2gChunkLayoutPlannerAgent]
    ↓ (layout_plan: grid + chunk positions)
[P2gNodeLayoutPlannerAgent]
    ↓ (node_layout_plan: node rel_bbox per chunk)
[P2gLayoutConstructorAgent]
    ↓ (layout_json: absolute bbox for all chunks/nodes)
[P2gLayoutCheckerAgent] → draft.png
    ↓
[P2gVlmNodeRendererAgent] → rendered nodes
```

### Optimization Points

优化将在以下三个关键点进行:

1. **Semantic Constructor Level**: 在生成semantic_json时,通过prompt约束控制chunk和node的数量和粒度
2. **Layout Planner Level**: 在生成layout_plan时,限制grid维度和chunk分布
3. **Node Layout Planner Level**: 在分配node bbox时,确保宽高比合理
4. **Post-Processing Level**: 添加验证和自动修复逻辑

## Components and Interfaces

### 1. Enhanced Prompt Templates

#### 1.1 Semantic Constructor Prompt Enhancement

在`prompts_repo.py`中的`p2g_semantic_constructor`相关prompt中添加设计原则:

```python
CHUNK_DESIGN_PRINCIPLES = """
[CHUNK 设计原则]
1. 每个 chunk 应包含至少 4-6 个有实质内容的 nodes
2. 避免创建只包含标题或单一元素的 chunk
3. 标题、注释等轻量元素应归属到其关联的核心模块 chunk 中
4. 推荐的 chunk 数量：简单图 3-4 个，复杂图 5-7 个，最多不超过 7 个
5. 横跨全宽的"薄层"chunk（如标题行、分隔行）应尽量合并到上方或下方的核心 chunk

[NODE 设计原则]
1. 每个 node 应代表一个独立的可视化单元
2. 避免将同类元素拆分为多个 nodes（如多个箭头应合并为一个"连接组"）
3. 注释和说明文字应尽量合并，除非它们在空间上明显分离
4. 推荐的 node 数量：每个 chunk 4-8 个，整图 20-35 个
5. 按认知单元而非数据结构来组织 nodes
"""
```

#### 1.2 Chunk Layout Planner Prompt Enhancement

```python
GRID_COMPLEXITY_CONSTRAINTS = """
[GRID 复杂度约束]
1. 网格行数不超过 4 行
2. 网格列数不超过 4 列
3. 总网格单元数不超过 12 个 (rows × cols ≤ 12)
4. 优先使用的网格配置：2x2, 2x3, 3x2, 3x3, 3x4
5. 避免使用 5x3, 4x4 或更复杂的配置

[CHUNK 合并规则]
1. 如果某个 chunk 只包含 1-3 个 nodes，考虑将其合并到相邻的 chunk
2. 横跨全宽的"薄层"chunk（如标题行）高度不应超过画布高度的 15%
3. 最终的 chunk 数量建议控制在 3-7 个
"""
```

#### 1.3 Node Layout Planner Prompt Enhancement

```python
ASPECT_RATIO_CONSTRAINTS = """
[BBOX 宽高比约束]
1. 所有 node 的 bbox 宽高比应在 0.3 到 3.0 之间
2. VLM 渲染的 node 最小尺寸：宽度 100px，高度 60px
3. 文本块 node 的 bbox 应根据预估文本长度和字体大小计算
4. 模块框 node 的最小尺寸：150x100 pixels
5. 连接器/箭头 node 可以有更极端的宽高比 (3.0-10.0)

[NODE 类型与尺寸映射]
- module_box: 最小 150x100, 宽高比 1.0-2.0
- text_block: 根据文本长度动态计算, 宽高比 1.5-3.0
- annotation: 高度与文本行数成正比, 宽高比 2.0-4.0
- shape/connector: 宽高比 3.0-10.0
- image_placeholder: 最小面积 20000 平方像素, 宽高比 0.8-1.5
"""
```

### 2. Validation and Post-Processing Module

#### 2.1 Layout Validator

```python
class LayoutValidator:
    """布局验证器,检查生成的布局是否符合约束"""
    
    def validate_chunk_count(self, semantic_json: dict) -> ValidationResult:
        """验证chunk数量是否在3-7之间"""
        pass
    
    def validate_grid_complexity(self, layout_plan: dict) -> ValidationResult:
        """验证网格复杂度是否符合约束"""
        pass
    
    def validate_node_aspect_ratios(self, node_layout_plan: dict) -> ValidationResult:
        """验证所有node的宽高比是否在合理范围内"""
        pass
    
    def validate_bbox_boundaries(self, layout_json: dict) -> ValidationResult:
        """验证所有bbox是否在画布边界内且不重叠"""
        pass
```

#### 2.2 Layout Corrector

```python
class LayoutCorrector:
    """布局修正器,自动修复常见的布局问题"""
    
    def merge_lightweight_chunks(self, semantic_json: dict) -> dict:
        """合并只包含少量nodes的轻量chunk"""
        pass
    
    def adjust_extreme_aspect_ratios(self, node_layout_plan: dict) -> dict:
        """调整极端宽高比的node bbox"""
        pass
    
    def fix_bbox_overlaps(self, layout_json: dict) -> dict:
        """修复bbox重叠问题"""
        pass
    
    def ensure_connectivity(self, layout_json: dict, semantic_json: dict) -> dict:
        """确保所有nodes在其parent chunk边界内"""
        pass
```

### 3. Layout Quality Metrics

#### 3.1 Metrics Calculator

```python
class LayoutQualityMetrics:
    """布局质量评估指标计算器"""
    
    def calculate_chunk_count(self, semantic_json: dict) -> int:
        """计算chunk总数"""
        pass
    
    def calculate_grid_dimensions(self, layout_plan: dict) -> tuple[int, int]:
        """计算网格维度 (rows, cols)"""
        pass
    
    def calculate_aspect_ratio_distribution(self, node_layout_plan: dict) -> dict:
        """计算node宽高比分布统计"""
        pass
    
    def calculate_extreme_aspect_ratio_percentage(self, node_layout_plan: dict) -> float:
        """计算极端宽高比node的百分比"""
        pass
    
    def calculate_avg_nodes_per_chunk(self, semantic_json: dict) -> float:
        """计算每个chunk平均包含的node数量"""
        pass
    
    def generate_quality_report(self, semantic_json: dict, layout_plan: dict, 
                               node_layout_plan: dict) -> dict:
        """生成完整的质量评估报告"""
        pass
```

## Data Models

### Enhanced Semantic JSON

```python
{
    "chunks": [
        {
            "chunk_id": str,
            "title": str,
            "summary": str,
            "node_ids": List[str],
            "node_count": int,  # 新增: 用于验证
            "is_lightweight": bool  # 新增: 标记是否为轻量chunk
        }
    ],
    "nodes": [
        {
            "node_id": str,
            "node_type": str,  # text_block, shape, annotation, image_placeholder
            "chunk_id": str,
            "desc": str,
            "estimated_content_length": int  # 新增: 用于计算bbox
        }
    ],
    "edges": [...]
}
```

### Enhanced Layout Plan

```python
{
    "global": {
        "grid_rows": int,  # 限制: ≤ 4
        "grid_cols": int,  # 限制: ≤ 4
        "flow_direction": str,
        "notes": str,
        "complexity_score": float  # 新增: grid_rows * grid_cols
    },
    "chunks": [
        {
            "chunk_id": str,
            "row": int,
            "col": int,
            "span_row": int,
            "span_col": int,
            "size_hint": str,
            "relation_note": str,
            "is_full_width": bool  # 新增: 标记是否横跨全宽
        }
    ]
}
```

### Enhanced Node Layout Plan

```python
{
    "chunks": [
        {
            "chunk_id": str,
            "nodes": [
                {
                    "node_id": str,
                    "rel_bbox": {
                        "x": float,  # 相对于chunk的坐标
                        "y": float,
                        "w": float,
                        "h": float
                    },
                    "aspect_ratio": float,  # 新增: w/h
                    "is_extreme_ratio": bool  # 新增: 标记是否为极端宽高比
                }
            ]
        }
    ]
}
```

### Validation Result

```python
{
    "is_valid": bool,
    "violations": [
        {
            "type": str,  # "chunk_count", "grid_complexity", "aspect_ratio", etc.
            "severity": str,  # "error", "warning"
            "message": str,
            "location": str,  # chunk_id or node_id
            "suggested_fix": str
        }
    ],
    "metrics": {
        "chunk_count": int,
        "grid_dimensions": tuple[int, int],
        "extreme_aspect_ratio_count": int,
        "avg_nodes_per_chunk": float
    }
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Chunk count constraint
*For any* generated semantic_json, the number of chunks should be between 3 and 7 (inclusive)
**Validates: Requirements 1.1**

### Property 2: Lightweight chunk merging
*For any* chunk in semantic_json with fewer than 4 nodes, it should either be merged with an adjacent chunk or be a special case (like a title chunk with justification)
**Validates: Requirements 1.2**

### Property 3: Grid dimension constraints
*For any* generated layout_plan, both grid_rows and grid_cols should be no more than 4
**Validates: Requirements 2.1, 2.2**

### Property 4: Grid complexity limit
*For any* generated layout_plan, the product of grid_rows and grid_cols should not exceed 12
**Validates: Requirements 2.3**

### Property 5: Node aspect ratio bounds
*For any* node bbox in node_layout_plan, the aspect ratio (width/height) should be between 0.3 and 3.0, except for connector/arrow nodes which can have ratios between 3.0 and 10.0
**Validates: Requirements 3.1, 3.2**

### Property 6: VLM node minimum dimensions
*For any* node marked for VLM rendering, its bbox should have minimum width of 100 pixels and minimum height of 60 pixels
**Validates: Requirements 3.3**

### Property 7: Bbox boundary containment
*For any* chunk bbox and its child node bboxes, all node bboxes should be fully contained within their parent chunk bbox
**Validates: Requirements 5.3**

### Property 8: No bbox overlaps
*For any* two chunks at the same level, their bboxes should not overlap
**Validates: Requirements 5.2**

### Property 9: Canvas boundary containment
*For any* chunk or node bbox, it should be fully contained within the canvas boundaries
**Validates: Requirements 5.1**

### Property 10: Module box minimum size
*For any* node classified as a module box, its bbox should have minimum dimensions of 150x100 pixels
**Validates: Requirements 6.1**

### Property 11: Connector aspect ratio
*For any* node classified as a connector or arrow, its aspect ratio should be between 3.0 and 10.0
**Validates: Requirements 6.3**

### Property 12: Complex visual content area
*For any* node requiring complex visual content, its bbox area should be at least 20000 square pixels
**Validates: Requirements 6.4**

## Error Handling

### 1. Validation Errors

当验证失败时,系统应:
1. 记录详细的错误信息,包括违反的约束、位置和建议的修复方案
2. 尝试自动修复(如果可能)
3. 如果自动修复失败,返回详细的错误报告给用户

### 2. Prompt Constraint Violations

当LLM生成的结果违反prompt中的约束时:
1. 不进行重试(避免无限循环)
2. 记录违反的约束
3. 调用LayoutCorrector进行后处理修复
4. 如果修复成功,继续流程;如果失败,返回错误

### 3. Extreme Cases

对于极端情况(如用户要求非常复杂的图表):
1. 在target_analyst阶段就进行复杂度评估
2. 如果预估复杂度过高,建议用户简化需求或分解为多个图表
3. 提供复杂度评分和建议

## Testing Strategy

### Unit Tests

1. **Prompt Template Tests**: 验证新增的约束文本是否正确注入到prompt中
2. **Validator Tests**: 测试各个验证函数是否正确识别违规情况
3. **Corrector Tests**: 测试修正函数是否能正确修复常见问题
4. **Metrics Calculator Tests**: 测试指标计算是否准确

### Property-Based Tests

使用`hypothesis`库进行property-based testing:

1. **Property Test 1: Chunk count constraint**
   - 生成随机的semantic_json
   - 验证chunk数量在3-7之间
   - **Feature: layout-optimization, Property 1: Chunk count constraint**

2. **Property Test 2: Grid complexity limit**
   - 生成随机的layout_plan
   - 验证grid_rows * grid_cols ≤ 12
   - **Feature: layout-optimization, Property 4: Grid complexity limit**

3. **Property Test 3: Aspect ratio bounds**
   - 生成随机的node_layout_plan
   - 验证所有node的aspect ratio在合理范围内
   - **Feature: layout-optimization, Property 5: Node aspect ratio bounds**

4. **Property Test 4: Bbox containment**
   - 生成随机的layout_json
   - 验证所有node bbox在其parent chunk内
   - **Feature: layout-optimization, Property 7: Bbox boundary containment**

5. **Property Test 5: No overlaps**
   - 生成随机的layout_json
   - 验证所有chunk bbox不重叠
   - **Feature: layout-optimization, Property 8: No bbox overlaps**

### Integration Tests

1. **End-to-End Layout Generation**: 使用真实的用户target,测试完整的布局生成流程
2. **Correction Pipeline**: 测试验证→修正→再验证的完整流程
3. **Quality Metrics**: 测试质量指标计算和报告生成

### Regression Tests

使用当前的测试用例(如`tests/test_p2g_layout_pipeline.py`)作为回归测试基准:
1. 确保优化后的系统仍能处理现有的测试用例
2. 对比优化前后的布局质量指标
3. 验证优化后的布局是否更符合科研绘图范式

## Implementation Notes

### Phase 1: Prompt Enhancement (Week 1)
1. 在`prompts_repo.py`中添加新的约束文本
2. 更新三个主要agent的prompt模板
3. 进行初步测试,观察LLM是否遵守新约束

### Phase 2: Validation Module (Week 2)
1. 实现`LayoutValidator`类
2. 实现`LayoutQualityMetrics`类
3. 在各个agent的`update_state_result`中集成验证逻辑

### Phase 3: Correction Module (Week 3)
1. 实现`LayoutCorrector`类
2. 实现各种修正算法(chunk合并、bbox调整等)
3. 集成到pipeline中

### Phase 4: Testing & Refinement (Week 4)
1. 编写property-based tests
2. 进行端到端测试
3. 根据测试结果调整约束参数和修正算法
4. 生成质量对比报告

## Performance Considerations

1. **Validation Overhead**: 验证逻辑应该高效,避免显著增加处理时间
2. **Correction Complexity**: 修正算法应该有明确的终止条件,避免无限循环
3. **Parallel Processing**: Node layout planning已经支持并行,应保持这一优化
4. **Caching**: 考虑缓存验证结果,避免重复计算

## Future Enhancements

1. **Machine Learning-Based Optimization**: 使用历史数据训练模型,预测最优的chunk划分和grid配置
2. **Interactive Refinement**: 提供UI让用户交互式调整布局
3. **Style Templates**: 提供预定义的布局模板(如"流程图风格"、"架构图风格"等)
4. **Adaptive Constraints**: 根据图表复杂度动态调整约束参数
