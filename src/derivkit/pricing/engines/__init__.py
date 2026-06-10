"""Pricing engines and compatibility matrix."""

from derivkit.core.enums import EngineMethod, ExerciseType, ProcessType

# Engine compatibility: (process_type, exercise_type) -> supported methods
COMPATIBILITY_MATRIX: dict[tuple[ProcessType, ExerciseType], set[EngineMethod]] = {
    (ProcessType.BSM, ExerciseType.EUROPEAN): {
        EngineMethod.ANALYTIC,
        EngineMethod.TREE,
        EngineMethod.FDM,
        EngineMethod.MC,
        EngineMethod.QUAD,
    },
    (ProcessType.BSM, ExerciseType.AMERICAN): {
        EngineMethod.TREE,
        EngineMethod.FDM,
        EngineMethod.MC,
    },
}


def validate_compatibility(
    process_type: ProcessType,
    exercise: ExerciseType,
    method: EngineMethod,
) -> None:
    """Raise if engine is incompatible with process/exercise."""
    allowed = COMPATIBILITY_MATRIX.get((process_type, exercise), set())
    if method not in allowed:
        raise ValueError(
            f"Engine {method.value} not compatible with "
            f"process={process_type.value}, exercise={exercise.value}"
        )


from derivkit.pricing.engines.analytic import AnalyticEngine
from derivkit.pricing.engines.fdm import FdmEngine
from derivkit.pricing.engines.mc import McEngine
from derivkit.pricing.engines.quad import QuadEngine
from derivkit.pricing.engines.tree import TreeEngine

ENGINE_REGISTRY: dict[EngineMethod, type] = {
    EngineMethod.ANALYTIC: AnalyticEngine,
    EngineMethod.TREE: TreeEngine,
    EngineMethod.FDM: FdmEngine,
    EngineMethod.MC: McEngine,
    EngineMethod.QUAD: QuadEngine,
}


def create_engine(method: EngineMethod | str, **params: object) -> object:
    """Factory for pricing engines."""
    if isinstance(method, str):
        method = EngineMethod(method)
    cls = ENGINE_REGISTRY[method]
    return cls(**params)
