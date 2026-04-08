from google.adk.agents.llm_agent import Agent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.adk.tools.tool_context import ToolContext
import time

def exit_loop(tool_context: ToolContext):
    """Call this function ONLY when no further research is needed, signaling the iterative process should end."""
    print(f"  [Tool Call] exit_loop triggered by {tool_context.agent_name}")
    tool_context.actions.escalate = True
    # Return empty dict as tools should typically return JSON-serializable output
    return {}

def rate_limit_callback(callback_context):
    """Pause briefly to prevent hitting 429 quota limits during rapid loops."""
    time.sleep(3)

# --- RESEARCH LOGIC ---
_research_worker = Agent(
    model='gemini-2.5-flash',
    name='research_worker',
    description='Worker agent that performs a single research step.',
    instruction='''
    Use google_search to find facts and synthesize them for the user.
    Critically evaluate your findings. If the data is incomplete or you need more context, prepare to search again in the next iteration.
    You must include the links you found as references in your response, formatting them like citations in a research paper (e.g., [1], [2]).
    Use the exit_loop tool to terminate the research early if no further research is needed.
    If you need to ask the user for clarifications, call the exit_loop function early to interrupt the research cycle.
    ''',
    tools=[GoogleSearchTool(), exit_loop],
    after_agent_callback=rate_limit_callback,
)

# The LoopAgent iterates the worker up to 3 times for deeper research
research_agent = LoopAgent(
    name='research_specialist',
    description='Deep web research specialist.',
    sub_agents=[_research_worker],
    max_iterations=3,
)