"""Resource lookup tests for source and installed-wheel layouts."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ff_local_knowledge import resources


class ResourceLookupTests(unittest.TestCase):
    """Verify that installation resources remain available outside a source checkout."""

    def test_installed_package_does_not_search_arbitrary_ancestor_resources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_host = root / "source-host"
            for relative in ("templates/knowledge", "profiles", "skills"):
                (source_host / relative).mkdir(parents=True)
            fake_module = (
                source_host
                / ".venv"
                / "Lib"
                / "site-packages"
                / "ff_local_knowledge"
                / "resources.py"
            )
            fake_module.parent.mkdir(parents=True)
            installed_root = root / "installed" / "share" / "ff-local-knowledge-base"
            for relative in ("templates/knowledge", "profiles", "skills"):
                (installed_root / relative).mkdir(parents=True)
            neutral_cwd = root / "work"
            neutral_cwd.mkdir()

            old_cwd = Path.cwd()
            os.chdir(neutral_cwd)
            try:
                with patch.dict(os.environ, {}, clear=True), patch.object(
                    resources, "__file__", str(fake_module)
                ), patch(
                    "ff_local_knowledge.resources.sysconfig.get_path",
                    return_value=str(root / "installed"),
                ):
                    self.assertEqual(resources.locate_resource_root(), installed_root.resolve())
            finally:
                os.chdir(old_cwd)

    def test_locate_resource_root_uses_installed_share_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installed_root = root / "share" / "ff-local-knowledge-base"
            (installed_root / "templates" / "knowledge").mkdir(parents=True)
            (installed_root / "profiles").mkdir()
            (installed_root / "skills").mkdir()
            fake_module = root / "site-packages" / "ff_local_knowledge" / "resources.py"
            fake_module.parent.mkdir(parents=True)

            old_cwd = Path.cwd()
            os.chdir(root)
            try:
                with patch.dict(os.environ, {}, clear=True), patch.object(
                    resources, "__file__", str(fake_module)
                ), patch("ff_local_knowledge.resources.sysconfig.get_path", return_value=str(root)):
                    self.assertEqual(resources.locate_resource_root(), installed_root.resolve())
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
