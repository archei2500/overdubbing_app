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
                    shutil.copyfile(old_path, aud_path)
                    tf.speedup(aud_path, coef)
        else:
            # ограничение на ускорение в случае с аудио не накладываем, т. к. в видеофрагмент важно уложиться
            shutil.copyfile(old_path, aud_path)
            tf.speedup(aud_path, coef)
    else:  # в любом случае копируем в новую папку
        shutil.copyfile(old_path, aud_path)


def check_vid_duration(aud_path, vid_path, limit, times):
    # получение продолжительности видео
    audio = AudioSegment.from_file(aud_path)
    video = VideoFileClip(vid_path).without_audio()
    times.append(len(audio) / 1000)
    if abs(len(audio) / 1000 - video.duration) > 0.05:  # аудио короче или длиннее видео на более чем 50 мс
        coef = round(video.duration / (len(audio) / 1000), 3)
        if limit:
            # проверка коэффициента, замедление или усорение будет выполнено, только если коэффициент в данных пределах
            if coef <= 1.1 and coef >= 0.9:
                video = accel_decel(video, video.duration / coef, abruptness=0)
                os.remove(vid_path)
                video.write_videofile(vid_path, threads=4)
            else:  # иначе работа с самим аудио
                if coef > 1:  # если видео собирались ускорить, к аудио добавляем паузу
                    pause_len = video.duration - (len(audio) / 1000)  # в с
                    add_pause(aud_path, aud_path, pause_len)
                else:  # если видео собирались замедлить, то ускоряем аудио
                    tf.speedup(aud_path, 1 / coef)
                    audio = AudioSegment.from_file(aud_path)
                    times.pop()
                    times.append(len(audio) / 1000)
        else:
            video = accel_decel(video, video.duration / coef, abruptness=0)
            os.remove(vid_path)
            video.write_videofile(vid_path, threads=4)


def extract_number(s):
    match = re.search(r'\d+', s) # регулярное выражение \d+ означает "одна или более цифр подряд"
    if match:
        return int(match.group())
    else:
        return 0


path_to_all = 'all'
path_to_fragments = 'all/fragments'
path_to_intermediate = 'all/int_fragms'
path_to_screensaver = 'all/int_fragms/s.mp4'
path_to_res = "result.mp4"
subs_path = 'new_subs.srt'
