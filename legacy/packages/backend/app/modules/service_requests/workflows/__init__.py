# Workflows exports

# =============================================================================
# NEW ARCHITECTURE (v2) - Autonomous workflows
# =============================================================================

# Core interfaces and dataclasses
from .workflow_interface import (
    WorkflowInterface,
    PredefinedWorkflow,
    WorkflowStep,
    WorkflowContext,
    ValidationResult,
    DocumentRequirement,
    TariffConfig,
    SupplementDefinition,
    StepType,
    RenovacionMotivo,
)

# Pasaporte workflow v2 (autonomous)
from .pasaporte_workflow_v2 import (
    PasaporteWorkflow,
    get_pasaporte_workflow
)

# Conducir workflow v2 (autonomous) - Migrated 2026-02-05
from .conducir_workflow import (
    ConducirWorkflow,
    LicenseClass,
    ApplicantType,
    DuplicadoMotivo,
    get_conducir_workflow
)

# Contrato workflow v2 (autonomous) - Migrated 2026-02-06
from .contrato_workflow import ContratoWorkflow

# PromocionAdministrativa workflow v2 (autonomous) - Migrated 2026-02-07
from .funcion_publica.promocion_workflow import (
    PromocionAdministrativaWorkflow,
    PromocionType,
    get_promocion_administrativa_workflow,
)

# CarnetFuncionario workflow v2 (autonomous) - Migrated 2026-02-07
from .funcion_publica.carnet_workflow import (
    CarnetFuncionarioWorkflow,
    get_carnet_funcionario_workflow,
)

# VerificacionFuncionario workflow v2 (autonomous) - Migrated 2026-02-07
from .funcion_publica.verificacion_workflow import (
    VerificacionFuncionarioWorkflow,
    get_verificacion_funcionario_workflow,
)

# PermisoExtraordinario workflow v2 (autonomous) - Migrated 2026-02-07
from .funcion_publica.permiso_workflow import (
    PermisoExtraordinarioWorkflow,
    PermisoMotivo,
    get_permiso_extraordinario_workflow,
)

# CertificadoAdministrativo workflow v2 (autonomous) - Migrated 2026-02-07
from .funcion_publica.certificado_workflow import (
    CertificadoAdministrativoWorkflow,
    CertificadoTipo,
    get_certificado_administrativo_workflow,
)

# Vehiculo workflows v2 (autonomous, split by domain) - Migrated 2026-02-07
from .vehiculos.matriculacion_workflow import (
    MatriculacionTransferenciaWorkflow,
    get_matriculacion_transferencia_workflow,
)
from .vehiculos.inspeccion_workflow import (
    InspeccionVehiculoWorkflow,
    get_inspeccion_vehiculo_workflow,
)
from .vehiculos.duplicado_workflow import (
    DuplicadoVehiculoWorkflow,
    get_duplicado_vehiculo_workflow,
)

# Extranjeria workflows v2 (autonomous) - Migrated 2026-02-07
from .extranjeria import (
    ResidenciaWorkflow,
    get_residencia_workflow,
    TramitesVisadoWorkflow,
    get_tramites_visado_workflow,
    # Backward compat aliases
    ProrrogaVisadoWorkflow,
    get_prorroga_visado_workflow,
)

# BundlePayment workflow (OMS — autonomo fiscal obligations) - 2026-03-20
from .bundle_payment_workflow import (
    BundlePaymentWorkflow,
    get_bundle_payment_workflow,
)

# Generic workflows (data-driven from database, now v2)
from .generic_workflow import (
    GenericWorkflowStandard,
    GenericWorkflowDirectPayment,
    load_generic_workflow
)

__all__ = [
    # === NEW (v2) ===
    # Protocol and base class
    "WorkflowInterface",
    "PredefinedWorkflow",
    # Core dataclasses
    "WorkflowStep",
    "WorkflowContext",
    "ValidationResult",
    "DocumentRequirement",
    "TariffConfig",
    "SupplementDefinition",
    "StepType",
    "RenovacionMotivo",
    # Pasaporte v2
    "PasaporteWorkflow",
    "get_pasaporte_workflow",
    # Conducir v2
    "ConducirWorkflow",
    "LicenseClass",
    "ApplicantType",
    "DuplicadoMotivo",
    "get_conducir_workflow",

    # Contrato v2
    "ContratoWorkflow",
    # PromocionAdministrativa v2
    "PromocionAdministrativaWorkflow",
    "PromocionType",
    "get_promocion_administrativa_workflow",
    # CarnetFuncionario v2
    "CarnetFuncionarioWorkflow",
    "get_carnet_funcionario_workflow",
    # VerificacionFuncionario v2
    "VerificacionFuncionarioWorkflow",
    "get_verificacion_funcionario_workflow",
    # PermisoExtraordinario v2
    "PermisoExtraordinarioWorkflow",
    "PermisoMotivo",
    "get_permiso_extraordinario_workflow",
    # CertificadoAdministrativo v2
    "CertificadoAdministrativoWorkflow",
    "CertificadoTipo",
    "get_certificado_administrativo_workflow",

    # Vehiculo v2 (3 workflows by domain)
    "MatriculacionTransferenciaWorkflow",
    "get_matriculacion_transferencia_workflow",
    "InspeccionVehiculoWorkflow",
    "get_inspeccion_vehiculo_workflow",
    "DuplicadoVehiculoWorkflow",
    "get_duplicado_vehiculo_workflow",

    # Extranjeria v2
    "ResidenciaWorkflow",
    "get_residencia_workflow",
    "TramitesVisadoWorkflow",
    "get_tramites_visado_workflow",
    "ProrrogaVisadoWorkflow",       # backward compat alias
    "get_prorroga_visado_workflow",  # backward compat alias

    # BundlePayment (OMS)
    "BundlePaymentWorkflow",
    "get_bundle_payment_workflow",

    # Generic workflows (data-driven, now v2)
    "GenericWorkflowStandard",
    "GenericWorkflowDirectPayment",
    "load_generic_workflow"
]
