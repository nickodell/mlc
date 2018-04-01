from exceptions import *


class GraphNode(object):
    def __init__(self, next_states, io, curr_ms, prev_states=None):
        self.next_states = tuple(next_states)
        # list of namedtuples
        if not isinstance(io, list) and io is not None:
            raise TypeError("Bad io type %s" % type(io))
        self.io = io
        self.curr_ms = curr_ms
        if prev_states is not None:
            self.prev_states = prev_states
        else:
            self.prev_states = set()

    def eval(self, branch_enable=None):
        if self.is_end():
            raise ProgramEndException()  # end of program
        elif self.is_branch():
            if branch_enable is None:
                raise BranchEnableException()
            if branch_enable:
                return self.next_states[1], self.io
            else:
                return self.next_states[0], self.io
        else:
            return self.next_states[0], self.io  # only one option

    def is_branch(self):
        if len(self.next_states) == 2:
            return True

    def is_end(self):
        if len(self.next_states) == 0:
            return True

    def fill_in_prev_states(self, states):
        for next_state in self.next_states:
            next_node = states[next_state]
            next_node.prev_states.add(self.curr_ms)
