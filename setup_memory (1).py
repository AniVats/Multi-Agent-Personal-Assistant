import vertexai
import os

PROJECT_ID=os.getenv("PROJECT_ID")
LOCATION=os.getenv("LOCATION", "us-central1")

client = vertexai.Client(project=PROJECT_ID, location=LOCATION)

# Create Reasoning Engine for Memory Bank
agent_engine = client.agent_engines.create()

# You will need this resource name to give it to ADK
print(agent_engine.api_resource.name)