#!/usr/bin/env python3
from __future__ import print_function
from recordclass import recordclass
import collections
from collections import namedtuple
# from collections import deque
from copy import deepcopy
import sys
from graphnode import GraphNode
from exceptions import *

ms_args = "posx posy dirx diry elevator skip"
MarioState_mut = recordclass("MarioState_mut", ms_args)
MarioState = namedtuple("MarioState", ms_args)
IOState = recordclass("IOState", "mem varp")
IOOp = namedtuple("IOOp", "type repeat")
steps = 0


def iop_tostring(io):
    return "%s%s" % (io.repeat, io.type)


def is_io(cell):
    return cell in [")", "(", "+", "-", ".", ":", ",", ";"]


def elevdir(code, posx, posy, maxy, searchdir=None):
    for i in reversed(range(posy)):
        if code[(i, posx)] == "\"":
            return -1
    return 1


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def enumerate_states(code, maxy):
    discovered_states = {}
    initial_state = get_initial_state()
    undiscovered_states = [initial_state]
    while len(undiscovered_states) != 0:
        to_explore = undiscovered_states.pop()
        if to_explore in discovered_states:
            # dupe!
            continue

        # Explore this state
        next_states = []
        try:
            next_state, io = eval_ml_step_no_io(code, to_explore, maxy)
            next_states.append(next_state)
        except BranchEnableException:
            # io will be the same either way
            next_state, io = eval_ml_step_no_io(code, to_explore, maxy,
                                                branch_enable=False)
            next_states.append(next_state)
            next_state, _ = eval_ml_step_no_io(code, to_explore, maxy,
                                               branch_enable=True)
            next_states.append(next_state)
        except ProgramEndException:
            io = None
            next_states = []
        io_list = [io] if io is not None else None
        discovered_states[to_explore] = GraphNode(
            next_states, io_list, to_explore)
        for state in next_states:
            if state not in discovered_states:
                # we haven't found this one
                # add it to the list
                # don't worry about duplicates
                undiscovered_states.append(state)
    return discovered_states


def count_end_states(states):
    return sum(map(lambda state: len(state.next_states) == 0,
                   states.values()))


def eval_ml_fsm(states):
    initial_state = get_initial_state()
    ios = IOState(mem=[0], varp=0)
    current = states[initial_state]
    while True:
        try:
            ret = current.eval()
        except BranchEnableException:
            ben = branch_enable(ios.mem, ios.varp)
            ret = current.eval(ben)
        except ProgramEndException:
            break
        next_state, io = ret
        if io is not None:
            eval_ml_step_io(ios, io)
        current = states[next_state]


def emit_ml_fsm(states):
    initial_state = get_initial_state()
    # Number each state
    state_num = {}
    for i, state in enumerate(states.keys()):
        state_num[state] = i

    def state_name(state):
        num = state_num[state]
        return "state%s" % num
    with open("ml.c", "wt") as f:
        def write_indent(level, str):
            indent_str = "     " * level
            f.write(indent_str)
            f.write(str)
            f.write("\n")
        write_indent(0, "#include <stdio.h>")
        write_indent(0, "int a[1024];")
        write_indent(0, "int *p = a;")
        write_indent(0, "int main() {")
        write_indent(1, "goto %s;" % state_name(initial_state))
        for state in states:
            node = states[state]
            write_indent(0, "%s:" % state_name(state))
            if node.is_end():
                write_indent(1, "goto end;")
            elif node.is_branch():
                write_indent(1, "if(*p != 0) goto %s;" %
                             state_name(node.next_states[0]))
                write_indent(1, "goto %s;" % state_name(node.next_states[1]))
            else:
                if node.io is not None:
                    for iop in node.io:
                        # write_indent(1, str(iop))
                        c_code = emit_ml_single_io(iop.type, iop.repeat)
                        if isinstance(c_code, str):
                            write_indent(1, c_code)
                        else:
                            for line in c_code:
                                write_indent(1, line)
                # go to next state
                write_indent(1, "goto %s;" % state_name(node.next_states[0]))
        write_indent(0, "end:")
        write_indent(1, "return 0;")
        write_indent(0, "}")


def emit_ml_single_io(io, repeat):
    if io == ")":
        # ios.varp += repeat
        return "p += %s;" % repeat
    elif io == "(":
        # ios.varp -= repeat
        return "p -= %s;" % repeat
    elif io == "+":
        # ios.mem[ios.varp] += repeat
        return "*p += %s;" % repeat
    elif io == "-":
        # ios.mem[ios.varp] -= repeat
        return "*p -= %s;" % repeat
    elif io == ".":
        return ["putchar(*p);" for i in range(repeat)]
    elif io == ":":
        return ["printf(\"%d \", *p);" for i in range(repeat)]
    elif io == ",":
        return ["*p = getchar();" for i in range(repeat)]
    elif io == ";":
        return ["*p = scanf(\"%d\");" for i in range(repeat)]
    else:
        raise Exception("Can't match IO type '%s' str '%s'" % (type(io), io))



def concat_io(io1, io2):
    """Return io1 + io2"""
    if io1 is None:
        return io2
    if io2 is None:
        return io1
    return io1 + io2


def combine_states(all_states, node1, node2):
    new_io = concat_io(node1.io, node2.io)
    new_state = GraphNode(next_states=node2.next_states,
                          io=new_io, curr_ms=node1.curr_ms,
                          prev_states=node1.prev_states)
    # Fix prev_state on node2's next state
    assert len(node2.next_states) == 1
    next_node = all_states[node2.next_states[0]]
    next_node.prev_states.remove(node2.curr_ms)
    next_node.prev_states.add(node1.curr_ms)
    key = new_state.curr_ms
    value = new_state
    return key, value


def combine_like_io(io_list):
    if io_list is None:
        return None
    output_list = []
    current_stack = []
    for io in io_list:
        if len(current_stack) == 0 or \
                current_stack[0].type == io.type:
            # compatible
            current_stack.append(io)
        else:
            # incompatible
            # dump current stack
            current_type = current_stack[0].type
            total_repeat = sum(map(lambda x: x.repeat, current_stack))
            combined_iop = IOOp(type=current_type, repeat=total_repeat)
            output_list.append(combined_iop)
            current_stack = []
            # now append
            current_stack.append(io)
    if len(current_stack) != 0:
        current_type = current_stack[0].type
        total_repeat = sum(map(lambda x: x.repeat, current_stack))
        combined_iop = IOOp(type=current_type, repeat=total_repeat)
        output_list.append(combined_iop)
        current_stack = []
    return output_list


def combine_io_map(states):
    states = deepcopy(states)
    for node in states.values():
        node.io = combine_like_io(node.io)
    return states


def is_linear(node):
    """A state is linear if it has one next state and one prev state
    Most common kind of case"""
    return len(node.next_states) == 1 and \
        len(node.prev_states) == 1
    # return len(node.next_states) == 1


def combine_linear(states):
    # Don't modify our argument
    states = deepcopy(states)
    for state, node in states.items():
        node.fill_in_prev_states(states)
    dirty = True
    while dirty:
        dirty = False
        for state, node1 in states.items():
            if not is_linear(node1):
                continue
            node2 = states[node1.next_states[0]]
            if not is_linear(node2):
                continue
            key, val = combine_states(states, node1, node2)
            del states[node1.curr_ms]
            del states[node2.curr_ms]
            states[key] = val
            dirty = True
            break

    return states


def create_dotfile(states, initial_state):
    with open("ml.dot", "wt") as f:
        f.write("""
digraph finite_state_machine {
    node [shape = point ]; state_init
""")
        # Number each state
        state_num = {}
        for i, state in enumerate(states.keys()):
            state_num[state] = i
        # for state, i in state_num.values():
            label = states[state].io
            if label is None:
                label = " "
            else:
                label = list(map(iop_tostring, label))
            # truncate too-long label
            if len(label) > 30:
                label = label[:30]
            # convert to string
            label = "".join(label)
            f.write("    node [shape = circle, label=\"%s\"] state_%s;\n"
                    % (label, i))
        # Emit each state transition
        for state, node in states.items():
            from_index = state_num[state]
            for next_state in node.next_states:
                to_index = state_num[next_state]
                f.write("    state_%s -> state_%s\n" % (from_index, to_index))
        # Emit init -> first transition
        first_index = state_num[initial_state]
        f.write("    state_init -> state_%s\n" % first_index)
        f.write("""
}""")


def get_initial_state():
    return MarioState(posx=0, posy=0, dirx=1, diry=0, elevator=False, skip=0)


def eval_ml(code, maxy):
    ms = get_initial_state()
    ios = IOState(mem=[0], varp=0)
    while True:
        try:
            ret = eval_ml_step_no_io(code, ms, maxy)
        except BranchEnableException:
            ben = branch_enable(ios.mem, ios.varp)
            ret = eval_ml_step_no_io(code, ms, maxy, ben)
        except ProgramEndException:
            break
        next_state, io = ret
        if io is not None:
            eval_ml_step_io(ios, [io])
        ms = next_state


def eval_ml_step_io(iostate, many_io):
    if not isinstance(many_io, (tuple, list)):
        raise Exception("Bad io list type " + type(many_io))
    for io in many_io:
        if not isinstance(io, IOOp):
            raise Exception("Bad io type " + str(type(io)) + ", " + str(io))
        eval_ml_single_io(iostate, io.type, io.repeat)


def eval_ml_single_io(ios, io, repeat):
    if io == ")":
        ios.varp += repeat
        # ios.mem << 0 if ios.varp > varl
        while ios.varp >= len(ios.mem):
            ios.mem.append(0)
    elif io == "(":
        ios.varp -= repeat
        if ios.varp < 0:
            eprint("Error: trying to access Memory Cell -1")
            sys.exit(1)
    elif io == "+":
        ios.mem[ios.varp] += repeat
    elif io == "-":
        ios.mem[ios.varp] -= repeat
    elif io == ".":
        for i in range(repeat):
            sys.stdout.write(chr(ios.mem[ios.varp]))
        sys.stdout.flush()
    elif io == ":":
        for i in range(repeat):
            sys.stdout.write("%s " % ios.mem[ios.varp])
    elif io == ",":
        for i in range(repeat):
            ios.mem[ios.varp] = ord(sys.stdin.read(1))
    elif io == ";":
        for i in range(repeat):
            ios.mem[ios.varp] = int(input())
    else:
        raise Exception("Can't match IO type '%s' str '%s'" % (type(io), io))


def branch_enable(mem, varp):
    return mem[varp] == 0


def eval_ml_step_no_io(code, ms_immut, maxy, branch_enable=None):
    global steps
    # change from namedtuple to recordclass
    ms = MarioState_mut(*ms_immut)
    io = None
    just_branched = False
    steps += 1
    if ms.posy < 0:
        eprint("Error: trying to get out of the program!\n")
        sys.exit(1)
    if ms.posy > maxy:
        # we've fallen
        # eprint("falling at (%s, %s)" % (ms.posy, ms.posx))
        raise ProgramEndException()
    cell = code[(ms.posy, ms.posx)]
    if not ms.skip:
        if cell == "\"":
            ms.diry = -1
            ms.elevator = False
        elif is_io(cell):
            io = cell
        elif cell == ">":
            ms.dirx = 1
        elif cell == "<":
            ms.dirx = -1
        elif cell == "^":
            ms.diry = -1
        elif cell == "!":
            ms.dirx = ms.diry = 0
        elif cell == "[":
            if branch_enable is None:
                raise BranchEnableException()
            if branch_enable:  # mem[varp == 0]
                ms.skip = True
                just_branched = True
        elif cell == "@":
            ms.dirx = -ms.dirx
    if ms.posy > maxy:
        # we've fallen
        # eprint("falling at (%s, %s)" % (ms.posy, ms.posx))
        raise ProgramEndException()
    if code[(ms.posy, ms.posx)] in "><@" and not ms.skip:
        ms.elevator = False
        ms.diry = 0
        ms.posx += ms.dirx
    elif ms.diry != 0:
        ms.posy += ms.diry
        if not ms.elevator:
            ms.diry = 0
    else:
        below_cell = code[(ms.posy + 1, ms.posx)]
        if below_cell in ["=", "|", "\""]:
            ms.posx += ms.dirx
        elif below_cell == "#":
            ms.posx += ms.dirx
            if cell == "!" and not ms.skip:
                ms.elevator = True
                ms.diry = elevdir(code, ms.posx, ms.posy, maxy)
                if ms.diry == 0:
                    eprint(
                        "Error: No matching elevator ending " +
                        "found at (%s, %s)\n" % (ms.posx, ms.posy))
                    sys.exit(1)
                ms.posy += ms.diry
        else:
            ms.posy += 1
    if ms.skip and not just_branched:
        ms.skip = False
    # wrap in IOOp
    if io is not None:
        io = IOOp(type=io, repeat=1)
    # wrap back in namedtuple
    return MarioState(*ms), io


def main():
    if len(sys.argv) == 2:
        s = open(sys.argv[1], "r").readlines()
    else:
        eprint("Usage: ml.py <filename>")
        sys.exit(1)
    code = collections.defaultdict(lambda: " ")
    maxy = 0
    for y, line in enumerate(s):
        for x, c in enumerate(line):
            if c == " ":
                # don't bother storing spaces
                continue
            code[(y, x)] = c
            if y > maxy:
                maxy = y
    # print(maxy)
    # eval_ml(code, maxy)
    states = enumerate_states(code, maxy)
    # print("Found %s states" % len(states))
    # print("Found %s end states" % count_end_states(states))
    # for node in states.values():
    #     print(node.io)
    # for state in states:
    #     print(state)
    states = combine_linear(states)
    states = combine_io_map(states)
    # eval_ml_fsm(states)
    emit_ml_fsm(states)
    create_dotfile(states, get_initial_state())
    print("Done in %s steps" % steps)


if __name__ == '__main__':
    # import cProfile
    # cProfile.run('main()', sort='cumtime')
    main()
