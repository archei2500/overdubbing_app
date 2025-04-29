import os
os.environ["COQUI_TOS_AGREED"] = "1"

from gtts import gTTS, lang
import asyncio
import edge_tts
from edge_tts import VoicesManager
import TTS_functions as tf
import iso639
import gradio as gr
from pydub import AudioSegment
from moviepy.editor import VideoFileClip # AudioFileClip, concatenate_videoclips
from faster_whisper import WhisperModel
import shutil
import torch
from speechkit import configure_credentials, creds
from TTS.api import TTS
# from TTS.tts.configs.xtts_config import XttsAudioConfig
import locale
import subprocess
# from pprint import pprint
# from omegaconf import OmegaConf
# from scipy.io import wavfile
# import numpy as np


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


def check_gtts_lang(language):
    lang_capital = language.title()
    # проверка наличия языков
    lang_av_ct = 0
    for val in lang.tts_langs().values():
        if lang_capital in val:
            lang_av_ct += 1
    if lang_av_ct > 1:
        out = ""
        out += 'Several suitable languages have been found: '
        lang_arr = [val for val in lang.tts_langs().values() if lang_capital in val]
        out += ', '.join(lang_arr)
        out += 'Select one of them (enter a number from 1 to ' + str(lang_av_ct) + '):'
        return [gr.Number(visible=True, label=out, interactive=True), lang_av_ct]
    elif not lang_av_ct:
        raise gr.Error('gTTS does not support this language!')
    else:
        return [gr.Number(visible=False), 0]


def check_lang_issue_field(lang_num, lang_av_ct, language):
    if 1 > lang_num or lang_num > lang_av_ct:
        return [gr.Number(label="You entered the number incorrectly. Try again."), gr.Textbox()]
    else:
        lang_arr = [val for val in lang.tts_langs().values() if language.title() in val]
        return [gr.Number(label="Desision", visible=False), gr.Textbox(value=lang_arr[lang_num - 1])]


async def run_fish_audio_command(command):
    """Асинхронный запуск команд Fish Audio"""
    proc = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {stderr.decode()}")


async def speech_synthesis(tool, model_name, language, gender, speed_str, device, voice, role, API_key, lines):
    print("WE ENTERED")
    # при первом некорректном валидационном вызове
    if isinstance(voice, str) and (voice.endswith('.srt') or voice.endswith('.txt')):
        print("Skipping validation call")
        return None
    language = language.lower()
    lang_capital = language.title()
    lang_code = iso639.to_iso639_1(lang_capital)
    try:
        speed = float(speed_str)
        if speed <= 0:
            raise gr.Error("Speed cannot be a negative value!")
    except ValueError:
        raise gr.Error("You entered an incorrect speed value!")

    if os.path.exists(tf.path_to_init):
        shutil.rmtree(tf.path_to_init)
        os.makedirs(tf.path_to_init)
    else:
        os.makedirs(tf.path_to_init, exist_ok=True)

    # ЕСЛИ ВЫБРАЛИ YANDEX
    if tool == "Yandex-Speechkit":
        # Проверки входных данных
        if language not in tf.yandex_languages:
            raise gr.Error('This language is not supported by Yandex SpeechKit!')
        if voice not in [item['name'] for item in tf.yandex_languages[language]]:
            raise gr.Error('There is no such voice in Yandex SpeechKit!')
        if not API_key:
            raise gr.Error('Для синтеза речи с помощью Yandex SpeechKit необходим ключ API!')
        # Аутентификация через API-ключ.
        configure_credentials(yandex_credentials=creds.YandexCredentials(api_key=API_key))
        # синтез речи с помощью Yandex SpeechKit
        for i in range(0, len(lines), 4):
            export_path = tf.path_to_init + '/' + str(int(i / 4)) + '.wav'
            tf.synthesize(lines[i + 3], export_path, voice, role)  # синтез фразы
            if speed != 1:
                tf.speedup(export_path, speed)

    # ЕСЛИ ВЫБРАЛИ COQUI
    elif tool == "Coqui TTS":
        if model_name == "xtts_v2" and not os.path.isfile(tf.clone_sample):
            raise gr.Error('XTTSv2 definitely needs a voice clone file, but you haven\'t uploaded a sample!')
        if model_name == "xtts_v2" and language not in tf.xtts_languages:
            raise gr.Error('This language is not supported by XTTSv2!')
        if model_name == "tacotron2-DDC_ph (only english)" and language != "english":
            raise gr.Error('tacotron2-DDC_ph supports only english language!')
        if model_name == "xtts_v2":
            if not tf.xtts_inst:
                # загрузка многоязычной модели
                model_str = "tts_models/multilingual/multi-dataset/" + model_name
                #torch.serialization.add_safe_globals([XttsAudioConfig])
                tts = TTS(model_str).to(device)
                tf.xtts_inst = True
        else:
            if not tf.taco_inst:
                model_str = "tts_models/en/ljspeech/" + model_name
                tts = TTS(model_str).to(device)
                tf.taco_inst = True
        # синтез речи
        for i in range(0, len(lines), 4):
            export_path = tf.path_to_init + '/' + str(int(i / 4)) + '.wav'
            # синтез фразы
            if model_name == "xtts_v2":
                tts.tts_to_file(text=lines[i + 3], file_path=export_path, speaker_wav=[tf.clone_sample],
                                language=lang_code)
            else:
                tts.tts_to_file(text=lines[i + 3], file_path=export_path)
            if speed != 1:
                tf.speedup(export_path, speed)
        # восстановление кодировки в среде (UTF-8)
        locale.getpreferredencoding = tf.getpreferredencoding

    # ЕСЛИ ВЫБРАЛИ GTTS
    elif tool == "gTTS":
        print("UURURURURUR")
        # получение кода языка из инвертированного словаря, возвращаемого gTTS
        lang_code = {v: k for k, v in lang.tts_langs().items()}.get(lang_capital)
        print(lang_code)
        # синтез речи с помощью gTTS
        for i in range(0, len(lines), 4):
            export_path = tf.path_to_init + '/' + str(int(i / 4)) + '.wav'
            print(export_path)
            # синтез фразы
            aud_gtts = gTTS(lines[i + 3], lang=lang_code)
            aud_gtts.save(export_path)
            if speed != 1:
                tf.speedup(export_path, speed)

    # ЕСЛИ ВЫБРАЛИ EDGE TTS
    elif tool == "Microsoft Edge TTS":
        # проверка наличия языка и модели
        gender = 'Male' if gender == 'male' else 'Female'
        if not tf.vm_crtd:
            vm = await VoicesManager.create()  # создание объекта голосового менеджера
            tf.vm = vm
            tf.vm_crtd = True
        else:
            vm = tf.vm
        voices = vm.find(Language=lang_code)
        if not voices:
            raise gr.Error('This language is not supported by Microsoft Edge TTS!')
        v_found = False
        for v in voices:  # проверка на то, что выбранный голос есть для такого языка
            print(v['ShortName'])
            print(voice)
            if v['ShortName'] == voice:
                if v['Gender'] != gender:
                    raise gr.Error('This voice has a different gender. Try to test it in the next tab.')
                v_found = True
                break
        print(v_found)
        if not v_found:
            raise gr.Error('There is no voice with that name for the selected language!')
        # синтез речи с использованием Edge TTS
        for i in range(0, len(lines), 4):
            export_path = tf.path_to_init + '/' + str(int(i / 4)) + '.wav'
            # синтез фразы
            aud_edge = edge_tts.Communicate(lines[i + 3], voice)
            await aud_edge.save(export_path)
            if speed != 1:
                tf.speedup(export_path, speed)

    # ЕСЛИ ВЫБРАЛИ SILERO MODELS
    elif tool == "Silero Models":
        # проверка на наличие языка
        if lang_capital not in tf.silero_languages:
            raise gr.Error('This language is not supported by Silero Models!')
        # выбор модели
        model_id, speaker, ver = tf.choice_silero_model(language, gender=gender)
        if not speaker and ver == '3-4':
            speaker = voice
        model, example_text = torch.hub.load(repo_or_dir='snakers4/silero-models', model='silero_tts',
                                             language=lang_code, speaker=model_id)
        model.to(device)
        # синтез речи с помощью Silero Models
        for i in range(0, len(lines), 4):
            export_path = tf.path_to_init + '/' + str(int(i / 4)) + '.wav'
            if ver == '3-4':
                aud_silero = model.apply_tts(text=lines[i + 3], speaker=speaker, sample_rate=48000, put_accent=True,
                                             put_yo=True)
                tf.silero_save(aud_silero, export_path, 48000)
            else:
                aud_silero = model.apply_tts(texts=[lines[i + 3]], sample_rate=16000)
                tf.silero_save(aud_silero, export_path, 16000)
            if speed != 1:
                tf.speedup(export_path, speed)

    # ЕСЛИ ВЫБРАЛИ FISH-SPEECH
    # СОМНИТЕЛЬНАЯ СОВМЕСТИМОСТЬ
    elif tool == "Fish Audio":
        # проверка на наличие языка
        if language not in tf.fish_languages:
            raise gr.Error('This language is not supported by Fish Audio!')
        # проверка на то, что файл с образцом голоса загружен
        if not (os.path.isfile(tf.clone_sample) and os.path.isfile(tf.clone_text)):
            raise gr.Error('You have not uploaded a voice clone sample and transcript.')
        # загрузка модели
        await run_fish_audio_command(["huggingface-cli", "download", "fishaudio/fish-speech-1.5", "--local-dir",
                        "fish-speech/checkpoints/fish-speech-1.5"])
        # subprocess.run(["huggingface-cli", "download", "fishaudio/fish-speech-1.5", "--local-dir",
        #                 "fish-speech/checkpoints/fish-speech-1.5"])
        # синтез речи
        # генерация промпта из голоса (fake.npy)
        checkpoint_path_firefly = "fish-speech/checkpoints/fish-speech-1.5/firefly-gan-vq-fsq-8x1024-21hz-generator.pth"
        command = ["python", "fish-speech/fish_speech/models/vqgan/inference.py", "-i", tf.clone_sample,
                   "--checkpoint-path", checkpoint_path_firefly]
        await run_fish_audio_command(command)
        #subprocess.run(command)
        # текст промпта
        txt_file = open(tf.clone_text, 'r')
        prompt_text = txt_file.read()
        txt_file.close()
        for i in range(0, len(lines), 4):
            export_path = tf.path_to_init + '/' + str(int(i / 4)) + '.wav'
            # синтез фразы
            # 1) Generate vocals from semantic tokens
            prompt_tokens = "fake.npy"
            checkpoint_path = "fish-speech/checkpoints/fish-speech-1.5"
            command = ["python", "fish-speech/fish_speech/models/text2semantic/inference.py", "--text", lines[i+3],
                       "--prompt-text", prompt_text, "--prompt-tokens", prompt_tokens, "--checkpoint-path",
                       checkpoint_path, "--num-samples", "1", "--half"]
            await run_fish_audio_command(command)
            #subprocess.run(command)
            # 2) Преобразование вокала из семантических токенов
            inp = "temp/codes_0.npy"
            command = ["python", "fish-speech/fish_speech/models/vqgan/inference.py", "-i", inp, "--checkpoint-path",
                       checkpoint_path_firefly]
            await run_fish_audio_command(command)
            #subprocess.run(command)
            os.rename('fake.wav', export_path)
            if speed != 1:
                tf.speedup(export_path, speed)

    # ЕСЛИ ВЫБРАЛИ F5-TTS
    elif tool == "F5-TTS":
        # проверка на наличие языка
        if language not in ['english', 'chinese']:
            raise gr.Error('Данный язык не поддерживается F5-TTS!')
        # проверка на то, что файл с образцом голоса загружен
        if not (os.path.isfile(tf.clone_sample) and os.path.isfile(tf.clone_text)):
            raise gr.Error('You have not uploaded a voice clone sample and transcript.')
        # синтез речи
        # текст промпта
        txt_file = open(tf.clone_text, 'r')
        prompt_text = txt_file.read()
        txt_file.close()
        for i in range(0, len(lines), 4):
            export_path = tf.path_to_init + '/' + str(int(i / 4)) + '.wav'
            # синтез фразы
            command = ["f5-tts_infer-cli", "--model", "F5TTS_v1_Base", "--ref_audio", tf.clone_sample, "--ref_text",
                       prompt_text, "--gen_text", lines[i + 3]]
            subprocess.run(command)
            os.rename('tests/infer_cli_basic.wav', export_path)
            if speed != 1:
                tf.speedup(export_path, speed)


# ОСНОВНАЯ ФУНКЦИЯ ДЛЯ ДУБЛЯЖА
async def make_TTS(tts_tool, model_name, language, gender, speed, voice, role, API_key, srt_uploaded="none",
             clone_uploaded="none", prompt_transcript_uploaded="none", progress=gr.Progress()):
    print(tts_tool, model_name, language, gender, speed, voice, role, API_key, srt_uploaded, clone_uploaded, prompt_transcript_uploaded)
    if isinstance(voice, str) and (voice.endswith('.srt') or voice.endswith('.txt')):
        print("Skipping validation call")
        return [gr.Textbox(), gr.DownloadButton()]
    progress(0, desc='Preparing...')
    if language and language.isalpha():
        if srt_uploaded and os.path.isfile(srt_uploaded):
            if srt_uploaded != tf.path_to_text:
                os.rename(srt_uploaded, tf.path_to_text)
        else:
            if os.path.isfile("subtitles_" + iso639.to_iso639_1(language.title())):
                os.rename("subtitles_" + iso639.to_iso639_1(language.title()), tf.path_to_text)
            elif not os.path.isfile(tf.path_to_text):
                raise gr.Error("You haven't uploaded a text file!")
        if tf.check_txtfile(tf.path_to_text):
            # считываем из файла строки
            lines = tf.read_srt_file()
        else:
            raise gr.Error('Incorrect structure of the selected file!')
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if clone_uploaded and os.path.isfile(clone_uploaded) and clone_uploaded != tf.clone_sample:
            os.rename(clone_uploaded, tf.clone_sample)
        if prompt_transcript_uploaded and os.path.isfile(prompt_transcript_uploaded) and prompt_transcript_uploaded != tf.clone_text:
            os.rename(clone_uploaded, tf.clone_text)
        progress(0.4, desc="Synthesizing speech...")
        await speech_synthesis(tts_tool, model_name, language, gender, speed, device, voice, role, API_key, lines)
        progress(0.9, desc="Creating zip-archive...")
        shutil.make_archive(base_name=tf.path_to_init, format="zip", root_dir=tf.path_to_init)
        progress(1.0, desc="Done!")
        return [gr.Textbox(visible=False), gr.DownloadButton(value=tf.path_to_init + ".zip", visible=True)]
    else:
        raise gr.Error("Please enter the speech synthesis language correctly!")


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


