"""
Generate Sphinx Documentation.

Usage:
  generate_docs.py [--src=<path>] [--docs=<path>] [--output=<path>] [--force] [--build] [--recursive]

Options:
  --src=<path>       Root source directory [default: src]
  --docs=<path>      Sphinx docs directory [default: docs]
  --output=<path>    .rst output directory [default: docs/source]
  --force            Force re-generate .rst files
  --build            Also build HTML documentation
  --recursive        Recursively find all subpackages in --src
"""

import os
import subprocess
from docopt import docopt
from pathlib import Path


class SphinxDocGenerator:
    def __init__(self, src_root: str, docs_path: str, rst_output_path: str, force: bool = False, build: bool = False, recursive: bool = False):
        self.src_root = os.path.abspath(src_root)
        self.docs_path = os.path.abspath(docs_path)
        self.rst_output_path = os.path.abspath(rst_output_path)
        self.force = force
        self.build = build
        self.recursive = recursive
        self.ignore_dirs = {'__pycache__', '.venv', 'venv', 'build', '.git', 'tests'}

    def clean_rst_files(self):
        if os.path.exists(self.rst_output_path):
            for file in os.listdir(self.rst_output_path):
                if file.endswith(".rst") and file != "index.rst":
                    os.remove(os.path.join(self.rst_output_path, file))
            print(f"🧹 Cleaned .rst files in {self.rst_output_path}")
        else:
            os.makedirs(self.rst_output_path)
            print(f"📂 Created output directory: {self.rst_output_path}")

    def find_package_dirs(self):
        """Find all directories with an __init__.py recursively (i.e., Python packages)."""
        if not self.recursive:
            # Only process the root if not recursive
            return [self.src_root]

        package_dirs = []
        for root, dirs, files in os.walk(self.src_root):
            # Exclude ignored directories
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            if '__init__.py' in files:
                package_dirs.append(root)
        return package_dirs

    def run_apidoc(self, package_dirs):
        print("⚙️  Generating RST files:")
        for pkg_path in package_dirs:
            relative_path = os.path.relpath(pkg_path, self.src_root)
            print(f"   📦 {relative_path}")
            cmd = [
                "sphinx-apidoc",
                "-o", self.rst_output_path,
                pkg_path,
            ]
            if self.force:
                cmd.append("--force")
            subprocess.run([c for c in cmd if c], check=True)

    def build_html_docs(self):
        build_dir = os.path.join(self.docs_path, "build", "html")
        os.makedirs(build_dir, exist_ok=True)
        print("📦 Building HTML docs...")
        subprocess.run([
            "sphinx-build",
            "-b", "html",
            self.docs_path,
            build_dir
        ], check=True)
        print(f"✅ HTML documentation available at: {build_dir}")

    def generate(self):
        if self.force:
            self.clean_rst_files()
        package_dirs = self.find_package_dirs()
        self.run_apidoc(package_dirs)
        if self.build:
            self.build_html_docs()
        else:
            print("✅ Done: RST files generated.")


def main():
    args = docopt(__doc__)
    generator = SphinxDocGenerator(
        src_root=args["--src"],
        docs_path=args["--docs"],
        rst_output_path=args["--output"],
        force=args["--force"],
        build=args["--build"],
        recursive=args["--recursive"]
    )
    generator.generate()


if __name__ == "__main__":
    generator = SphinxDocGenerator(
    src_root=Path(__file__).parent.parent.parent,
    docs_path=Path(__file__).parent ,
    rst_output_path=Path(__file__).parent / "source",
    build=True,
    force=True,
    recursive=True,
    )
    generator.generate()
