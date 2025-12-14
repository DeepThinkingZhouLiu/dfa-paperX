"""
Paper Graph Toolkit
~~~~~~~~~~~~~~~~~~~

用于 Paper2Graph pipeline 的布局验证和计算工具集。

工具列表：
- semantic_validator: 验证 semantic_json 结构完整性
- space_utilization_validator: 验证 chunk 内 nodes 的空间利用率
- node_overlap_validator: 验证 chunk 内 nodes 是否重叠
- chunk_grid_validator: 验证 chunks 的网格位置是否冲突
- bbox_validator: 验证最终 layout_json 的 bbox 有效性
- grid_layout_solver: 网格布局求解器
- layout_solver: 布局求解器基类
"""

from dataflow_agent.toolkits.papergraphtool.semantic_validator import (
    validate_semantic_schema,
)

from dataflow_agent.toolkits.papergraphtool.space_utilization_validator import (
    validate_space_utilization,
    validate_all_chunks,
    generate_improvement_suggestions,
    create_space_utilization_validator_tool,
)

from dataflow_agent.toolkits.papergraphtool.node_overlap_validator import (
    check_bbox_overlap,
    validate_nodes_overlap,
    validate_all_chunks_overlap,
    generate_overlap_fix_suggestions,
    create_node_overlap_validator_tool,
)

from dataflow_agent.toolkits.papergraphtool.chunk_grid_validator import (
    validate_chunk_grid_positions,
    generate_grid_fix_suggestions,
    visualize_grid_occupancy,
    create_chunk_grid_validator_tool,
)

from dataflow_agent.toolkits.papergraphtool.bbox_validator import (
    validate_layout_json,
    generate_bbox_fix_suggestions,
)

__all__ = [
    # semantic_validator
    "validate_semantic_schema",
    # space_utilization_validator
    "validate_space_utilization",
    "validate_all_chunks",
    "generate_improvement_suggestions",
    "create_space_utilization_validator_tool",
    # node_overlap_validator
    "check_bbox_overlap",
    "validate_nodes_overlap",
    "validate_all_chunks_overlap",
    "generate_overlap_fix_suggestions",
    "create_node_overlap_validator_tool",
    # chunk_grid_validator
    "validate_chunk_grid_positions",
    "generate_grid_fix_suggestions",
    "visualize_grid_occupancy",
    "create_chunk_grid_validator_tool",
    # bbox_validator
    "validate_layout_json",
    "generate_bbox_fix_suggestions",
]
