#!/usr/bin/env python3
"""
Script Runner
Ensures scripts run with the correct virtual environment
"""

import hashlib
import os
import sys
import subprocess
from pathlib import Path


TIMEOUT_DEPS = 600  # 10 minutes


def get_venv_python() -> Path:
    """Get the virtual environment Python executable"""
    skill_dir = Path(__file__).parent.parent
    venv_dir = skill_dir / ".venv"

    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    else:
        return venv_dir / "bin" / "python"


def ensure_venv() -> Path:
    """Ensure virtual environment exists, return Python path"""
    venv_python = get_venv_python()

    if not venv_python.exists():
        print("Setting up environment...")
        skill_dir = Path(__file__).parent.parent
        setup_script = skill_dir / "scripts" / "setup_environment.py"

        result = subprocess.run(
            [sys.executable, str(setup_script)], timeout=TIMEOUT_DEPS
        )
        if result.returncode != 0:
            print("Failed to set up environment")
            sys.exit(1)

    return venv_python


def _file_hash(path: Path) -> str:
    """Return SHA-256 hex digest of a file, or '' if missing."""
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_deps():
    """Ensure Python dependencies are up-to-date."""
    skill_dir = Path(__file__).parent.parent
    req_file = skill_dir / "requirements.txt"
    hash_file = skill_dir / ".venv" / ".requirements.hash"

    if not req_file.exists():
        return

    current_hash = _file_hash(req_file)
    if hash_file.exists() and hash_file.read_text().strip() == current_hash:
        return  # up-to-date

    setup_script = skill_dir / "scripts" / "setup_environment.py"
    venv_python = get_venv_python()
    result = subprocess.run([str(venv_python), str(setup_script)], timeout=TIMEOUT_DEPS)
    if result.returncode == 0:
        hash_file.write_text(current_hash)


def ensure_node_deps():
    """Ensure Node.js dependencies are up-to-date (mirrors ensure_deps)."""
    skill_dir = Path(__file__).parent.parent
    package_json = skill_dir / "package.json"
    hash_file = skill_dir / ".node_modules.hash"

    if not package_json.exists():
        return

    current_hash = _file_hash(package_json)
    if hash_file.exists() and hash_file.read_text().strip() == current_hash:
        return  # up-to-date

    print("Installing Node.js dependencies...")
    npm_cmd = ["npm.cmd", "install"] if os.name == "nt" else ["npm", "install"]
    try:
        result = subprocess.run(npm_cmd, cwd=str(skill_dir), timeout=300)
    except FileNotFoundError:
        print("npm not found — please install Node.js")
        return

    if result.returncode == 0:
        hash_file.write_text(current_hash)


def main():
    if len(sys.argv) < 2:
        print("Usage: python run.py <command> [args...]")
        sys.exit(1)

    command = sys.argv[1]
    cmd_args = sys.argv[2:]

    venv_python = ensure_venv()
    ensure_deps()
    ensure_node_deps()

    # Determine if it's a Python script or a command
    if command.endswith(".py"):
        # Run Python script
        skill_dir = Path(__file__).parent.parent
        script_path = skill_dir / "scripts" / command

        if not script_path.exists():
            # Try as absolute/relative path
            script_path = Path(command).resolve()
            if not script_path.exists():
                print(f"Script not found: {command}")
                sys.exit(1)

        cmd = [str(venv_python), str(script_path)] + cmd_args
    else:
        # Run executable from venv (e.g., mineru)
        skill_dir = Path(__file__).parent.parent
        venv_dir = skill_dir / ".venv"

        if os.name == "nt":
            exe_path = venv_dir / "Scripts" / f"{command}.exe"
        else:
            exe_path = venv_dir / "bin" / command

        if not exe_path.exists():
            print(f"Command not found in venv: {command}")
            sys.exit(1)

        cmd = [str(exe_path)] + cmd_args

    try:
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(130)


if __name__ == "__main__":
    main()
