from gtts import gTTS, lang
import asyncio
import edge_tts
from edge_tts import VoicesManager
import TTS_functions as tf
import iso639
import gradio as gr
from pydub import AudioSegment
from moviepy.editor import VideoFileClip # AudioFileClip, concatenate_videoclips
import os
from faster_whisper import WhisperModel


def crop_aud(clone, start_str, end_str):
    if not clone:
        raise gr.Error("You haven't uploaded the prompt!")
    if start_str != '0':
        ok_s, start = tf.form_boundary(start_str, clone)  # формирование времени начала в секундах
    else:
        start = 0
        ok_s = True
    if end_str != '0':
        ok_e, end = tf.form_boundary(end_str, clone)  # формирование времени окончания в секундах
    else:
        end = 0
        ok_e = True

    if ok_s and ok_e:
        # обрезаем аудио (AudioSegment работает с миллисекундами)
        old_audio = AudioSegment.from_file(clone)
        if start != 0 and end != 0:
            extract = old_audio[start * 1000:end * 1000]
        elif start == 0:
            extract = old_audio[:end * 1000]
        elif end == 0:
            extract = old_audio[start * 1000:]
        else:
            extract = old_audio
        # сохраняем
        tf.clone_sample = tf.clone_sample[:-3] + clone[-3:]
        extract.export(tf.clone_sample, format=clone[-3:])

    return [gr.Audio(value=tf.clone_sample), gr.DownloadButton(visible=True, value=tf.clone_sample)]


# def prompt_from_vid(start_str, end_str):
#     if not os.path.isfile(tf.path_to_video):
#         raise gr.Error("You haven't uploaded the video!")
#     video = VideoFileClip(tf.path_to_video)
#     video.audio.write_audiofile(tf.clone_sample)
#     return crop_aud(tf.clone_sample, start_str, end_str)


def process_cut(path_to_vid, vid_or_not, clone=None, start_str='0', end_str='0'):
    if vid_or_not:
        clone = "clone_aud.wav"
        if not os.path.isfile(path_to_vid):
            raise gr.Error("You haven't uploaded the video!")
        video = VideoFileClip(path_to_vid)
        video.audio.write_audiofile(clone)
    return crop_aud(clone, start_str, end_str)


def transcribe_prompt(extract_from_vid, cut_prompt, clone=None, progress=gr.Progress()):
    if (extract_from_vid or cut_prompt) and not os.path.isfile(tf.clone_sample):
        raise gr.Error("You didn't extract the prompt from the video or crop it!")
    elif extract_from_vid or cut_prompt:
        clone = tf.clone_sample
    if not (extract_from_vid or cut_prompt) and not clone:
        raise gr.Error("You didn't download the prompt!")
    progress(0, desc='The model is being downloaded...')
    model = WhisperModel('base', device="cpu", compute_type="int8")
    progress(0.3, desc='Speech will be recognized soon...')
    segments, _ = model.transcribe(clone, beam_size=5)
    progress(0.6, desc='Writing result to file...')
    txt_file = open(tf.clone_text, 'w')
    txt_massive = ""
    for segment in segments:
        txt_massive += segment.text
        txt_file.write(segment.text)
    txt_file.close()
    progress(1.0, desc='Completed!')
    if clone != tf.clone_sample:
        if os.path.isfile(tf.clone_sample):
            os.remove(tf.clone_sample)
        os.rename(clone, tf.clone_sample)
    return gr.Textbox(value=txt_massive)


async def recommend_TTS(language, cloning, gender, emotions):
    selected = False
    output_text = []

    language = language.lower()
    if emotions:
        if language in tf.yandex_languages:
            header = False
            if cloning:  # Если голос будет клонироваться, пол голоса модели не важен
                for model in tf.yandex_languages.get(language):
                    if model['roles']:
                        if not header:
                            output_text.append('It\'s better to check the current models on their website.')
                            output_text.append('The following models from the Yandex SpeechKit library may be suitable for you: \n')
                            header = True
                        output_text.append('Name: ' + model['name'] + '\nGender: ' + model['gender'] + '\nWith possible roles: ' +
                              ', '.join(model['roles']))
            else:
                for model in tf.yandex_languages.get(language):
                    if model['gender'] == gender and model['roles']:
                        if not header:
                            output_text.append('It\'s better to check the current models on their website.')
                            output_text.append('The following models from the Yandex SpeechKit library may be suitable for you: \n')
                            header = True
                        output_text.append('Name: ' + model['name'] + '\nWith possible roles: ' + ', '.join(model['roles']))
        else:
            output_text.append('Unfortunately, emotions are not available in the chosen language.')
    else:
        # Проверка Yandex SpeechKit
        if language in tf.yandex_languages.keys():
            header = False
            if cloning:  # Если голос будет клонироваться, пол голоса модели не важен
                for model in tf.yandex_languages.get(language):
                    if not header:
                        output_text.append('It\'s better to check the current models on their website.')
                        output_text.append('The following models from the Yandex SpeechKit library may be suitable for you: \n')
                        header = True
                    output_text.append('Name: ' + model['name'] + '\nGender: ' + model['gender'] + '\nWith possible roles: ' +
                              ', '.join(model['roles']))
            else:
                gender_yandex = 'male' if gender == 'мужской' else 'female'
                for model in tf.yandex_languages.get(language):
                    if model['gender'] == gender_yandex:
                        if not header:
                            output_text.append('It\'s better to check the current models on their website.')
                            output_text.append('The following models from the Yandex SpeechKit library may be suitable for you: \n')
                            header = True
                        output_text.append('Name: ' + model['name'] + '\nWith possible roles: ' + ', '.join(model['roles']))
            if header:
                selected = True
        # Проверка Coqui TTS
        if cloning:
            if language == 'english':
                output_text.append('Also consider the XTTSv2 and Tacotron2-DCC_ph models from Coqui TTS.')
            elif language in tf.xtts_languages:
                if selected:
                    output_text.append('Also consider XTTSv2 model from Coqui TTS.')
                else:
                    output_text.append('The XTTSv2 model from Coqui TTS may be suitable for you.')
                    selected = True
        elif language == 'english' and gender == 'женский':
            output_text.append('The Tacotron2-DDC_ph model from Coqui TTS may be suitable for you.')
            selected = True

        language = language[0].upper() + language[1:]
        # Проверка gTTS
        lang_available = False
        for val in lang.tts_langs().values():
            if language in val:
                lang_available = True
        if lang_available:
            if selected:
                output_text.append('Also consider gtts.')
            else:
                output_text.append('Speech synthesis using gtts may be suitable for you.')
                selected = True
            if not cloning:
                output_text.append('Please note that there is no choice of the gender of the model\'s voice in gtts.')
        # Проверка edge-tts
        lang_code = iso639.to_iso639_1(language)  # получение кода языка ISO639-1
        gender_edge = 'Male' if gender == 'male' else 'Female'
        if not tf.vm_crtd:
            vm = await VoicesManager.create()
            tf.vm = vm
            tf.vm_crtd = True
        else:
            vm = tf.vm
        if cloning:
            voices = vm.find(Language=lang_code)
            if voices:
                if selected:
                    output_text.append('Also consider Microsoft Edge TTS.')
                    output_text.append('The following voices may be suitable for you:')
                else:
                    output_text.append('The following Microsoft Edge TTS voices may be suitable for you:')
                    selected = True
                for voice in voices:
                    output_text.append(voice['ShortName'] + ', gender: ' + voice['Gender'])
        else:
            voices = vm.find(Gender=gender_edge, Language=lang_code)
            if voices:
                if selected:
                    output_text.append('Also consider Microsoft Edge TTS.')
                    output_text.append('The following voices may be suitable for you:')
                else:
                    output_text.append('The following Microsoft Edge TTS voices may be suitable for you:')
                    selected = True
                for voice in voices:
                    output_text.append(voice['ShortName'])
        # Проверка Silero Models
        if language in tf.silero_languages:
            if selected:
                output_text.append('We can also recommend Silero Models.')
            else:
                output_text.append('Silero Models might be suitable for you.')
                selected = True
        language = language.lower()
        # Проверка Fish-Speech
        if language in tf.fish_languages and cloning:
            if selected:
                output_text.append(
                    'Also consider the Fish-Speech model, which clones the voice well and synthesizes high-quality speech.')
            else:
                output_text.append(
                    'The Fish-Speech model may be suitable for you. It clones the voice well and synthesizes high-quality speech.')
                selected = True
            output_text.append(
                'The recommended loading time is 30 seconds (no less than 10 and no more than 90).')
        # Проверка F5-TTS
        if language in ['english', 'chinese'] and cloning:
            if selected:
                output_text.append('Also consider the F5-TTS model, which clones the voice well and synthesizes high-quality speech.')
            else:
                output_text.append('The F5-TTS may be suitable for you - the model clones the voice well and synthesizes high-quality speech.')
                selected = True
            output_text.append('The recommended loading time is no more than 12 seconds.')
        if not selected:
            output_text.append('Unfortunately, there are no models with the requested parameters.')

    return gr.Textbox('\n'.join(output_text), visible=True)


