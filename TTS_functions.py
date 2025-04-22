# from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
# from moviepy.video.fx.accel_decel import accel_decel
# import re
# from IPython.display import clear_output, Audio, display
from pydub import AudioSegment


# import os
# from google.colab import files
# import subprocess
# import ffmpeg
# import torch
# import locale # для восстановления кодировки
# import iso639 # для кодов языков
# import cv2

def form_boundary(time, clone_path):
    ok = True
    pos = time.find(':')
    if pos != -1:
        buf = time[: pos]
        if not (len(buf) > 0 and len(buf) < 3 and buf.isdigit() and int(buf) >= 0):
            ok = False
        buf = time[pos + 1:]
        if not (len(buf) > 0 and len(buf) < 3 and buf.isdigit() and int(buf) >= 0):
            ok = False
        if ok:
            buf = int(time[: pos]) * 60 + int(time[pos + 1:])
            dur = len(AudioSegment.from_file(clone_path))
            if buf > dur:  # если больше продолжительности видео
                ok = False
                print("Введённое вами время превышает продолжительность аудиофайла!")
    else:
        ok = False

    return ok, buf


# times = [] # для корректировки субтитров в конце
#
#
# def str_to_time(s):
#   return int(s[6:8]) + 60 * int(s[3:5]) + 3600 * int(s[:2]) + float('0.' + s[9:12])
#
#
# def time_to_str(time):
#   hours = int(time // 3600)
#   minutes = int((time - 3600 * hours) // 60)
#   seconds = time - 60 * minutes
#   str_sec = str(round(seconds, 3)).replace('.', ',')
#   return str(hours).zfill(2) + ':' + str(minutes).zfill(2) + ':' + str_sec[:str_sec.find(',')].zfill(2) + ',' + str_sec[str_sec.find(',') + 1:].ljust(3, '0')
#
#
# def extract_number(s):
#   match = re.search(r'\d+', s) # регулярное выражение \d+ означает "одна или более цифр подряд"
#   if match:
#     return int(match.group())
#   else:
#     return 0
#
#
# def add_pause(old_path, aud_path, dur):
#   # генерация тишины (в миллисекундах)
#   silence = AudioSegment.silent(duration = dur * 1000)
#   audio = AudioSegment.from_file(old_path)
#   audio += silence
#   audio.export(aud_path, format = "wav")
#
#
# def speedup(path, speed):
#   filter = "atempo=" + str(speed)
#   command = "ffmpeg -i " + path + " -filter:a " + filter + " /content/changed.wav"
#   process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#   output, error = process.communicate()
#   os.remove(path)
#   os.rename("/content/changed.wav", path)
#
#
# def check_duration(old_path, aud_path, start, end, slow_aud, limit):
#   duration = (end - start) * 1000 # в миллисекундах
#   # измеряем продолжительность синтезированного фрагмента
#   audio = AudioSegment.from_file(old_path)
#   if len(audio) != duration: # если аудио получилось больше или меньше требуемой продолжительности
#     # нужно его ускорить и замедлить или добавить паузу (в зависимости от режима)
#     coef = len(audio) / duration # коэффициент растяжения или сжатия
#     if coef < 1:
#       if not slow_aud: # не замедляем аудио
#         add_pause(old_path, aud_path, (duration - len(audio)) / 1000)
#       else:
#         if limit:
#           if coef >= 0.9: # замедление будет выполнено, только если аудио не станет медленнее этого значения
#             !cp $old_path $aud_path
#             speedup(aud_path, coef)
#         else:
#           !cp $old_path $aud_path
#           speedup(aud_path, coef)
#     else:
#       # ограничение на ускорение в случае с аудио не накладываем, т. к. в видеофрагмент важно уложиться
#       !cp $old_path $aud_path
#       speedup(aud_path, coef)
#   else: # Всё равно копируем в новую папку
#     !cp $old_path $aud_path
#
#
# def getpreferredencoding(do_setlocale = True):
#     return "UTF-8"
#
#
# def video_duration(filename):
#   video = cv2.VideoCapture(filename)
#
#   fps = video.get(cv2.CAP_PROP_FPS)
#   frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
#   duration = frame_count / fps
#
#   video.release()
#
#   return duration
#
#
# def check_vid_duration(aud_path, vid_path, limit):
#   # получение продолжительности видео
#   audio = AudioSegment.from_file(aud_path)
#   video = VideoFileClip(vid_path).without_audio()
#   times.append(len(audio) / 1000)
#   if abs(len(audio) / 1000 - video.duration) > 0.05: # аудио короче или длиннее видео на более чем 50 мс
#     coef = round(video.duration / (len(audio) / 1000), 3)
#     if limit:
#       # проверка коэффициента, замедление или усорение будет выполнено, только если коэффициент в данных пределах
#       if coef <= 1.1 and coef >= 0.9:
#         video = accel_decel(video, video.duration / coef, abruptness = 0)
#         os.remove(vid_path)
#         video.write_videofile(vid_path, threads = 4)
#       else: # иначе работа с самим аудио
#         if coef > 1: # если видео собирались ускорить, к аудио добавляем паузу
#           pause_len = video.duration - (len(audio) / 1000) # в с
#           add_pause(aud_path, aud_path, pause_len)
#         else: # если видео собирались замедлить, то ускоряем аудио
#           speedup(aud_path, 1 / coef)
#           audio = AudioSegment.from_file(aud_path)
#           times.pop()
#           times.append(len(audio) / 1000)
#     else:
#       video = accel_decel(video, video.duration / coef, abruptness = 0)
#       os.remove(vid_path)
#       video.write_videofile(vid_path, threads = 4)
#
# def choice_silero_model(lang, gender='female'):
#   ver = '3-4'
#   voice = None # для тех языков, где нет выбора голосов
#   indic_languages = ['bengali', 'gujarati', 'hindi', 'kannada', 'malayalam',
#                      'manipuri', 'rajasthani', 'tamil', 'telugu']
#
#   if lang == 'russian':
#     model_id = 'v4_ru'
#   elif lang == 'english':
#     model_id = 'v3_en'
#   elif lang == 'german':
#     model_id = 'v3_de'
#   elif lang == 'spanish':
#     model_id = 'v3_es'
#   elif lang == 'french':
#     model_id = 'v3_fr'
#   elif lang == 'bashkir':
#     model_id = 'aigul_v2'
#     ver = '2'
#   elif lang == 'kalmyk':
#     model_id = 'v3_xal'
#   elif lang == 'tatar':
#     model_id = 'v3_tt'
#     voice = 'dilyara'
#   elif lang == 'uzbek':
#     model_id = 'v4_uz'
#     voice = 'dilnavoz'
#   elif lang == 'ukrainian':
#     model_id = 'v4_ua'
#   # индийские языки
#   elif lang in indic_languages:
#     model_id = 'v4_indic'
#     if lang != 'manipuri':
#       voice = language + '_' + gender
#     else:
#       voice = 'manipuri_female'
#   # кириллические языки
#   else:
#     model_id = 'cyrillic'
#
#   return model_id, voice, ver
#
#
# # Функция синтеза для Yandex-Speechkit
# def synthesize(text, export_path, voice, role):
#   model = model_repository.synthesis_model()
#
#   # настройки синтеза
#   model.voice = voice
#   model.role = role
#
#   # синтез речи и создание аудио с результатом
#   result = model.synthesize(text, raw_format = False)
#   result.export(export_path, 'wav')
#
#
# # Проверка на то, что файл имеет необходимую структуру
# def check_txtfile(filename):
#   txtfile = open(filename, "r", encoding = "utf-8")
#   lines = [''] + txtfile.read().split('\n')
#   txtfile.close()
#   ok = True
#   if (len(lines) % 4 == 0):
#     for i in range(0, len(lines), 4):
#       if lines[i]:
#         ok = False
#       if not re.match(r'^\d+$', lines[i + 1]):
#         ok = False
#       if not re.match(r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}', lines[i + 2]):
#         ok = False
#       if not lines[i + 3]:
#         ok = False
#   else:
#     ok = False
#   return ok
#
#
# def silero_save(audio, path, sample_rate):
#   # Преобразуем тензор в массив NumPy
#   audio_np = audio.numpy()
#   # Нормализуем значения массива NumPy к диапазону [-1, 1]
#   audio_np = np.clip(audio_np, -1, 1)
#   # Масштабируем значения к диапазону int16 для сохранения в формате WAV
#   audio_np_int16 = np.int16(audio_np * 32767)
#   # Сохраняем массив NumPy как файл WAV
#   wavfile.write(path, sample_rate, audio_np_int16)


# переменные для регулирования процесса загрузки видео и/или аудио
yt_downloaded = False
gd_mounted = False
gtts_installed = False
edge_installed = False
silero_installed = False
yandex_installed = False
coqui_installed = False
fish_installed = False
f5_installed = False
vm_crtd = False
vm = None

path_to_text = 'subtitles.srt'
path_to_video = 'vid.mp4'
clone_sample = 'clone_voice.wav'
clone_text = 'clone.txt'
path_to_init = 'synthesized1'
path_to_synth = 'synthesized'

yandex_languages = {'german': [{'name': 'lea', 'gender': 'female', 'roles': []}],
                    'english': [{'name': 'john', 'gender': 'male', 'roles': []}],
                    'hebrew': [{'name': 'naomi', 'gender': 'female', 'roles': ['modern', 'classic']}],
                    'kazakh': [{'name': 'amira', 'gender': 'female', 'roles': []},
                               {'name': 'madi', 'gender': 'male', 'roles': []}],
                    'russian': [{'name': 'alena', 'gender': 'female', 'roles': ['neutral', 'good']},
                                {'name': 'filipp', 'gender': 'male', 'roles': []},
                                {'name': 'ermil', 'gender': 'male', 'roles': ['neutral', 'good']},
                                {'name': 'jane', 'gender': 'female', 'roles': ['neutral', 'good', 'evil']},
                                {'name': 'madirus', 'gender': 'male', 'roles': []},
                                {'name': 'omazh', 'gender': 'female', 'roles': ['neutral', 'evil']},
                                {'name': 'zahar', 'gender': 'male', 'roles': ['neutral', 'good']},
                                {'name': 'dasha', 'gender': 'female', 'roles': ['neutral', 'good', 'friendly']},
                                {'name': 'julia', 'gender': 'female', 'roles': ['neutral', 'strict']},
                                {'name': 'lera', 'gender': 'female', 'roles': ['neutral', 'friendly']},
                                {'name': 'marina', 'gender': 'female', 'roles': ['neutral', 'whisper', 'strict']},
                                {'name': 'alexander', 'gender': 'male', 'roles': ['neutral', 'good']},
                                {'name': 'kirill', 'gender': 'male', 'roles': ['neutral', 'strict', 'good']},
                                {'name': 'anton', 'gender': 'male', 'roles': ['neutral', 'good']}],
                    'uzbek': [{'name': 'nigora', 'gender': 'female', 'roles': []}]
                    }
xtts_languages = ['english', 'spanish', 'french', 'german', 'italian', 'portuguese', 'polish', 'turkish', 'russian',
                  'dutch', 'czech', 'arabic', 'chinese', 'japanese', 'hungarian', 'korean']
silero_languages = ['Russian', 'Ukrainian', 'Uzbek', 'Avar', 'Bashkir', 'Bulgarian', 'Chechen',
                    'Chuvash', 'Erzya', 'Kalmyk', 'Karachay-Balkar', 'Kazakh', 'Khakas',
                    'Komi-Ziryan', 'Lezghian', 'Mari', 'Mari High', 'Nogai', 'Ossetic', 'Tatar',
                    'Tuvinian', 'Udmurt', 'Yakut', 'Hindi', 'Malayalam', 'Manipuri', 'Bengali',
                    'Rajasthani', 'Tamil', 'Telugu', 'Gujarati', 'Kannada', 'English', 'German',
                    'Spanish', 'French']
fish_languages = ['english', 'spanish', 'french', 'german', 'russian', 'arabic', 'chinese', 'japanese', 'korean']
