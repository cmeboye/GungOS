"""Bounded expression tree with editable rows and explicit mathematical slots."""

MAX_ITEMS = 384
MAX_DEPTH = 10
SLOTS = {
    'pow': ('exponent',), 'sub': ('subscript',), 'sqrt': ('radicand',),
    'frac': ('numerator', 'denominator'), 'int': ('lower bound', 'upper bound', 'expression in x'),
    'sum': ('index variable', 'lower bound', 'upper bound', 'summand'),
    'prod': ('index variable', 'lower bound', 'upper bound', 'factor'),
    'logb': ('base', 'argument'), 'log': ('argument',),
    'sin': ('argument',), 'cos': ('argument',), 'tan': ('argument',),
    'ln': ('argument',), 'exp': ('argument',), 'abs': ('argument',),
}


class Node:
    def __init__(self, kind, rows=None):
        self.kind = kind
        self.rows = rows if rows is not None else [[] for _ in SLOTS.get(kind, ())]


def clone(row):
    return [item if isinstance(item, str) else Node(item.kind, [clone(r) for r in item.rows]) for item in row]


def count(row):
    return sum(1 if isinstance(item, str) else 1+sum(count(r) for r in item.rows) for item in row)


def depth(row):
    return max([0]+[1+max([depth(r) for r in item.rows]) for item in row
                   if isinstance(item, Node) and item.rows])


def source(row, complete=True):
    out = ''
    for item in row:
        if isinstance(item, str):
            out += item
            continue
        args = []
        for r in item.rows:
            if complete and not r:
                raise ValueError('Fill the '+SLOTS[item.kind][len(args)]+' slot')
            args.append(source(r, complete))
        kind = item.kind
        if kind == 'pow': out += '^('+args[0]+')'
        elif kind == 'sub': out += '_'+args[0]
        elif kind == 'frac': out += '(('+args[0]+')/('+args[1]+'))'
        elif kind == 'pi': out += 'pi'
        elif kind == 'logb': out += 'logb('+','.join(args)+')'
        else: out += kind+'('+','.join(args)+')'
    return out


def locations(row, parents=None):
    """Ordered slot rows, retaining their path so recalled trees stay editable."""
    parents = [] if parents is None else parents
    result = [(row, parents)]
    for i, item in enumerate(row):
        if isinstance(item, Node):
            for slot, child in enumerate(item.rows):
                result.extend(locations(child, parents+[(row, i, slot)]))
    return result


class Editor:
    def __init__(self):
        self.clear()

    def clear(self):
        self.root, self.parents, self.index = [], [], 0
        self.row = self.root

    def load(self, row):
        self.root = clone(row)
        self.row, self.parents, self.index = self.root, [], len(self.root)

    def insert(self, char):
        if count(self.root) >= MAX_ITEMS:
            raise ValueError('Expression limit: 384 items')
        self.row.insert(self.index, char)
        self.index += 1

    def template(self, kind, rows=None):
        if kind in ('sum','prod') and rows is None:
            self._replace(self.index, self.index, kind, [list('k'), [], [], []], focus=1)
        else:
            self._replace(self.index, self.index, kind, rows)

    def _replace(self, begin, end, kind, rows=None, focus=0):
        """Validate a replacement before changing any text or cursor path."""
        if kind not in SLOTS and kind != 'pi':
            raise ValueError('Unknown template')
        node = Node(kind, rows)
        size = count(self.root)-count(self.row[begin:end])+1+sum(count(r) for r in node.rows)
        nesting = len(self.parents)+(1+max(depth(r) for r in node.rows) if node.rows else 0)
        if nesting > MAX_DEPTH or size > MAX_ITEMS:
            raise ValueError('Expression nesting/size limit')
        self.row[begin:end] = [node]
        self.index = begin
        if node.rows:
            self.parents.append((self.row, self.index, focus))
            self.row, self.index = node.rows[focus], len(node.rows[focus])
        else:
            self.index += 1

    def _numerator_start(self, end):
        """Capture a multiplicative term; +, -, = and commas delimit it.

        Keep powers, signed exponents, scientific notation and grouped function
        arguments together. This preserves 1/2/ -> (1/2)/ rather than 1/(2/...).
        """
        level = 0
        for i in range(end-1, -1, -1):
            item = self.row[i]
            if not isinstance(item, str): continue
            if item == ')': level += 1
            elif item == '(':
                if level == 0: return i+1
                level -= 1
            elif level == 0:
                if item in ('=', ','): return i+1
                if item in ('+', '-'):
                    previous = i-1
                    while previous >= 0 and self.row[previous] == ' ': previous -= 1
                    before = self.row[previous] if previous >= 0 else None
                    unary = before is None or before in ('+', '-', '*', '/', '^', '(', '=', ',')
                    exponent = before in ('e', 'E') and previous > 0 and isinstance(self.row[previous-1], str) and (
                        self.row[previous-1].isdigit() or self.row[previous-1] == '.')
                    if not unary and not exponent: return i+1
        return 0

    def expand(self):
        """Space expands a trailing shorthand without changing unrelated input."""
        prefix = self.row[:self.index]
        # Prefer the named logarithm template over a generic subscript.
        if prefix[-4:] == list('log_') and not (
                len(prefix) > 4 and isinstance(prefix[-5], str) and (prefix[-5].isalpha() or prefix[-5] == '_')):
            self._replace(self.index-4, self.index, 'logb')
            return True
        if prefix and prefix[-1] == '/':
            end = self.index-1
            while end > 0 and self.row[end-1] == ' ': end -= 1
            if end == 0 or self.row[end-1] in ('+', '-', '*', '/', '^', '_', '=', ',', '('):
                raise ValueError('Enter a numerator before /')
            begin = self._numerator_start(end)
            numerator = self.row[begin:end]
            self._replace(begin, self.index, 'frac', [numerator, []], focus=1)
            return True
        if prefix and prefix[-1] in ('^', '_'):
            kind = 'pow' if prefix[-1] == '^' else 'sub'
            if self.index < 2:
                raise ValueError('Enter a base before this template')
            self._replace(self.index-1, self.index, kind)
            return True
        # Recognise name(...) immediately before the cursor, including filled
        # arguments. Nested plain parentheses are kept as typed text.
        if prefix and prefix[-1] == ')':
            level, opening = 0, -1
            for i in range(len(prefix)-1, -1, -1):
                item = prefix[i]
                if not isinstance(item, str): continue
                if item == ')': level += 1
                elif item == '(':
                    level -= 1
                    if level == 0:
                        opening = i
                        break
            if opening >= 0:
                begin = opening
                while begin > 0 and isinstance(prefix[begin-1], str) and prefix[begin-1].isalpha():
                    begin -= 1
                name = ''.join(prefix[begin:opening])
                base = None
                # Also accept log_2() / log_b(5) + Space. Ordinary function
                # recognition still permits numeric coefficients (2sqrt(...)).
                candidate = opening
                while candidate > 0 and isinstance(prefix[candidate-1], str) and (
                        prefix[candidate-1].isalpha() or prefix[candidate-1].isdigit() or prefix[candidate-1] == '_'):
                    candidate -= 1
                first = candidate
                while first < opening and prefix[first].isdigit(): first += 1
                alias = ''.join(prefix[first:opening])
                if alias.startswith('log_'):
                    base, name, begin = list(alias[4:]), 'logb', first
                if name in SLOTS and name not in ('pow', 'sub'):
                    rows, depth = [[]], 0
                    for item in prefix[opening+1:-1]:
                        if item == '(' : depth += 1
                        elif item == ')': depth -= 1
                        if item == ',' and depth == 0: rows.append([])
                        else: rows[-1].append(item)
                    if base is not None: rows.insert(0, base)
                    if name in ('sum','prod'):
                        # Only the empty shorthand and indexed four-argument
                        # form are templates. Keep scalar/dataset calls as text.
                        if len(rows) == 1 and not rows[0]:
                            self._replace(begin, self.index, name, [list('k'), [], [], []], focus=1)
                            return True
                        if len(rows) != 4: return False
                        index = ''.join(rows[0]).strip() if all(isinstance(item, str) for item in rows[0]) else ''
                        if not index or not index[0].isalpha() or not all(c.isalpha() or c.isdigit() or c == '_' for c in index):
                            return False
                    if len(rows) > len(SLOTS[name]):
                        raise ValueError('Too many template arguments')
                    rows += [[] for _ in range(len(SLOTS[name])-len(rows))]
                    self._replace(begin, self.index, name, rows,
                                  focus=1 if base is not None and base else 0)
                    return True
        if self.index >= 2 and prefix[-2:] == ['p', 'i'] and not (
                self.index > 2 and isinstance(prefix[-3], str) and (prefix[-3].isalpha() or prefix[-3] == '_')):
            self._replace(self.index-2, self.index, 'pi')
            return True
        return False

    def exit_slot(self, right=True):
        if not self.parents: return False
        parent, index, _ = self.parents.pop()
        self.row, self.index = parent, index+(1 if right else 0)
        return True

    def move(self, direction):
        if direction > 0:
            if self.index == len(self.row): return self.exit_slot()
            item = self.row[self.index]
            if isinstance(item, Node) and item.rows:
                self.parents.append((self.row, self.index, 0))
                self.row, self.index = item.rows[0], 0
            else: self.index += 1
        else:
            if self.index == 0: return self.exit_slot(False)
            item = self.row[self.index-1]
            if isinstance(item, Node) and item.rows:
                self.parents.append((self.row, self.index-1, len(item.rows)-1))
                self.row = item.rows[-1]
                self.index = len(self.row)
            else: self.index -= 1
        return True

    def tab(self, backwards=False):
        rows = locations(self.root)
        selected = next(i for i, (row, _) in enumerate(rows) if row is self.row)
        selected = (selected+(-1 if backwards else 1)) % len(rows)
        self.row, self.parents = rows[selected]
        self.parents = self.parents[:]
        self.index = len(self.row)

    def vertical(self, direction):
        if not self.parents: return False
        parent, index, slot = self.parents[-1]
        node = parent[index]
        target = slot+direction
        if target < 0 or target >= len(node.rows): return False
        self.parents[-1] = (parent, index, target)
        self.row = node.rows[target]
        self.index = min(self.index, len(self.row))
        return True

    def delete(self, forward=False):
        index = self.index if forward else self.index-1
        if 0 <= index < len(self.row):
            del self.row[index]
            if not forward: self.index -= 1
        elif not forward and self.parents:
            # Delete an empty template as one unit. Filled slots exit first.
            if not any(self.parents[-1][0][self.parents[-1][1]].rows):
                self.exit_slot(False)
                del self.row[self.index]
            else: self.exit_slot(False)

    def focus_missing(self):
        for row, parents in locations(self.root)[1:]:
            if not row:
                self.row, self.parents, self.index = row, parents, 0
                return True
        return False

    def hint(self):
        if not self.parents: return 'SPACE expands templates | UP history'
        parent, index, slot = self.parents[-1]
        return SLOTS[parent[index].kind][slot]+' | TAB next | RIGHT exits'
