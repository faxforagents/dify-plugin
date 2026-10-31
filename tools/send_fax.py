from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.faxforagents_api import call, resource_id


class SendFaxTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        key = self.runtime.credentials.get("api_key", "")
        quote_id = resource_id(tool_parameters.get("quote_id"), "quote_id")
        approval_id = tool_parameters.get("approval_id") or None
        if approval_id:
            approval_id = resource_id(approval_id, "approval_id")
        idempotency_key = str(tool_parameters.get("idempotency_key") or "").strip() or f"dify:{quote_id}"
        client_reference = str(tool_parameters.get("client_reference") or "").strip()[:200] or None
        job = call(
            key,
            "POST",
            "/v1/faxes",
            body={"quote_id": quote_id, "approval_id": approval_id, "client_reference": client_reference},
            headers={"Idempotency-Key": idempotency_key},
        )
        how = ""
        if job.get("approval_id"):
            how = f" under approval {job['approval_id']}"
        elif job.get("policy_version_id"):
            how = f" under policy version {job['policy_version_id']}"
        yield self.create_text_message(
            f"Fax {job['id']} queued to {job.get('to')}{how} ({job.get('billable_pages')} page(s), "
            f"{job.get('amount_micro')} micro held). Not delivered yet: read it with Get fax status."
        )
        yield self.create_json_message({"fax": job, "idempotency_key": idempotency_key})
        yield self.create_variable_message("fax_id", job["id"])
        yield self.create_variable_message("state", job.get("state"))
