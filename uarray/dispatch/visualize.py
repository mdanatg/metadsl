import ast
import functools
import typing

import graphviz
import numpy

from ..core.abstractions import Variable
from ..numpy.ast import AST
from .core import *

__all__ = ["visualize_diff", "visualize_progress"]


@functools.singledispatch
def description(expr):
    return str(expr)


@description.register
def _box_desc(box: Box):
    return box._str_without_value()
    # name = type(box).__qualname__
    # other_fields = [
    #     f.name for f in dataclasses.fields(box) if f.init and f.name != "value"
    # ]
    # n_ports = len(other_fields) + 1
    # return f"""<
    #     <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">
    #     <TR>
    #         <TD COLSPAN="{n_ports}">{name}</TD>
    #     </TR>
    #     <TR>
    #         <TD PORT="0">value</TD>
    #         {' '.join(f'<TD>{field}={getattr(box, field)}</TD>' for field in other_fields)}
    #     </TR>
    #     </TABLE>
    # >"""


@description.register
def _operation_desc(op: Operation):
    name = description(key(op))
    n_ports = len(children(op))
    if n_ports == 0:
        return f"""<
        <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">
        <TR>
            <TD>{name}</TD>
        </TR>
        </TABLE>
    >"""
    return f"""<
        <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">
        <TR>
            <TD COLSPAN="{n_ports}">{name}</TD>
        </TR>
        <TR>
        {' '.join(f'<TD PORT="{i}"></TD>' for i in range(n_ports))}
        </TR>
        </TABLE>
    >"""


@description.register(type(lambda: None))
def _operation_func(op):
    return op.__qualname__


@description.register(AST)
def _ast_description(op):
    comma = ", "
    init = f"({comma.join(map(description, op.init))})"
    return f"AST({comma.join((description(op.get),init))})"


@description.register(ast.AST)
def _ast_ast_description(op):
    return ast.dump(op, annotate_fields=False)


class _Cls:
    @classmethod
    def _(cls):
        pass


@description.register(type(_Cls._))
def _operation_method(op):
    return op.__qualname__


@description.register
def description_type(op: type):
    return op.__qualname__


@description.register
def description_ufunc(op: numpy.ufunc):
    return f"ufunc: {op.__name__}"


_id = 0


@functools.singledispatch
def id_(expr) -> str:
    global _id
    _id += 1
    return str(_id)


@id_.register
def id_box(b: Box):
    return str(id(b))


@id_.register
def id_operation(b: Operation):
    return str(id(b))


@id_.register
def id_variable(b: Variable):
    return str(id(b))


@functools.singledispatch
def attributes(expr):
    return {"shape": "plaintext", "style": ""}


@attributes.register
def attributes_box(expr: Box):
    return {"shape": "box", "style": "filled"}


@attributes.register
def attributes_var(expr: Variable):
    return {"shape": "circle", "style": "dashed"}


@functools.singledispatch
def children_nodes(expr):
    return children(expr)


@children_nodes.register
def _box_children(box: Box):
    return (box.value,)
    # return (getattr(box, f.name) for f in dataclasses.fields(box) if f.init)


def visualize(expr, dot: graphviz.Digraph, seen: typing.Set[str]) -> str:
    expr_id = id_(expr)
    if expr_id in seen:
        return expr_id
    seen.add(expr_id)
    dot.attr("node", **attributes(expr))
    dot.node(expr_id, description(expr))
    for i, child in enumerate(children_nodes(expr)):
        child_id = visualize(child, dot, seen)
        dot.edge(f"{expr_id}:{i}", child_id)
    return expr_id


def visualize_highlight(
    expr, highlight_expr, dot: graphviz.Digraph, seen: typing.Set[str]
) -> str:
    expr_id = id_(expr)
    if expr_id in seen:
        return expr_id
    if expr_id == id_(highlight_expr):
        with dot.subgraph(name="cluster_0") as dot:
            ret = visualize(expr, dot, seen)
            dot.attr(label="replaced")
            dot.attr(color="red")
            return ret
    else:
        seen.add(expr_id)
        dot.attr("node", **attributes(expr))
        dot.node(expr_id, description(expr))
        for i, child in enumerate(children_nodes(expr)):
            child_id = visualize_highlight(child, highlight_expr, dot, seen)
            dot.edge(f"{expr_id}:{i}", child_id)
        return expr_id


def visualize_diff(expr, highlight_expr):
    d = graphviz.Digraph()
    visualize_highlight(expr, highlight_expr, d, set())
    return d


def visualize_progress(expr, max_n=200):
    raise NotImplementedError


try:
    from IPython.display import display, SVG, clear_output

    svg_formatter = get_ipython().display_formatter.formatters[  # type: ignore
        "image/svg+xml"
    ]
except Exception:
    pass
else:

    def svg(expr):
        d = graphviz.Digraph()
        visualize(expr, d, set())
        return d._repr_svg_()

    def visualize_progress(expr, max_n=1000):
        d = graphviz.Digraph()
        visualize(expr, d, set())
        display(SVG(d._repr_svg_()))

        e = copy(expr, {})
        for i, replaced in enumerate(replace_inplace_generator(e)):
            if i > max_n:
                raise Exception(f"Over {max_n} replacements")
            new_svg = SVG(visualize_diff(e, replaced)._repr_svg_())
            clear_output(wait=True)
            display(new_svg)

    svg_formatter.for_type(Box, svg)
    # svg_formatter.for_type(LazyNDArray, lambda a: svg(a.box))