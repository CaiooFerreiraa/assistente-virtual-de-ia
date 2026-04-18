import whisper
import whisper

model = whisper.load_model("small")

audio = whisper.load_audio("audio.mp3")
audio = whisper.pad_or_trim(audio)

mel = whisper.log_mel_spectrogram(audio, n_mels=model.dims.n_mels).to(model.device)

_, probs = model.detect_language(mel)

options = whisper.DecodingOptions()
result = whisper.decode(model, mel, options)

print(result.text)