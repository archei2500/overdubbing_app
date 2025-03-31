import gradio as gr
import ASR_functions
from faster_whisper import WhisperModel
import whisper
import os
from deep_translator import GoogleTranslator
import iso639
import subprocess
from moviepy.editor import VideoFileClip


asr_model_downloaded = False
path_to_video = 'vid.mp4'


def extract_aud_from_video(upload_method, youtube_url, uploaded_file):
    # Удаление файлов, если такие уже были в ФС прежде
    # if os.path.isfile(path_to_video):
    #     os.remove(path_to_video)
    # if os.path.isfile('aud.wav'):
    #     os.remove('aud.wav')

    if upload_method == "From the device":
        if uploaded_file is not None:
            os.rename(uploaded_file, path_to_video)
        else:
            raise gr.Error("The file has not been uploaded!")
    else:
        subprocess.run([
            "yt-dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=wav]/best[ext=mp4]",
            "--output", "vid.%(ext)s",
            youtube_url
        ], check=True)

    # извлечение аудиодорожки из видео
    video = VideoFileClip(path_to_video)
    video.audio.write_audiofile('aud.wav')


def read_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def make_subtitles(upload_method, youtube_url, uploaded_file, prompt, word_timestamps, faster_whisper, device, max_dur_str, model_name, progress=gr.Progress()):
    global asr_model_downloaded

    progress(0, desc="Starting processing...")
    aud_path = "aud.wav"
    max_dur = int(max_dur_str)

    progress(0.1, desc="Extracting audio...")
    extract_aud_from_video(upload_method, youtube_url, uploaded_file)

    progress(0.3, desc="Loading model...")
    if not asr_model_downloaded:
        if faster_whisper:
            if device == "cpu":
                compute_type = "int8"
            else:
                compute_type = "int8_float16"
            model = WhisperModel(model_name, device=device, compute_type=compute_type)
            asr_model_downloaded = True
        else:
            model = whisper.load_model(model_name)
            asr_model_downloaded = True

    path_to_words = 'words.txt'
    progress(0.5, desc="Transcribing audio...")
    if os.path.isfile(aud_path):
        # Распознавание речи
        if faster_whisper:
            segments, info = model.transcribe(aud_path, beam_size=5, initial_prompt=prompt,
                                              word_timestamps=word_timestamps)
            lang = info.language
            ASR_functions.faster_result_to_file(segments, 'result.srt', word_timestamps, path_to_words)
        else:
            result = model.transcribe(aud_path, initial_prompt=prompt, word_timestamps=word_timestamps)
            # temperature=(0.0, 0.2, 0.4, 0.6) # ДОБАВИТЬ ВВОД ТЕМПЕРАТУРЫ
            lang = result['language']
            ASR_functions.write_result_to_file(result, 'result.srt')

        if word_timestamps and not faster_whisper:
            ASR_functions.write_words_to_file(result, path_to_words)

        if lang == 'ru' or lang == 'en':
            ok = ASR_functions.check_punctuation_percent('result.srt', lang, True)
            if not ok:
                raise gr.Error(f" [!] Вероятно, модель пропустила знаки пунктуации. Рекомендуется перезапустить процесс распознавания.")

        # объединение сегментов
        word_lines = []
        if word_timestamps:
            with open(path_to_words, 'r') as wf:
                word_lines = [''] + wf.read().split('\n')

        new_lines = ASR_functions.process_text("result.srt", max_dur, word_lines)

        txt_file = open('subtitles.srt', "w")
        txt_file.write(new_lines[0][1:] + '\n')  # без символа переноса на новую строку
        if len(new_lines) > 1:
            for line in new_lines[1:-1]:
                txt_file.write(line + '\n')
            txt_file.write(new_lines[-1])
        txt_file.close()

        # корректировка номеров таймингов
        ASR_functions.correct_timings("subtitles.srt")
        progress(1.0, desc="Completed!")
        return ["complete", gr.Textbox(visible=False)]
    else:
        raise gr.Error('Вы не загрузили видео. Пожалуйста, вернитесь к ячейке загрузки видео.')


def update_ui_asr(processing_done):
    if processing_done == "complete":
        return [
            gr.Dropdown(visible=True, choices=["subtitles.srt", "result.srt", "words.txt"], value="subtitles.srt",
                        interactive=True),
            gr.DownloadButton(visible=True, value="subtitles.srt"),
            gr.Button(visible=True),
            gr.Textbox(visible=True),
            gr.Textbox(visible=True),
            gr.Textbox(read_file("subtitles.srt"), visible=True)
        ]


def translate(language):
    language = language.lower()
    lang_capital = language[0].upper() + language[1:]
    lan = iso639.to_iso639_1(lang_capital)  # получение кода языка ISO639-1
    path_to_tr_text = 'subtitles_' + lan + '.srt'
    # создание соответствующего файла для перевода в любом случае
    output_file = open(path_to_tr_text, "w")
    # получение списка языков, поддерживаемых переводчиком
    langs_list = GoogleTranslator().get_supported_languages()
    if language in langs_list:  # если выбранный язык есть в этом списке
        txtfile = open("subtitles.srt", "r")
        lines = [''] + txtfile.read().split('\n')
        for i, line in enumerate(lines):
            if i != len(lines) - 1:
                if i % 4 == 3:
                    translated = GoogleTranslator(source='auto', target=lan).translate(line)
                    output_file.write(translated + "\n")
                else:
                    if i != 0:
                        output_file.write(line + "\n")
            else:
                translated = GoogleTranslator(source='auto', target=lan).translate(line)
                output_file.write(translated)
        txtfile.close()
    else:
        print("Данный язык не поддерживается переводчиком.")
    output_file.close()
    return lan, True, gr.Textbox(visible=False)
