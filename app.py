import gradio as gr
import os
import ASR_main_functions as amf
os.environ['XDG_RUNTIME_DIR'] = '/tmp/runtime-user'
os.environ['ALSA_CONFIG_PATH'] = '/dev/null'

path_to_video = 'vid.mp4'
asr_model_downloaded = False


def toggle_vid_upload_fields(upload_method):
    return [
        gr.File(visible=upload_method == "From the device"),
        gr.Textbox(visible=upload_method == "Link from YouTube"),
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
        gr.Markdown("Yeah.")
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


demo.launch(share=True, max_file_size=None)