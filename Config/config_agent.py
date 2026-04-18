from langchain.agents.structured_output import ToolStrategy
from langgraph.checkpoint.memory import InMemorySaver
from langchain.chat_models import init_chat_model
from Dataclass.ResponseForm import ResponseFormat
from Config.Prompt import prompt_system
from langchain.agents import create_agent
from dotenv import load_dotenv
import os
load_dotenv()

checkpointer = InMemorySaver()
config = {"configurable": {"thread_id": "1"}}

model = init_chat_model(
  "gpt-5.4-mini",
  api_key=os.getenv("OPENAI_API_KEY"),
  temperature=0.5,
  max_tokens=1000,
  timeout=10
)

agent = create_agent(
  model=model,
  tools=[],
  system_prompt=prompt_system(),
  checkpointer=checkpointer,
  response_format=ToolStrategy(ResponseFormat)
)