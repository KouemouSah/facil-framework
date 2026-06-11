# Extranjeria workflows (v2 - PredefinedWorkflow)
# Aligned with Orden Ministerial 01/2021

from .residencia_workflow import ResidenciaWorkflow, get_residencia_workflow
from .tramites_visado_workflow import TramitesVisadoWorkflow, get_tramites_visado_workflow

# Backward compatibility aliases (renamed from ProrrogaVisadoWorkflow in v2.2)
ProrrogaVisadoWorkflow = TramitesVisadoWorkflow
get_prorroga_visado_workflow = get_tramites_visado_workflow

__all__ = [
    "ResidenciaWorkflow",
    "get_residencia_workflow",
    "TramitesVisadoWorkflow",
    "get_tramites_visado_workflow",
    # Backward compat
    "ProrrogaVisadoWorkflow",
    "get_prorroga_visado_workflow",
]
