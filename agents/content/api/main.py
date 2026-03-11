"""
OpenClaw Monitoring API
=======================
FastAPI + Socket.IO server that broadcasts Redis events to the Frontend.
"""

import asyncio
import json
import logging
from typing import Any

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import redis.asyncio as aioredis
import os

from ..config.settings import settings

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("openclaw.api")

# --- Setup Socket.IO ---
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = FastAPI(title="OpenClaw Mon")

# Serve the Dashboard at the root and /dashboard.html
@app.get("/")
@app.get("/dashboard.html")
async def serve_dashboard():
    dashboard_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dashboard.html"))
    if not os.path.exists(dashboard_path):
        logger.error(f"Dashboard not found at {dashboard_path}")
        return {"error": "Dashboard file not found"}
    return FileResponse(dashboard_path)

# Add StaticFiles mount for generated previews
previews_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "previews"))
os.makedirs(previews_path, exist_ok=True)
app.mount("/previews", StaticFiles(directory=previews_path), name="previews")

# Add CORS for the Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bridge Socket.IO to FastAPI
sio_app = socketio.ASGIApp(sio, app)

# --- Redis Connectivity & Event Bridge ---
REDIS_URL = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}"
HEARTBEAT_CHANNEL = "openclaw:agents:heartbeats"
EVENT_PATTERN = "openclaw:events:*"

async def redis_event_bridge():
    """Listens to Redis and broadcasts to all connected Socket.IO clients."""
    logger.info(f"Connecting to Redis at {REDIS_URL}...")
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    
    try:
        await pubsub.subscribe(HEARTBEAT_CHANNEL)
        await pubsub.psubscribe(EVENT_PATTERN)
        
        logger.info("Redis Event Bridge active. Waiting for events...")
        
        async for message in pubsub.listen():
            if message["type"] not in ["message", "pmessage"]:
                continue
            
            try:
                channel = message["channel"] if message["type"] == "message" else message["pattern"]
                actual_channel = message["channel"] if message["type"] == "pmessage" else channel
                
                data = json.loads(message["data"])
                
                # Broadcast to Frontend
                if actual_channel == HEARTBEAT_CHANNEL:
                    await sio.emit("agent_heartbeat", data)
                else:
                    event_type = actual_channel.replace("openclaw:events:", "")
                    await sio.emit("department_event", {
                        "type": event_type,
                        "agent": data.get("agent_name", "Unknown"),
                        "payload": data.get("payload", {}),
                    })
            except Exception as e:
                logger.error(f"Error processing Redis message: {e}")
                
    except asyncio.CancelledError:
        logger.info("Redis event bridge shutting down...")
    finally:
        await pubsub.unsubscribe()
        await r.close()

@app.on_event("startup")
async def startup_event():
    app.state.redis_task = asyncio.create_task(redis_event_bridge())

@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state, 'redis_task'):
        app.state.redis_task.cancel()
        await asyncio.gather(app.state.redis_task, return_exceptions=True)

@app.get("/status")
async def get_status():
    return {"status": "online", "department": "OpenClaw Content"}

# Entry point for uvicorn
# Command: uvicorn openclaw.agents.content.api.main:sio_app --reload --port 8000
