# Requirements Document

## Introduction

本需求文档描述了对Paper2GraphX布局生成系统的优化需求。当前系统在生成科研论文方法图时,存在chunk数量过多、网格划分过细、以及node bbox不合理(过于细长)等问题,导致后续VLM渲染的内容无法适配到预定义的bbox中。本优化旨在改进布局算法,使生成的图表更符合科研绘图的常见范式,并确保node的bbox尺寸合理,适合内容渲染。

## Glossary

- **Paper2GraphX**: 将学术论文描述转换为可视化方法图的系统
- **Chunk**: 图表中的语义模块,包含一组相关的nodes
- **Node**: 图表中的基本可视化单元,如文本框、形状、图像等
- **Bbox (Bounding Box)**: 节点或chunk的边界框,定义其位置和尺寸(x, y, width, height)
- **Layout Pipeline**: 布局生成流程,包括语义分析、chunk规划、node布局等步骤
- **Grid**: 用于对齐和定位chunks的网格系统
- **Aspect Ratio**: 宽高比,bbox的width与height的比值
- **VLM (Vision Language Model)**: 用于渲染node内容的视觉语言模型
- **Layout Planner**: 负责规划chunk在grid中位置的agent
- **Node Layout Planner**: 负责在chunk内部布局nodes的agent
- **Semantic Constructor**: 负责将目标描述转换为语义化chunk和node结构的agent

## Requirements

### Requirement 1

**User Story:** 作为系统开发者,我希望减少生成图表中的chunk数量,使其更符合科研绘图的常见范式,从而提高图表的可读性和视觉清晰度。

#### Acceptance Criteria

1. WHEN the Layout Planner generates a layout plan THEN the system SHALL limit the total number of chunks to between 3 and 7
2. WHEN a chunk contains fewer than 4 nodes THEN the system SHALL merge it with an adjacent semantically-related chunk
3. WHEN the system identifies a title-only chunk THEN the system SHALL either merge it with the first content chunk or treat it as a global header element
4. WHEN chunks span the full width of the canvas THEN the system SHALL limit their height to no more than 15% of the total canvas height
5. WHEN the Semantic Constructor creates chunks THEN the system SHALL group nodes by cognitive units rather than by data structure

### Requirement 2

**User Story:** 作为系统开发者,我希望简化网格结构,使其从当前的5x3或更复杂的配置简化为更常见的2x2、2x3或3x3配置,从而降低视觉复杂度。

#### Acceptance Criteria

1. WHEN the Layout Planner determines grid dimensions THEN the system SHALL limit grid rows to no more than 4
2. WHEN the Layout Planner determines grid dimensions THEN the system SHALL limit grid columns to no more than 4
3. WHEN the total grid cells exceed 12 THEN the system SHALL reject the layout plan and request simplification
4. WHEN the system generates a layout plan THEN the system SHALL prefer grid configurations of 2x2, 2x3, 3x2, 3x3, or 3x4
5. WHEN multiple chunks occupy a single row or column THEN the system SHALL ensure they are semantically related in the pipeline flow

### Requirement 3

**User Story:** 作为系统开发者,我希望确保每个node的bbox具有合理的宽高比,避免过于细长的bbox,从而确保VLM渲染的内容能够适配到bbox中。

#### Acceptance Criteria

1. WHEN the Node Layout Planner assigns a bbox to a node THEN the system SHALL ensure the aspect ratio is between 0.3 and 3.0
2. WHEN a node's assigned bbox has an aspect ratio outside the acceptable range THEN the system SHALL adjust the bbox dimensions to bring it within range
3. WHEN a node requires VLM rendering THEN the system SHALL ensure its bbox has a minimum width of 100 pixels and minimum height of 60 pixels
4. WHEN a node is a text block THEN the system SHALL calculate bbox dimensions based on estimated text content length and font size
5. WHEN the system detects a node with extreme aspect ratio (< 0.2 or > 5.0) THEN the system SHALL flag it for manual review or automatic correction

### Requirement 4

**User Story:** 作为系统开发者,我希望在prompt中添加明确的约束和指导原则,使LLM生成的布局更符合科研绘图的最佳实践。

#### Acceptance Criteria

1. WHEN the system invokes the Semantic Constructor agent THEN the system SHALL include chunk design principles in the prompt specifying minimum node count per chunk
2. WHEN the system invokes the Layout Planner agent THEN the system SHALL include grid complexity constraints in the prompt
3. WHEN the system invokes the Node Layout Planner agent THEN the system SHALL include aspect ratio constraints in the prompt
4. WHEN the system generates prompts for layout agents THEN the system SHALL include examples of good and bad layouts
5. WHEN the system provides design principles in prompts THEN the system SHALL specify that title and annotation elements should be merged with content chunks

### Requirement 5

**User Story:** 作为系统开发者,我希望添加布局验证和后处理步骤,在生成布局后自动检测和修复常见问题。

#### Acceptance Criteria

1. WHEN a layout plan is generated THEN the system SHALL validate that all chunk bboxes are within canvas boundaries
2. WHEN a layout plan is generated THEN the system SHALL validate that no two chunks overlap
3. WHEN node bboxes are assigned THEN the system SHALL validate that all nodes are within their parent chunk boundaries
4. WHEN the system detects layout violations THEN the system SHALL attempt automatic correction before failing
5. WHEN automatic correction fails THEN the system SHALL provide detailed error messages indicating which constraints were violated

### Requirement 6

**User Story:** 作为系统开发者,我希望系统能够根据node类型和内容智能地分配bbox尺寸,确保渲染内容能够适配。

#### Acceptance Criteria

1. WHEN a node is classified as a module box THEN the system SHALL allocate a bbox with minimum dimensions of 150x100 pixels
2. WHEN a node is classified as an annotation THEN the system SHALL allocate a bbox with height proportional to estimated text lines
3. WHEN a node is classified as a connector or arrow THEN the system SHALL allocate a thin bbox with aspect ratio between 3.0 and 10.0
4. WHEN a node requires complex visual content THEN the system SHALL allocate a bbox with area at least 20000 square pixels
5. WHEN multiple nodes of the same type are in a chunk THEN the system SHALL allocate similar bbox sizes for visual consistency

### Requirement 7

**User Story:** 作为系统开发者,我希望系统提供布局质量评估指标,以便量化评估优化效果。

#### Acceptance Criteria

1. WHEN a layout is generated THEN the system SHALL calculate and report the total number of chunks
2. WHEN a layout is generated THEN the system SHALL calculate and report the grid dimensions
3. WHEN a layout is generated THEN the system SHALL calculate and report the distribution of node aspect ratios
4. WHEN a layout is generated THEN the system SHALL calculate and report the percentage of nodes with extreme aspect ratios
5. WHEN a layout is generated THEN the system SHALL calculate and report the average number of nodes per chunk
