"""
tests_mapper.py — Test file identification for ChangeGraph.

Maps affected source modules/functions to relevant test files using:
  1. Naming conventions: test_<module>.py or <module>_test.py
  2. Import scanning: test files that import the affected module
  3. Function name matching: test files containing test_<function_name>

All analysis is deterministic — no LLM involvement.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional

from .python_ast import ParsedModule, parse_file


@dataclass
class TestFileMatch:
    """A test file identified as relevant to the change."""
    file_path: str
    module_name: str
    match_reasons: list[str] = field(default_factory=list)
    matched_functions: list[str] = field(default_factory=list)

    @property
    def primary_reason(self) -> str:
        return self.match_reasons[0] if self.match_reasons else "Unknown"


class TestMapper:
    """
    Identifies test files relevant to a set of changed/affected modules.

    The mapper works against the full list of ParsedModules from the repo,
    including test files.
    """

    def __init__(self, all_modules: list[ParsedModule]):
        self.all_modules = all_modules
        self._test_modules = self._collect_test_modules()

    def _collect_test_modules(self) -> list[ParsedModule]:
        """Return only modules whose name starts with 'test_' or ends with '_test'."""
        return [
            m for m in self.all_modules
            if m.module_name.startswith("test_") or m.module_name.endswith("_test")
        ]

    def find_tests(
        self,
        affected_modules: list[str],
        affected_function_names: Optional[list[str]] = None,
    ) -> list[TestFileMatch]:
        """
        Return test files relevant to the affected modules and functions.

        affected_modules: list of module name stems (e.g. ["checkout", "payment"])
        affected_function_names: optional list of bare function names
        """
        affected_set = set(affected_modules)
        affected_funcs = set(affected_function_names or [])
        results: dict[str, TestFileMatch] = {}

        for test_mod in self._test_modules:
            reasons: list[str] = []
            matched_funcs: list[str] = []

            # 1. Naming convention: test_<module> or <module>_test
            for mod_name in affected_set:
                if test_mod.module_name == f"test_{mod_name}":
                    reasons.append(
                        f"Naming convention: '{test_mod.module_name}' matches "
                        f"test file for '{mod_name}'"
                    )
                elif test_mod.module_name == f"{mod_name}_test":
                    reasons.append(
                        f"Naming convention: '{test_mod.module_name}' matches "
                        f"test file for '{mod_name}'"
                    )

            # 2. Import-based matching: test file imports an affected module
            for imp in test_mod.imports:
                imported_top = imp.module.split(".")[0]
                if imported_top in affected_set:
                    reasons.append(
                        f"Import: '{test_mod.module_name}' imports '{imp.module}' "
                        f"(affected module)"
                    )
                    break  # one reason per test file per category is enough

            # 3. Function name matching: test functions mention affected function names
            if affected_funcs:
                for fn in test_mod.functions:
                    for afn in affected_funcs:
                        if afn.lower() in fn.name.lower():
                            matched_funcs.append(fn.name)
                            if fn.name not in [r.split("'")[1] for r in reasons if "'" in r]:
                                reasons.append(
                                    f"Function match: '{fn.name}' in "
                                    f"'{test_mod.module_name}' references '{afn}'"
                                )

            if reasons:
                key = test_mod.file_path
                if key not in results:
                    results[key] = TestFileMatch(
                        file_path=test_mod.file_path,
                        module_name=test_mod.module_name,
                        match_reasons=reasons,
                        matched_functions=list(set(matched_funcs)),
                    )
                else:
                    # Merge reasons
                    results[key].match_reasons.extend(
                        r for r in reasons if r not in results[key].match_reasons
                    )
                    results[key].matched_functions = list(
                        set(results[key].matched_functions + matched_funcs)
                    )

        # Sort: most reasons first (most relevant test files at the top)
        return sorted(results.values(), key=lambda x: -len(x.match_reasons))
