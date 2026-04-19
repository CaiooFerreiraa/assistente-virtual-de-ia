from Dataclass.Context import Context
from Config.config_agent import agent, build_config
from Config.config_voice import print_and_speak
from Config.transcription_fixes import apply_transcription_fixes
from Config.config_whisper import (
  list_audio_input_devices,
  record_audio_data,
  record_until_silence,
  test_audio_input,
  transcribe_audio_data,
  transcribe_audio,
)
from Application.spotify_command_service import execute_spotify_command
from concurrent.futures import ThreadPoolExecutor, as_completed
from Domain.voice_commands import (
  DEFAULT_WAKE_WORD_ALIASES,
  extract_message_after_wake_word,
  is_probably_incomplete_command,
  join_command_parts,
)
from queue import Empty, Queue
from threading import Event, Thread
from uuid import uuid4
import argparse


def run_agent(message: str, user_id: str = "1", source: str = "text"):
  try:
    command_response = execute_spotify_command(message)
    if command_response is not None:
      print_and_speak(command_response)
      return command_response
  except Exception as error:
    print_and_speak(f"Erro ao executar comando no Spotify: {error}")
    return None

  thread_id = f"{user_id}-{uuid4().hex}"
  context = Context(
    user_id=user_id,
    message=message,
    source=source,
    thread_id=thread_id
  )

  try:
    response = agent.invoke(
      {"messages": [{"role": "user", "content": message}]},
      config=build_config(thread_id),
      context=context
    )
  except Exception as error:
    print_and_speak(f"Erro ao executar agente: {error}")
    return None

  msg = response.get("structured_response")
  if msg is not None:
    print_and_speak(msg.punny_response)
    return msg

  last_message = response["messages"][-1]
  print_and_speak(last_message.content)
  return last_message


def wait_threads(futures):
  for future in as_completed(futures):
    try:
      future.result()
    except Exception:
      pass


def log_future_error(future):
  try:
    future.result()
  except Exception as error:
    print(f"Erro na thread do agente: {error}")


def submit_agent_task(executor, futures, message: str, user_id: str, source: str):
  future = executor.submit(run_agent, message, user_id, source)
  future.add_done_callback(log_future_error)
  futures.append(future)


def run_text_messages(messages: list[str], user_id: str):
  futures = []
  with ThreadPoolExecutor() as executor:
    for message in messages:
      submit_agent_task(executor, futures, message, user_id, "text")

    wait_threads(futures)


def run_audio_file(audio_path: str, user_id: str):
  message = transcribe_audio(audio_path)
  run_text_messages([message], user_id)


def run_listening_loop(
  user_id: str,
  duration_seconds: int,
  cycles: int | None,
  wake_word: str,
  mic_device: str | None,
  silence_seconds: float,
  voice_threshold: float,
  fixed_window: bool
):
  wake_words = [wake_word, *DEFAULT_WAKE_WORD_ALIASES]
  audio_queue = Queue(maxsize=3)
  stop_event = Event()
  futures = []
  pending_command_parts = []
  pending_command_chunks = 0

  def recorder_loop():
    current_cycle = 0

    try:
      while not stop_event.is_set() and (cycles is None or current_cycle < cycles):
        current_cycle += 1
        print("Escutando...")

        if fixed_window:
          audio = record_audio_data(
            duration_seconds=duration_seconds,
            device_name=mic_device
          )
        else:
          audio = record_until_silence(
            max_duration_seconds=duration_seconds,
            silence_seconds=silence_seconds,
            device_name=mic_device,
            voice_threshold=voice_threshold,
          )

        while not stop_event.is_set():
          try:
            audio_queue.put(audio, timeout=0.2)
            break
          except Exception:
            continue
    except Exception as error:
      print(f"Erro ao escutar o microfone: {error}")
    finally:
      stop_event.set()

  with ThreadPoolExecutor() as executor:
    recorder = Thread(target=recorder_loop, daemon=True)
    recorder.start()

    try:
      while not stop_event.is_set() or not audio_queue.empty():
        try:
          audio = audio_queue.get(timeout=0.2)
        except Empty:
          continue

        message = transcribe_audio_data(audio)

        if not message:
          continue

        message = apply_transcription_fixes(message)
        print(f"Transcrito: {message}")

        agent_message = extract_message_after_wake_word(message, wake_words)
        if agent_message is None:
          if pending_command_parts and pending_command_chunks > 0:
            pending_command_parts.append(message)
            pending_command_chunks -= 1
            command = join_command_parts(pending_command_parts)

            if pending_command_chunks == 0 or not is_probably_incomplete_command(command):
              submit_agent_task(executor, futures, command, user_id, "voice")
              pending_command_parts = []
              pending_command_chunks = 0

            continue

          print(f"Ignorado: chame '{wake_word}' para ativar o agente.")
          continue

        if is_probably_incomplete_command(agent_message):
          pending_command_parts = [agent_message]
          pending_command_chunks = 2
          print("Comando parcial detectado. Vou ouvir o complemento.")
          continue

        submit_agent_task(executor, futures, agent_message, user_id, "voice")

        if message.lower().strip() in ["sair", "encerrar", "parar"]:
          stop_event.set()
          break
    except KeyboardInterrupt:
      print("Encerrando escuta. Aguardando threads em andamento...")
      stop_event.set()
    finally:
      recorder.join(timeout=duration_seconds + 1)
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
  parser.add_argument("--mic-device")
  parser.add_argument("--list-mics", action="store_true")
  parser.add_argument("--test-mic", action="store_true")
  parser.add_argument("--silence-seconds", type=float, default=1.0)
  parser.add_argument("--voice-threshold", type=float, default=0.008)
  parser.add_argument("--fixed-window", action="store_true")
  args = parser.parse_args()

  if args.list_mics:
    print("\n".join(list_audio_input_devices()))
    return

  if args.test_mic:
    print(test_audio_input(args.seconds, args.mic_device))
    return

  if args.listen:
    run_listening_loop(
      args.user_id,
      args.seconds,
      args.cycles,
      args.wake_word,
      args.mic_device,
      args.silence_seconds,
      args.voice_threshold,
      args.fixed_window
    )
    return

  if args.audio:
    run_audio_file(args.audio, args.user_id)
    return

  messages = args.text or ["Qual minha música favorita?"]
  run_text_messages(messages, args.user_id)


if __name__ == "__main__":
  main()
