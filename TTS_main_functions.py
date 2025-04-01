from gtts import gTTS, lang
import asyncio
import edge_tts
from edge_tts import VoicesManager
import TTS_functions
import iso639
import gradio as gr


async def recommend_TTS(language, cloning, gender, emotions):
    selected = False
    output_text = []

    language = language.lower()
    if emotions:
        if language in TTS_functions.yandex_languages:
            header = False
            if cloning:  # Если голос будет клонироваться, пол голоса модели не важен
                for model in TTS_functions.yandex_languages.get(language):
                    if model['roles']:
                        if not header:
                            output_text.append('It\'s better to check the current models on their website.')
                            output_text.append('The following models from the Yandex SpeechKit library may be suitable for you: \n')
                            header = True
                        output_text.append('Name: ' + model['name'] + '\nGender: ' + model['gender'] + '\nWith possible roles: ' +
                              ', '.join(model['roles']))
            else:
                for model in TTS_functions.yandex_languages.get(language):
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
        if language in TTS_functions.yandex_languages.keys():
            header = False
            if cloning:  # Если голос будет клонироваться, пол голоса модели не важен
                for model in TTS_functions.yandex_languages.get(language):
                    if not header:
                        output_text.append('It\'s better to check the current models on their website.')
                        output_text.append('The following models from the Yandex SpeechKit library may be suitable for you: \n')
                        header = True
                    output_text.append('Name: ' + model['name'] + '\nGender: ' + model['gender'] + '\nWith possible roles: ' +
                              ', '.join(model['roles']))
            else:
                gender_yandex = 'male' if gender == 'мужской' else 'female'
                for model in TTS_functions.yandex_languages.get(language):
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
            elif language in TTS_functions.xtts_languages:
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
        if not TTS_functions.vm_crtd:
            vm = await VoicesManager.create()
            TTS_functions.vm = vm
            TTS_functions.vm_crtd = True
        else:
            vm = TTS_functions.vm
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
        if language in TTS_functions.silero_languages:
            if selected:
                output_text.append('We can also recommend Silero Models.')
            else:
                output_text.append('Silero Models might be suitable for you.')
                selected = True
        language = language.lower()
        # Проверка Fish-Speech
        if language in TTS_functions.fish_languages and cloning:
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


