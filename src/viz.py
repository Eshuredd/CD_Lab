from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set

from parser.ast import ASTNode, Program
from ir.ir import IRProgram, IRFunction, Instruction, is_label


def _escape_label(s: str) -> str:
    """Just prepares a Python string so Graphviz can show it nicely."""
    return (
        str(s)
        .replace("\\", "\\\\")
        .replace("\"", "\\\"")
        .replace("\n", "\\n")
    )


def ast_to_dot(program: Program) -> str:
    """Takes the full AST and converts it into a DOT graph description."""

    lines: List[str] = [
        "digraph AST {",
        "  node [shape=box, fontname=\"Courier\"];",
        "  rankdir=TB;",
    ]

    next_id = 0

    def new_id() -> str:
        nonlocal next_id
        nid = f"n{next_id}"
        next_id += 1
        return nid

    def node_label(node: ASTNode) -> str:
        cls = node.__class__.__name__
        # try to show some main fields in the node label if present
        important_fields = []
        for key in ("name", "op", "value", "kind"):
            if hasattr(node, key):
                important_fields.append(f"{key}={getattr(node, key)!r}")
        if important_fields:
            return _escape_label(cls + "\\n" + ", ".join(important_fields))
        return _escape_label(cls)

    def visit(node: ASTNode, parent_id: Optional[str], field_name: Optional[str]) -> str:
        nid = new_id()
        lines.append(f"  {nid} [label=\"{node_label(node)}\"];")
        if parent_id is not None:
            if field_name:
                lines.append(
                    f"  {parent_id} -> {nid} [label=\"{_escape_label(field_name)}\"];"
                )
            else:
                lines.append(f"  {parent_id} -> {nid};")

        for key, value in getattr(node, "__dict__", {}).items():
            if isinstance(value, ASTNode):
                visit(value, nid, key)
            elif isinstance(value, list):
                for idx, elem in enumerate(value):
                    if isinstance(elem, ASTNode):
                        visit(elem, nid, f"{key}[{idx}]")
        return nid

    if isinstance(program, Program):
        visit(program, None, None)

    lines.append("}")
    return "\n".join(lines)


# CFG to DOT

@dataclass
class BasicBlock:
    name: str
    start_idx: int
    end_idx: int
    instructions: List[Instruction]
    successors: List[str]


def _build_basic_blocks(func: IRFunction) -> Dict[str, BasicBlock]:
    insns = func.instructions
    if not insns:
        return {}

    label_to_idx: Dict[str, int] = {}
    for i, insn in enumerate(insns):
        if insn.op == "LABEL":
            label_to_idx[insn.args[0]] = i

    leaders: Set[int] = {0}

    for i, insn in enumerate(insns):
        op = insn.op
        if op == "LABEL":
            leaders.add(i)
        if op in ("JMP", "JMP_IF", "JMP_IF_NOT"):
            target_label = insn.args[-1]
            if target_label in label_to_idx:
                leaders.add(label_to_idx[target_label])
            if i + 1 < len(insns):
                leaders.add(i + 1)

    sorted_leaders = sorted(leaders)
    idx_to_block_name: Dict[int, str] = {}
    blocks: Dict[str, BasicBlock] = {}

    for bi, start in enumerate(sorted_leaders):
        end = (
            sorted_leaders[bi + 1]
            if bi + 1 < len(sorted_leaders)
            else len(insns)
        )
        name = f"{func.name}_B{bi}"
        idx_to_block_name[start] = name
        block_insns = insns[start:end]
        blocks[name] = BasicBlock(
            name=name,
            start_idx=start,
            end_idx=end,
            instructions=block_insns,
            successors=[],
        )

    starts = sorted(idx_to_block_name.keys())
    start_to_next_block_name: Dict[int, Optional[str]] = {}
    for i, s in enumerate(starts):
        nxt = starts[i + 1] if i + 1 < len(starts) else None
        start_to_next_block_name[s] = idx_to_block_name.get(nxt) if nxt is not None else None

    for start, block_name in idx_to_block_name.items():
        block = blocks[block_name]
        if not block.instructions:
            continue
        last = block.instructions[-1]
        op, args = last.op, last.args

        if op == "JMP":
            target = args[0]
            if target in label_to_idx:
                succ_block = idx_to_block_name.get(label_to_idx[target])
                if succ_block:
                    block.successors.append(succ_block)
        elif op in ("JMP_IF", "JMP_IF_NOT"):
            cond, target = args[0], args[1]
            if target in label_to_idx:
                succ_block = idx_to_block_name.get(label_to_idx[target])
                if succ_block:
                    block.successors.append(succ_block)
            fall_through = start_to_next_block_name.get(start)
            if fall_through:
                block.successors.append(fall_through)
        elif op in ("RET", "EXIT"):
            pass
        else:
            fall_through = start_to_next_block_name.get(start)
            if fall_through:
                block.successors.append(fall_through)

    return blocks

def ir_linear_to_dot(program: IRProgram) -> str:
    """
    Render the linear IR as a DOT graph where each instruction is a node and
    edges represent execution order (with jumps to labels).
    """
    lines: List[str] = [
        "digraph IR {",
        "  node [shape=box, fontname=\"Courier\"];",
        "  rankdir=TB;",
    ]

    for func in program.functions:
        lines.append(f"  subgraph \"cluster_{func.name}\" {{")
        lines.append(f"    label=\"{_escape_label(func.name)}\";")

        insns = func.instructions
        label_to_idx: Dict[str, int] = {}
        for i, insn in enumerate(insns):
            if insn.op == "LABEL":
                label_to_idx[insn.args[0]] = i

        # Nodes
        for i, insn in enumerate(insns):
            node_name = f"{func.name}_{i}"
            label = _escape_label(f"{i}: {insn!r}")
            lines.append(f"    \"{node_name}\" [label=\"{label}\"];")

        for i, insn in enumerate(insns):
            node_name = f"{func.name}_{i}"
            op, args = insn.op, insn.args

            if op not in ("JMP", "RET", "EXIT") and i + 1 < len(insns):
                next_name = f"{func.name}_{i + 1}"
                lines.append(f"    \"{node_name}\" -> \"{next_name}\";")

            if op == "JMP":
                target = args[0]
                if target in label_to_idx:
                    target_name = f"{func.name}_{label_to_idx[target]}"
                    lines.append(f"    \"{node_name}\" -> \"{target_name}\" [color=\"blue\"];")
            elif op in ("JMP_IF", "JMP_IF_NOT"):
                target = args[1]
                if target in label_to_idx:
                    target_name = f"{func.name}_{label_to_idx[target]}"
                    lines.append(
                        f"    \"{node_name}\" -> \"{target_name}\" [color=\"red\", style=\"dashed\"];"
                    )

        lines.append("  }")

    lines.append("}")
    return "\n".join(lines)

