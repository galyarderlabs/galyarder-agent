import asyncio
from pathlib import Path
from g_agent.agent.context import ContextBuilder

builder = ContextBuilder(Path('/home/galyarder/.g-agent/workspace'))
print(builder.build_system_prompt())
