import gradio as gr
import os
import shutil
import Dub_functions as dfunc
import TTS_functions as tf
import ASR_functions as af
import subprocess
from pydub import AudioSegment
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
from zipfile import ZipFile


def video_cutting(vid_uploaded, mode, vid_fragms_uploaded, progress=gr.Progress()):
    if not os.path.isfile(tf.path_to_video):
        if vid_uploaded:
            os.rename(vid_uploaded, tf.path_to_video)
        else:
            raise gr.Error("You haven't uploaded the video. It is necessary to do this on the first tab.")

    if mode == "Stretch/narrow video to fit phrases (takes a lot of time)":
        # создание директорий
        if os.path.exists(dfunc.path_to_all):
            shutil.rmtree(dfunc.path_to_all)
            os.makedirs(dfunc.path_to_all)
            if vid_fragms_uploaded:
                with ZipFile(vid_fragms_uploaded) as z:
                    z.extractall(dfunc.path_to_all)
            else:
                os.makedirs(dfunc.path_to_fragments)
                os.makedirs(dfunc.path_to_intermediate)
        else:
            os.makedirs(dfunc.path_to_all, exist_ok=True)
            if vid_fragms_uploaded:
                with ZipFile(vid_fragms_uploaded) as z:
                    z.extractall(dfunc.path_to_all)
            else:
                os.makedirs(dfunc.path_to_fragments, exist_ok=True)
                os.makedirs(dfunc.path_to_intermediate, exist_ok=True)

        if not vid_fragms_uploaded:
            if os.path.isfile(tf.path_to_video) and os.path.isfile(tf.path_to_text):
                # считываем из файла строки
                lines = tf.read_srt_file()
                # копируем заставку
                progress(0.1, desc="Copying the screensaver...")
                command = ["ffmpeg", "-y", "-i", tf.path_to_video, "-to", str(af.str_to_time(lines[2][:lines[2].find(' ')])),
                           "-async", str(1), "/content/int_fragms/s.mp4"]
                subprocess.run(command)
                # остальные фрагменты
                progress(0.2, desc="Copying other fragments...")
                for i in range(0, len(lines), 4):
                    out_path1 = dfunc.path_to_fragments + '/' + str(int(i / 4)) + '.mp4'
                    out_path2 = dfunc.path_to_intermediate + '/' + str(int(i / 4)) + '.mp4'
                    start = af.str_to_time(lines[i + 2][:lines[i + 2].find(' ')])  # в секундах, float
                    end = af.str_to_time(lines[i + 2][lines[i + 2].rfind(' ') + 1:])
                    # копирование части видео по таймингу
                    command = ["ffmpeg", "-y", "-i", tf.path_to_video, "-ss", start + 0.001, "-to", end, "-async", str(1),
                               out_path1]
                    subprocess.run(command)
                    if i != len(lines) - 4:  # не последний тайминг
                        next_start = af.str_to_time(lines[i + 6][:lines[i + 6].find(' ')])
                        if next_start - end > 0:
                            command = ["ffmpeg", "-y", "-i", tf.path_to_video, "-ss", end + 0.001, "-to", next_start,
                                       "-async", str(1), out_path2]
                            subprocess.run(command)
                    else:
                        if round(dfunc.video_duration(tf.path_to_video), 3) > end:
                            command = ["ffmpeg", "-y", "-i", tf.path_to_video, "-ss", end + 0.001, "-async", str(1),
                                       out_path2]
                            subprocess.run(command)
                progress(0.9, desc="Creating zip-archive...")
                shutil.make_archive(base_name="all_fragments", format="zip", root_dir=dfunc.path_to_all)
                return [gr.Textbox("Cutting completed."), gr.DownloadButton(visible=True, value="path_to_zip")]
            else:
                raise gr.Error('It looks like you haven\'t uploaded a video or a text file (or both).')
        else:
            return [gr.Textbox("Skipping cutting..."), gr.DownloadButton(visible=False)]
    else:
        return [gr.Textbox("Skipping cutting..."), gr.DownloadButton(visible=False)]


# предусмотреть вариант использования уже загруженных фрагментов речи
def make_dubbing(mode, slow_aud, limit, speech_fragms_uploaded, progress=gr.Progress()):
    print("WE ENTERED 2")
    print(mode, slow_aud, limit, speech_fragms_uploaded)
    times = []

    if os.path.exists(tf.path_to_init) and os.path.isfile(tf.path_to_text):
        if os.path.exists(tf.path_to_synth):
            shutil.rmtree(tf.path_to_synth)
            os.makedirs(tf.path_to_synth)
            if speech_fragms_uploaded:
                with ZipFile(speech_fragms_uploaded) as z:
                    z.extractall(dfunc.path_to_all)
        else:
            os.makedirs(tf.path_to_synth, exist_ok=True)
            if speech_fragms_uploaded:
                with ZipFile(speech_fragms_uploaded) as z:
                    z.extractall(dfunc.path_to_all)

        # чтение файла
        lines = tf.read_srt_file()
        if mode == "Simple audio overlay by timings":
            if os.path.isfile(tf.path_to_video):
                dfunc.path_to_screensaver = 's.mp4'
                # вырезание заставки из видео
                if af.str_to_time(lines[2][:lines[2].find(' ')]) > 0:
                    progress(0.1, desc="Copying the screensaver...")
                    command = ["ffmpeg", "-y", "-i", tf.path_to_video, "-to",
                               str(af.str_to_time(lines[2][:lines[2].find(' ')])), "-async", str(1),
                               dfunc.path_to_screensaver]
                    subprocess.run(command)
                # основная логика
                progress(0.2, desc="Changing audio durations...")
                for i in range(0, len(lines), 4):
                    old_path = tf.path_to_init + '/' + str(int(i / 4)) + '.wav'
                    new_path = tf.path_to_synth + '/' + str(int(i / 4)) + '.wav'
                    # изменение продолжительности аудио в соответствии с таймингом
                    dfunc.check_duration(old_path, new_path, af.str_to_time(lines[i + 2][:lines[i + 2].find(' ')]),
                                         af.str_to_time(lines[i + 2][lines[i + 2].rfind(' ') + 1:]), slow_aud, limit)
                    # добавление паузы после фразы до следующего тайминга или до конца
                    audio = AudioSegment.from_wav(new_path)
                    aud_len = len(audio) / 1000
                    if i != len(lines) - 4:  # если не последний тайминг
                        # продолжительность от начала текущего сегмента до начала следующего (в секундах)
                        fragm_dur = af.str_to_time(lines[i + 6][:lines[i + 6].find(' ')]) - af.str_to_time(
                            lines[i + 2][:lines[i + 2].find(' ')])
                        if aud_len < fragm_dur:
                            dfunc.add_pause(new_path, new_path, fragm_dur - aud_len)
                    else:  # последний тайминг
                        # продолжительность от начала текущего сегмента до конца видео (в секундах)
                        fragm_dur = dfunc.video_duration(tf.path_to_video) - af.str_to_time(lines[i + 2][:lines[i + 2].find(' ')])
                        if aud_len < fragm_dur:
                            dfunc.add_pause(new_path, new_path, fragm_dur - aud_len)
            else:
                raise gr.Error("You haven't uploaded the video. It is necessary to do this on the first tab.")

        else:
            if os.path.exists(dfunc.path_to_fragments and os.path.exists(dfunc.path_to_intermediate)):
                for i in range(0, len(lines), 4):
                    progress(0.3, desc="Processing video clips...")
                    old_path = tf.path_to_init + '/' + str(int(i / 4)) + '.wav'
                    new_path = tf.path_to_synth + '/' + str(int(i / 4)) + '.wav'
                    vid_path = dfunc.path_to_fragments + '/' + str(int(i / 4)) + '.mp4'
                    pause_path = dfunc.path_to_intermediate + '/' + str(int(i / 4)) + '.mp4'
                    # замедление/ускорение видеофрагмента, если синтезированная фраза длиннее/короче
                    times = dfunc.check_vid_duration(old_path, vid_path, limit, times)
                    if os.path.exists(pause_path):  # есть следующий фрагмент видео (тайминги не одинаковые для конца и начала след. фразы)
                        # добавление паузы, равной продолжительности следующего видеофрагмента
                        dfunc.add_pause(old_path, new_path, dfunc.video_duration(pause_path))
                    else:  # иначе всё равно копируем в новую папку
                        shutil.copyfile(old_path, new_path)
            else:
                raise gr.Error("You didn't upload the fragments in the downloads section.")

        # склеиваем все фразы в целую аудиодорожку
        progress(0.5, desc="Combining all phrases...")
        synthesized = [tf.path_to_synth + '/' + item for item in os.listdir(tf.path_to_synth) if '.ipynb' not in item]
        synthesized = sorted(synthesized, key=dfunc.extract_number)
        start = af.str_to_time(lines[2][:lines[2].find(' ')])
        if start:  # фраза начинается не с самого начала
            combined = AudioSegment.silent(duration=start * 1000)  # тишина
        else:
            combined = None
        for fragment in synthesized:
            audio = AudioSegment.from_file(fragment, format="wav")
            if combined is None:
                combined = audio
            else:
                combined += audio
        # сохранение результата
        combined.export('/content/synthesized_speech.wav', format="wav")

        # Наложение на видео новой аудиодорожки
        if mode == "Stretch/narrow video to fit phrases (takes a lot of time)":
            progress(0.6, desc="Combining all fragments...")
            # объединение изменённых видеофрагментов
            fragments = [dfunc.path_to_fragments + '/' + item for item in os.listdir(dfunc.path_to_fragments) if
                         '.ipynb' not in item]
            fragments = sorted(fragments, key=dfunc.extract_number)
            int_fragms = [dfunc.path_to_intermediate + '/' + item for item in os.listdir(dfunc.path_to_intermediate) if
                          '.ipynb' not in item and 's' not in item]
            int_fragms = sorted(int_fragms, key=dfunc.extract_number)
            loaded_video_list = [VideoFileClip(dfunc.path_to_intermediate + '/s.mp4')]
            for i, vid in enumerate(fragments):
                loaded_video_list.append(VideoFileClip(vid))
                next_fragm = dfunc.path_to_intermediate + '/' + str(i) + '.mp4'
                if os.path.exists(next_fragm):  # если существует промежуточный фрагмент
                    loaded_video_list.append(VideoFileClip(next_fragm))
            concatenate_clip = concatenate_videoclips(loaded_video_list)
            if os.path.exists(tf.path_to_video):
                os.remove(tf.path_to_video)
            concatenate_clip.write_videofile(tf.path_to_video, logger=None)

            # исправление файла с субтитрами с помощью списка times
            progress(0.7, desc="Creating new subtitles...")
            start_timing = ""
            for i in range(0, len(lines), 4):
                audio_length = times[int(i / 4)]  # в секундах
                if i == 0:  # первый тайминг
                    start_timing = lines[i + 2][:lines[i + 2].find(' ')]
                    end_timing = af.time_to_str(af.str_to_time(start_timing) + audio_length)
                    lines[i + 2] = start_timing + ' --> ' + end_timing
                    pause = dfunc.path_to_intermediate + '/' + str(int(i / 4)) + '.mp4'
                    if os.path.exists(pause):
                        start_timing = af.time_to_str(af.str_to_time(end_timing) + dfunc.video_duration(pause))
                    else:
                        start_timing = end_timing
                elif i == len(lines) - 4:  # последний
                    end_timing = af.time_to_str(af.str_to_time(start_timing) + audio_length)
                    lines[i + 2] = start_timing + ' --> ' + end_timing
                else:  # средний
                    end_timing = af.time_to_str(af.str_to_time(start_timing) + audio_length)
                    lines[i + 2] = start_timing + ' --> ' + end_timing
                    pause = dfunc.path_to_intermediate + '/' + str(int(i / 4)) + '.mp4'
                    if os.path.exists(pause):
                        start_timing = af.time_to_str(af.str_to_time(end_timing) + dfunc.video_duration(pause))
                    else:
                        start_timing = end_timing

            txt_file = open(dfunc.subs_path, 'w', encoding="utf-8")
            for line in lines[1:-1]:
                txt_file.write(line + '\n')
            if len(lines) != 1:
                txt_file.write(lines[-1])
            txt_file.close()

        # добавление в начало аудиодорожки заставки на случай, если она была музыкальной
        if os.path.isfile(dfunc.path_to_screensaver):
            screensaver = VideoFileClip(dfunc.path_to_screensaver)
            music = screensaver.audio
            music.write_audiofile('music.wav')
            full_audio = AudioSegment.from_wav('synthesized_speech.wav')
            full_audio = AudioSegment.from_wav('music.wav') + full_audio[screensaver.duration * 1000:]
        else:
            full_audio = AudioSegment.from_wav('synthesized_speech.wav')
        full_audio.export('synthesized_speech1.wav', format='wav')

        # Наложение на видео аудиодорожки
        progress(0.9, desc="Overlay on a video audio track...")
        command = ["ffmpeg", "-i", tf.path_to_video, "-i", "synthesized_speech1.wav", "-c:v", "copy", "-c:a",
                   "aac", "-strict", "experimental", "-map", "0:v:0", "-map", "1:a:0", dfunc.path_to_res]
        subprocess.run(command)
        progress(1.0, desc="Done. Congratulations!")

        if mode == "Stretch/narrow video to fit phrases (takes a lot of time)":
            return [gr.Textbox(visible=False), gr.DownloadButton(visible=True, value=dfunc.subs_path),
                    gr.DownloadButton(visible=True, value=dfunc.path_to_res)]
        else:
            return [gr.Textbox(visible=False), gr.DownloadButton(visible=False),
                    gr.DownloadButton(visible=True, value=dfunc.path_to_res)]
    else:
        if not os.path.exists(tf.path_to_init):
            raise gr.Error("The folder with synthesized speech was not found. Perhaps you haven't synthesized it. Or you haven't uploaded the archive.")
        else:
            raise gr.Error("You haven't uploaded the text. You can do this in the downloads section.")
