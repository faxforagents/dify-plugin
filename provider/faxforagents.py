from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from tools.faxforagents_api import FaxForAgentsError, call


class FaxForAgentsProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            call(credentials.get("api_key", ""), "GET", "/v1/me")
        except FaxForAgentsError as e:
            raise ToolProviderCredentialValidationError(str(e)) from e
