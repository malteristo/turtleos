from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .audit import AuditLog, AuditRecord
from .events import Event, utc_now
from .paths import RuntimePaths
from .policy import CapabilityRegistry
from .tasks import Task, TaskStore


CAPABILITY_ID = "model.run_probe"


@dataclass(frozen=True)
class ProviderSpec:
    provider: str
    model: str
    raw: str

    @classmethod
    def parse(cls, value: str) -> "ProviderSpec":
        if ":" not in value:
            raise ValueError(f"Provider must use provider:model form: {value}")
        provider, model = value.split(":", 1)
        provider = provider.strip().lower()
        model = model.strip()
        if not provider or not model:
            raise ValueError(f"Provider must use provider:model form: {value}")
        if provider not in {"ollama", "anthropic", "gemini", "stub"}:
            raise ValueError(f"Unsupported provider {provider!r}; use ollama, anthropic, gemini, or stub")
        return cls(provider=provider, model=model, raw=value)

    def to_dict(self) -> dict[str, str]:
        return {"provider": self.provider, "model": self.model, "raw": self.raw}


@dataclass(frozen=True)
class ModelProbeResult:
    capability_id: str
    status: str
    artifact_path: str
    message: str
    provider_count: int
    successful_count: int
    audit_record_ids: list[str]

    def to_dict(self) -> dict[str, str | int | list[str]]:
        return {
            "capability_id": self.capability_id,
            "status": self.status,
            "artifact_path": self.artifact_path,
            "message": self.message,
            "provider_count": self.provider_count,
            "successful_count": self.successful_count,
            "audit_record_ids": self.audit_record_ids,
        }


def submit_model_probe(
    *,
    principal: str,
    title: str,
    prompt: str,
    context: str,
    providers: list[str],
    source: str,
    interface: str,
    registry_path: Path | str = Path("mage_registry.yaml"),
    scope: str = "model-probe",
    trust_level: str = "operator",
    approved: bool = False,
) -> Task:
    """Create a durable model-probe task and persist provider outputs for review."""
    if not providers:
        raise ValueError("At least one provider is required")
    parsed_providers = [ProviderSpec.parse(provider) for provider in providers]
    paths = RuntimePaths.for_principal(principal, registry_path=Path(registry_path))
    paths.ensure()
    audit = AuditLog(paths.audit_dir)
    store = TaskStore(paths.tasks_dir)

    event = Event(
        source=source,
        interface=interface,
        principal=principal,
        scope=scope,
        trust_level=trust_level,
        payload={
            "title": title,
            "prompt": prompt,
            "context": context,
            "providers": [provider.to_dict() for provider in parsed_providers],
        },
    )
    task = Task.from_event(event, kind="model.probe", title=title)
    task.checkpoint["event"] = event.to_dict()

    event_record = audit.append(
        AuditRecord("event.received", "ok", task_id=task.task_id, event_id=event.event_id, details=event.to_dict())
    )
    task.audit_refs.append(event_record.record_id)
    created_record = audit.append(AuditRecord("task.created", "ok", task_id=task.task_id, event_id=event.event_id))
    task.audit_refs.append(created_record.record_id)
    store.save(task)

    try:
        task.mark_running()
        running_record = audit.append(AuditRecord("task.running", "ok", task_id=task.task_id, event_id=event.event_id))
        task.audit_refs.append(running_record.record_id)
        store.save(task)

        policy = CapabilityRegistry.default(paths)
        decision = policy.authorize(capability_id=CAPABILITY_ID, principal=principal, approved=approved)
        policy_record = audit.append(
            AuditRecord(
                "policy.checked",
                "ok",
                task_id=task.task_id,
                event_id=event.event_id,
                details=decision.to_dict(),
            )
        )
        task.audit_refs.append(policy_record.record_id)

        runner = ModelProbeRunner(paths)
        result = runner.run(
            task_id=task.task_id,
            title=title,
            prompt=prompt,
            context=context,
            providers=parsed_providers,
            audit=audit,
            event_id=event.event_id,
        )
        task.audit_refs.extend(result.audit_record_ids)
        capability_record = audit.append(
            AuditRecord(
                "capability.called",
                result.status,
                task_id=task.task_id,
                event_id=event.event_id,
                details=result.to_dict(),
            )
        )
        task.audit_refs.append(capability_record.record_id)
        validation = policy.validate_artifact_path(capability_id=result.capability_id, artifact_path=result.artifact_path)
        task.artifact_refs.append(result.to_dict())
        artifact_record = audit.append(
            AuditRecord(
                "artifact.validated",
                validation["status"],
                task_id=task.task_id,
                event_id=event.event_id,
                details=validation,
            )
        )
        task.audit_refs.append(artifact_record.record_id)
        if result.successful_count == 0:
            task.mark_failed("All model providers failed", next_action="Inspect the probe artifact and provider audit records.")
            failed_record = audit.append(
                AuditRecord(
                    "task.failed",
                    "error",
                    task_id=task.task_id,
                    event_id=event.event_id,
                    details={"error": task.failure, "artifact_path": result.artifact_path},
                )
            )
            task.audit_refs.append(failed_record.record_id)
        else:
            task.mark_completed(next_action="Review the persisted probe artifact before changing model defaults.")
            complete_record = audit.append(
                AuditRecord("task.completed", "ok", task_id=task.task_id, event_id=event.event_id)
            )
            task.audit_refs.append(complete_record.record_id)
    except Exception as exc:
        task.mark_failed(str(exc), next_action="Inspect audit and repair the failing model provider or policy.")
        failed_record = audit.append(
            AuditRecord("task.failed", "error", task_id=task.task_id, event_id=event.event_id, details={"error": str(exc)})
        )
        task.audit_refs.append(failed_record.record_id)
        store.save(task)
        raise

    store.save(task)
    return task


class ModelProbeRunner:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        self.probe_dir = paths.native_runtime_dir / "model-probes"

    def run(
        self,
        *,
        task_id: str,
        title: str,
        prompt: str,
        context: str,
        providers: list[ProviderSpec],
        audit: AuditLog,
        event_id: str,
    ) -> ModelProbeResult:
        self.probe_dir.mkdir(parents=True, exist_ok=True)
        probe_id = f"probe_{uuid4().hex[:12]}"
        responses: list[dict[str, Any]] = []
        audit_record_ids: list[str] = []
        for provider in providers:
            response = self._call_provider(provider=provider, prompt=prompt, context=context)
            responses.append(response)
            record = audit.append(
                AuditRecord(
                    "model.provider.completed" if response["status"] == "ok" else "model.provider.failed",
                    response["status"],
                    task_id=task_id,
                    event_id=event_id,
                    details={
                        "provider": provider.to_dict(),
                        "latency_seconds": response.get("latency_seconds"),
                        "error": response.get("error"),
                    },
                )
            )
            audit_record_ids.append(record.record_id)

        successful = [response for response in responses if response["status"] == "ok"]
        artifact = {
            "probe_id": probe_id,
            "task_id": task_id,
            "title": title,
            "created_at": utc_now(),
            "context_digest": hashlib.sha256(context.encode("utf-8")).hexdigest(),
            "prompt_digest": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt": prompt,
            "context": context,
            "providers": [provider.to_dict() for provider in providers],
            "responses": responses,
            "comparison": {
                "status": "ready_for_review" if successful else "all_failed",
                "successful_count": len(successful),
                "provider_count": len(providers),
                "note": "This artifact preserves comparable outputs; practice-quality judgment remains a human/Spirit review step.",
            },
        }
        path = self.probe_dir / f"{probe_id}.json"
        path.write_text(json.dumps(artifact, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return ModelProbeResult(
            capability_id=CAPABILITY_ID,
            status="ok" if successful else "failed",
            artifact_path=str(path),
            message="model probe artifact written",
            provider_count=len(providers),
            successful_count=len(successful),
            audit_record_ids=audit_record_ids,
        )

    def _call_provider(self, *, provider: ProviderSpec, prompt: str, context: str) -> dict[str, Any]:
        started = time.monotonic()
        try:
            if provider.provider == "stub":
                output = _stub_response(provider, prompt, context)
            elif provider.provider == "ollama":
                output = _ollama_response(provider.model, prompt, context)
            elif provider.provider == "anthropic":
                output = _anthropic_response(provider.model, prompt, context)
            elif provider.provider == "gemini":
                output = _gemini_response(provider.model, prompt, context)
            else:
                raise ValueError(f"Unsupported provider: {provider.provider}")
            return {
                "provider": provider.provider,
                "model": provider.model,
                "status": "ok",
                "output": output,
                "latency_seconds": round(time.monotonic() - started, 3),
            }
        except Exception as exc:
            return {
                "provider": provider.provider,
                "model": provider.model,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "latency_seconds": round(time.monotonic() - started, 3),
            }


def _probe_messages(prompt: str, context: str) -> list[dict[str, str]]:
    user_content = f"Context:\n{context.strip() or '(none)'}\n\nProbe prompt:\n{prompt.strip()}"
    return [{"role": "user", "content": user_content}]


def _system_prompt() -> str:
    return (
        "You are responding inside a turtleOS model probe. Answer the probe directly. "
        "Do not mention that you are in a benchmark unless it is relevant to the question."
    )


def _stub_response(provider: ProviderSpec, prompt: str, context: str) -> str:
    return (
        f"[stub:{provider.model}] prompt_chars={len(prompt)} context_chars={len(context)} "
        f"prompt_sha256={hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:12]}"
    )


def _ollama_response(model: str, prompt: str, context: str) -> str:
    base_url = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": _system_prompt()}, *_probe_messages(prompt, context)],
        "stream": False,
        "options": {"num_ctx": int(os.environ.get("MODEL_PROBE_NUM_CTX", "16384"))},
    }
    if os.environ.get("MODEL_PROBE_THINK"):
        payload["think"] = os.environ["MODEL_PROBE_THINK"].lower() == "true"
    request = urllib.request.Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=int(os.environ.get("MODEL_PROBE_TIMEOUT", "300"))) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data.get("message", {}).get("content", "").strip() or "(no response generated)"


def _anthropic_response(model: str, prompt: str, context: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("anthropic package is not installed") from exc
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=int(os.environ.get("MODEL_PROBE_MAX_TOKENS", "4096")),
        system=_system_prompt(),
        messages=_probe_messages(prompt, context),
    )
    parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    return "\n".join(parts).strip() or "(no response generated)"


def _gemini_response(model: str, prompt: str, context: str) -> str:
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not configured")
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("google-genai package is not installed") from exc
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=f"{_system_prompt()}\n\nContext:\n{context.strip() or '(none)'}\n\nProbe prompt:\n{prompt.strip()}",
    )
    return response.text or "(no response generated)"
