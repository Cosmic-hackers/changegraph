"""
python_ast.py — Python AST-based source file parser for ChangeGraph.

Parses a single Python file and extracts:
  - Module-level imports (from x import y, import x)
  - Top-level and nested function definitions
  - Class definitions
  - Function call relationships (which function calls which)
  - Attribute-access calls (obj.method())

All analysis is purely deterministic — no LLM involvement.
"""

import ast
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FunctionInfo:
    """Metadata about a function definition found in a source file."""
    name: str
    qualified_name: str      # e.g. "MyClass.my_method"
    module: str              # module name (file stem)
    lineno: int
    end_lineno: int
    decorators: list[str] = field(default_factory=list)
    is_method: bool = False
    parent_class: Optional[str] = None
    calls: list[str] = field(default_factory=list)  # bare names of called functions


@dataclass
class ClassInfo:
    """Metadata about a class definition found in a source file."""
    name: str
    module: str
    lineno: int
    end_lineno: int
    bases: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)


@dataclass
class ImportInfo:
    """A single import statement parsed from a file."""
    module: str              # the imported module (e.g. "checkout", "os.path")
    names: list[str]         # specific names imported ("*" for star import, [] for bare module import)
    is_from: bool            # True for "from x import y"
    lineno: int


@dataclass
class ParsedModule:
    """All symbols extracted from a single Python source file."""
    module_name: str          # stem of the filename
    file_path: str            # absolute or relative path
    imports: list[ImportInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)


class _CallVisitor(ast.NodeVisitor):
    """Collect all function-call names within a node subtree."""

    def __init__(self):
        self.calls: list[str] = []

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            self.calls.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            # e.g. module.function() → record "function"
            self.calls.append(node.func.attr)
        self.generic_visit(node)


class _ModuleVisitor(ast.NodeVisitor):
    """Walk a module AST and collect all symbol information."""

    def __init__(self, module_name: str, file_path: str):
        self.module_name = module_name
        self.file_path = file_path
        self.imports: list[ImportInfo] = []
        self.functions: list[FunctionInfo] = []
        self.classes: list[ClassInfo] = []
        self._current_class: Optional[str] = None

    # ------------------------------------------------------------------ imports
    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(
                ImportInfo(
                    module=alias.name,
                    names=[],
                    is_from=False,
                    lineno=node.lineno,
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        names = [alias.name for alias in node.names]
        self.imports.append(
            ImportInfo(
                module=module,
                names=names,
                is_from=True,
                lineno=node.lineno,
            )
        )

    # ------------------------------------------------------------------ classes
    def visit_ClassDef(self, node: ast.ClassDef):
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(base.attr)

        cls = ClassInfo(
            name=node.name,
            module=self.module_name,
            lineno=node.lineno,
            end_lineno=getattr(node, "end_lineno", node.lineno),
            bases=bases,
        )
        self.classes.append(cls)

        # Descend into the class body to pick up methods
        prev_class = self._current_class
        self._current_class = node.name
        self.generic_visit(node)
        self._current_class = prev_class

        # Record method names on the class
        cls.methods = [
            fn.name
            for fn in self.functions
            if fn.parent_class == node.name
        ]

    # ---------------------------------------------------------------- functions
    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._handle_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._handle_function(node)

    def _handle_function(self, node):
        decorators = []
        for d in node.decorator_list:
            if isinstance(d, ast.Name):
                decorators.append(d.id)
            elif isinstance(d, ast.Attribute):
                decorators.append(d.attr)

        is_method = self._current_class is not None
        qualified = (
            f"{self._current_class}.{node.name}"
            if is_method
            else node.name
        )

        cv = _CallVisitor()
        cv.visit(node)

        fn = FunctionInfo(
            name=node.name,
            qualified_name=qualified,
            module=self.module_name,
            lineno=node.lineno,
            end_lineno=getattr(node, "end_lineno", node.lineno),
            decorators=decorators,
            is_method=is_method,
            parent_class=self._current_class,
            calls=cv.calls,
        )
        self.functions.append(fn)
        # Do NOT call generic_visit here — we already visited the body via
        # _CallVisitor.  We must NOT descend again or we'd double-register
        # nested functions.  Instead we handle the body manually.
        for child in ast.iter_child_nodes(node):
            # Visit nested functions / classes within the body
            self.visit(child)


def parse_file(file_path: str) -> ParsedModule:
    """
    Parse a Python source file and return a ParsedModule.

    Raises SyntaxError if the file cannot be parsed.
    Raises FileNotFoundError if the file does not exist.
    """
    module_name = os.path.splitext(os.path.basename(file_path))[0]

    with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
        source = fh.read()

    tree = ast.parse(source, filename=file_path)

    visitor = _ModuleVisitor(module_name=module_name, file_path=file_path)
    visitor.visit(tree)

    return ParsedModule(
        module_name=module_name,
        file_path=file_path,
        imports=visitor.imports,
        functions=visitor.functions,
        classes=visitor.classes,
    )


def parse_directory(directory: str, exclude_dirs: Optional[list[str]] = None) -> list[ParsedModule]:
    """
    Recursively parse all Python files under *directory*.

    Returns one ParsedModule per .py file found.
    Skips __pycache__ and any directories listed in exclude_dirs.
    """
    exclude = set(exclude_dirs or [])
    exclude.add("__pycache__")

    modules = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in exclude and not d.startswith(".")]
        for filename in files:
            if filename.endswith(".py"):
                full_path = os.path.join(root, filename)
                try:
                    modules.append(parse_file(full_path))
                except SyntaxError as exc:
                    print(f"[AST] Skipping {full_path}: {exc}")
    return modules
