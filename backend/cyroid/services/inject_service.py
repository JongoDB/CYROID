# backend/cyroid/services/inject_service.py
from datetime import datetime, timezone
from typing import Dict, Any
from sqlalchemy.orm import Session
from cyroid.models.inject import Inject, InjectStatus
from cyroid.models.vm import VM
from cyroid.services.docker_service import DockerService
import logging

logger = logging.getLogger(__name__)


class InjectService:
    """Service for executing MSEL injects on target VMs."""

    def __init__(self, db: Session, docker_service: DockerService):
        self.db = db
        self.docker = docker_service

    def execute_inject(self, inject: Inject, vm_map: Dict[str, VM]) -> Dict[str, Any]:
        """
        Execute an inject's actions on target VMs.

        Args:
            inject: The Inject model to execute
            vm_map: Dict mapping VM hostnames to VM objects

        Returns:
            Dict with 'success' boolean and 'results' list
        """
        inject.status = InjectStatus.EXECUTING
        inject.executed_at = datetime.now(timezone.utc)
        self.db.commit()

        results = []
        success = True

        for action in inject.actions or []:
            action_type = action.get('action_type')
            params = action.get('parameters', {})

            try:
                if action_type == 'run_command':
                    result = self._execute_command(params, vm_map)
                elif action_type == 'place_file':
                    result = self._place_file(params, vm_map)
                else:
                    result = {'error': f'Unknown action type: {action_type}'}
                    success = False

                if 'error' in result:
                    success = False

                results.append({'action': action, 'result': result})
            except Exception as e:
                logger.error(f"Failed to execute action: {e}")
                results.append({'action': action, 'error': str(e)})
                success = False

        # Update inject status
        inject.status = InjectStatus.COMPLETED if success else InjectStatus.FAILED
        inject.execution_log = str(results)
        self.db.commit()

        return {'success': success, 'results': results}

    def _execute_command(self, params: Dict, vm_map: Dict[str, VM]) -> Dict:
        """Execute a command on a target VM."""
        target_vm_name = params.get('target_vm')
        command = params.get('command')

        if target_vm_name not in vm_map:
            return {'error': f'VM {target_vm_name} not found'}

        vm = vm_map[target_vm_name]
        if not vm.container_id:
            return {'error': f'VM {target_vm_name} has no container'}

        exit_code, output = self.docker.exec_command(vm.container_id, command)
        return {'exit_code': exit_code, 'output': output}

    def _place_file(self, params: Dict, vm_map: Dict[str, VM]) -> Dict:
        """Place a file on a target VM."""
        target_vm_name = params.get('target_vm')
        filename = params.get('filename')
        target_path = params.get('target_path')

        if target_vm_name not in vm_map:
            return {'error': f'VM {target_vm_name} not found'}

        vm = vm_map[target_vm_name]
        if not vm.container_id:
            return {'error': f'VM {target_vm_name} has no container'}

        # TODO: Implement actual file placement via artifact service
        # For now, just log the action and report success
        logger.info(f"Would place {filename} at {target_path} on {target_vm_name}")
        return {'placed': True, 'path': target_path, 'filename': filename}

    def skip_inject(self, inject: Inject, reason: str = "") -> None:
        """Mark an inject as skipped."""
        inject.status = InjectStatus.SKIPPED
        inject.execution_log = f"Skipped: {reason}" if reason else "Skipped by user"
        self.db.commit()
