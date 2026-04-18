"""Central module that imports every model so Alembic autogenerate sees them."""

from app.models.audit import AuditLog  # noqa: F401
from app.models.backup import BackupArchive, RestoreEvent, RestoreState  # noqa: F401
from app.models.cycle import (  # noqa: F401
    Assignment,
    AssignmentState,
    EvaluationCycle,
    Template,
    TemplateVersion,
)
from app.models.feedback import (  # noqa: F401
    FeedbackEvent,
    FeedbackKind,
    FeedbackSignal,
    SubjectBlock,
)
from app.models.models import (  # noqa: F401
    Experiment,
    InferenceRouting,
    ModelVersion,
    ModelVersionStatus,
    RegisteredModel,
    RollbackEvent,
)
from app.models.plans import BomLine, Plan, PlanShareLink, PlanVersion  # noqa: F401
from app.models.rbac import Permission, Role, role_permissions, user_roles  # noqa: F401
from app.models.scoring import (  # noqa: F401
    CalculationTrace,
    GradeValue,
    RuleSet,
    RuleSetVersion,
    Submission,
)
from app.models.user import FailedLogin, Session, User  # noqa: F401
