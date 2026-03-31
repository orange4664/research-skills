"""
ast_analyzer.py — Deep AST analysis for Python ML repositories.

Uses Python's built-in `ast` module to extract:
- Class definitions (especially nn.Module subclasses)
- Function definitions with signatures
- Function call graphs
- Model layer structure from __init__
- Import dependency graph

Inspired by PyCG (ICSE'21) approach to assignment-based call resolution.
"""

import ast
import os
from pathlib import Path


class CallGraphBuilder(ast.NodeVisitor):
    """Build a function-level call graph from AST."""

    def __init__(self, module_name: str):
        self.module = module_name
        self.current_class: str | None = None
        self.current_func: str | None = None
        self.calls: dict[str, list[str]] = {}
        self.definitions: dict[str, dict] = {}

    def _qualified_name(self, name: str) -> str:
        parts = [self.module]
        if self.current_class:
            parts.append(self.current_class)
        parts.append(name)
        return ".".join(parts)

    def _caller_name(self) -> str | None:
        if self.current_func:
            return self._qualified_name(self.current_func)
        return self.module

    def visit_ClassDef(self, node: ast.ClassDef):
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        old_func = self.current_func
        self.current_func = node.name
        qname = self._qualified_name(node.name)

        # Extract signature
        args = []
        for arg in node.args.args:
            if arg.arg != "self":
                annotation = ""
                if arg.annotation:
                    try:
                        annotation = f": {ast.unparse(arg.annotation)}"
                    except Exception:
                        pass
                args.append(f"{arg.arg}{annotation}")

        # Extract docstring
        docstring = ast.get_docstring(node) or ""
        if len(docstring) > 200:
            docstring = docstring[:200] + "..."

        # Extract decorators
        decorators = []
        for dec in node.decorator_list:
            try:
                decorators.append(ast.unparse(dec))
            except Exception:
                pass

        self.definitions[qname] = {
            "name": node.name,
            "type": "method" if self.current_class else "function",
            "class": self.current_class,
            "args": args,
            "decorators": decorators,
            "docstring": docstring,
            "lineno": node.lineno,
            "end_lineno": getattr(node, "end_lineno", None),
        }

        self.calls.setdefault(qname, [])
        self.generic_visit(node)
        self.current_func = old_func

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call):
        caller = self._caller_name()
        if caller:
            try:
                callee = ast.unparse(node.func)
                self.calls.setdefault(caller, []).append(callee)
            except Exception:
                pass
        self.generic_visit(node)


class ClassAnalyzer(ast.NodeVisitor):
    """Extract class definitions, especially nn.Module subclasses."""

    def __init__(self, module_name: str):
        self.module = module_name
        self.classes: list[dict] = []
        self._current_class: str | None = None

    def visit_ClassDef(self, node: ast.ClassDef):
        bases = []
        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except Exception:
                bases.append("?")

        # Check if it's an ML model class
        is_model = any(
            b in bases or b.endswith(".Module") or b.endswith("LightningModule")
            for b in bases
            if isinstance(b, str)
        )

        methods = [
            n.name for n in ast.walk(node)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        # Extract layers from __init__ (self.xxx = nn.Layer(...))
        layers = []
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if (isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == "self"):
                        try:
                            value_str = ast.unparse(child.value)
                            if any(kw in value_str for kw in [
                                "nn.", "Conv", "Linear", "BatchNorm", "LayerNorm",
                                "Dropout", "Embedding", "LSTM", "GRU", "Transformer",
                                "Attention", "Pool", "ReLU", "Sequential",
                                "layers.", "tf.keras",
                            ]):
                                layers.append(f"{target.attr}: {value_str[:80]}")
                        except Exception:
                            pass

        docstring = ast.get_docstring(node) or ""
        if len(docstring) > 200:
            docstring = docstring[:200] + "..."

        self.classes.append({
            "name": node.name,
            "file": self.module,
            "bases": bases,
            "is_model": is_model,
            "methods": methods,
            "layers": layers,
            "docstring": docstring,
            "lineno": node.lineno,
        })

        self.generic_visit(node)


class ImportAnalyzer(ast.NodeVisitor):
    """Extract import statements and build import graph."""

    def __init__(self):
        self.imports: list[dict] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append({
                "type": "import",
                "module": alias.name,
                "alias": alias.asname,
                "lineno": node.lineno,
            })

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            self.imports.append({
                "type": "from",
                "module": module,
                "name": alias.name,
                "alias": alias.asname,
                "lineno": node.lineno,
            })


def analyze_file_ast(filepath: str, module_name: str) -> dict:
    """Analyze a single Python file using AST."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return {"error": f"SyntaxError in {filepath}", "module": module_name}

    # Call graph
    cg = CallGraphBuilder(module_name)
    cg.visit(tree)

    # Classes
    ca = ClassAnalyzer(module_name)
    ca.visit(tree)

    # Imports
    ia = ImportAnalyzer()
    ia.visit(tree)

    return {
        "module": module_name,
        "definitions": cg.definitions,
        "calls": cg.calls,
        "classes": ca.classes,
        "imports": ia.imports,
    }


def analyze_ast(code_dir: str) -> dict:
    """Analyze all Python files in a directory using AST.

    Returns:
        dict with keys:
        - classes: all class definitions (model classes highlighted)
        - call_graph: function → [callees] mapping
        - definitions: all function/method definitions with signatures
        - import_graph: file → [imported modules] mapping
        - model_classes: nn.Module subclasses with layer details
        - key_functions: important functions (train, forward, loss, etc.)
    """
    code_path = Path(code_dir)
    all_classes = []
    all_calls = {}
    all_definitions = {}
    import_graph = {}

    for pyfile in sorted(code_path.rglob("*.py")):
        if ".git" in pyfile.parts or "__pycache__" in pyfile.parts:
            continue
        rel = str(pyfile.relative_to(code_path))
        module_name = rel.replace(os.sep, ".").replace(".py", "")

        result = analyze_file_ast(str(pyfile), module_name)
        if "error" in result:
            continue

        all_classes.extend(result["classes"])
        all_calls.update(result["calls"])
        all_definitions.update(result["definitions"])

        # Build import graph
        import_graph[module_name] = list({
            imp["module"] for imp in result["imports"] if imp["module"]
        })

    # Identify model classes
    model_classes = [c for c in all_classes if c["is_model"]]

    # Identify key functions
    key_patterns = [
        "train", "forward", "loss", "evaluate", "eval", "test",
        "sample", "generate", "infer", "predict", "build_model",
        "main", "run", "setup", "configure",
    ]
    key_functions = {}
    for qname, defn in all_definitions.items():
        name_lower = defn["name"].lower()
        for pattern in key_patterns:
            if pattern in name_lower:
                key_functions.setdefault(pattern, []).append({
                    "qualified_name": qname,
                    "file": qname.rsplit(".", 1)[0] if "." in qname else qname,
                    **defn,
                })
                break

    # Simplify call graph — deduplicate and limit
    simplified_calls = {}
    for caller, callees in all_calls.items():
        unique = list(dict.fromkeys(callees))[:20]  # cap at 20
        if unique:
            simplified_calls[caller] = unique

    return {
        "classes": all_classes,
        "model_classes": model_classes,
        "call_graph": simplified_calls,
        "definitions": all_definitions,
        "import_graph": import_graph,
        "key_functions": key_functions,
        "stats": {
            "total_classes": len(all_classes),
            "model_classes": len(model_classes),
            "total_functions": len(all_definitions),
            "total_call_edges": sum(len(v) for v in simplified_calls.values()),
        },
    }
