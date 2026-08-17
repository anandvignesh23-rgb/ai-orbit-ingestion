from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.sources.base import BaseSource, RawRecord, SourceError

LOGGER = logging.getLogger("source.huggingface")

HUGGINGFACE_MODELS_URL = "https://huggingface.co/api/models"
HUGGINGFACE_MODEL_BASE_URL = "https://huggingface.co"
DEFAULT_TASKS = [
    "text-generation",
    "text-classification",
    "sentence-similarity",
    "automatic-speech-recognition",
    "text-to-image",
    "image-classification",
    "object-detection",
]


class HuggingFaceSource(BaseSource):
    def __init__(
        self,
        tasks: Iterable[str] | None = None,
        limit: int = 10,
        timeout: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.tasks = list(tasks or DEFAULT_TASKS)
        self.limit = limit
        self.timeout = timeout
        self._client = client

    @property
    def source_name(self) -> str:
        return "huggingface"

    def discover(self) -> list[RawRecord]:
        records: list[RawRecord] = []
        try:
            with self._managed_client() as client:
                for task in self.tasks:
                    payload = self._list_models(client, task)
                    if not isinstance(payload, list):
                        LOGGER.warning("unexpected_models_shape task=%s", task)
                        continue
                    for item in payload:
                        record = self._record_from_item(item, fallback_task=task)
                        if record is not None:
                            records.append(record)
        except SourceError:
            LOGGER.exception("huggingface_discovery_failed")
            return []

        LOGGER.info("discovered=%s", len(records))
        return records

    def extract(self, candidate: RawRecord) -> RawRecord:
        return candidate

    def _managed_client(self) -> _ClientContext:
        if self._client is not None:
            return _ClientContext(self._client, should_close=False)
        return _ClientContext(httpx.Client(timeout=self.timeout), should_close=True)

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _list_models(self, client: httpx.Client, task: str) -> list[Any]:
        try:
            response = client.get(
                HUGGINGFACE_MODELS_URL,
                params={
                    "pipeline_tag": task,
                    "sort": "downloads",
                    "direction": "-1",
                    "limit": self.limit,
                    "full": "true",
                },
            )
        except (httpx.TimeoutException, httpx.TransportError):
            raise

        if response.status_code in {429, 503}:
            raise SourceError(f"huggingface_temporarily_unavailable status={response.status_code}")
        if response.status_code >= 500:
            raise SourceError(f"huggingface_server_error status={response.status_code}")
        if response.status_code >= 400:
            raise SourceError(f"huggingface_client_error status={response.status_code}")

        try:
            data = response.json()
        except ValueError as exc:
            raise SourceError("huggingface_malformed_json") from exc
        if not isinstance(data, list):
            raise SourceError("huggingface_unexpected_json_shape")
        return data

    def _record_from_item(
        self,
        item: Any,
        fallback_task: str | None = None,
    ) -> RawRecord | None:
        if not isinstance(item, dict):
            LOGGER.warning("malformed_model_record")
            return None

        model_id = item.get("modelId") or item.get("id")
        if not model_id:
            LOGGER.warning("missing_required_model_id")
            return None

        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        pipeline_task = item.get("pipeline_tag") or fallback_task
        model_url = f"{HUGGINGFACE_MODEL_BASE_URL}/{model_id}"
        payload = {
            "model_id": model_id,
            "name": model_id.split("/")[-1],
            "provider": item.get("author") or _provider_from_model_id(model_id),
            "downloads": item.get("downloads"),
            "pipeline_task": pipeline_task,
            "tags": tags,
            "license": _license_from_tags(tags),
            "last_modified": item.get("lastModified") or item.get("last_modified"),
            "model_url": model_url,
        }
        return RawRecord(
            source_name=self.source_name,
            source_url=model_url,
            record_type="model",
            payload=payload,
        )


def _provider_from_model_id(model_id: str) -> str | None:
    if "/" not in model_id:
        return None
    provider = model_id.split("/", 1)[0].strip()
    return provider or None


def _license_from_tags(tags: list[Any]) -> str | None:
    for tag in tags:
        if not isinstance(tag, str):
            continue
        if tag.startswith("license:"):
            return tag.split(":", 1)[1]
    return None


class _ClientContext:
    def __init__(self, client: httpx.Client, should_close: bool) -> None:
        self.client = client
        self.should_close = should_close

    def __enter__(self) -> httpx.Client:
        return self.client

    def __exit__(self, *args: object) -> None:
        if self.should_close:
            self.client.close()
