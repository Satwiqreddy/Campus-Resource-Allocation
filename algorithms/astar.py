"""A* over partial allocations.

State  : (i, path) - events[0..i) have been decided, path holds an Option or None (REJECT) each.
Action : ALLOCATE one of event i's options, or REJECT it.
g(n)   : sum of priority-weighted deviations + reject costs so far.
h(n)   : for every undecided event, the cheapest of (its best option, rejecting it), ignoring
         clashes - a relaxation, so h never overestimates and A* returns the optimal plan.
"""
import heapq
import itertools

from algorithms.allocation import greedy


def astar(events, options, reject_cost, check, max_expansions=200_000):
    n = len(events)
    h = [0.0] * (n + 1)
    for i in range(n - 1, -1, -1):
        e = events[i]
        h[i] = h[i + 1] + min([o.penalty for o in options[e]] + [reject_cost[e]])

    tie = itertools.count()
    frontier = [(h[0], 0, next(tie), 0.0, ())]
    expanded = 0
    while frontier:
        _, neg_i, _, g, path = heapq.heappop(frontier)
        i = -neg_i
        if i == n:
            return dict(zip(events, path)), expanded
        expanded += 1
        if expanded > max_expansions:
            # ponytail: exponential worst case; fall back to greedy past the cap. Add beam search if fests grow huge.
            return greedy(events, options, check), expanded
        e = events[i]
        assigned = [o for o in path if o]
        for o in options[e]:
            if check(o, assigned) is None:
                heapq.heappush(frontier, (g + o.penalty + h[i + 1], -(i + 1), next(tie), g + o.penalty, path + (o,)))
        heapq.heappush(frontier, (g + reject_cost[e] + h[i + 1], -(i + 1), next(tie), g + reject_cost[e], path + (None,)))
    raise AssertionError("unreachable: REJECT is always a valid action")
