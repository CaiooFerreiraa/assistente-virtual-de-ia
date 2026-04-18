from langchain.agents.structured_output import ToolStrategy
from langgraph.checkpoint.memory import InMemorySaver
from langchain.chat_models import init_chat_model
from Dataclass.ResponseForm import ResponseFormat
from Dataclass.Context import Context
from Config.Prompt import prompt_system
from Tools.spotify import (
  abrir_spotify,
  aumentar_volume,
  buscar_musica,
  diminuir_volume,
  fechar_spotify,
  musica_anterior,
  pausar_musica,
  proxima_musica,
  tocar_musica,
  volume_atual,
)
from langchain.agents import create_agent
from dotenv import load_dotenv
import os
load_dotenv()

checkpointer = InMemorySaver()

def build_config(thread_id: str):
  return {"configurable": {"thread_id": thread_id}}

config = build_config("1")

model = init_chat_model(
  "gpt-5.4-mini",
  api_key=os.getenv("OPENAI_API_KEY"),
  temperature=0.5,
  max_tokens=1000,
  timeout=10
)

agent = create_agent(
  model=model,
  tools=[
    abrir_spotify,
    fechar_spotify,
    buscar_musica,
    tocar_musica,
    pausar_musica,
    proxima_musica,
    musica_anterior,
    aumentar_volume,
    diminuir_volume,
    volume_atual,
  ],
  system_prompt=prompt_system(),
  checkpointer=checkpointer,
  context_schema=Context,
  response_format=ToolStrategy(ResponseFormat)
)
