"""Deterministic, closed v1 projection for the future YASB consumer."""

import json

from .model import DocumentView, ProviderState

def project_document(document: DocumentView) -> str:
    """Return exactly one canonical JSON document and one terminating newline."""

    if not isinstance(document, DocumentView):
        raise TypeError("document must be a DocumentView")
    providers: list[dict[str, object]] = []
    for view in document.providers:
        item: dict[str, object] = {
            "provider": view.provider.value,
            "state": view.state.value,
        }
        if view.display_label is not None:
            item["display_label"] = view.display_label
        if view.state is ProviderState.SAFE_ERROR:
            if view.error is None:
                raise ValueError("safe_error requires an error code")
            item["error"] = {"code": view.error.code.value}
        providers.append(item)
    return (
        json.dumps(
            {"version": 1, "providers": providers},
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    )

def project_bytes(document: DocumentView) -> bytes:
    """Return the projection encoded as UTF-8 for stdout."""

    return project_document(document).encode("utf-8")
