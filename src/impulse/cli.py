import os

import click
import sys

from impulse.application import use_cases
from impulse import adapters
from impulse import ports
import grimp


@click.group()
def main():
    pass


@main.command()
@click.option(
    "--show-import-totals",
    is_flag=True,
    help="Label arrows with the number of imports they represent.",
)
@click.option(
    "--show-cycle-breakers",
    is_flag=True,
    help=(
        "Identify a set of dependencies that, if removed, would make the graph acyclic, "
        "and display them as dashed lines."
    ),
)
@click.option(
    "--format",
    type=click.Choice(["html", "dot"]),
    default="html",
    help="Output format (default to html).",
)
@click.option("--force-console", is_flag=True, help="Force the use of the console output.")
@click.option(
    "--depth",
    type=int,
    default=1,
    help="Depth of submodules to include in the graph (default: 1 for direct children).",
)
@click.argument("module_name", type=str)
def drawgraph(
    module_name: str,
    show_import_totals: bool,
    show_cycle_breakers: bool,
    force_console: bool,
    format: str,
    depth: int,
) -> None:
    viewer: ports.GraphViewer
    if format == "html":
        if not force_console and sys.stdout.isatty():
            # the output is not redirected to a file
            viewer = adapters.BrowserGraphViewer()
        else:
            viewer = adapters.ConsoleGraphViewer()
    elif format == "dot":
        viewer = adapters.ConsoleDotViewer()
    else:
        raise ValueError(f"Invalid format: {format}")
    use_cases.draw_graph(
        module_name=module_name,
        show_import_totals=show_import_totals,
        show_cycle_breakers=show_cycle_breakers,
        depth=depth,
        sys_path=sys.path,
        current_directory=os.getcwd(),
        get_top_level_package=adapters.get_top_level_package,
        build_graph=grimp.build_graph,
        viewer=viewer,
    )
