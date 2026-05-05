"""Semantic Excel workbook diffs for humans and LLM agents."""

from .diff import diff_workbooks
from .reporting import write_artifacts

__version__ = "0.1.0"

__all__ = ["__version__", "diff_workbooks", "write_artifacts"]
