"""Shared restricted arithmetic compiler; no renderer or native dependency."""


def compile_expression(text, names, variables, limit, label):
    if not text or len(text) > limit:
        raise ValueError('Use 1 to %d characters' % limit)
    i = 0
    while i < len(text):
        char = text[i]
        if char.isdigit() or char == '.':
            end = i + 1
            while end < len(text) and (text[end].isdigit() or text[end] == '.'):
                end += 1
            if end < len(text) and text[end] in 'eE':
                end += 1
                if end < len(text) and text[end] in '+-':
                    end += 1
                while end < len(text) and text[end].isdigit():
                    end += 1
            float(text[i:end])
            i = end
        elif char.isalpha() or char == '_':
            end = i + 1
            while end < len(text) and (text[end].isalpha() or text[end].isdigit() or text[end] == '_'):
                end += 1
            name = text[i:end]
            if name.startswith('_') or name not in names and name not in variables:
                raise ValueError('Unknown name: ' + name)
            i = end
        elif char in ' +-*/%(),\t':
            i += 1
        else:
            raise ValueError('Unsupported character: ' + char)
    return compile(text, label, 'eval')
