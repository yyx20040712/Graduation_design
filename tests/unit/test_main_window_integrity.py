"""Smoke test: verify MainWindow class integrity without GUI display.

Catches runtime errors like missing methods that would only surface
when the GUI launches (e.g., AttributeError on _build_elevation_view).
"""

import pytest


class TestMainWindowIntegrity:
    """Verify that MainWindow class has all methods referenced internally."""

    def test_all_referenced_methods_exist(self):
        """Check that self._xxx() calls in MainWindow correspond to defined methods."""
        import ast
        import os

        fp = os.path.join(
            os.path.dirname(__file__), "..", "..", "ddesign_tool", "src", "ui", "main_window.py"
        )
        fp = os.path.abspath(fp)
        with open(fp, encoding="utf-8") as f:
            tree = ast.parse(f.read())

        # Collect all defined methods in MainWindow class
        defined_methods = set()
        # Collect all self.method_name() calls
        called_methods = set()

        class MethodCollector(ast.NodeVisitor):
            def __init__(self):
                self.in_mainwindow = False

            def visit_ClassDef(self, node):
                if node.name == "MainWindow":
                    self.in_mainwindow = True
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            defined_methods.add(item.name)
                    self.generic_visit(node)
                    self.in_mainwindow = False

            def visit_Call(self, node):
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
                        called_methods.add(node.func.attr)
                self.generic_visit(node)

        collector = MethodCollector()
        collector.visit(tree)

        # Methods that are legitimately called via external objects or tkinter internals
        exempt = {
            "mainloop", "title", "geometry", "configure", "protocol",
            "bind", "bind_all", "after", "update_idletasks",
            "pack", "grid", "place", "destroy", "quit",
            "get", "set", "insert", "delete", "focus", "selection",
            "configure", "cget", "winfo", "event_generate",
            "focus_get", "unbind_all", "focus_set", "register",
        }

        missing = called_methods - defined_methods - exempt
        if missing:
            pytest.fail(
                f"MainWindow calls {len(missing)} undefined methods: {sorted(missing)}\n"
                f"These would cause AttributeError at runtime."
            )
