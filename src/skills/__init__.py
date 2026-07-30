"""
skills — registry, YAML loader, and skill definitions.

Public API:
    from skills import load_skills          # merged built-in + YAML skills
    from skills.registry import BUILTIN_SKILLS
    from skills.loader import load_yaml_skills
"""

from .loader import load_skills

__all__ = ["load_skills"]
