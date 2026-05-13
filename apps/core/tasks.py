"""Background-task shim — wraps django-q2's ``async_task`` in the ``.enqueue()`` call style.

Use:
    from apps.core.tasks import task

    @task
    def send_quotation_via_line(doc_id: int, tenant_id: int) -> None:
        ...

    # somewhere in a view/service:
    send_quotation_via_line.enqueue(doc.pk, doc.tenant_id)

The decorated function is still a plain callable (``send_quotation_via_line(...)`` works
inline); ``.enqueue()`` schedules it onto django-q's Redis-backed queue (drained by
``manage.py qcluster``). In dev/tests ``Q_CLUSTER['sync']=True`` runs every ``async_task``
inline so test assertions about post-POST side effects continue to hold; production sets
``sync=False`` and the qcluster process picks the tasks up.

Task functions MUST activate the tenant context themselves (CLAUDE.md §5) — pass the
``tenant_id`` as an arg and ``with tenant_context(Tenant.objects.get(pk=tenant_id)):``
inside the body.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from django_q.tasks import async_task


class _Task:
    """Callable wrapper that exposes ``.enqueue(*a, **kw)`` alongside the plain function."""

    def __init__(self, fn: Callable[..., Any]) -> None:
        self._fn = fn
        functools.update_wrapper(self, fn)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._fn(*args, **kwargs)

    def enqueue(self, *args: Any, **kwargs: Any) -> str:
        """Hand the call off to django-q. Returns the queued task id (string)."""
        return async_task(f"{self._fn.__module__}.{self._fn.__qualname__}", *args, **kwargs)


def task(fn: Callable[..., Any] | None = None, **_options: Any):
    """Mark a function as a background task. Usable as ``@task`` or ``@task(...)``."""
    if fn is None:
        return lambda f: _Task(f)
    return _Task(fn)
