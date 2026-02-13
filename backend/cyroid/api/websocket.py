# backend/cyroid/api/websocket.py
"""WebSocket endpoints for real-time console and status updates."""
import asyncio
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from starlette.websockets import WebSocketState
from sqlalchemy.orm import Session
import websockets

from cyroid.database import get_db
from cyroid.models.vm import VM
from cyroid.models.range import Range
from cyroid.utils.security import decode_access_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

# VNC port for desktop VMs (noVNC websockify)
VNC_WEBSOCKET_PORT = 8006


def get_dind_docker_client(range_obj: Range):
    """Get a Docker client for a DinD range.

    Returns None if range is not a DinD deployment.
    """
    if not range_obj.dind_container_id or not range_obj.dind_docker_url:
        return None

    from cyroid.services.dind_service import get_dind_service
    dind_service = get_dind_service()
    return dind_service.get_range_client(str(range_obj.id), range_obj.dind_docker_url)


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

    For DinD-isolated ranges, connects to the Docker daemon inside the DinD container.
    For non-DinD ranges (legacy), connects to the host Docker daemon.
    """
    await websocket.accept()

    # Get database session for auth and lookup only
    db = next(get_db())

    try:
        # Authenticate
        user = await get_current_user_ws(websocket, token, db)
        if not user:
            return

        # Get VM with range loaded
        vm = db.query(VM).filter(VM.id == vm_id).first()
        if not vm:
            await websocket.close(code=4004, reason="VM not found")
            return

        if not vm.container_id:
            await websocket.close(code=4000, reason="VM has no running container")
            return

        # Get the range to check if it's a DinD deployment
        range_obj = db.query(Range).filter(Range.id == vm.range_id).first()
        if not range_obj:
            await websocket.close(code=4000, reason="VM range not found")
            return

        # Extract what we need before releasing the session
        container_id = vm.container_id
        dind_container_id = range_obj.dind_container_id
        dind_docker_url = range_obj.dind_docker_url
        range_id_str = str(range_obj.id)

        # Release DB session - no longer needed for the streaming phase
        db.close()
        db = None

        # Get the appropriate Docker client (DinD or host)
        if dind_container_id and dind_docker_url:
            from cyroid.services.dind_service import get_dind_service
            dind_service = get_dind_service()
            docker_client = dind_service.get_range_client(range_id_str, dind_docker_url)
            logger.debug(f"Using DinD Docker client for VM {vm_id}")
        else:
            # Non-DinD (legacy) - use host Docker client
            from cyroid.services.docker_service import get_docker_service
            docker_client = get_docker_service().client
            logger.debug(f"Using host Docker client for VM {vm_id}")

        # Get container and create exec instance
        container = docker_client.containers.get(container_id)

        # Try /bin/bash first, fall back to /bin/sh
        # Use shell with login to get proper environment
        shell_cmd = ["/bin/sh", "-c", "if [ -x /bin/bash ]; then exec /bin/bash; else exec /bin/sh; fi"]

        # Create interactive exec instance
        exec_instance = docker_client.api.exec_create(
            container_id,
            cmd=shell_cmd,
            stdin=True,
            tty=True,
            stdout=True,
            stderr=True,
        )

        # Start exec and get socket
        exec_socket = docker_client.api.exec_start(
            exec_instance["Id"],
            socket=True,
            tty=True,
        )

        # Keep socket in blocking mode but use select for async behavior
        exec_socket._sock.setblocking(False)

        # Track if connection is still alive
        connection_alive = True

        async def read_from_container():
            """Read output from container and send to WebSocket."""
            nonlocal connection_alive
            try:
                # Initial wait for shell to start
                await asyncio.sleep(0.1)

                while connection_alive:
                    try:
                        data = exec_socket._sock.recv(4096)
                        if data:
                            # Skip Docker stream header (8 bytes) if present
                            if len(data) > 8 and data[0] in (0, 1, 2):
                                data = data[8:]
                            if data:  # Check again after stripping header
                                await websocket.send_text(data.decode("utf-8", errors="replace"))
                        else:
                            # Empty data means socket closed
                            logger.info(f"Container socket closed for VM {vm_id}")
                            connection_alive = False
                            break
                    except BlockingIOError:
                        # No data available, wait a bit
                        await asyncio.sleep(0.05)
                    except OSError as e:
                        # Socket error (connection reset, etc.)
                        logger.warning(f"Socket error for VM {vm_id}: {e}")
                        connection_alive = False
                        break
            except Exception as e:
                logger.error(f"Error reading from container: {e}")
                connection_alive = False

        async def write_to_container():
            """Read input from WebSocket and send to container."""
            nonlocal connection_alive
            try:
                while connection_alive:
                    try:
                        data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                        exec_socket._sock.send(data.encode())
                    except asyncio.TimeoutError:
                        # No input from user, continue loop
                        continue
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for VM {vm_id}")
                connection_alive = False
            except Exception as e:
                logger.error(f"Error writing to container: {e}")
                connection_alive = False

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
        if db is not None:
            db.close()


@router.websocket("/ws/vnc/{vm_id}")
async def vm_vnc_console(
    websocket: WebSocket,
    vm_id: UUID,
    token: str = Query(...),
):
    """
    WebSocket proxy for VNC console access (noVNC).
    Proxies WebSocket traffic to the VM's noVNC server for graphical desktop access.
    Used for Windows VMs and Linux VMs with desktop environments.

    For DinD-isolated ranges:
        - Uses iptables DNAT port forwarding via the DinD management IP
        - VNC traffic: Traefik -> DinD mgmt IP:proxy_port -> iptables DNAT -> VM:vnc_port

    For non-DinD ranges (legacy):
        - Connects directly to the container's IP address on the host Docker network
    """
    await websocket.accept()

    db = next(get_db())
    vnc_ws = None

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

        # Get the range to check for DinD and VNC proxy mappings
        range_obj = db.query(Range).filter(Range.id == vm.range_id).first()
        if not range_obj:
            await websocket.close(code=4000, reason="VM range not found")
            return

        # Extract what we need before releasing the session
        container_id = vm.container_id
        vnc_proxy_mappings = range_obj.vnc_proxy_mappings
        dind_docker_url = range_obj.dind_docker_url
        dind_container_id = range_obj.dind_container_id
        range_id_str = str(range_obj.id)

        # Release DB session - no longer needed for the streaming phase
        db.close()
        db = None

        # Determine VNC connection target
        vnc_host = None
        vnc_port = VNC_WEBSOCKET_PORT

        # Check if this is a DinD deployment with VNC proxy mappings
        vm_id_str = str(vm_id)
        if vnc_proxy_mappings and vm_id_str in vnc_proxy_mappings:
            # DinD deployment - use proxy mapping
            proxy_info = vnc_proxy_mappings[vm_id_str]
            vnc_host = proxy_info.get("proxy_host")
            vnc_port = proxy_info.get("proxy_port", VNC_WEBSOCKET_PORT)
            logger.debug(f"Using DinD VNC proxy for VM {vm_id}: {vnc_host}:{vnc_port}")
        elif dind_docker_url:
            # DinD deployment but no proxy mapping - get container IP from DinD
            if dind_container_id and dind_docker_url:
                from cyroid.services.dind_service import get_dind_service
                dind_service = get_dind_service()
                dind_client = dind_service.get_range_client(range_id_str, dind_docker_url)
            else:
                dind_client = None
            if dind_client:
                try:
                    container = dind_client.containers.get(container_id)
                    # Get IP from the first network the container is attached to
                    networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
                    for network_name, network_config in networks.items():
                        vnc_host = network_config.get("IPAddress")
                        if vnc_host:
                            break

                    # Determine VNC port based on image type
                    image_tags = container.image.tags if container.image.tags else []
                    image_name = image_tags[0] if image_tags else ""
                    if "kasmweb" in image_name:
                        vnc_port = 6901
                    elif "linuxserver/" in image_name or "lscr.io/linuxserver" in image_name:
                        vnc_port = 3000
                    elif "dockur" in image_name or "qemux" in image_name:
                        vnc_port = 8006
                    else:
                        vnc_port = 3000  # Default for containers

                    logger.debug(f"Using DinD container IP for VM {vm_id}: {vnc_host}:{vnc_port}")
                except Exception as e:
                    logger.error(f"Failed to get container info from DinD for VM {vm_id}: {e}")
                    await websocket.close(code=4000, reason="Container not found in DinD")
                    return
        else:
            # Non-DinD (legacy) - get container IP from host Docker
            from cyroid.services.docker_service import get_docker_service
            docker = get_docker_service()

            try:
                container = docker.client.containers.get(container_id)
                # Get IP from the first network the container is attached to
                networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
                for network_name, network_config in networks.items():
                    vnc_host = network_config.get("IPAddress")
                    if vnc_host:
                        break
            except Exception as e:
                logger.error(f"Failed to get container info for VM {vm_id}: {e}")
                await websocket.close(code=4000, reason="Container not found")
                return

        if not vnc_host:
            await websocket.close(code=4000, reason="Could not determine VNC connection target")
            return

        # Connect to the VNC WebSocket server
        vnc_url = f"ws://{vnc_host}:{vnc_port}/websockify"
        logger.info(f"Connecting to VNC at {vnc_url} for VM {vm_id}")

        try:
            vnc_ws = await websockets.connect(
                vnc_url,
                subprotocols=["binary"],
                ping_interval=None,  # Disable ping to avoid conflicts with noVNC
            )
        except Exception as e:
            logger.error(f"Failed to connect to VNC server for VM {vm_id}: {e}")
            await websocket.close(code=4000, reason=f"VNC connection failed: {str(e)}")
            return

        logger.info(f"VNC proxy established for VM {vm_id}")

        async def client_to_vnc():
            """Forward messages from client to VNC server."""
            try:
                while True:
                    data = await websocket.receive_bytes()
                    await vnc_ws.send(data)
            except WebSocketDisconnect:
                logger.info(f"Client disconnected from VNC proxy for VM {vm_id}")
            except Exception as e:
                logger.debug(f"Client->VNC error for VM {vm_id}: {e}")

        async def vnc_to_client():
            """Forward messages from VNC server to client."""
            try:
                async for message in vnc_ws:
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)
            except websockets.exceptions.ConnectionClosed:
                logger.info(f"VNC server closed connection for VM {vm_id}")
            except Exception as e:
                logger.debug(f"VNC->Client error for VM {vm_id}: {e}")

        # Run both proxy tasks concurrently
        done, pending = await asyncio.wait(
            [
                asyncio.create_task(client_to_vnc()),
                asyncio.create_task(vnc_to_client()),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        logger.info(f"VNC WebSocket disconnected for VM {vm_id}")
    except Exception as e:
        logger.error(f"VNC WebSocket error for VM {vm_id}: {e}")
        try:
            await websocket.close(code=4000, reason=str(e))
        except Exception:
            pass
    finally:
        if db is not None:
            db.close()
        if vnc_ws:
            try:
                await vnc_ws.close()
            except Exception:
                pass


@router.websocket("/ws/range-console/{range_id}")
async def range_console(
    websocket: WebSocket,
    range_id: UUID,
    token: str = Query(...),
):
    """
    WebSocket endpoint for Range Console - shell access to the DinD container.

    Provides interactive terminal to the Docker-in-Docker container that hosts
    the range's networks and VMs. Useful for:
    - Running docker commands (ps, logs, inspect)
    - Viewing network configuration (iptables, ip routes)
    - Troubleshooting range deployment issues
    - Debugging container networking

    Only available for DinD-based deployments.
    """
    await websocket.accept()

    db = next(get_db())

    try:
        # Authenticate
        user = await get_current_user_ws(websocket, token, db)
        if not user:
            return

        # Check user has admin or range_engineer role for console access
        if user.role not in ["admin", "range_engineer"]:
            await websocket.close(code=4003, reason="Insufficient permissions")
            return

        # Get range
        range_obj = db.query(Range).filter(Range.id == range_id).first()
        if not range_obj:
            await websocket.close(code=4004, reason="Range not found")
            return

        # Check if range has DinD container
        if not range_obj.dind_container_id:
            await websocket.close(code=4000, reason="Range is not a DinD deployment")
            return

        # Extract what we need before releasing the session
        dind_container_id = range_obj.dind_container_id

        # Release DB session - no longer needed for the streaming phase
        db.close()
        db = None

        # Get the DinD container from the host Docker
        from cyroid.services.docker_service import get_docker_service
        docker_service = get_docker_service()
        host_client = docker_service.client

        try:
            dind_container = host_client.containers.get(dind_container_id)
        except Exception as e:
            await websocket.close(code=4000, reason=f"DinD container not found: {e}")
            return

        # Check container is running
        if dind_container.status != "running":
            await websocket.close(code=4000, reason="DinD container is not running")
            return

        # Create interactive shell exec in the DinD container
        shell_cmd = ["/bin/sh", "-c", "if [ -x /bin/bash ]; then exec /bin/bash; else exec /bin/sh; fi"]

        exec_instance = host_client.api.exec_create(
            dind_container.id,
            cmd=shell_cmd,
            stdin=True,
            tty=True,
            stdout=True,
            stderr=True,
            privileged=True,  # Allow full access for diagnostics
        )

        # Start exec and get socket
        exec_socket = host_client.api.exec_start(
            exec_instance["Id"],
            socket=True,
            tty=True,
        )

        exec_socket._sock.setblocking(False)

        connection_alive = True

        async def read_from_container():
            """Read output from DinD container and send to WebSocket."""
            nonlocal connection_alive
            try:
                await asyncio.sleep(0.1)  # Wait for shell to start

                while connection_alive:
                    try:
                        data = exec_socket._sock.recv(4096)
                        if data:
                            # Skip Docker stream header (8 bytes) if present
                            if len(data) > 8 and data[0] in (0, 1, 2):
                                data = data[8:]
                            if data:
                                await websocket.send_text(data.decode("utf-8", errors="replace"))
                        else:
                            logger.info(f"DinD container socket closed for range {range_id}")
                            connection_alive = False
                            break
                    except BlockingIOError:
                        await asyncio.sleep(0.05)
                    except OSError as e:
                        logger.warning(f"Socket error for range {range_id}: {e}")
                        connection_alive = False
                        break
            except Exception as e:
                logger.error(f"Error reading from DinD container: {e}")
                connection_alive = False

        async def write_to_container():
            """Read input from WebSocket and send to DinD container."""
            nonlocal connection_alive
            try:
                while connection_alive:
                    try:
                        data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                        exec_socket._sock.send(data.encode())
                    except asyncio.TimeoutError:
                        continue
            except WebSocketDisconnect:
                logger.info(f"Range console WebSocket disconnected for range {range_id}")
                connection_alive = False
            except Exception as e:
                logger.error(f"Error writing to DinD container: {e}")
                connection_alive = False

        # Run both tasks concurrently
        await asyncio.gather(
            read_from_container(),
            write_to_container(),
            return_exceptions=True,
        )

    except WebSocketDisconnect:
        logger.info(f"Range console WebSocket disconnected for range {range_id}")
    except Exception as e:
        logger.error(f"Range console WebSocket error for range {range_id}: {e}")
        try:
            await websocket.close(code=4000, reason=str(e))
        except Exception:
            pass
    finally:
        if db is not None:
            db.close()


@router.websocket("/ws/status/{range_id}")
async def range_status(
    websocket: WebSocket,
    range_id: UUID,
    token: str = Query(...),
):
    """
    WebSocket endpoint for range status updates.
    Combines periodic polling with real-time event notifications.
    """
    await websocket.accept()

    db = next(get_db())
    connection_id = f"status_{range_id}_{id(websocket)}"

    try:
        user = await get_current_user_ws(websocket, token, db)
        if not user:
            return

        from cyroid.models.range import Range
        from cyroid.services.event_broadcaster import get_connection_manager

        range_obj = db.query(Range).filter(Range.id == range_id).first()
        if not range_obj:
            await websocket.close(code=4004, reason="Range not found")
            return

        # Register with connection manager for real-time events
        connection_manager = get_connection_manager()
        await connection_manager.connect(connection_id, websocket)
        await connection_manager.subscribe_to_range(connection_id, str(range_id))

        # Send initial status immediately
        vms = db.query(VM).filter(VM.range_id == range_id).all()
        current_status = {str(vm.id): vm.status.value for vm in vms}
        await websocket.send_json({
            "type": "status_update",
            "range_id": str(range_id),
            "range_status": range_obj.status.value,
            "vms": current_status,
        })

        # Poll for status updates (as backup to real-time events)
        last_status = current_status.copy()
        while True:
            # Refresh data
            db.expire_all()
            vms = db.query(VM).filter(VM.range_id == range_id).all()
            current_status = {str(vm.id): vm.status.value for vm in vms}
            db.refresh(range_obj)

            # Check for changes
            if current_status != last_status:
                await websocket.send_json({
                    "type": "status_update",
                    "range_id": str(range_id),
                    "range_status": range_obj.status.value,
                    "vms": current_status,
                })
                last_status = current_status.copy()

            await asyncio.sleep(3)  # Poll every 3 seconds as backup

    except WebSocketDisconnect:
        logger.info(f"Status WebSocket disconnected for range {range_id}")
    except Exception as e:
        logger.error(f"Status WebSocket error for range {range_id}: {e}")
        try:
            await websocket.close(code=4000, reason=str(e))
        except Exception:
            pass
    finally:
        # Clean up connection
        try:
            connection_manager = get_connection_manager()
            await connection_manager.disconnect(connection_id)
        except Exception:
            pass
        db.close()


@router.websocket("/ws/events")
async def system_events(
    websocket: WebSocket,
    token: str = Query(...),
    range_id: Optional[UUID] = Query(None),
):
    """
    WebSocket endpoint for real-time event streaming.

    Broadcasts deployment progress, VM status changes, errors, and notifications.
    Optionally filter by range_id to receive only events for a specific range.

    Message types received:
    - Event broadcasts (event_type, message, range_id, vm_id, data, timestamp)
    - Ping messages (type: "ping") for keepalive

    Client can send:
    - {"action": "subscribe", "range_id": "uuid"} - Subscribe to range events
    - {"action": "unsubscribe", "range_id": "uuid"} - Unsubscribe from range
    - {"action": "subscribe_vm", "vm_id": "uuid"} - Subscribe to VM events
    """
    await websocket.accept()

    db = next(get_db())
    connection_id = f"events_{id(websocket)}"

    try:
        user = await get_current_user_ws(websocket, token, db)
        if not user:
            return

        # Release DB session - only needed for auth
        db.close()
        db = None

        from cyroid.services.event_broadcaster import (
            get_connection_manager,
            RANGE_CHANNEL_PREFIX,
            VM_CHANNEL_PREFIX
        )

        connection_manager = get_connection_manager()
        await connection_manager.connect(connection_id, websocket)

        # If range_id specified, subscribe to that range
        if range_id:
            await connection_manager.subscribe_to_range(connection_id, str(range_id))

        # Send connected confirmation
        await websocket.send_json({
            "type": "connected",
            "message": "Real-time events connected",
            "subscriptions": [f"range:{range_id}"] if range_id else []
        })

        # Listen for client messages (subscription changes) and keep alive
        while True:
            # Check if connection is still open
            if websocket.client_state != WebSocketState.CONNECTED:
                logger.debug(f"Events WebSocket {connection_id}: client disconnected")
                break

            try:
                # Wait for client message with timeout
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=30.0
                )

                action = data.get("action")

                if action == "subscribe" and "range_id" in data:
                    await connection_manager.subscribe_to_range(
                        connection_id, data["range_id"]
                    )
                    await websocket.send_json({
                        "type": "subscribed",
                        "channel": f"range:{data['range_id']}"
                    })

                elif action == "unsubscribe" and "range_id" in data:
                    channel = f"{RANGE_CHANNEL_PREFIX}{data['range_id']}"
                    await connection_manager.unsubscribe(connection_id, channel)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "channel": f"range:{data['range_id']}"
                    })

                elif action == "subscribe_vm" and "vm_id" in data:
                    await connection_manager.subscribe_to_vm(
                        connection_id, data["vm_id"]
                    )
                    await websocket.send_json({
                        "type": "subscribed",
                        "channel": f"vm:{data['vm_id']}"
                    })

                elif action == "ping":
                    await websocket.send_json({"type": "pong"})

            except asyncio.TimeoutError:
                # Send keepalive ping if still connected
                if websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.send_json({"type": "ping"})
                    except Exception:
                        # Connection closed during send, exit loop
                        break

    except WebSocketDisconnect:
        logger.debug(f"Events WebSocket disconnected: {connection_id}")
    except RuntimeError as e:
        # Handle "Cannot call receive while another coroutine is waiting"
        # This happens during rapid reconnection
        if "another coroutine" in str(e).lower():
            logger.debug(f"Events WebSocket {connection_id}: concurrent receive, closing")
        else:
            logger.warning(f"Events WebSocket runtime error ({type(e).__name__}): {e}")
    except Exception as e:
        # Log with exception type for better debugging
        error_msg = str(e) if str(e) else type(e).__name__
        logger.warning(f"Events WebSocket error ({type(e).__name__}): {error_msg}")
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close(code=4000, reason=error_msg[:120])
        except Exception:
            pass
    finally:
        # Clean up connection
        try:
            connection_manager = get_connection_manager()
            await connection_manager.disconnect(connection_id)
        except Exception:
            pass
        if db is not None:
            db.close()
