
# Generated from canonical contract schemas. Do not edit by hand.

from typing import Literal

CredentialState = Literal['missing', 'active', 'invalid', 'expired', 'revoked', 'rotation_pending']
InstanceStatus = Literal['pending_setup', 'active', 'disabled', 'setup_failed', 'archived']
HealthStatus = Literal['unknown', 'healthy', 'degraded', 'unhealthy', 'auth_expired']
