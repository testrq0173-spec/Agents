
import asyncio
import os
import sys
from dotenv import load_dotenv

# Path setup
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Load env
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

from openclaw.agents.content.agent02_writer.agent import BlogWriterAgent, AgentConfig
from openclaw.agents.content.core.base_agent import RedisConfig

async def run_writer():
    print("=" * 60)
    print("  OpenClaw Blog Writer Agent Runner")
    print("=" * 60)
    
# Explicitly configure Redis
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("d:/Agents/writer_debug.log", mode="w"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger("writer_runner")
    
    r_config = RedisConfig(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=int(os.getenv("REDIS_DB", 0)),
        socket_timeout=None
    )
    
    config = AgentConfig(
        agent_id="writer-01",
        agent_name="Writer Agent",
        redis=r_config
    )
    agent = BlogWriterAgent(config)
    
    try:
        # Manually connect Redis for the standalone runner
        print(f"Connecting to Redis at {r_config.host}:{r_config.port}...")
        await agent._connect_redis()
        
        # Start listening to Redis events
        print("Starting event listener...")
        await agent.start_listening()
        
        print("\n[READY] Writer Agent is listening for 'content_briefs_ready' events...")
        print("Please run 'python test_smoke.py' in another terminal.\n")
        
        # Keep running
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        import traceback
        with open("d:/Agents/writer_error.log", "w") as f:
            f.write(traceback.format_exc())
        print(f"\n[FATAL ERROR] {e}")
        print("Check d:/Agents/writer_error.log for full details.")
    finally:
        print("\nStopping Agent...")
        await agent.stop()

if __name__ == "__main__":
    try:
        asyncio.run(run_writer())
    except KeyboardInterrupt:
        pass
