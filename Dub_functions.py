import cv2
from pydub import AudioSegment
import shutil
import TTS_functions as tf
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
from moviepy.video.fx.accel_decel import accel_decel
import os
import re


# def str_to_time(s):
#     return int(s[6:8]) + 60 * int(s[3:5]) + 3600 * int(s[:2]) + float('0.' + s[9:12])


def video_duration(filename):
    video = cv2.VideoCapture(filename)

    fps = video.get(cv2.CAP_PROP_FPS)
    frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = frame_count / fps

    video.release()

    return duration


def add_pause(old_path, aud_path, dur):
    # генерация тишины (в миллисекундах)
    silence = AudioSegment.silent(duration=dur * 1000)
    audio = AudioSegment.from_file(old_path)
    audio += silence
    audio.export(aud_path, format="wav")


def check_duration(old_path, aud_path, start, end, slow_aud, limit):
    duration = (end - start) * 1000  # в миллисекундах
    # измеряем продолжительность синтезированного фрагмента
    audio = AudioSegment.from_file(old_path)
    if len(audio) != duration:  # если аудио получилось больше или меньше требуемой продолжительности
        # нужно его ускорить и замедлить или добавить паузу (в зависимости от режима)
        coef = len(audio) / duration  # коэффициент растяжения или сжатия
        if coef < 1:
            if not slow_aud:  # не замедляем аудио
                add_pause(old_path, aud_path, (duration - len(audio)) / 1000)
            else:
                if limit:
                    if coef >= 0.9:  # замедление будет выполнено, только если аудио не станет медленнее этого значения
                        shutil.copyfile(old_path, aud_path)
                        tf.speedup(aud_path, coef)
                    else:
                        add_pause(old_path, aud_path, (duration - len(audio)) / 1000)
                else:
                    shutil.copyfile(old_path, aud_path)
                    tf.speedup(aud_path, coef)
        else:
            # ограничение на ускорение в случае с аудио не накладываем, т. к. в видеофрагмент важно уложиться
            shutil.copyfile(old_path, aud_path)
            tf.speedup(aud_path, coef)
    else:  # в любом случае копируем в новую папку
        shutil.copyfile(old_path, aud_path)


# старое - меняем его
def check_vid_duration(aud_path, vid_path, limit, times):
    # получение продолжительности видео
    audio = AudioSegment.from_file(aud_path)
    video = VideoFileClip(vid_path).without_audio()
    audio_duration = len(audio) / 1000
    vid_duration = video.duration
    final_duration = vid_duration
    # times.append(len(audio) / 1000)
    if abs(audio_duration - vid_duration) > 0.05:  # аудио короче или длиннее видео на более чем 50 мс
        coef = round(vid_duration / audio_duration, 3)
        if limit:
            # проверка коэффициента, замедление или усорение будет выполнено, только если коэффициент в данных пределах
            if 1.1 >= coef >= 0.9:
                print("OH WEEE RE ")
                video = accel_decel(video, vid_duration / coef, abruptness=0)
                os.remove(vid_path)
                video.write_videofile(vid_path, threads=4)
                final_duration = audio_duration
            else:  # иначе работа с самим аудио
                if coef > 1:  # если видео собирались ускорить, к аудио добавляем паузу
                    pause_len = vid_duration - audio_duration  # в с
                    add_pause(aud_path, aud_path, pause_len)
                else:  # если видео собирались замедлить, то ускоряем аудио
                    tf.speedup(aud_path, 1 / coef)
                    audio = AudioSegment.from_file(aud_path)
                    times.pop()
                    times.append(len(audio) / 1000)
        else:
            video = accel_decel(video, vid_duration / coef, abruptness=0)
            os.remove(vid_path)
            video.write_videofile(vid_path, threads=4)
            final_duration = audio_duration
    times.append(final_duration)


# def check_vid_duration(aud_path, vid_path, limit):
#     audio = AudioSegment.from_file(aud_path)
#     video = VideoFileClip(vid_path).without_audio()
#     audio_duration = len(audio) / 1000  # Длительность аудио в секундах
#     video_duration = video.duration  # Длительность видео в секундах
#
#     # Проверяем, нужно ли изменять длительность
#     if abs(audio_duration - video_duration) > 0.05:  # Разница > 50 мс
#         coef = round(video_duration / audio_duration, 3)
#
#         if limit and (coef > 1.1 or coef < 0.9):  # Если ограничение и коэффициент вне диапазона
#             # Работаем с аудио (добавляем паузу или ускоряем)
#             if coef > 1:  # Видео длиннее -> добавляем паузу к аудио
#                 pause_len = video_duration - audio_duration
#                 add_pause(aud_path, aud_path, pause_len)
#                 final_duration = video_duration  # После паузы аудио = видео
#             else:  # Видео короче -> ускоряем аудио
#                 speedup(aud_path, 1 / coef)
#                 final_duration = video_duration  # После ускорения аудио = видео
#         else:  # Либо нет ограничений, либо коэффициент в допустимых пределах
#             # Меняем скорость видео
#             video = accel_decel(video, video_duration / coef, abruptness=0)
#             os.remove(vid_path)
#             video.write_videofile(vid_path, threads=4)
#             final_duration = len(AudioSegment.from_file(aud_path)) / 1000  # Новая длительность аудио
#     else:  # Разница <= 50 мс, ничего не меняем
#         final_duration = audio_duration
#
#     times.append(final_duration)  # Добавляем итоговую длительность


def extract_number(s):
    match = re.search(r'\d+', s)  # регулярное выражение \d+ означает "одна или более цифр подряд"
    if match:
        return int(match.group())
    else:
        return 0


# for lip sync
def convert_frames_to_video(path_in, path_out, fps):
    frame_array = []
    files = [os.path.join(path_in, f) for f in os.listdir(path_in) if os.path.isfile(os.path.join(path_in, f))]
    files = sorted(files, key=extract_number)

    size = (10, 10)
    for file in files:
        # чтение файлов с кадрами
        img = cv2.imread(file)
        height, width, layers = img.shape
        size = (width, height)
        # добавление кадров в список изображений
        frame_array.append(img)
    out = cv2.VideoWriter(path_out, cv2.VideoWriter_fourcc(*'DIVX'), fps, size)
    for i in range(len(frame_array)):
        # запись списка изображений в качестве видео
        out.write(frame_array[i])
    out.release()


path_to_all = 'all'
path_to_fragments = 'all/fragments'
path_to_intermediate = 'all/int_fragms'
path_to_screensaver = 'all/int_fragms/s.mp4'
path_to_res = "result.mp4"
subs_path = 'new_subs.srt'
