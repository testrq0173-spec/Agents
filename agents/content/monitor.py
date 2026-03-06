"""
OpenClaw Live Event Monitor
===========================
Listens to Redis Pub/Sub channels and prints agent activity in real-time.
Run this in a separate terminal window to watch your agents work.
"""

import asyncio
import json
import os
from datetime import datetime
from colorama import init, Fore, Style

# Initialize colorama for pretty terminal output
init(autoreset=True)

# Load configuration (minimal set)
from dotenv import load_dotenv
load_dotenv()

import redis.asyncio as aioredis

# --- Config ---
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
HEARTBEAT_CHANNEL = "openclaw:agents:heartbeats"
EVENT_PATTERN = "openclaw:events:*"

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

async def monitor():
    print(f"{Fore.CYAN}{Style.BRIGHT}============================================================")
    print(f"{Fore.CYAN}{Style.BRIGHT}   📡 OPENCLAW LIVE DEPARTMENT MONITOR")
    print(f"{Fore.CYAN}{Style.BRIGHT}============================================================\n")

    try:
        r = aioredis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)
        pubsub = r.pubsub()
        
        # Subscribe to heartbeats and all event channels
        await pubsub.subscribe(HEARTBEAT_CHANNEL)
        await pubsub.psubscribe(EVENT_PATTERN)
        
        print(f"{Fore.GREEN}[CONNECTED]{Style.RESET_ALL} Listening on {HEARTBEAT_CHANNEL} and {EVENT_PATTERN}...")
        print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} Agents will appear here as soon as they start.\n")

        async for message in pubsub.listen():
            if message["type"] not in ["message", "pmessage"]:
                continue
            
            # Handle messages
            try:
                channel = message["channel"] if message["type"] == "message" else message["pattern"]
                actual_channel = message["channel"] if message["type"] == "pmessage" else channel
                
                data = json.loads(message["data"])
                
                # 1. HEARTBEAT MESSAGE
                if actual_channel == HEARTBEAT_CHANNEL:
                    agent = data.get("agent_name", "Unknown")
                    status = data.get("status", "idle")
                    cycle = data.get("cycle_count", 0)
                    
                    status_color = Fore.GREEN if status == "running" else Fore.BLUE
                    
                    # Print heartbeats in a compact line to avoid clutter
                    print(f"{Fore.WHITE}[{get_timestamp()}] {Fore.MAGENTA}💗 {agent:<20} {status_color}{status.upper():<10} {Fore.WHITE}Cycle: {cycle}")

                # 2. DEPARTMENT EVENTS
                elif "openclaw:events:" in actual_channel:
                    event_type = actual_channel.replace("openclaw:events:", "")
                    agent = data.get("agent_name", "Unknown")
                    payload = data.get("payload", {})
                    
                    print(f"\n{Fore.CYAN}{'='*60}")
                    print(f"{Fore.YELLOW}🚀 EVENT: {event_type.upper()}")
                    print(f"{Fore.WHITE}AGENT: {agent}")
                    
                    if event_type == "content_briefs_ready":
                        print(f"{Fore.GREEN}TITLE: {payload.get('title')}")
                        print(f"{Fore.GREEN}PRIORITY: {payload.get('priority')}")
                    elif event_type == "post_published":
                        print(f"{Fore.GREEN}URL: {payload.get('cms_post_url')}")
                        print(f"{Fore.GREEN}SEO SCORE: {payload.get('overall_seo_score')}")
                    
                    print(f"{Fore.CYAN}{'='*60}\n")

            except Exception as e:
                print(f"{Fore.RED}[ERROR] Failed to parse message: {e}")

    except Exception as e:
        print(f"{Fore.RED}[CRITICAL] Connection error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(monitor())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Monitor stopped.")
