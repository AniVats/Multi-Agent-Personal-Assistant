import os
import sys

# Add parent directory to the Python path to resolve imports for 'research' and 'todo'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zoneinfo import ZoneInfo
from google.adk.agents.llm_agent import Agent
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.tools.load_memory_tool import load_memory_tool
from datetime import datetime
from google.adk.tools.agent_tool import AgentTool

# Import our new sub agent
from research import research_agent  
from todo import todo_agent
from calendar_manager import calendar_agent
import tzlocal

# Automatically detect the local system timezone
TIMEZONE = tzlocal.get_localzone_name()

# Callback for persistent memory storage
async def auto_save_session_to_memory_callback(callback_context):
    await callback_context._invocation_context.memory_service.add_session_to_memory(
        callback_context._invocation_context.session)

# Callback to inject the current time into the prompt
async def setup_agent_context(callback_context, **kwargs):
    now = datetime.now(ZoneInfo(TIMEZONE))
    callback_context.state["current_time"] = now.strftime("%A, %Y-%m-%d %I:%M %p")
    callback_context.state["timezone"] = TIMEZONE

# --- ROOT AGENT DEFINITION ---
root_agent = Agent(
    model='gemini-2.5-flash',
    name='executive_assistant',
    description='A professional AI Executive Assistant with memory and specialized tools.',
    instruction='''
    You are an elite, high-signal AI Executive Assistant. 
    Your goal is to help the user manage their knowledge, tasks, research, and schedule.

    ## Your Capabilities:
    1. Memory: Use load_memory to recall personal facts.
    2. Research: Delegate complex web investigations to the research_specialist.
    3. Tasks: Delegate all to-do list management to the todo_specialist.
    4. Scheduling: Delegate all calendar queries to the calendar_specialist.
    
    ## 🕒 Current State
    - Time: {current_time?}
    - Timezone: {timezone?}

    Always be direct and professional.
    ''',
    tools=[
        PreloadMemoryTool(), 
        load_memory_tool,
        AgentTool(todo_agent),
        AgentTool(calendar_agent)
    ],
    sub_agents=[research_agent],
    before_agent_callback=[setup_agent_context],
    after_agent_callback=[auto_save_session_to_memory_callback],
)