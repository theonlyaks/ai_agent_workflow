"""Exception hierarchy. Every error raised on purpose by the app derives from WorkflowAgentError."""


class WorkflowAgentError(Exception):
    """Base class for all application errors."""


class ConfigError(WorkflowAgentError):
    """Invalid Excel workflow file, YAML binding, or tool configuration (fail fast at startup)."""


class WorkflowNotFoundError(WorkflowAgentError):
    pass


class ToolError(WorkflowAgentError):
    """A tool failed in a way the user should be told about (bad file, missing column...)."""


class ToolInputError(ToolError):
    """A tool received arguments it cannot work with."""


class TransientToolError(ToolError):
    """A temporary failure (timeout, 503...). The executor retries these per the step's retry policy."""


class LLMError(WorkflowAgentError):
    """The LLM call failed (network, auth, rate limit, invalid response)."""


class LLMUnavailableError(LLMError):
    """No LLM is configured (offline mode) or it was disabled."""


class LLMRefusalError(LLMError):
    """The model declined the request (stop_reason == 'refusal')."""
