from dataclasses import dataclass

@dataclass 
class ResponseFormat:
  punny_response: str
  tools_to_use: list[str]