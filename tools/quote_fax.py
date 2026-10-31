from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.faxforagents_api import FaxForAgentsError, call, dollars, resource_id


class QuoteFaxTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        key = self.runtime.credentials.get("api_key", "")
        to = str(tool_parameters.get("to") or "").strip()
        if not to.startswith("+"):
            raise FaxForAgentsError("to must be a number in E.164, for example +12025550123.")
        text = tool_parameters.get("text") or None
        markdown = tool_parameters.get("markdown") or None
        document_id = tool_parameters.get("document_id") or None
        given = [v for v in (text, markdown, document_id) if v]
        if len(given) != 1:
            raise FaxForAgentsError("Pass exactly one of text, markdown or document_id.")
        if document_id:
            document_id = resource_id(document_id, "document_id")
            document = call(key, "GET", f"/v1/documents/{document_id}")
        else:
            body = {"text": text, "markdown": markdown, "filename": tool_parameters.get("filename") or None}
            document = call(key, "POST", "/v1/documents", body=body)
            document_id = document["id"]
        cover = {
            k: str(tool_parameters.get(k)).strip()
            for k in ("to_name", "from_name", "subject", "message")
            if tool_parameters.get(k)
        }
        quote = call(
            key,
            "POST",
            "/v1/fax-quotes",
            body={"document_id": document_id, "to": to, "cover": cover or None},
        )
        if quote.get("authorization_required"):
            path = "a person must approve it in the dashboard before Send fax"
        elif quote.get("environment") == "test":
            path = "sandbox, not charged: Send fax sends it as is"
        else:
            path = "no approval needed: Send fax sends it as is"
        yield self.create_text_message(
            f"Quote {quote['id']}: {quote.get('billable_pages')} billable page(s) to {quote.get('to')} for "
            f"{dollars(quote.get('amount_micro', 0))}, expires {quote.get('expires_at')}; {path}. Nothing was sent."
        )
        yield self.create_json_message({"document": document, "quote": quote})
        yield self.create_variable_message("quote_id", quote["id"])
        yield self.create_variable_message("document_id", document_id)
        yield self.create_variable_message("authorization_required", bool(quote.get("authorization_required")))
