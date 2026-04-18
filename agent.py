from Dataclass.Context import Context
from Config.config_agent import agent, config

response = agent.invoke(
 {"messages": [{"role": "user", "content": "Qual minha música favorita?"}]},
 config=config,
 context=Context(user_id="1")
)

msg = response["structured_response"]

print(msg.punny_response)