from Dataclass.Context import Context
from Config.config_agent import agent, build_config
from Config.config_whisper import listen_and_transcribe, transcribe_audio
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4
import argparse
import re


def extract_message_after_wake_word(message: str, wake_word: str) -> str | None:
  pattern = rf"\b{re.escape(wake_word)}\b"
  match = re.search(pattern, message, flags=re.IGNORECASE)

  if match is None:
    return None

  message_after_wake_word = message[match.end():].strip(" ,.!?:;\n\t")
  if message_after_wake_word:
    return message_after_wake_word

  message_before_wake_word = message[:match.start()].strip(" ,.!?:;\n\t")

  return message_before_wake_word or message


def run_agent(message: str, user_id: str = "1", source: str = "text"):
  thread_id = f"{user_id}-{uuid4().hex}"
  context = Context(
    user_id=user_id,
    message=message,
    source=source,
    thread_id=thread_id
  )

  response = agent.invoke(
    {"messages": [{"role": "user", "content": message}]},
    config=build_config(thread_id),
    context=context
  )

  msg = response.get("structured_response")
  if msg is not None:
    print(msg.punny_response)
    return msg

  last_message = response["messages"][-1]
  print(last_message.content)
  return last_message


def wait_threads(futures):
  for future in as_completed(futures):
    try:
      future.result()
    except Exception as error:
      print(f"Erro na thread do agente: {error}")


def run_text_messages(messages: list[str], user_id: str):
  futures = []
  with ThreadPoolExecutor() as executor:
    for message in messages:
      futures.append(executor.submit(run_agent, message, user_id, "text"))

    wait_threads(futures)


def run_audio_file(audio_path: str, user_id: str):
  message = transcribe_audio(audio_path)
  run_text_messages([message], user_id)


def run_listening_loop(
  user_id: str,
  duration_seconds: int,
  cycles: int | None,
  wake_word: str
):
  futures = []

  with ThreadPoolExecutor() as executor:
    try:
      current_cycle = 0
      while cycles is None or current_cycle < cycles:
        current_cycle += 1
        print("Escutando...")
        message = listen_and_transcribe(duration_seconds=duration_seconds)

        if not message:
          continue

        print(f"Transcrito: {message}")

        agent_message = extract_message_after_wake_word(message, wake_word)
        if agent_message is None:
          print(f"Ignorado: chame '{wake_word}' para ativar o agente.")
          continue

        futures.append(executor.submit(run_agent, agent_message, user_id, "voice"))

        if message.lower().strip() in ["sair", "encerrar", "parar"]:
          break
    except KeyboardInterrupt:
      print("Encerrando escuta. Aguardando threads em andamento...")
    finally:
      wait_threads(futures)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--user-id", default="1")
  parser.add_argument("--text", action="append")
  parser.add_argument("--audio")
  parser.add_argument("--listen", action="store_true")
  parser.add_argument("--seconds", type=int, default=5)
  parser.add_argument("--cycles", type=int)
  parser.add_argument("--wake-word", default="Steel")
  args = parser.parse_args()

  if args.listen:
    run_listening_loop(args.user_id, args.seconds, args.cycles, args.wake_word)
    return

  if args.audio:
    run_audio_file(args.audio, args.user_id)
    return

  messages = args.text or ["Qual minha música favorita?"]
  run_text_messages(messages, args.user_id)


if __name__ == "__main__":
  main()
