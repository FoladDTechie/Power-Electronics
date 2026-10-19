# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Abdulazeez Bello
"""Minimal S-expression reader/writer for KiCad files (no external deps)."""


class Q(str):
    """A quoted string token."""


def parse(text):
    i, n = 0, len(text)
    stack = [[]]
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c == "(":
            stack.append([])
            i += 1
        elif c == ")":
            done = stack.pop()
            stack[-1].append(done)
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while text[j] != '"':
                if text[j] == "\\":
                    buf.append(text[j:j + 2])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            stack[-1].append(Q("".join(buf)))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            stack[-1].append(text[i:j])
            i = j
    assert len(stack) == 1
    return stack[0]


def dump(node, indent=0):
    if not isinstance(node, list):
        if isinstance(node, Q):
            return '"' + node + '"'
        return str(node)
    simple = all(not isinstance(x, list) for x in node)
    if simple:
        return "(" + " ".join(dump(x) for x in node) + ")"
    pad = "\t" * (indent + 1)
    parts = []
    head = []
    rest_start = 0
    for k, x in enumerate(node):
        if isinstance(x, list):
            rest_start = k
            break
        head.append(dump(x))
    out = "(" + " ".join(head)
    for x in node[rest_start:]:
        out += "\n" + pad + dump(x, indent + 1)
    out += "\n" + "\t" * indent + ")"
    return out


def find(node, key):
    """Return first direct child list whose head is key."""
    for x in node:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def find_all(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def walk(node):
    if isinstance(node, list):
        yield node
        for x in node:
            yield from walk(x)
