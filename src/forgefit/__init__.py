"""ForgeFit: A Python-based API resilience testing toolkit.

Simulates service failures, injects faults, and evaluates application behavior
under adverse conditions.
"""

from forgefit.client import ClientResponse, ResilienceClient
from forgefit.config import ResilienceConfig
from forgefit.engine import ResilienceEngine, SafetyViolationError
from forgefit.exporters import (
    export_opentelemetry,
    export_prometheus,
    export_report,
)
from forgefit.models import RequestOutcome, ResilienceReport, Scenario
from forgefit.reports import (
    MetricDelta,
    ReportComparison,
    ReportSummary,
    compare_reports,
    list_reports,
    load_report,
    save_report,
)
from forgefit.schedules import (
    ConstantFaultSchedule,
    FaultSchedule,
    RampedFaultSchedule,
    StepEntry,
    StepFaultSchedule,
    create_fault_schedule,
)

__version__ = "1.0.0"
__all__ = [
    "ClientResponse",
    "ConstantFaultSchedule",
    "FaultSchedule",
    "MetricDelta",
    "RampedFaultSchedule",
    "ReportComparison",
    "ReportSummary",
    "RequestOutcome",
    "ResilienceClient",
    "ResilienceConfig",
    "ResilienceEngine",
    "ResilienceReport",
    "SafetyViolationError",
    "Scenario",
    "StepEntry",
    "StepFaultSchedule",
    "__version__",
    "compare_reports",
    "create_fault_schedule",
    "export_opentelemetry",
    "export_prometheus",
    "export_report",
    "list_reports",
    "load_report",
    "save_report",
]
