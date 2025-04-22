import gradio as gr
import os
import ASR_main_functions as amf
import TTS_functions as tf
import TTS_main_functions as tmf
os.environ['XDG_RUNTIME_DIR'] = '/tmp/runtime-user'
os.environ['ALSA_CONFIG_PATH'] = '/dev/null'

path_to_video = 'vid.mp4'
asr_model_downloaded = False


def toggle_vid_upload_fields(upload_method):
    return [
        gr.File(visible=upload_method == "From the device"),
        gr.Textbox(visible=upload_method == "Link from YouTube"),
    ]


def update_uploads(cg_1, cg_2):
    return [gr.Markdown(visible=False), gr.File(visible="Subtitles" in cg_1, interactive="Subtitles" in cg_1),
            gr.File(visible="Clone sample (audio prompt)" in cg_1, interactive="Clone sample (audio prompt)" in cg_1),
            gr.File(visible="Prompt transcription" in cg_1, interactive="Prompt transcription" in cg_1),
            gr.File(visible="Synthesized speech fragments (zip)" in cg_2,
                    interactive="Synthesized speech fragments (zip)" in cg_2),
            gr.File(visible="Video fragments (zip)" in cg_2, interactive="Video fragments (zip)" in cg_2),
            gr.Checkbox(visible="Clone sample (audio prompt)" not in cg_1,
                        interactive="Clone sample (audio prompt)" not in cg_1,
                        value=False),
            gr.Checkbox(visible="Prompt transcription" not in cg_1, interactive="Prompt transcription" not in cg_1, value=False),
            gr.Checkbox(visible="Clone sample (audio prompt)" in cg_1,
                        interactive="Clone sample (audio prompt)" in cg_1,
                        value=False)
            #gr.Dropdown(visible="Clone sample (audio prompt)" in cg_1, interactive="Clone sample (audio prompt)" in cg_1)
            ]


with gr.Blocks() as demo:
    with gr.Tab("Automatic Subtitles"):
        # Часть с загрузкой видео
        gr.Markdown("### <center>Video uploading")
        upload_method = gr.Dropdown(
            label="Upload method: ",
            choices=["From the device", "Link from YouTube"],
            value="From the device"
        )
        with gr.Row():
            file_upload = gr.File(label="Download the video from your computer", visible=True)
            youtube_url = gr.Textbox(label="Insert the YouTube link", visible=False)
        gr.Markdown("### <center>Creating the subtitles")
        with gr.Row():
            with gr.Column():
                # Распознавание речи
                gr.Markdown("#### <center>*Speech recognition*")
                gr.Markdown("##### Choose a Whisper model:")
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
                asr_file_dropdown = gr.Dropdown(label="Select the file to download",
                                                choices=["subtitles.srt", "result.srt", "words.txt"],
                                                visible=False)
                ASR_content_display = gr.Textbox(label="File content", interactive=False, visible=False)
                download_btn = gr.DownloadButton(visible=False)

            with gr.Column():
                gr.Markdown("#### <center>*Translation (optional)*")
                # Перевод
                tr_lang = gr.Textbox(label="Enter the language you want to translate the subtitles into", visible=False)
                tr_btn = gr.Button("Translate", visible=False)
                tr_progress_textbox = gr.Textbox(label="Please wait...", visible=False, interactive=False)
                ASR_status = gr.State("")
                lang = gr.State("")
                tr_content_display = gr.Textbox(label="File content", visible=False, interactive=False)
                tr_dwnld = gr.DownloadButton(visible=False)
                tr_success = gr.State(False)
    with gr.Tab("Video Dubbing"):
        gr.Markdown("### <center>Files uploading")
        loadings = gr.CheckboxGroup(
            label="Choose what you will upload:",
            choices=["Subtitles", "Clone sample (audio prompt)", "Prompt transcription"])
        advanced_loadings = gr.CheckboxGroup(
            label="Advanced",
            choices=["Synthesized speech fragments (zip)", "Video fragments (zip)"])
        load_choice_done = gr.Button("Let's download!")
        load_markdown = gr.Markdown("1. Upload the video in the previous tab, if it hasn't been uploaded yet.\n"
                    "2. You can download a new file with subtitles, or the system will automatically search for a file from the previous tab.\n"
                    "3. Clone sample - optional. If you do not choose to download it, you can also choose below to extract a fragment from the video for this purpose.\n"
                    "4. For some models, you may need to have transcription of the audio sample (or audio prompt). This can also be done using ASR - just select the option below then.\n"
                    "5. The choice for advanced users is to download synthesized fragments and video fragments after their generation to continue working.")
        with gr.Row():
            srt_upload = gr.File(label="Download SRT file from your computer", visible=False,
                                 file_types=[".srt", ".txt"])
            prompt_upload = gr.File(label="Download audio prompt from your computer", visible=False,
                                    file_types=[".wav", ".mp3"])
            prompt_tr_upload = gr.File(label="Download prompt transcription (txt) from your computer", visible=False,
                                       file_types=[".txt"])
        with gr.Row():
            speech_fragms_upload = gr.File(label="Download speech fragments", visible=False, file_types=[".zip"])
            vid_fragms_upload = gr.File(label="Download video fragments", visible=False, file_types=[".zip"])
        cut_prompt = gr.Checkbox(label="Do you want to trim the prompt?", visible=False)
        extract_prompt = gr.Checkbox(label="Extract audio prompt from the video?", visible=False)
        ASR_prompt_tr = gr.Checkbox(label="Transcribe prompt with ASR model?", visible=False)
        with gr.Row():
            with gr.Column():
                prompt_from_vid = gr.Markdown("#### <center>Video --> prompt extraction", visible=False)
                cut_prompt_md = gr.Markdown("#### <center>Prompt cropping", visible=False)
                cut_vid_prompt = gr.Markdown("Enter the beginning and end of the interval in the <minutes>:<seconds> format or 0 if you do not specify one or both boundaries:",
                                             visible=False)
                start_prompt = gr.Textbox(label="start", visible=False, value="0")
                end_prompt = gr.Textbox(label="end", visible=False, value="0")
                cut_done = gr.Button("Let's do it", visible=False)
                cut_prompt_display = gr.Audio("Result", visible=False, interactive=False)
                cut_prompt_dwnld = gr.DownloadButton("Download prompt", visible=False)
            with gr.Column():
                prompt_tr_btn = gr.Button("Transcribe prompt", visible=False)
                prompt_tr_display = gr.Textbox(label="Your transciption", visible=False)
        gr.Markdown("#### <center>Speech synthesis settings")
        with gr.Row():
            with gr.Column():
                tts_tool = gr.Dropdown(choices=["Yandex SpeechKit", "Coqui TTS", "gTTS", "Microsoft Edge TTS",
                                                "Silero Models", "Fish Audio", "F5-TTS"],
                                       label="Choose a synthesis tool",
                                       value="Coqui TTS")
                tts_lang = gr.Textbox(label="Enter the language (in English) in which the synthesis will be performed:")
                # tts_cloning = gr.Checkbox(label="") # пока не будем делать раздел с клонированием - проблемно
                tts_gender = gr.Dropdown(choices=["male", "female"],
                                         label="Which voice gender is preferable?",
                                         value="male",
                                         visible=False) # внимание - надо будет сделать видимым и interactive, если будет загружен промпт
                speed_str = gr.Textbox(label="Do you need to slow down or speed up synthesized phrases right away?"
                                             "Enter 1 if not necessary, and speed if necessary.", value="1")
            with gr.Column():
                tts_voice = gr.Textbox(label="Enter voice name", visible=False)
                tts_role = gr.Textbox(label="Voice role (or not if the model hasn't roles)", value="not", visible=False)
                tts_model = gr.Dropdown(label="Select a model (for Coqui TTS)",
                                        choices=["xtts_v2", "tacotron2-DDC_ph (only english)"],
                                        value="xtts_v2",
                                        visible=False
                                        )
                API_key_yandex = gr.Textbox(label="Yandex API key", visible=False)
                speech_zip_dwld = gr.DownloadButton(label="Download zip with speech", visible=False)
        with gr.Row():
            with gr.Column():
                gr.Markdown("#### <center>Resulting video settings")
                vid_mode = gr.Dropdown(label="Select mode",
                                       choices=["Simple audio overlay by timings", "Stretch/narrow video to fit phrases (takes a lot of time)"],
                                       value="Simple audio overlay by timings")
                slow_aud = gr.Checkbox(label="Slow down phrases to better match initial pronunciation time?", visible=False)
                limit = gr.Checkbox(label="Limit deceleration/acceleration? (for both options)"
                                          "This is necessary so that there is not too much difference between the speeds of phrases or video clips in the final video, if the synthesized phrase is much longer/shorter than the original one.")
                dwnld_raw_video = gr.DownloadButton(label="Download raw video (without lip sync)", visible=False)
            # here lip sync will be
    with gr.Tab("Testing TTS"):
        with gr.Row():
            with gr.Column():
                gr.Markdown("### <center>Recommendations")
                gr.Markdown("#### <center>Fill in the fields below and you will be offered suitable speech synthesis options.")
                rec_TTS_lang = gr.Textbox(label="Enter the language (in English) in which the synthesis will be performed:")
                test_clone = gr.Checkbox(label="Are you going to clone the voice? (to enhance the similarity with the original)")
                rec_gender = gr.Dropdown(choices=["male", "female"],
                                          label="Which voice gender is preferable?",
                                          value="male")
                test_emotions = gr.Checkbox(label="Do you need to add emotion to the voice?")
                recommend_btn = gr.Button("Get recommendations")
                recommend_textbox = gr.Textbox(label="Your recommendations", interactive=False, visible=False)
            with gr.Column():
                gr.Markdown("### <center>Voice testing")
                # добавить к нему обработчик изменения, чтобы показывал варианты Silero
                test_tool = gr.Dropdown(label="Select a synthesizer for testing:",
                                        choices=["gTTS", "Microsoft Edge TTS", "Silero Models"],
                                        value="gTTS")
                silero_txt = gr.Markdown("...", visible=False)
                test_TTS_lang = gr.Textbox(label="Enter the language (for gTTS and Silero Models), in English:")
                test_voice_name = gr.Textbox(label="Enter voice (for Microsoft Edge TTS and Silero Models):")
                test_gender = gr.Dropdown(choices=["male", "female"],
                                          label="Select the voice gender (for some Silero languages)",
                                          value="male")
                test_text = gr.Textbox(label="Enter the test text:")
    # 1
    # Отслеживает изменения в выборе метода загрузки видео и подгружает соответствующее поле
    upload_method.change(
        fn=toggle_vid_upload_fields,
        inputs=upload_method,
        outputs=[file_upload, youtube_url]
    )

    # нажатие кнопки "Распознать речь"
    asr_btn.click(
        fn=amf.make_subtitles,
        inputs=[upload_method, youtube_url, file_upload, prompt, word_timestamps, faster_whisper, device, max_dur,
                model_name],
        outputs=[ASR_status, ASR_progress_textbox],
        # show_progress=True
    ).then(
        fn=amf.update_ui_asr,
        inputs=[ASR_status],
        outputs=[asr_file_dropdown, download_btn, tr_btn, tr_lang, tr_progress_textbox, ASR_content_display]
    )

    # изменение выбора файла для отображения содержимого и загрузки
    asr_file_dropdown.change(
        fn=lambda selected_file: [gr.DownloadButton(value=selected_file), amf.read_file(selected_file)],
        inputs=asr_file_dropdown,
        outputs=[download_btn, ASR_content_display]
    )

    # нажатие кнопки "Translate"
    tr_btn.click(
        fn=amf.translate,
        inputs=[tr_lang],
        outputs=[lang, tr_success, tr_progress_textbox]
    ).then(
        fn=lambda lang, tr_success: [gr.DownloadButton(
            visible=tr_success,
            value=f"subtitles_{lang}.srt" if tr_success else None
        ), gr.Textbox(
            amf.read_file(f"subtitles_{lang}.srt"),
            visible=tr_success
        )],
        inputs=[lang, tr_success],
        outputs=[tr_dwnld, tr_content_display]
    )

    #2
    # нажатие кнопки выбора, что загружать
    load_choice_done.click(
        fn=update_uploads,
        inputs=[loadings, advanced_loadings],
        outputs=[load_markdown, srt_upload, prompt_upload, prompt_tr_upload, speech_fragms_upload, vid_fragms_upload,
                 extract_prompt, ASR_prompt_tr, cut_prompt] #tts_gender
    )

    # надо обрезать загруженный промпт - показываются элементы интерфейса
    cut_prompt.change(
        fn=lambda x: [gr.Markdown(visible=x), gr.Markdown(visible=False), gr.Markdown(visible=x), gr.Textbox(visible=x), gr.Textbox(visible=x),
                      gr.Button(visible=x), gr.Audio(visible=x)],
        inputs=cut_prompt,
        outputs=[cut_prompt_md, prompt_from_vid, cut_vid_prompt, start_prompt, end_prompt, cut_done, cut_prompt_display]
    )

    # надо извлечь промпт из видео - показываются элементы интерфейса
    extract_prompt.change(
        fn=lambda x: [gr.Markdown(visible=x), gr.Markdown(visible=False), gr.Markdown(visible=x), gr.Textbox(visible=x), gr.Textbox(visible=x),
                      gr.Button(visible=x), gr.Audio(visible=x)],
        inputs=extract_prompt,
        outputs=[prompt_from_vid, cut_prompt_md, cut_vid_prompt, start_prompt, end_prompt, cut_done, cut_prompt_display]
    )

    # надо распознать речь из промпта - показываются элементы интерфейса
    ASR_prompt_tr.change(
        fn=lambda x: [gr.Button(visible=x), gr.Textbox(visible=x)],
        inputs=ASR_prompt_tr,
        outputs=[prompt_tr_btn, prompt_tr_display]
    )

    # и извлечение промпта из видео, и его обезка
    cut_done.click(
        fn=tmf.process_cut,
        inputs=[file_upload, extract_prompt, prompt_upload, start_prompt, end_prompt],
        outputs=[cut_prompt_display, cut_prompt_dwnld]
    )

    # автоматическая расшифровка промпта
    prompt_tr_btn.click(
        fn=tmf.transcribe_prompt,
        inputs=[extract_prompt, cut_prompt, prompt_upload],
        outputs=prompt_tr_display
    )

    # СИНТЕЗ РЕЧИ
    # видимости
    tts_tool.change(
        fn=lambda tool: [gr.Dropdown(visible=tool in ["Yandex SpeechKit", "Microsoft Edge TTS", "Silero Models"],
                                     interactive=tool in ["Yandex SpeechKit", "Microsoft Edge TTS", "Silero Models"]),
                         gr.Textbox(visible=tool in ["Yandex SpeechKit", "Microsoft Edge TTS", "Silero Models"]),
                         gr.Textbox(visible=tool=="Yandex SpeechKit"),
                         gr.Dropdown(visible=tool=="Coqui TTS", interactive=tool=="Coqui TTS"),
                         gr.Textbox(visible=tool=="Yandex SpeechKit")],
        inputs=tts_tool,
        outputs=[tts_gender, tts_voice, tts_role, tts_model, API_key_yandex]
    )

    # with gr.Column():
    #     tts_tool = gr.Dropdown(choices=["Yandex SpeechKit", "Coqui TTS", "gTTS", "Microsoft Edge TTS",
    #                                     "Silero Models", "Fish Audio", "F5-TTS"],
    #                            label="Choose a synthesis tool",
    #                            value="Coqui TTS")
    #     tts_lang = gr.Textbox(label="Enter the language (in English) in which the synthesis will be performed:")
    #     # tts_cloning = gr.Checkbox(label="") # пока не будем делать раздел с клонированием - проблемно
    #     tts_gender = gr.Dropdown(choices=["male", "female"],
    #                              label="Which voice gender is preferable?",
    #                              value="male",
    #                              visible=False)  # внимание - надо будет сделать видимым и interactive, если будет загружен промпт
    #     speed_str = gr.Textbox(label="Do you need to slow down or speed up synthesized phrases right away?"
    #                                  "Enter 1 if not necessary, and speed if necessary.", value="1")
    # with gr.Column():
    #     tts_voice = gr.Textbox(label="Enter voice name", visible=False)
    #     tts_role = gr.Textbox(label="Voice role (or not if the model hasn't roles)", value="not", visible=False)
    #     tts_model = gr.Dropdown(label="Select a model (for Coqui TTS)",
    #                             choices=["xtts_v2", "tacotron2-DDC_ph (only english)"],
    #                             value="xtts_v2",
    #                             visible=False
    #                             )
    #     API_key_yandex = gr.Textbox(label="Yandex API key", visible=False)
    #     speech_zip_dwld = gr.DownloadButton(label="Download zip with speech", visible=False)


    #3
    # нажатие кнопки "Получить рекомендации"
    recommend_btn.click(
        fn=tmf.recommend_TTS,
        inputs=[rec_TTS_lang, test_clone, rec_gender, test_emotions],
        outputs=recommend_textbox
    )

    # изменение выбранного инструмента при тестировании
    test_tool.change(
        fn=lambda selected_tool: gr.Markdown(visible=selected_tool == "Silero Models"),
        inputs=test_tool,
        outputs=silero_txt
    )


demo.launch(share=True, max_file_size=None)