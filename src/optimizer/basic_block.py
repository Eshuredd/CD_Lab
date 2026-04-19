"""Basic-block optimization on the linear IR.

The pass builds an explicit control-flow graph of basic blocks for each
function and applies three classic block-level transformations until a
fixed point:

  1. Jump threading through empty blocks
       LABEL B ; JMP C        any branch whose target is B is redirected
                              straight to C.  Chains B -> C -> D -> ... are
                              followed to the final non-empty target.

  2. Unreachable basic-block elimination
       Blocks not reachable from the function entry block are removed
       entirely.  The entry block (which carries FUNC_ENTRY) is always
       kept.

  3. Linear chain merging
       If block A ends with `JMP B`, B has exactly one predecessor (A),
       and B is not the entry block, then B is merged into A: A's `JMP`
       and B's leading `LABEL` are dropped and B's instructions are
       appended to A.

The surviving blocks are then concatenated back into the linear IR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from ir.ir import Instruction, IRFunction, IRProgram


@dataclass
class _Block:
    name: str
    insns: List[Instruction] = field(default_factory=list)
    succs: List[str] = field(default_factory=list)
    preds: List[str] = field(default_factory=list)


def _split_blocks(func: IRFunction) -> List[_Block]:
    """Split a function's instruction list into basic blocks."""
    insns = func.instructions
    if not insns:
        return []

    label_to_idx: Dict[str, int] = {}
    for i, ins in enumerate(insns):
        if ins.op == "LABEL":
            label_to_idx[ins.args[0]] = i

    leaders = {0}
    for i, ins in enumerate(insns):
        op = ins.op
        if op == "LABEL":
            leaders.add(i)
        if op in ("JMP", "JMP_IF", "JMP_IF_NOT"):
            tgt = ins.args[-1]
            if tgt in label_to_idx:
                leaders.add(label_to_idx[tgt])
            if i + 1 < len(insns):
                leaders.add(i + 1)
        elif op in ("RET", "EXIT") and i + 1 < len(insns):
            leaders.add(i + 1)

    sorted_leaders = sorted(leaders)
    blocks: List[_Block] = []
    for bi, start in enumerate(sorted_leaders):
        end = sorted_leaders[bi + 1] if bi + 1 < len(sorted_leaders) else len(insns)
        bi_insns = [Instruction(ins.op, list(ins.args)) for ins in insns[start:end]]
        if bi_insns and bi_insns[0].op == "LABEL":
            name = bi_insns[0].args[0]
        elif bi == 0:
            name = "_entry"
        else:
            name = f"_b{bi}"
        blocks.append(_Block(name=name, insns=bi_insns))
    return blocks


def _recompute_cfg(blocks: List[_Block]) -> None:
    """Rebuild successor and predecessor lists from the current block bodies."""
    n2b = {b.name: b for b in blocks}
    for b in blocks:
        b.succs = []
        b.preds = []

    for i, b in enumerate(blocks):
        fall = blocks[i + 1].name if i + 1 < len(blocks) else None
        if not b.insns:
            if fall:
                b.succs.append(fall)
            continue
        last = b.insns[-1]
        op = last.op
        if op == "JMP":
            tgt = last.args[0]
            if tgt in n2b:
                b.succs.append(tgt)
        elif op in ("JMP_IF", "JMP_IF_NOT"):
            tgt = last.args[1]
            if tgt in n2b:
                b.succs.append(tgt)
            if fall:
                b.succs.append(fall)
        elif op in ("RET", "EXIT"):
            pass
        else:
            if fall:
                b.succs.append(fall)

    for b in blocks:
        for s in b.succs:
            n2b[s].preds.append(b.name)


def _empty_jmp_target(b: _Block) -> str | None:
    """If `b` is exactly `LABEL ; JMP X`, return X; else None."""
    if len(b.insns) == 2 and b.insns[0].op == "LABEL" and b.insns[1].op == "JMP":
        return b.insns[1].args[0]
    return None


def _jump_thread(blocks: List[_Block]) -> int:
    """Redirect branches whose target is an empty `LABEL ; JMP X` block."""
    redirect: Dict[str, str] = {}
    for b in blocks:
        tgt = _empty_jmp_target(b)
        if tgt is not None and tgt != b.name:
            redirect[b.name] = tgt

    if not redirect:
        return 0

    def resolve(name: str) -> str:
        seen: set[str] = set()
        while name in redirect and name not in seen:
            seen.add(name)
            name = redirect[name]
        return name

    changes = 0
    for b in blocks:
        if not b.insns:
            continue
        last = b.insns[-1]
        if last.op == "JMP":
            old = last.args[0]
            new = resolve(old)
            if new != old:
                last.args[0] = new
                changes += 1
        elif last.op in ("JMP_IF", "JMP_IF_NOT"):
            old = last.args[1]
            new = resolve(old)
            if new != old:
                last.args[1] = new
                changes += 1
    return changes


def _drop_unreachable(blocks: List[_Block]) -> Tuple[List[_Block], int]:
    """Remove blocks not reachable from the entry block (kept first)."""
    if not blocks:
        return blocks, 0
    n2b = {b.name: b for b in blocks}
    entry = blocks[0].name
    seen: set[str] = set()
    stack = [entry]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        b = n2b.get(n)
        if b is None:
            continue
        for s in b.succs:
            stack.append(s)
    new_blocks = [b for b in blocks if b.name in seen]
    removed = len(blocks) - len(new_blocks)
    return new_blocks, removed


def _merge_linear_chains(blocks: List[_Block]) -> Tuple[List[_Block], int]:
    """Merge `A: ... JMP B` into A when B has only A as a predecessor."""
    if not blocks:
        return blocks, 0
    n2b = {b.name: b for b in blocks}
    entry = blocks[0].name
    merges = 0
    changed = True
    while changed:
        changed = False
        for a in blocks:
            if not a.insns:
                continue
            last = a.insns[-1]
            if last.op != "JMP":
                continue
            tgt = last.args[0]
            if tgt == entry or tgt not in n2b:
                continue
            b = n2b[tgt]
            if len(b.preds) != 1 or b.preds[0] != a.name:
                continue
            b_body = (
                b.insns[1:]
                if b.insns and b.insns[0].op == "LABEL"
                else list(b.insns)
            )
            a.insns = a.insns[:-1] + b_body
            a.succs = list(b.succs)
            for s in b.succs:
                sb = n2b.get(s)
                if sb is None:
                    continue
                sb.preds = [a.name if p == b.name else p for p in sb.preds]
            blocks = [x for x in blocks if x.name != b.name]
            del n2b[b.name]
            merges += 1
            changed = True
            break
    return blocks, merges


def _bb_func(func: IRFunction) -> Tuple[IRFunction, Dict[str, int]]:
    blocks = _split_blocks(func)
    threaded = unreachable = merged = 0

    while True:
        _recompute_cfg(blocks)
        t = _jump_thread(blocks)
        if t:
            _recompute_cfg(blocks)

        blocks, u = _drop_unreachable(blocks)
        if u:
            _recompute_cfg(blocks)

        blocks, m = _merge_linear_chains(blocks)

        threaded += t
        unreachable += u
        merged += m
        if t == 0 and u == 0 and m == 0:
            break

    new_insns: List[Instruction] = []
    for b in blocks:
        new_insns.extend(b.insns)

    stats = {
        "jump_threaded": threaded,
        "blocks_removed": unreachable,
        "blocks_merged": merged,
    }
    return (
        IRFunction(
            func.name,
            func.return_type,
            func.param_names,
            func.param_types,
            new_insns,
        ),
        stats,
    )


class BasicBlockOptResult:
    def __init__(
        self, program: IRProgram, per: Dict[str, Dict[str, int]]
    ) -> None:
        self.program = program
        self.stats_per_function = per

    @property
    def total_changes(self) -> int:
        return sum(sum(s.values()) for s in self.stats_per_function.values())

    def summary(self) -> str:
        lines = ["Basic-block Optimization Pass:"]
        for fn, s in self.stats_per_function.items():
            lines.append(
                f"  {fn}: threaded={s['jump_threaded']}, "
                f"blocks_removed={s['blocks_removed']}, "
                f"blocks_merged={s['blocks_merged']}"
            )
        lines.append(f"  Total: {self.total_changes} CFG-level change(s)")
        return "\n".join(lines)


def basic_block_opt(program: IRProgram) -> BasicBlockOptResult:
    funcs: List[IRFunction] = []
    per: Dict[str, Dict[str, int]] = {}
    for fn in program.functions:
        nf, s = _bb_func(fn)
        funcs.append(nf)
        per[fn.name] = s
    return BasicBlockOptResult(IRProgram(funcs), per)
