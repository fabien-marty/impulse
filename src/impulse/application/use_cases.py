from collections.abc import Set
from collections.abc import Callable
import itertools
import grimp
from impulse import ports, dotfile


def draw_graph(
    module_name: str,
    show_import_totals: bool,
    show_cycle_breakers: bool,
    sys_path: list[str],
    current_directory: str,
    get_top_level_package: Callable[[str], str],
    build_graph: Callable[[str], grimp.ImportGraph],
    viewer: ports.GraphViewer,
    depth: int = 1,
) -> None:
    """
    Create a file showing a graph of the supplied package.
    Args:
        module_name: the package or subpackage name of any importable Python package.
        show_import_totals: whether to label the arrows with the total number of imports they represent.
        show_cycle_breakers: marks a set of dependencies that, if removed, would make the graph acyclic.
        sys_path: the sys.path list (or a test double).
        current_directory: the current working directory.
        get_top_level_package: the function to retrieve the top level package name. This will usually be the first part
            of the dotted module name (before the first dot), but for namespace packages it should be the 'portion' name.
        build_graph: the function which builds the graph of the supplied package
            (pass grimp.build_graph or a test double).
        viewer: GraphViewer for generating the graph image and opening it.
        depth: the depth of submodules to include in the graph (default: 1 for direct children).
    """
    # Add current directory to the path, as this doesn't happen automatically.
    sys_path.insert(0, current_directory)

    top_level_package = get_top_level_package(module_name)
    grimp_graph = build_graph(top_level_package)

    dot = _build_dot(grimp_graph, module_name, show_import_totals, show_cycle_breakers, depth)

    viewer.view(dot)


def _find_modules_up_to_depth(
    grimp_graph: grimp.ImportGraph, module_name: str, depth: int
) -> Set[str]:
    """
    Find all modules up to and including the specified depth below the given module.

    For depth=1, returns direct children.
    For depth=2, returns direct children AND grandchildren.
    And so on.
    """
    if depth < 1:
        raise ValueError("Depth must be at least 1")

    all_modules: set[str] = set()
    current_level = {module_name}

    for _ in range(depth):
        next_level: set[str] = set()
        for mod in current_level:
            next_level.update(grimp_graph.find_children(mod))
        all_modules.update(next_level)
        current_level = next_level

    return all_modules


class _DotGraphBuildStrategy:
    def __init__(self, depth: int = 1) -> None:
        self.depth = depth

    def build(self, module_name: str, grimp_graph: grimp.ImportGraph) -> dotfile.DotGraph:
        modules = _find_modules_up_to_depth(grimp_graph, module_name, self.depth)

        self.prepare_graph(grimp_graph, modules)

        dot = dotfile.DotGraph(
            title=module_name, concentrate=self.should_concentrate(), depth=self.depth
        )
        for mod in modules:
            dot.add_node(mod)
        for upstream, downstream in itertools.permutations(modules, r=2):
            if edge := self.build_edge(grimp_graph, upstream, downstream):
                dot.add_edge(edge)

        return dot

    def should_concentrate(self) -> bool:
        return True

    def prepare_graph(self, grimp_graph: grimp.ImportGraph, modules: Set[str]) -> None:
        pass

    def build_edge(
        self, grimp_graph: grimp.ImportGraph, upstream: str, downstream: str
    ) -> dotfile.Edge | None:
        raise NotImplementedError


class _ModuleSquashingBuildStrategy(_DotGraphBuildStrategy):
    """Fast builder for when we don't need additional data about the imports."""

    def prepare_graph(self, grimp_graph: grimp.ImportGraph, modules: Set[str]) -> None:
        for mod in modules:
            grimp_graph.squash_module(mod)

    def build_edge(
        self, grimp_graph: grimp.ImportGraph, upstream: str, downstream: str
    ) -> dotfile.Edge | None:
        if grimp_graph.direct_import_exists(importer=downstream, imported=upstream):
            return dotfile.Edge(source=downstream, destination=upstream)
        return None


class _ImportExpressionBuildStrategy(_DotGraphBuildStrategy):
    """Slower builder for when we want to work on the whole graph,
    without squashing modules.
    """

    def __init__(
        self,
        *,
        module_name: str,
        show_import_totals: bool,
        show_cycle_breakers: bool,
        depth: int = 1,
    ) -> None:
        super().__init__(depth=depth)
        self.module_name = module_name
        self.show_import_totals = show_import_totals
        self.show_cycle_breakers = show_cycle_breakers
        self.cycle_breakers: set[tuple[str, str]] | None = None

    def should_concentrate(self) -> bool:
        # We need to see edge direction emphasized separately.
        return not (self.show_import_totals or self.show_cycle_breakers)

    def prepare_graph(self, grimp_graph: grimp.ImportGraph, modules: Set[str]) -> None:
        super().prepare_graph(grimp_graph, modules)

        if self.show_cycle_breakers:
            self.cycle_breakers = self._get_coarse_grained_cycle_breakers(grimp_graph, modules)

    def _get_coarse_grained_cycle_breakers(
        self, grimp_graph: grimp.ImportGraph, modules: Set[str]
    ) -> set[tuple[str, str]]:
        # In the form (importer, imported).
        coarse_grained_cycle_breakers: set[tuple[str, str]] = set()

        for fine_grained_cycle_breaker in grimp_graph.nominate_cycle_breakers(self.module_name):
            importer, imported = fine_grained_cycle_breaker
            importer_ancestor = self._get_self_or_ancestor(candidate=importer, ancestors=modules)
            imported_ancestor = self._get_self_or_ancestor(candidate=imported, ancestors=modules)

            if importer_ancestor and imported_ancestor:
                coarse_grained_cycle_breakers.add((importer_ancestor, imported_ancestor))

        return coarse_grained_cycle_breakers

    @staticmethod
    def _get_self_or_ancestor(candidate: str, ancestors: Set[str]) -> str | None:
        for ancestor in ancestors:
            if candidate == ancestor or candidate.startswith(f"{ancestor}."):
                return ancestor
        return None

    def build_edge(
        self, grimp_graph: grimp.ImportGraph, upstream: str, downstream: str
    ) -> dotfile.Edge | None:
        # For depth > 1, we can't use as_packages=True because modules may share
        # descendants (e.g., foo.blue and foo.blue.alpha are both in our set).
        # In that case, only check for direct imports between exact modules.
        if self.depth > 1:
            import_exists = grimp_graph.direct_import_exists(
                importer=downstream, imported=upstream, as_packages=False
            )
        else:
            import_exists = grimp_graph.direct_import_exists(
                importer=downstream, imported=upstream, as_packages=True
            )

        if import_exists:
            if self.show_import_totals:
                number_of_imports = self._count_imports_between_packages(
                    grimp_graph, importer=downstream, imported=upstream
                )
                label = str(number_of_imports)
            else:
                label = ""

            if self.show_cycle_breakers:
                assert self.cycle_breakers is not None
                is_cycle_breaker = (downstream, upstream) in self.cycle_breakers
                emphasized = is_cycle_breaker
            else:
                emphasized = False

            return dotfile.Edge(
                source=downstream, destination=upstream, label=label, emphasized=emphasized
            )
        return None

    @staticmethod
    def _count_imports_between_packages(
        graph: grimp.ImportGraph, *, importer: str, imported: str
    ) -> int:
        return (
            len(graph.find_matching_direct_imports(import_expression=f"{importer} -> {imported}"))
            + len(
                graph.find_matching_direct_imports(
                    import_expression=f"{importer} -> {imported}.**"
                )
            )
            + len(
                graph.find_matching_direct_imports(
                    import_expression=f"{importer}.** -> {imported}"
                )
            )
            + len(
                graph.find_matching_direct_imports(
                    import_expression=f"{importer}.** -> {imported}.**"
                )
            )
        )


def _build_dot(
    grimp_graph: grimp.ImportGraph,
    module_name: str,
    show_import_totals: bool,
    show_cycle_breakers: bool,
    depth: int = 1,
) -> dotfile.DotGraph:
    strategy: _DotGraphBuildStrategy
    # Use ImportExpressionBuildStrategy when:
    # - show_import_totals or show_cycle_breakers is enabled, OR
    # - depth > 1 (squashing would remove deeper modules we want to show)
    if show_import_totals or show_cycle_breakers or depth > 1:
        strategy = _ImportExpressionBuildStrategy(
            module_name=module_name,
            show_import_totals=show_import_totals,
            show_cycle_breakers=show_cycle_breakers,
            depth=depth,
        )
    else:
        strategy = _ModuleSquashingBuildStrategy(depth=depth)

    return strategy.build(module_name, grimp_graph)
