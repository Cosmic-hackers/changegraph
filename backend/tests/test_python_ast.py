"""
backend/tests/test_python_ast.py — Tests for the Python AST parser.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.app.analyzers.python_ast import parse_file, parse_directory

SHOP_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "sample_repos", "test_shop")
CHECKOUT_PY = os.path.join(SHOP_DIR, "checkout.py")
USERS_PY = os.path.join(SHOP_DIR, "users.py")


class TestParseFile:
    def test_parses_checkout(self):
        mod = parse_file(CHECKOUT_PY)
        assert mod.module_name == "checkout"
        assert len(mod.functions) > 0

    def test_checkout_has_calculate_total(self):
        mod = parse_file(CHECKOUT_PY)
        fn_names = [fn.name for fn in mod.functions]
        assert "calculate_total" in fn_names

    def test_checkout_has_checkout_function(self):
        mod = parse_file(CHECKOUT_PY)
        fn_names = [fn.name for fn in mod.functions]
        assert "checkout" in fn_names

    def test_checkout_imports_payment(self):
        mod = parse_file(CHECKOUT_PY)
        imported = [imp.module for imp in mod.imports]
        assert "payment" in imported

    def test_checkout_imports_invoice(self):
        mod = parse_file(CHECKOUT_PY)
        imported = [imp.module for imp in mod.imports]
        assert "invoice" in imported

    def test_users_has_authenticate_user(self):
        mod = parse_file(USERS_PY)
        fn_names = [fn.name for fn in mod.functions]
        assert "authenticate_user" in fn_names

    def test_calculate_total_calls_get_product_price(self):
        mod = parse_file(CHECKOUT_PY)
        calc_fn = next(fn for fn in mod.functions if fn.name == "calculate_total")
        assert "get_product_price" in calc_fn.calls

    def test_module_name_is_file_stem(self):
        mod = parse_file(USERS_PY)
        assert mod.module_name == "users"

    def test_file_path_stored(self):
        mod = parse_file(CHECKOUT_PY)
        assert mod.file_path == CHECKOUT_PY


class TestParseDirectory:
    def test_finds_all_py_files(self):
        modules = parse_directory(SHOP_DIR)
        module_names = {m.module_name for m in modules}
        for expected in ("checkout", "payment", "invoice", "refund", "cart", "users", "products"):
            assert expected in module_names, f"Missing module: {expected}"

    def test_finds_test_files(self):
        modules = parse_directory(SHOP_DIR)
        module_names = {m.module_name for m in modules}
        assert "test_checkout" in module_names
        assert "test_payment" in module_names
        assert "test_refund" in module_names

    def test_returns_parsed_module_objects(self):
        modules = parse_directory(SHOP_DIR)
        assert all(hasattr(m, "functions") for m in modules)
        assert all(hasattr(m, "imports") for m in modules)

    def test_excludes_pycache(self):
        modules = parse_directory(SHOP_DIR)
        for m in modules:
            assert "__pycache__" not in m.file_path
