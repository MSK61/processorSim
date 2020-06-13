# -*- coding: utf-8 -*-

"""simulation services"""

############################################################
#
# Copyright 2017, 2019, 2020 Mohammed El-Afifi
# This file is part of processorSim.
#
# processorSim is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# processorSim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with processorSim.  If not, see
# <http://www.gnu.org/licenses/>.
#
# program:      processor simulator
#
# file:         sim_services.py
#
# function:     program execution simulation services
#
# description:  simulates program execution
#
# author:       Mohammed El-Afifi (ME)
#
# environment:  Visual Studdio Code 1.46.0, python 3.8.3, Fedora release
#               32 (Thirty Two)
#
# notes:        This is a private program.
#
############################################################

import collections
import copy
import enum
from enum import auto
import heapq
import itertools
from itertools import chain
import string
import typing
from typing import cast, Dict, Iterable, Iterator, List, Mapping, \
    MutableMapping, MutableSequence, Sequence, Tuple

import attr
import more_itertools
from more_itertools import first_true

from container_utils import BagValDict
from processor_utils import ProcessorDesc
import processor_utils.units
from processor_utils.units import FuncUnit, LockInfo, UnitModel
from program_defs import HwInstruction
from reg_access import AccessType, RegAccessQueue, RegAccQBuilder
from str_utils import ICaseString
_T = typing.TypeVar("_T")


class StallError(RuntimeError):

    """Stalled processor error"""

    def __init__(self, msg_tmpl: str, stalled_state: object) -> None:
        """Create a stalled processor error.

        `self` is this stalled processor error.
        `msg_tmpl` is the error message format taking the stalled
                   processor state as a positional argument.
        `stalled_state` is the stalled processor state.

        """
        RuntimeError.__init__(self, string.Template(msg_tmpl).substitute(
            {self.STATE_KEY: stalled_state}))
        self._stalled_state = stalled_state

    @property
    def processor_state(self) -> object:
        """Stalled processor state

        `self` is this stalled processor error.

        """
        return self._stalled_state

    STATE_KEY = "state"  # parameter key in message format


@attr.s(frozen=True)
class HwSpec:

    """Hardware specification"""

    processor_desc: ProcessorDesc = attr.ib()

    name_unit_map: Dict[ICaseString, UnitModel] = attr.ib(init=False)

    @name_unit_map.default
    def _(self) -> Dict[ICaseString, UnitModel]:
        """Build the name-to-unit mapping.

        `self` is this hardware specification.

        """
        # pylint: disable=no-member
        models = chain(
            self.processor_desc.in_ports, self.processor_desc.in_out_ports,
            map(lambda func_unit: func_unit.model,
                chain(self.processor_desc.out_ports,
                      self.processor_desc.internal_units)))
        return {unit.name: unit for unit in models}


class StallState(enum.Enum):

    """Instruction stalling state"""

    NO_STALL = auto()

    STRUCTURAL = auto()

    DATA = auto()


@attr.s
class InstrState:

    """Instruction state"""

    instr: int = attr.ib()

    stalled: StallState = attr.ib(default=StallState.NO_STALL)


def simulate(program: Sequence[HwInstruction], hw_info: HwSpec) -> List[
        BagValDict[ICaseString, InstrState]]:
    """Run the given program on the processor.

    `program` is the program to run.
    `hw_info` is the processor information.
    The function returns the pipeline diagram.

    """
    util_tbl: List[BagValDict[ICaseString, InstrState]] = []
    acc_queues = _build_acc_plan(enumerate(program))
    issue_rec = _IssueInfo()
    prog_len = len(program)

    while issue_rec.entered < prog_len or issue_rec.in_flight:
        _run_cycle(program, acc_queues, hw_info, util_tbl, issue_rec)

    return util_tbl


@attr.s
class _AcceptStatus:

    """Instruction acceptance status"""

    accepted: bool = attr.ib(default=True, init=False)

    mem_used: bool = attr.ib()


@attr.s(auto_attribs=True, frozen=True)
class _HostedInstr:

    """Instruction hosted inside a functional unit"""

    host: ICaseString

    index_in_host: int


@attr.s
class _InstrMovStatus:

    """Status of moving instructions"""

    moved: int = attr.ib(default=0, init=False)

    mem_used: bool = attr.ib(default=True, init=False)


class _IssueInfo:

    """Instruction issue information record"""

    def __init__(self) -> None:
        """Create an issue information record.

        `self` is this issue information record.

        """
        self._entered = 0
        self._exited = 0

    def bump_input(self) -> None:
        """Increment the entered instructions index.

        `self` is this issue information record.

        """
        self._entered += 1

    def pump_outputs(self, outputs: int) -> None:
        """Pump outputs out of the pipeline.

        `self` is this issue information record.
        `outputs` is the number of outputs to pump out of the pipeline.

        """
        self._exited += outputs

    @property
    def entered(self) -> int:
        """Instruction index

        `self` is this issue information record.

        """
        return self._entered

    @property
    def in_flight(self) -> bool:
        """True if there're in-flight instructions, otherwise False

        `self` is this issue information record.

        """
        return self._exited < self._entered


@attr.s(auto_attribs=True, frozen=True)
class _RegAvailState:

    """Registers availability state"""

    avail: bool

    regs: Iterable[ICaseString]


@attr.s(auto_attribs=True, frozen=True)
class _TransitionUtil:

    """Utilization transition of a single unit between two pulses"""

    old_util: typing.Collection[InstrState]

    new_util: Iterable[InstrState]


def _accept_instr(issue_rec: _IssueInfo, inputs: Iterable[UnitModel],
                  util_info: BagValDict[ICaseString, InstrState],
                  accept_res: _AcceptStatus) -> None:
    """Try to accept the next instruction to the unit.

    `issue_rec` is the issue record.
    `inputs` are the input processing units to select from for issuing
             the instruction.
    `util_info` is the unit utilization information.
    `accept_res` is the instruction acceptance result.
    The function tries to find an appropriate unit to issue the
    instruction to. It then updates the utilization information.

    """
    acceptor = first_true(inputs, pred=lambda unit:
                          not (accept_res.mem_used and unit.mem_access) and
                          _space_avail(unit, util_info))
    accept_res.accepted = cast(bool, acceptor)

    if acceptor:
        _issue_instr(util_info[acceptor.name], acceptor.mem_access, issue_rec,
                     accept_res)


def _add_access(instr: HwInstruction, instr_index: int,
                builders: Mapping[object, RegAccQBuilder]) -> None:
    """Append the instruction access to the given plan.

    `instr` is the instruction to append whose access to the access
            plan.
    `instr_index` is the instruction index.
    `builders` are the registry access plan builders.

    """
    _add_rd_access(instr_index, builders, instr.sources)
    _add_wr_access(instr_index, builders[instr.destination])


def _add_rd_access(instr: int, builders: Mapping[object, RegAccQBuilder],
                   registers: Iterable[object]) -> None:
    """Register the read access of the given registers.

    `instr` is the instruction index.
    `builders` are the registry access plan builders.
    `registers` are the registers which will be read-accessed.

    """
    for reg in registers:
        builders[reg].append(AccessType.READ, instr)


def _add_wr_access(instr: int, builder: RegAccQBuilder) -> None:
    """Register the write access of the given instruction.

    `instr` is the instruction index.
    `builder` is the access plan builder.

    """
    builder.append(AccessType.WRITE, instr)


def _build_acc_plan(program: Iterable[Tuple[int, HwInstruction]]) -> Dict[
        object, RegAccessQueue]:
    """Build the registry access plan through the program lifetime.

    `program` is the program to build a registry access plan for.
    The function returns the registry access plan.

    """
    builders: typing.DefaultDict[
        object, RegAccQBuilder] = collections.defaultdict(RegAccQBuilder)

    for instr_index, instr in program:
        _add_access(instr, instr_index, builders)

    return {reg: builder.create() for reg, builder in builders.items()}


def _build_cap_map(inputs: Iterable[UnitModel]) -> Dict[
        object, List[UnitModel]]:
    """Build the capability map for input units.

    `inputs` are the input processing units.

    """
    cap_map: Dict[object, List[UnitModel]] = {}

    for unit in inputs:
        for cap in unit.capabilities:
            cap_map.setdefault(cap, []).append(unit)

    return cap_map


def _calc_unstalled(instructions: Iterable[InstrState]) -> int:
    """Count the number of unstalled instructions.

    `instructions` are the list of instructions to count unstalled ones
                   in.

    """
    return more_itertools.quantify(
        instructions, lambda instr: instr.stalled == StallState.NO_STALL)


def _chk_data_stall(
        unit_locks: LockInfo, instr_index: object, instr: HwInstruction,
        acc_queues: Mapping[object, RegAccessQueue], reqs_to_clear:
        MutableMapping[ICaseString, MutableSequence[object]]) -> StallState:
    """Check if the instruction should have a data stall.

    `unit_locks` are the unit lock information.
    `instr_index` is the index of the instruction to check whose data
                  stall status.
    `instr` is the instruction to check whose data stall status.
    `acc_queues` are the planned access queues for registers.
    `reqs_to_clear` are the requests to be cleared from the access
                    queues.

    """
    avail_state = _regs_avail(unit_locks, instr_index, instr, acc_queues)

    if not avail_state.avail:
        return StallState.DATA

    _update_clears(reqs_to_clear, avail_state.regs, instr_index)
    return StallState.NO_STALL


def _chk_full_stall(
        old_util: object, new_util: object, util_tbl: object) -> None:
    """Check if the whole processor has stalled.

    `old_util` is the utilization information of the previous clock
               pulse.
    `new_util` is the utilization information of the current clock
               pulse.
    `util_tbl` is the utilization table.
    The function analyzes old and new utilization information and throws
    a StallError if a full stall is detected.

    """
    if new_util == old_util:
        raise StallError(
            f"Processor stalled with utilization ${StallError.STATE_KEY}",
            util_tbl)


def _chk_hazards(old_util: BagValDict[_T, InstrState], new_util:
                 Iterable[Tuple[_T, Iterable[InstrState]]], name_unit_map:
                 Mapping[_T, UnitModel], program: Sequence[HwInstruction],
                 acc_queues: Mapping[object, RegAccessQueue]) -> None:
    """Check different types of hazards.

    `old_util` is the utilization information of the previous clock
               pulse.
    `new_util` is the utilization information of the current clock
               pulse.
    `name_unit_map` is the name-to-unit mapping.
    `program` is the master instruction list.
    `acc_queues` are the planned access queues for registers.
    The function analyzes old and new utilization information and marks
    stalled instructions appropriately according to idientified hazards.

    """
    reqs_to_clear: Dict[ICaseString, MutableSequence[object]] = {}

    for unit, new_unit_util in new_util:
        _stall_unit(name_unit_map[unit].lock_info, _TransitionUtil(
            old_util[unit], new_unit_util), program, acc_queues, reqs_to_clear)

    items_to_clear = reqs_to_clear.items()

    for reg, req_lst in items_to_clear:
        for cur_req in req_lst:
            acc_queues[reg].dequeue(cur_req)


def _chk_avail_regs(
        avail_regs: MutableSequence[Sequence[ICaseString]],
        acc_queues: Mapping[object, RegAccessQueue], lock: bool,
        new_regs: Sequence[ICaseString], req_params: Iterable[object]) -> bool:
    """Check if the given registers can be accessed.

    `avail_regs` are the list of available registers.
    `lock` is the locking flag.
    `new_regs` are the potential registers to be added to the available
               registers list.
    `acc_queues` are the planned access queues for registers.
    `req_params` are the request parameters.

    """
    if not lock:
        return True

    if not all(acc_queues[reg].can_access(*req_params) for reg in new_regs):
        return False

    avail_regs.append(new_regs)
    return True


def _clr_src_units(instructions: Iterable[_HostedInstr],
                   util_info: BagValDict[ICaseString, _T]) -> None:
    """Clear the utilization of units releasing instructions.

    `instructions` is the information of instructions being moved from
                   one unit to a predecessor, sorted by their program
                   index.
    `util_info` is the unit utilization information.
    The function clears the utilization information of units from which
    instructions were moved to predecessor units.

    """
    for cur_instr in instructions:
        del util_info[cur_instr.host][cur_instr.index_in_host]


def _count_outputs(outputs: Iterable[UnitModel],
                   util_info: BagValDict[ICaseString, InstrState]) -> int:
    """Count the number of unstalled outputs.

    `outputs` are all the output units.
    `util_info` is the unit utilization information.

    """
    return sum(
        _calc_unstalled(util_info[out_port.name]) for out_port in outputs)


def _fill_cp_util(
        processor: ProcessorDesc, program: Sequence[HwInstruction], util_info:
        BagValDict[ICaseString, InstrState], issue_rec: _IssueInfo) -> None:
    """Calculate the utilization of a new clock pulse.

    `processor` is the processor to fill the utilization of whose units
                at the current clock pulse.
    `program` is the program to execute.
    `util_info` is the unit utilization information to fill.
    `issue_rec` is the issue record.

    """
    _flush_outputs(_get_out_ports(processor), util_info)
    in_units = chain(processor.in_out_ports, processor.in_ports)
    _fill_inputs(_build_cap_map(processor_utils.units.sorted_models(in_units)),
                 program, util_info, _mov_flights(
                     chain(processor.out_ports, processor.internal_units),
                     program, util_info), issue_rec)


def _fill_inputs(
        cap_unit_map: Mapping[object, Iterable[UnitModel]], program: Sequence[
            HwInstruction], util_info: BagValDict[ICaseString, InstrState],
        mem_busy: bool, issue_rec: _IssueInfo) -> None:
    """Fetch new program instructions into the pipeline.

    `cap_unit_map` is the mapping between capabilities and units.
    `program` is the program to fill the input units from whose
              instructions.
    `util_info` is the unit utilization information.
    `mem_busy` is the memory busy flag.
    `issue_rec` is the issue record.

    """
    prog_len = len(program)
    accept_res = _AcceptStatus(mem_busy)

    while issue_rec.entered < prog_len and accept_res.accepted:
        _accept_instr(issue_rec, cap_unit_map.get(
            program[issue_rec.entered].categ, []), util_info, accept_res)


def _fill_unit(unit: FuncUnit, program: Sequence[HwInstruction],
               util_info: BagValDict[ICaseString, InstrState]) -> bool:
    """Fill an output with instructions from its predecessors.

    `unit` is the destination unit to fill.
    `program` is the master instruction list.
    `util_info` is the unit utilization information.
    The function returns a flag indicating if a memory access is
    currently in progess.

    """
    candidates = _get_candidates(unit, program, util_info)
    # instructions sorted by program index
    mov_res = _mov_candidates(candidates, unit.model, util_info)
    # Need to sort instructions by their index in the host in a
    # descending order.
    _clr_src_units(
        sorted(itertools.islice(candidates, mov_res.moved), key=lambda candid:
               candid.index_in_host, reverse=True), util_info)
    return mov_res.mem_used


def _flush_output(out_instr_lst: MutableSequence[InstrState]) -> None:
    """Flush the output unit in preparation for a new cycle.

    `out_instr_lst` is the list of instructions in the output unit.

    """
    instr_indices = more_itertools.rlocate(
        out_instr_lst, lambda instr: instr.stalled == StallState.NO_STALL)

    for instr_index in instr_indices:
        del out_instr_lst[instr_index]


def _flush_outputs(out_units: Iterable[UnitModel],
                   util_info: BagValDict[ICaseString, InstrState]) -> None:
    """Flush output units in preparation for a new cycle.

    `out_units` are the output processing units.
    `util_info` is the unit utilization information.

    """
    for cur_out in out_units:
        _flush_output(util_info[cur_out.name])


def _get_candidates(
        unit: FuncUnit, program: Sequence[HwInstruction],
        util_info: BagValDict[ICaseString, InstrState]) -> List[_HostedInstr]:
    """Find candidate instructions in the predecessors of a unit.

    `unit` is the unit to match instructions from predecessors against.
    `program` is the master instruction list.
    `util_info` is the unit utilization information.

    """
    candidates = (_get_new_guests(pred.name, more_itertools.locate(util_info[
        pred.name], lambda instr: instr.stalled != StallState.DATA and program[
            instr.instr].categ in unit.model.capabilities)) for pred in
                  unit.predecessors if pred.name in util_info)
    return heapq.nsmallest(
        _space_avail(unit.model, util_info), chain.from_iterable(candidates),
        key=lambda instr_info:
        util_info[instr_info.host][instr_info.index_in_host].instr)


def _get_new_guests(src_unit: ICaseString,
                    instructions: Iterable[int]) -> Iterator[_HostedInstr]:
    """Prepare new hosted instructions.

    `src_unit` is the old host of instructions.
    `instructions` are the new instructions to be hosted.

    """
    return map(lambda instr: _HostedInstr(src_unit, instr), instructions)


def _get_out_ports(processor: ProcessorDesc) -> "chain[UnitModel]":
    """Find all units at the processor output boundary.

    `processor` is the processor to find whose output ports.
    The function returns an iterable over all ports at the output
    boundary.

    """
    return chain(processor.in_out_ports,
                 map(lambda port: port.model, processor.out_ports))


def _issue_instr(instr_lst: MutableSequence[InstrState], mem_access: bool,
                 issue_rec: _IssueInfo, accept_res: _AcceptStatus) -> None:
    """Issue the next instruction to the issue list.

    `instr_lst` is the list of hosted instructions in  a unit.
    `mem_access` is the hosting unit memory access flag.
    `issue_rec` is the issue record.
    `accept_res` is the instruction acceptance result.

    """
    instr_lst.append(InstrState(issue_rec.entered))
    issue_rec.bump_input()

    if mem_access:
        accept_res.mem_used = True


def _mov_candidate(candidate: InstrState, unit_util:
                   MutableSequence[InstrState], mem_access: bool) -> bool:
    """Move a candidate instruction between units.

    `candidate` is the candidate instruction to move.
    `unit_util` is the unit utilization information.
    `mem_access` is the unit memory access flag.

    """
    candidate.stalled = StallState.NO_STALL
    unit_util.append(candidate)
    return mem_access


def _mov_candidates(
        candidates: Iterable[_HostedInstr], unit: UnitModel,
        util_info: BagValDict[ICaseString, InstrState]) -> _InstrMovStatus:
    """Move candidate instructions between units.

    `candidates` are the candidate instructions to move.
    `unit` is the destination unit.
    `util_info` is the unit utilization information.

    """
    candid_seq = enumerate(candidates, 1)
    mov_res = _InstrMovStatus()

    for mov_res.moved, cur_candid in candid_seq:
        if _mov_candidate(util_info[cur_candid.host][cur_candid.index_in_host],
                          util_info[unit.name], unit.mem_access):
            return mov_res

    mov_res.mem_used = False
    return mov_res


def _mov_flights(
        dst_units: Iterable[FuncUnit], program: Sequence[HwInstruction],
        util_info: BagValDict[ICaseString, InstrState]) -> bool:
    """Move the instructions inside the pipeline.

    `dst_units` are the destination processing units.
    `program` is the master instruction list.
    `util_info` is the unit utilization information.
    The function returns a flag indicating if a memory access is
    currently in progess.

    """
    mem_busy = False

    for cur_dst in dst_units:
        if (not mem_busy or not cur_dst.model.mem_access) and _fill_unit(
                cur_dst, program, util_info):
            mem_busy = True

    return mem_busy


def _regs_avail(
        unit_locks: LockInfo, instr_index: object, instr: HwInstruction,
        acc_queues: Mapping[object, RegAccessQueue]) -> _RegAvailState:
    """Check if all needed registers can be accessed.

    `unit_locks` are the unit lock information.
    `instr_index` is the index of the instruction to check whose access
                  to registers.
    `instr` is the instruction to check whose access to registers.
    `acc_queues` are the planned access queues for registers.
    The function returns the registers availability state.

    """
    avail_reg_lists: List[Sequence[ICaseString]] = []
    return _RegAvailState(True, chain.from_iterable(avail_reg_lists)) if all(
        _chk_avail_regs(avail_reg_lists, acc_queues, *chk_params) for
        chk_params in
        [(unit_locks.rd_lock, instr.sources, [AccessType.READ, instr_index]),
         (unit_locks.wr_lock, [instr.destination],
          [AccessType.WRITE, instr_index])]) else _RegAvailState(False, [])


def _regs_loaded(old_unit_util: Iterable[InstrState], instr: object) -> bool:
    """Check if the registers were previously loaded.

    `old_unit_util` is the unit utilization information of the previous
                    clock pulse.
    `instr` is the index of the instruction whose registers are to be
            checked for being previously loaded.

    """
    return cast(bool, first_true(
        old_unit_util, pred=lambda old_instr:
        old_instr.instr == instr and old_instr.stalled != StallState.DATA))


def _run_cycle(program: Sequence[HwInstruction],
               acc_queues: Mapping[object, RegAccessQueue], hw_info: HwSpec,
               util_tbl: MutableSequence[BagValDict[ICaseString, InstrState]],
               issue_rec: _IssueInfo) -> None:
    """Run a single clock cycle.

    `program` is the program to run whose instructions.
    `acc_queues` are the planned access queues for registers.
    `hw_info` is the processor information.
    `util_tbl` is the utilization table.
    `issue_rec` is the issue record.

    """
    old_util = util_tbl[-1] if util_tbl else BagValDict()
    cp_util = copy.deepcopy(old_util)
    _fill_cp_util(hw_info.processor_desc, program, cp_util, issue_rec)
    _chk_hazards(
        old_util, cp_util.items(), hw_info.name_unit_map, program, acc_queues)
    _chk_full_stall(old_util, cp_util, util_tbl)
    issue_rec.pump_outputs(
        _count_outputs(_get_out_ports(hw_info.processor_desc), cp_util))
    util_tbl.append(cp_util)


def _space_avail(
        unit: UnitModel, util_info: BagValDict[ICaseString, _T]) -> int:
    """Calculate the free space for receiving instructions in the unit.

    `unit` is the unit to test whose free space.
    `util_info` is the unit utilization information.

    """
    return unit.width - len(util_info[unit.name])


def _stall_unit(unit_locks: LockInfo, trans_util: _TransitionUtil,
                program: Sequence[HwInstruction],
                acc_queues: Mapping[object, RegAccessQueue], reqs_to_clear:
                MutableMapping[ICaseString, MutableSequence[object]]) -> None:
    """Mark instructions in the given unit as stalled as needed.

    `unit_locks` are the unit lock information.
    `trans_util` is the unit utilization transition information of the
                 current and previous clock pulses.
    `program` is the master instruction list.
    `acc_queues` are the planned access queues for registers.
    `reqs_to_clear` are the requests to be cleared from the access
                    queues.

    """
    for instr in trans_util.new_util:
        instr.stalled = StallState.STRUCTURAL if _regs_loaded(
            trans_util.old_util, instr.instr) else _chk_data_stall(
                unit_locks, instr.instr, program[instr.instr], acc_queues,
                reqs_to_clear)


def _update_clears(reqs_to_clear: MutableMapping[ICaseString, MutableSequence[
        object]], regs: Iterable[ICaseString], instr: object) -> None:
    """Update the list of register accesses to be cleared.

    `reqs_to_clear` are the requests to be cleared from the access
                    queues.
    `regs` are the register whose access queues will be updated.
    `instr` is the index of the instruction to unstall.

    """
    for clr_reg in regs:
        reqs_to_clear.setdefault(clr_reg, []).append(instr)
