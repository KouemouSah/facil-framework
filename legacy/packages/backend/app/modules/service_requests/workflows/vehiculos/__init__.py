# Vehiculos workflows exports
from .matriculacion_workflow import (
    MatriculacionTransferenciaWorkflow,
    get_matriculacion_transferencia_workflow,
)
from .inspeccion_workflow import (
    InspeccionVehiculoWorkflow,
    get_inspeccion_vehiculo_workflow,
)
from .duplicado_workflow import (
    DuplicadoVehiculoWorkflow,
    get_duplicado_vehiculo_workflow,
)

__all__ = [
    "MatriculacionTransferenciaWorkflow",
    "get_matriculacion_transferencia_workflow",
    "InspeccionVehiculoWorkflow",
    "get_inspeccion_vehiculo_workflow",
    "DuplicadoVehiculoWorkflow",
    "get_duplicado_vehiculo_workflow",
]
