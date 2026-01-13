# backend/cyroid/api/websocket.py
"""WebSocket endpoints for real-time console and status updates."""
import asyncio
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from sqlalchemy.orm import Session

from cyroid.database import get_db
from cyroid.models.vm import VM
from cyroid.utils.security import decode_access_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


async def get_current_user_ws(websocket: WebSocket, token: str, db: Session):
    """Authenticate WebSocket connection using JWT token."""
    from cyroid.models.user import User

    user_id = decode_access_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token")
        return None

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        await websocket.close(code=4001, reason="User not found")
        return None

    return user


@router.websocket("/ws/console/{vm_id}")
async def vm_console(
    websocket: WebSocket,
    vm_id: UUID,
    token: str = Query(...),
):
    """
    WebSocket endpoint for VM console access.
    Provides interactive terminal to running containers.
    """
    await websocket.accept()

    # Get database session
    db = next(get_db())

    try:
        # Authenticate
        user = await get_current_user_ws(websocket, token, db)
        if not user:
            return

        # Get VM
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            await websocket.close(code=4004, reason="VM not found")
            return

        if not vm.container_id:
            await websocket.close(code=4000, reason="VM has no running container")
            return

        # Import Docker service
        from cyroid.services.docker_service import get_docker_service
        docker = get_docker_service()

        # Get container and create exec instance
        container = docker.client.containers.get(vm.container_id)

        # Create interactive exec instance
        exec_instance = docker.client.api.exec_create(
            vm.container_id,
            cmd="/bin/bash",
            stdin=True,
            tty=True,
            stdout=True,
            stderr=True,
        )

        # Start exec and get socket
        exec_socket = docker.client.api.exec_start(
            exec_instance["Id"],
            socket=True,
            tty=True,
        )

        # Set socket to non-blocking
        exec_socket._sock.setblocking(False)

        async def read_from_container():
            """Read output from container and send to WebSocket."""
            try:
                while True:
                    try:
                        data = exec_socket._sock.recv(4096)
                        if data:
                            # Skip Docker stream header (8 bytes) if present
                            if len(data) > 8 and data[0] in (0, 1, 2):
                                data = data[8:]
                            await websocket.send_text(data.decode("utf-8", errors="replace"))
                        else:
                            break
                    except BlockingIOError:
                        await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Error reading from container: {e}")

        async def write_to_container():
            """Read input from WebSocket and send to container."""
            try:
                while True:
                    data = await websocket.receive_text()
                    exec_socket._sock.send(data.encode())
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for VM {vm_id}")
            except Exception as e:
                logger.error(f"Error writing to container: {e}")

        # Run both tasks concurrently
        await asyncio.gather(
            read_from_container(),
            write_to_container(),
            return_exceptions=True,
        )

    except WebSocketDisconnect:
        logger.info(f"Console WebSocket disconnected for VM {vm_id}")
    except Exception as e:
        logger.error(f"Console WebSocket error for VM {vm_id}: {e}")
        await websocket.close(code=4000, reason=str(e))
    finally:
        db.close()


@router.websocket("/ws/status/{range_id}")
async def range_status(
    websocket: WebSocket,
    range_id: UUID,
    token: str = Query(...),
):
    """
    WebSocket endpoint for range status updates.
    Sends VM status changes in real-time.
    """
    await websocket.accept()

    db = next(get_db())

    try:
        user = await get_current_user_ws(websocket, token, db)
        if not user:
            return

        from cyroid.models.range import Range

        range_obj = db.query(Range).filter(Range.id == range_id).first()
        if not range_obj:
            await websocket.close(code=4004, reason="Range not found")
            return

        # Poll for status updates
        last_status = {}
        while True:
            # Get current VM statuses
            vms = db.query(VM).filter(VM.range_id == range_id).all()
            current_status = {str(vm.id): vm.status.value for vm in vms}

            # Check for changes
            if current_status != last_status:
                await websocket.send_json({
                    "type": "status_update",
                    "range_id": str(range_id),
                    "range_status": range_obj.status.value,
                    "vms": current_status,
                })
                last_status = current_status.copy()

            # Refresh range status
            db.refresh(range_obj)

            await asyncio.sleep(2)  # Poll every 2 seconds

    except WebSocketDisconnect:
        logger.info(f"Status WebSocket disconnected for range {range_id}")
    except Exception as e:
        logger.error(f"Status WebSocket error for range {range_id}: {e}")
        await websocket.close(code=4000, reason=str(e))
    finally:
        db.close()


@router.websocket("/ws/events")
async def system_events(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    WebSocket endpoint for system-wide events.
    Broadcasts deployment progress, errors, and notifications.
    """
    await websocket.accept()

    db = next(get_db())

    try:
        user = await get_current_user_ws(websocket, token, db)
        if not user:
            return

        # Keep connection alive and wait for events
        # In a real implementation, this would subscribe to a Redis pub/sub
        while True:
            # Ping to keep connection alive
            await websocket.send_json({"type": "ping"})
            await asyncio.sleep(30)

    except WebSocketDisconnect:
        logger.info("Events WebSocket disconnected")
    except Exception as e:
        logger.error(f"Events WebSocket error: {e}")
        await websocket.close(code=4000, reason=str(e))
    finally:
        db.close()
