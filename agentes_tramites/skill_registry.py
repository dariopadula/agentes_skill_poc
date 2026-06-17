import importlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


SkillHandler = Callable[
    [str, dict[str, object], list[dict[str, str]]],
    dict,
]


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    display_name: str
    description: str
    user_examples: tuple[str, ...]
    extractable_fields: tuple[str, ...]
    when_to_use: tuple[str, ...]
    keywords: tuple[str, ...]
    handler: SkillHandler


class SkillRegistry:
    """Catálogo central de skills ejecutables."""

    def __init__(self, catalog_path: Path | None = None) -> None:
        self._skills: dict[str, SkillDefinition] = {}
        if catalog_path is not None:
            self.load(catalog_path)

    def load(self, catalog_path: Path) -> None:
        with catalog_path.open(encoding="utf-8") as stream:
            catalog = json.load(stream)

        for skill_name, metadata in catalog.items():
            self.register(
                SkillDefinition(
                    name=skill_name,
                    display_name=metadata["nombre"],
                    description=metadata["descripcion"],
                    user_examples=tuple(metadata["ejemplos_usuario"]),
                    extractable_fields=tuple(
                        metadata["datos_que_puede_extraer"]
                    ),
                    when_to_use=tuple(metadata["cuando_usar"]),
                    keywords=tuple(metadata["palabras_clave"]),
                    handler=_import_handler(metadata["handler"]),
                )
            )

    def register(self, skill: SkillDefinition) -> None:
        if skill.name in self._skills:
            raise ValueError(f"La skill '{skill.name}' ya está registrada.")
        self._skills[skill.name] = skill

    def get(self, name: str) -> SkillDefinition:
        try:
            return self._skills[name]
        except KeyError as exc:
            raise KeyError(f"Skill no registrada: {name}") from exc

    def names(self) -> list[str]:
        return sorted(self._skills)

    def routing_catalog(self) -> dict[str, dict[str, object]]:
        """Metadatos enviados a routers, sin exponer rutas de código."""
        return {
            skill.name: {
                "nombre": skill.display_name,
                "descripcion": skill.description,
                "ejemplos_usuario": list(skill.user_examples),
                "datos_que_puede_extraer": list(skill.extractable_fields),
                "cuando_usar": list(skill.when_to_use),
                "palabras_clave": list(skill.keywords),
            }
            for skill in self._skills.values()
        }


def _import_handler(import_path: str) -> SkillHandler:
    try:
        module_path, function_name = import_path.split(":", maxsplit=1)
    except ValueError as exc:
        raise ValueError(
            f"Handler inválido '{import_path}'. Usar 'modulo:funcion'."
        ) from exc

    module = importlib.import_module(module_path)
    handler = getattr(module, function_name)
    if not callable(handler):
        raise TypeError(f"El handler '{import_path}' no es ejecutable.")
    return handler


def build_default_registry() -> SkillRegistry:
    catalog_path = Path(__file__).parent / "skills" / "skill_registry.json"
    return SkillRegistry(catalog_path)
