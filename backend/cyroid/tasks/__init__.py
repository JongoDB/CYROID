# cyroid/tasks/__init__.py
"""Dramatiq task definitions for async operations."""
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from cyroid.config import get_settings

settings = get_settings()

# Configure Redis broker
redis_broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(redis_broker)

from .deployment import deploy_range_task, teardown_range_task
from .vm_tasks import start_vm_task, stop_vm_task
from .blueprint_export import export_blueprint_async

__all__ = [
    'deploy_range_task',
    'teardown_range_task',
    'start_vm_task',
    'stop_vm_task',
    'export_blueprint_async',
]
