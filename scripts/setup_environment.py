#!/usr/bin/env python3
"""
Environment Setup
Manages virtual environment and dependencies using uv
"""

import hashlib
import os
import sys
import subprocess
import venv
from pathlib import Path


class SkillEnvironment:
    """Manages skill-specific virtual environment"""

    def __init__(self):
        self.skill_dir = Path(__file__).parent.parent
        self.venv_dir = self.skill_dir / ".venv"
        self.requirements_file = self.skill_dir / "requirements.txt"

        if os.name == "nt":
            self.venv_python = self.venv_dir / "Scripts" / "python.exe"
        else:
            self.venv_python = self.venv_dir / "bin" / "python"

    def ensure_venv(self) -> bool:
        """Ensure virtual environment exists"""
        if self.venv_dir.exists():
            return True

        print(f"Creating virtual environment in {self.venv_dir.name}/")
        try:
            venv.create(self.venv_dir, with_pip=True)
            print("Virtual environment created")
            return True
        except Exception as e:
            print(f"Failed to create venv: {e}")
            return False

    def _ensure_uv_installed(self) -> bool:
        """Ensure uv is installed"""
        try:
            result = subprocess.run(
                [str(self.venv_python), "-m", "uv", "--version"],
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0:
                return True
        except Exception:
            pass

        print("Installing uv...")
        try:
            result = subprocess.run(
                [str(self.venv_python), "-m", "pip", "install", "uv", "--quiet"],
                capture_output=True,
                timeout=120,
            )
            return result.returncode == 0
        except Exception:
            return False

    def install_deps(self) -> bool:
        """Install dependencies using uv pip install"""
        if not self.requirements_file.exists():
            print("No requirements.txt found")
            return True

        if not self._ensure_uv_installed():
            print("uv not available, falling back to pip...")
            result = subprocess.run(
                [
                    str(self.venv_python),
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    str(self.requirements_file),
                ]
            )
            return result.returncode == 0

        print("Installing dependencies with uv...")
        result = subprocess.run(
            [
                str(self.venv_python),
                "-m",
                "uv",
                "pip",
                "install",
                "-U",
                "-r",
                str(self.requirements_file),
            ]
        )
        return result.returncode == 0

    def install_node_deps(self) -> bool:
        """Run npm install for Node.js dependencies; skip if package.json unchanged."""
        package_json = self.skill_dir / "package.json"
        node_modules = self.skill_dir / "node_modules"
        hash_file = node_modules / ".node_modules.hash"

        if not package_json.exists():
            return True  # nothing to install

        current_hash = hashlib.sha256(package_json.read_bytes()).hexdigest()

        if (
            node_modules.exists()
            and hash_file.exists()
            and hash_file.read_text().strip() == current_hash
        ):
            return True  # already up-to-date

        print("Installing Node.js dependencies...")
        npm_cmd = ["npm.cmd", "install"] if os.name == "nt" else ["npm", "install"]
        try:
            result = subprocess.run(
                npm_cmd,
                cwd=str(self.skill_dir),
                timeout=300,
            )
        except FileNotFoundError:
            print("npm not found — please install Node.js")
            return False

        if result.returncode != 0:
            print("npm install failed")
            return False

        hash_file.write_text(current_hash)
        return True

    def install_playwright_browsers(self) -> bool:
        """Install Playwright browser (chromium)"""
        print("Installing Playwright chromium...")
        result = subprocess.run(
            [str(self.venv_python), "-m", "playwright", "install", "chromium"],
            timeout=300,
        )
        if result.returncode != 0:
            print("Failed to install Playwright chromium")
        return result.returncode == 0


def main():
    env = SkillEnvironment()

    if not env.ensure_venv():
        print("Failed to create virtual environment")
        return 1

    if not env.install_deps():
        print("Failed to install dependencies")
        return 1

    if not env.install_node_deps():
        print("Failed to install Node.js dependencies")
        return 1

    if not env.install_playwright_browsers():
        return 1

    print(f"\nEnvironment ready!")
    print(f"  Python: {env.venv_python}")


if __name__ == "__main__":
    sys.exit(main() or 0)
