from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.faxforagents_api import call, describe_fax, resource_id

# The carrier's raw payload (the signed webhook body and its headers) stays on the REST receipt.
RAW_EVIDENCE_KEYS = ("body", "headers")


def _agent_evidence(job: dict) -> dict:
    evidence = job.get("evidence")
    if isinstance(evidence, dict):
        job = {**job, "evidence": {k: v for k, v in evidence.items() if k not in RAW_EVIDENCE_KEYS}}
    return job


class GetFaxStatusTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        key = self.runtime.credentials.get("api_key", "")
        fax_id = resource_id(tool_parameters.get("fax_id"), "fax_id")
        job = _agent_evidence(call(key, "GET", f"/v1/faxes/{fax_id}"))
        text = describe_fax(job)
        if isinstance(job.get("evidence"), dict):
            text += (
                f" Evidence from {job.get('provider')}: {job.get('pages_sent')} of {job.get('billable_pages')} page(s)."
                " It is what the carrier reported, not legal proof the recipient accepted it."
            )
        yield self.create_text_message(text)
        yield self.create_json_message({"fax": job})
        yield self.create_variable_message("state", job.get("state"))
        yield self.create_variable_message("pages_sent", job.get("pages_sent"))
