from textwrap import dedent
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Edge:
    source: str
    destination: str
    label: str = ""
    emphasized: bool = False

    def __str__(self) -> str:
        return self.render(base_module="")

    def render(self, base_module: str) -> str:
        return f'"{DotGraph.render_module(self.source, base_module)}" ->  "{DotGraph.render_module(self.destination, base_module)}"{self._render_attrs()}\n'

    def _render_attrs(self) -> str:
        attrs: dict[str, str] = {}
        if self.label:
            attrs["label"] = self.label
        if self.emphasized:
            attrs["style"] = "dashed"
        if attrs:
            joined_attrs = ", ".join([f'{key}="{value}"' for key, value in attrs.items()])
            return f" [{joined_attrs}]"
        else:
            return ""


class DotGraph:
    """
    A directed graph that can be rendered in DOT format.

    https://en.wikipedia.org/wiki/DOT_(graph_description_language)
    """

    def __init__(self, title: str, concentrate: bool = True, depth: int = 1) -> None:
        self.title = title
        self.nodes: set[str] = set()
        self.edges: set[Edge] = set()
        self.concentrate = concentrate
        self.depth = depth

    def add_node(self, name: str) -> None:
        self.nodes.add(name)

    def add_edge(self, edge: Edge) -> None:
        self.edges.add(edge)

    def render(self) -> str:
        # concentrate=true means that we merge the lines together.
        return dedent(f"""digraph {{
            node [fontname=helvetica]
            {"concentrate=true" if self.concentrate else ""}
            {self._render_nodes()}
            {self._render_edges()}
        }}""")

    def _render_nodes(self) -> str:
        return "\n".join(
            f'"{self.render_module(node, self.title)}"\n' for node in sorted(self.nodes)
        )

    def _render_edges(self) -> str:
        return "\n".join(edge.render(self.title) for edge in sorted(self.edges))

    @staticmethod
    def render_module(module: str, base_module: str = "") -> str:
        # Render as relative module by stripping the base module prefix.
        if base_module and module.startswith(base_module + "."):
            relative = module[len(base_module) :]
            return relative  # Already starts with "."
        else:
            # Fallback: show as relative with just the last component
            return f".{module.split('.')[-1]}"
