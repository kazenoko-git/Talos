"""Check development dependencies without claiming hardware verification."""
import importlib.metadata
import shutil
import sys


def main():
    problems = []
    if sys.version_info < (3, 11):
        problems.append("Python 3.11 or newer is required")
    print(f"Python: {sys.version.split()[0]}")
    for package in ("cocotb", "pytest"):
        try:
            print(f"{package}: {importlib.metadata.version(package)}")
        except importlib.metadata.PackageNotFoundError:
            problems.append(f"Missing Python dependency: {package}; run make setup")
    compiler = shutil.which("iverilog")
    if compiler:
        print(f"Icarus Verilog: {compiler}")
    else:
        problems.append("Icarus Verilog (iverilog) is missing from PATH")
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    print("Development dependencies available. No RTL tests or synthesis were run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
