from io import StringIO
from unittest import mock

from impulse import adapters
from impulse.dotfile import DotGraph, Edge


class TestConsoleGraphViewer:
    def test_view_prints_html_to_stdout(self):
        """Test that ConsoleGraphViewer prints HTML content to stdout."""
        dot = DotGraph(title="test.module")
        dot.add_node("test.module.foo")
        dot.add_node("test.module.bar")
        dot.add_edge(Edge("test.module.foo", "test.module.bar"))

        viewer = adapters.ConsoleGraphViewer()

        with mock.patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            viewer.view(dot)
            output = mock_stdout.getvalue()

        # Verify it's HTML content
        assert "<!DOCTYPE html>" in output
        assert "<html>" in output
        assert "test.module" in output
        assert "Impulse" in output


class TestConsoleDotViewer:
    def test_view_prints_dot_to_stdout(self):
        """Test that ConsoleDotViewer prints DOT content to stdout."""
        dot = DotGraph(title="test.module")
        dot.add_node("test.module.foo")
        dot.add_node("test.module.bar")
        dot.add_edge(Edge("test.module.foo", "test.module.bar"))

        viewer = adapters.ConsoleDotViewer()

        with mock.patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            viewer.view(dot)
            output = mock_stdout.getvalue()

        # Verify it's DOT content
        assert "digraph" in output
        assert ".foo" in output
        assert ".bar" in output
        assert "->" in output
