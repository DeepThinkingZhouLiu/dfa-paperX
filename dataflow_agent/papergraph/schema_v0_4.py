from __future__ import annotations

from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field, validator


# -----------------------------
# 基础注解（语义层轻量标注）
# -----------------------------
class Annotation(BaseModel):
    id: Optional[str] = None
    type: Optional[str] = None
    content: str
    layout_hint: Optional[Dict[str, Any]] = None


# -----------------------------
# 语义层对象定义
# -----------------------------
NodeType = Literal["data", "module", "operation", "loss", "metric", "result"]
EdgeType = Literal["data_flow", "control_flow", "dependency"]


class NodeSpec(BaseModel):
    node_id: str = Field(..., description="Unique node id, e.g., 'node-1'")
    label: str = Field(..., description="Human-readable label (English)")
    type: NodeType
    role: Optional[str] = None
    description: Optional[str] = None
    annotations: Optional[List[Annotation]] = None
    pattern: Optional[Dict[str, Any]] = None


class EdgeSpec(BaseModel):
    edge_id: str = Field(..., description="Unique edge id, e.g., 'edge-1'")
    source: str = Field(..., description="Source node_id")
    target: str = Field(..., description="Target node_id")
    type: Optional[EdgeType] = None
    description: Optional[str] = None
    multiplicity: Optional[str] = None
    annotations: Optional[List[Annotation]] = None


class GroupSpec(BaseModel):
    group_id: str = Field(..., description="Unique group id, e.g., 'group-1'")
    title: Optional[str] = None
    type: Optional[str] = None
    chunks: Optional[List[str]] = None
    layout_hint: Optional[Dict[str, Any]] = None
    description: Optional[str] = None


class LayoutSpec(BaseModel):
    flow: Literal["left-to-right", "top-to-bottom"] = Field(
        "left-to-right", description="Diagram flow direction"
    )
    grid: Optional[Dict[str, Any]] = None


class Taxonomy(BaseModel):
    node_types: List[str] = Field(default_factory=list)
    edge_types: List[str] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)


class SemanticLayerPayload(BaseModel):
    nodes: List[NodeSpec]
    edges: List[EdgeSpec]
    groups: Optional[List[GroupSpec]] = None
    canvas: Optional[Dict[str, Any]] = None
    grid: Optional[Dict[str, Any]] = None
    layout: LayoutSpec = Field(default_factory=LayoutSpec)
    chunks: Optional[List[Dict[str, Any]]] = None
    taxonomy: Optional[Taxonomy] = None

    @validator("edges", each_item=False)
    def _validate_edge_refs(cls, v, values):
        node_ids = {n.node_id for n in values.get("nodes", [])}
        warnings = []
        for e in v:
            if e.source not in node_ids or e.target not in node_ids:
                warnings.append(
                    f"edge {e.edge_id} references missing node(s): {e.source}->{e.target}"
                )
        # 仅在工具层面记录警告，不在 Pydantic 校验失败，这里返回即可
        return v


# -----------------------------
# 工具层返回结构
# -----------------------------
class SaveSemanticResult(BaseModel):
    stats: Dict[str, int] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


# -----------------------------
# 美学层（Style Sheet）
# -----------------------------
class Globals(BaseModel):
    theme_prompt: Optional[str] = None
    font_family: Optional[str] = None
    palette: Optional[Dict[str, str]] = None  # e.g., {"primary": "#3366FF", "accent": "#FFCC00"}
    default_node_engine: Optional[Literal["vlm", "compositor"]] = None


class StyleSelector(BaseModel):
    element: Literal["node", "edge", "group"]
    type: Optional[str] = None
    role: Optional[str] = None


class StyleRule(BaseModel):
    selector: StyleSelector
    properties: Dict[str, Any]
    priority: Optional[int] = None


class StyleSheet(BaseModel):
    globals: Optional[Globals] = None
    rules: List[StyleRule] = Field(default_factory=list)

