import gradio as gr
import os
import subprocess
from moviepy.editor import VideoFileClip
from faster_whisper import WhisperModel
import whisper
import ASR_functions
from deep_translator import GoogleTranslator
import iso639
os.environ['XDG_RUNTIME_DIR'] = '/tmp/runtime-user'
os.environ['ALSA_CONFIG_PATH'] = '/dev/null'

path_to_video = 'vid.mp4'
asr_model_downloaded = False


def toggle_vid_upload_fields(upload_method):
    return [
        gr.File(visible=upload_method == "From the device"),
        gr.Textbox(visible=upload_method == "Link from YouTube"),
    ]


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


def make_subtitles(upload_method, youtube_url, uploaded_file, prompt, word_timestamps, faster_whisper, device, max_dur_str, model_name, progress=gr.Progress()):
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
        else:
            model = whisper.load_model(model_name)

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
        print('Вы не загрузили видео. Пожалуйста, вернитесь к ячейке загрузки видео.')


def read_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


# def make_subtitles(aud_path, prompt, word_timestamps, faster_whisper, device, max_dur):
#     if not asr_model_downloaded:
#         if faster_whisper:
#             if device == "cpu":
#                 compute_type = "int8"
#             else:
#                 compute_type = "int8_float16"
#             model = WhisperModel(model_name, device=device, compute_type=compute_type)
#         else:
#             model = whisper.load_model(model_name)
#
#     path_to_words = 'words.txt'
#     if os.path.isfile(aud_path):
#         # Распознавание речи
#         if faster_whisper:
#             segments, info = model.transcribe(aud_path, beam_size=5, initial_prompt=prompt,
#                                               word_timestamps=word_timestamps)
#             lang = info.language
#             ASR_functions.faster_result_to_file(segments, 'result.srt', word_timestamps, path_to_words)
#         else:
#             result = model.transcribe(aud_path, initial_prompt=prompt, word_timestamps=word_timestamps)
#             # temperature=(0.0, 0.2, 0.4, 0.6) # ДОБАВИТЬ ВВОД ТЕМПЕРАТУРЫ
#             lang = result['language']
#             ASR_functions.write_result_to_file(result, 'result.srt')
#
#         if word_timestamps and not faster_whisper:
#             ASR_functions.write_words_to_file(result, path_to_words)
#
#         if lang == 'ru' or lang == 'en':
#             ok = ASR_functions.check_punctuation_percent('result.srt', lang, True)
#             raise gr.Error(f" [!] Вероятно, модель пропустила знаки пунктуации. Рекомендуется перезапустить процесс распознавания.")
#
#         # объединение сегментов
#         word_lines = []
#         if word_timestamps:
#             with open(path_to_words, 'r') as wf:
#                 word_lines = [''] + wf.read().split('\n')
#
#         new_lines = ASR_functions.process_text("result.srt", max_dur, word_lines)
#
#         txt_file = open('subtitles.srt', "w")
#         txt_file.write(new_lines[0][1:] + '\n')  # без символа переноса на новую строку
#         if len(new_lines) > 1:
#             for line in new_lines[1:-1]:
#                 txt_file.write(line + '\n')
#             txt_file.write(new_lines[-1])
#         txt_file.close()
#
#         # корректировка номеров таймингов
#         ASR_functions.correct_timings("subtitles.srt")
#     else:
#         print('Вы не загрузили видео. Пожалуйста, вернитесь к ячейке загрузки видео.')


def update_ui_asr(processing_done):
    if processing_done == "complete":
        return [
            # gr.Loader(visible=False),
            gr.Dropdown(visible=True, choices=["subtitles.srt", "result.srt", "words.txt"], value="subtitles.srt",
                        interactive=True),
            gr.DownloadButton(visible=True, value="subtitles.srt"),
            gr.Button(visible=True),
            gr.Textbox(visible=True),
            gr.Textbox(visible=True),
            gr.Textbox(read_file("subtitles.srt"), visible=True)
        ]
    # return [gr.Dropdown(visible=False), gr.DownloadButton(visible=False), gr.Button(visible=False),
    #         gr.Textbox(visible=False), gr.Markdown(visible=True, value="## Processing... Please wait")]


def translate(language, progress=gr.Progress()):
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


def update_tr(translate_done, lang):
    if translate_done:
        return [
            gr.DownloadButton(visible=True, value="subtitles_" + lang + ".srt"),  # Показываем кнопку с файлом по умолчанию
        ]
    return [gr.DownloadButton(visible=False)]


with gr.Blocks() as demo:
    with gr.Tab("Automatic Subtitles"):
        # Часть с загрузкой видео
        gr.Markdown("### Video uploading")
        upload_method = gr.Dropdown(
            label="Upload method: ",
            choices=["From the device", "Link from YouTube"],
            value="From the device"
        )
        with gr.Row():
            file_upload = gr.File(label="Download the video from your computer", visible=True)
            youtube_url = gr.Textbox(label="Insert the YouTube link", visible=False)
        # Отслеживает изменения в выборе метода загрузки и подгружает соответствующее поле
        upload_method.change(
            fn=toggle_vid_upload_fields,
            inputs=upload_method,
            outputs=[file_upload, youtube_url]
        )
        # vid_btn = gr.Button("Done")
        # vid_btn.click(fn=extract_aud_from_video, inputs=[upload_method, youtube_url, file_upload])
        # Распознавание речи
        gr.Markdown("### Creating the subtitles")
        gr.Markdown("#### Choose a Whisper model:")
        faster_whisper = gr.Checkbox(label="Use faster-whisper")
        model_name = gr.Dropdown(choices=["tiny", "base", "small", "medium", "large-v2", "large-v3", "turbo"],
                                 label="Size",
                                 value="tiny")
        device = gr.Dropdown(choices=["cpu", "cuda"], label="Device", value="cpu")
        prompt = gr.Textbox(label="Prompt", value="The text below, consisting of segments — separate complete sentences, is a lecture on...")
        gr.Markdown("Do you need word timestamps?")
        word_timestamps = gr.Checkbox(
            label="word timestamps",
            info="This will most likely ensure that the timestamps in the subtitles are more accurate."
        )
        max_dur = gr.Textbox(label="Enter the maximum duration (in seconds) of a single phrase in the subtitles")
        asr_btn = gr.Button("Recognize speech")
        ASR_progress_textbox = gr.Textbox(label="Progress")
        # processing_load = gr.Loader(visible=False)
        asr_file_dropdown = gr.Dropdown(label="Select the file to download",
                                        choices=["subtitles.srt", "result.srt", "words.txt"],
                                        visible=False)
        ASR_content_display = gr.Textbox(label="File content", interactive=False, visible=False)
        download_btn = gr.DownloadButton(visible=False)
        tr_lang = gr.Textbox(label="Enter the language you want to translate the subtitles into", visible=False)
        tr_btn = gr.Button("Translate", visible=False)
        tr_progress_textbox = gr.Textbox(label="Please wait...", visible=False, interactive=False)
        ASR_status = gr.State("")

        asr_btn.click(
            fn=make_subtitles,
            inputs=[upload_method, youtube_url, file_upload, prompt, word_timestamps, faster_whisper, device, max_dur,
                    model_name],
            outputs=[ASR_status, ASR_progress_textbox],
            # show_progress=True
        ).then(
            fn=update_ui_asr,
            inputs=[ASR_status],
            outputs=[asr_file_dropdown, download_btn, tr_btn, tr_lang, tr_progress_textbox, ASR_content_display]
        )

        asr_file_dropdown.change(
            fn=lambda selected_file: [gr.DownloadButton(value=selected_file), read_file(selected_file)],
            inputs=asr_file_dropdown,
            outputs=[download_btn, ASR_content_display]
        )

        # asr_file_dropdown.change(
        #     fn=display_and_download,
        #     inputs=asr_file_dropdown,
        #     outputs=[download_btn, ASR_content_display]
        # )

        #asr_btn.click(fn=make_subtitles, inputs=[upload_method, youtube_url, file_upload, prompt, word_timestamps, faster_whisper, device, max_dur, model_name]).then(fn=update_ui_asr, outputs=[asr_file_dropdown, download_btn, tr_btn, tr_lang, status_md])
        lang = gr.State("")
        tr_content_display = gr.Textbox(label="File content", visible=False, interactive=False)
        tr_dwnld = gr.DownloadButton(visible=False)
        tr_success = gr.State(False)
        # tr_btn.click(fn=translate, inputs=[tr_lang], outputs=[lang, tr_success]).then(fn=lambda lang, success: gr.DownloadButton(
        #     visible=success,
        #     value=f"subtitles_{lang}.srt" if success else None
        # ), inputs=[tr_success, lang], outputs=[tr_dwnld])
        tr_btn.click(
            fn=translate,
            inputs=[tr_lang],
            outputs=[lang, tr_success, tr_progress_textbox]
            # show_progress=True
        ).then(
            fn=lambda lang, tr_success: [gr.DownloadButton(
                visible=tr_success,
                value=f"subtitles_{lang}.srt" if tr_success else None
            ),
            gr.Textbox(
                read_file(f"subtitles_{lang}.srt"),
                visible=tr_success
            )
            # read_file(f"subtitles_{lang}.srt")
            ],
            inputs=[lang, tr_success],
            outputs=[tr_dwnld, tr_content_display]
        )
    with gr.Tab("Video Dubbing"):
        gr.Markdown("Yeah.")


demo.launch(share=True, max_file_size=200*1024*1024)

# def flip_text(x):
#     return x[::-1]
#
#
# def flip_image(x):
#     return np.fliplr(x)
#
#
# with gr.Blocks() as demo:
#     gr.Markdown("Flip text or image files using this demo.")
#     with gr.Tab("Flip Text"):
#         text_input = gr.Textbox()
#         text_output = gr.Textbox()
#         text_button = gr.Button("Flip")
#     with gr.Tab("Flip Image"):
#         with gr.Row():
#             image_input = gr.Image()
#             image_output = gr.Image()
#         image_button = gr.Button("Flip")
#
#     with gr.Accordion("Open for More!", open=False):
#         gr.Markdown("Look at me...")
#         temp_slider = gr.Slider(
#             0, 1,
#             value=0.1,
#             step=0.1,
#             interactive=True,
#             label="Slide me",
#         )
#
#     text_button.click(flip_text, inputs=text_input, outputs=text_output)
#     image_button.click(flip_image, inputs=image_input, outputs=image_output)

# import gradio as gr
#
# def sentence_builder(quantity, animal, countries, place, activity_list, morning):
#     return f"""The {quantity} {animal}s from {" and ".join(countries)} went to the {place} where they {" and ".join(activity_list)} until the {"morning" if morning else "night"}"""
#
# demo = gr.Interface(
#     sentence_builder,
#     [
#         gr.Slider(2, 20, value=4, label="Count", info="Choose between 2 and 20"),
#         gr.Dropdown(
#             ["cat", "dog", "bird"], label="Animal", info="Will add more animals later!"
#         ),
#         gr.CheckboxGroup(["USA", "Japan", "Pakistan"], label="Countries", info="Where are they from?"),
#         gr.Radio(["park", "zoo", "road"], label="Location", info="Where did they go?"),
#         gr.Dropdown(
#             ["ran", "swam", "ate", "slept"], value=["swam", "slept"], multiselect=True, label="Activity", info="Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed auctor, nisl eget ultricies aliquam, nunc nisl aliquet nunc, eget aliquam nisl nunc vel nisl."
#         ),
#         gr.Checkbox(label="Morning", info="Did they do it in the morning?"),
#     ],
#     "text",
#     examples=[
#         [2, "cat", ["Japan", "Pakistan"], "park", ["ate", "swam"], True],
#         [4, "dog", ["Japan"], "zoo", ["ate", "swam"], False],
#         [10, "bird", ["USA", "Pakistan"], "road", ["ran"], False],
#         [8, "cat", ["Pakistan"], "zoo", ["ate"], True],
#     ]
# )
#
# if __name__ == "__main__":
#     demo.launch()