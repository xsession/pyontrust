from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from ..errors import GraphValidationError
from ..models import GraphSpec
from ..blocks.registry import BlockRegistry, default_block_registry


@dataclass
class ValidatedGraph:
    graph: GraphSpec


def validate_graph(spec: GraphSpec, *, registry: BlockRegistry | None = None) -> ValidatedGraph:
    reg = registry or default_block_registry()

    block_ids = {b.id for b in spec.blocks}
    if len(block_ids) != len(spec.blocks):
        raise GraphValidationError("Duplicate block IDs")

    for b in spec.blocks:
        if b.type not in reg.list_blocks():
            raise GraphValidationError(f"Unknown block type: {b.type}")

    # v0.2: require exactly one source block
    source_ids: List[str] = []
    for b in spec.blocks:
        inst = reg.get(b.type)()
        if bool(getattr(inst, "is_source", False)):
            source_ids.append(b.id)

    if len(source_ids) != 1:
        raise GraphValidationError("Graph must contain exactly one source block")

    source_id = source_ids[0]

    # Validate edges: ports exist and types match
    for e in spec.edges:
        if e.src_block not in block_ids or e.dst_block not in block_ids:
            raise GraphValidationError("Edge references missing block")

        if e.dst_block == source_id:
            raise GraphValidationError("Edges into the source block are not supported")

        sb = next(b for b in spec.blocks if b.id == e.src_block)
        db = next(b for b in spec.blocks if b.id == e.dst_block)
        sdef = reg.get(sb.type)()
        ddef = reg.get(db.type)()

        sout = sdef.output_ports().get(e.src_port)
        din = ddef.input_ports().get(e.dst_port)
        if sout is None:
            raise GraphValidationError(f"Missing src port: {e.src_block}.{e.src_port}")
        if din is None:
            raise GraphValidationError(f"Missing dst port: {e.dst_block}.{e.dst_port}")
        if sout != din:
            raise GraphValidationError(
                f"Type mismatch: {e.src_block}.{e.src_port} ({sout}) -> {e.dst_block}.{e.dst_port} ({din})"
            )

    # v0.1: forbid cycles (single clock domain, no feedback)
    # Simple DFS on block graph
    adj: Dict[str, List[str]] = {b.id: [] for b in spec.blocks}
    for e in spec.edges:
        adj[e.src_block].append(e.dst_block)

    temp = set()
    perm = set()

    def visit(n: str) -> None:
        if n in perm:
            return
        if n in temp:
            raise GraphValidationError("Cycle detected (feedback not supported in v0.1)")
        temp.add(n)
        for m in adj.get(n, []):
            visit(m)
        temp.remove(n)
        perm.add(n)

    for b in spec.blocks:
        visit(b.id)

    return ValidatedGraph(graph=spec)
