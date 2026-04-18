from dataclasses import dataclass

@dataclass
class Context:
  user_id: str
  message: str = ""
  source: str = "text"
  thread_id: str = "1"
