import gradio as gr
import os
import shutil
import subprocess
from moviepy.editor import VideoFileClip, concatenate_videoclips
from pydub import AudioSegment
import cv2

import ASR_functions as af
import TTS_functions as tf
import Dub_functions as dfunc

path_to_auds = 'aud_fragms'
path_to_vids = 'vid_fragms'
path_to_lip_res = 'lip_results'


def func_lip_sync(timings_str, lip_tool, pad_top, pad_left, pad_right, pad_bottom, nosmooth, gfpgan, raw_video):
    if raw_video and os.path.isfile(raw_video):
        tf.path_to_video = raw_video
    else:
        raise gr.Error("There is no dubbed video!")

    if timings_str:
        try:
            timings = [int(n) for n in timings_str.split()]
            timings.sort()  # сортировка по возрастанию
        except ValueError:
            raise gr.Error("You entered the fragment numbers incorrectly.")
    else:
        raise gr.Error("You must enter the fragment numbers!")

    lines = tf.read_srt_file()
    print(lines)

    # проверка на принадлежность существующему диапазону таймингов, введённых пользователем
    if timings[0] >= 1 and timings[-1] <= len(lines) / 4:
        # создание папок для хранения аудио- и видеофрагментов
        if os.path.exists(path_to_auds):
            shutil.rmtree(path_to_auds)
            os.makedirs(path_to_auds)
        else:
            os.makedirs(path_to_auds, exist_ok=True)
        if os.path.exists(path_to_vids):
            shutil.rmtree(path_to_vids)
            os.makedirs(path_to_vids)
        else:
            os.makedirs(path_to_vids, exist_ok=True)

        # из видео вырезаются фрагменты для анимации губ
        for i, timing in enumerate(timings):
            start = af.str_to_time(lines[(timing - 1) * 4 + 2][:lines[(timing - 1) * 4 + 2].find(' ')])
            end = af.str_to_time(lines[(timing - 1) * 4 + 2][lines[(timing - 1) * 4 + 2].rfind(' ') + 1:])
            out_path = path_to_vids + '/' + str(i) + '.mp4'
            # фрагмент вырезается по таймингу
            command = ["ffmpeg", "-y", "-i", tf.path_to_video, "-ss", str(start + 0.001), "-to", str(end), "-async",
                       "1",
                       out_path]
            subprocess.run(command)
            # извлечение аудиодорожки с проверкой на то, что аудио и видео точно одной продолжительности
            video = VideoFileClip(out_path)
            video.audio.write_audiofile(path_to_auds + '/' + str(i) + '.wav')  # извлечение аудиодорожки
            difference = video.duration - len(AudioSegment.from_file(path_to_auds + '/' + str(i) + '.wav')) / 1000
            if difference > 0:
                os.remove(out_path)
                command = ["ffmpeg", "-y", "-i", tf.path_to_video, "-to", str(video.duration - difference), "-async",
                           "1",
                           out_path]
        # фрагменты заносятся в списки и сортируются по возрастанию
        lip_fragments_list = [path_to_vids + '/' + item for item in os.listdir(path_to_vids) if '.ipynb' not in item]
        lip_fragments_list = sorted(lip_fragments_list, key=dfunc.extract_number)
        aud_fragments_list = [path_to_auds + '/' + item for item in os.listdir(path_to_auds) if '.ipynb' not in item]
        aud_fragments_list = sorted(aud_fragments_list, key=dfunc.extract_number)

        # создание папки для результатов lip sync
        if os.path.exists(path_to_lip_res):
            shutil.rmtree(path_to_lip_res)
            os.makedirs(path_to_lip_res)
        else:
            os.makedirs(path_to_lip_res, exist_ok=True)

        # выбирается одна из моделей
        checkpoint_path = 'checkpoints/wav2lip.pth' if lip_tool == 'Wav2Lip' else 'checkpoints/wav2lip_gan.pth'

        # синхронизация губ
        for i, lip_fragm in enumerate(lip_fragments_list):
            print("SYNCRONISEEEE")
            output_file_path = path_to_lip_res + '/' + str(i) + '.mp4'
            face_path = lip_fragm
            audio_path = aud_fragments_list[i]
            # временное копирование
            shutil.copyfile(face_path, "Wav2Lip/face.mp4")
            shutil.copyfile(audio_path, "Wav2Lip/audio.wav")
            buf_output = "vidde.mp4"

            command = [
                "python", "inference.py",
                "--checkpoint_path", checkpoint_path,
                "--face", "face.mp4",
                "--audio", "audio.wav",
                "--outfile", "vidde.mp4",
                "--pads", str(pad_top), str(pad_bottom), str(pad_left), str(pad_right)
            ]
            if nosmooth:
                command.append("--nosmooth")
            result = subprocess.run(command, capture_output=True, text=True, cwd="Wav2Lip")
            print("STDOUT:", result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
            os.remove("Wav2Lip/face.mp4")
            os.remove("Wav2Lip/audio.wav")
            os.rename("Wav2Lip/vidde.mp4", output_file_path)
            print(os.path.isfile(output_file_path))

            # Увеличение размеров кадров после обработки, т. к. они уменьшаются
            vcap1 = cv2.VideoCapture(face_path)  # старое видео до Wav2Lip
            vcap2 = cv2.VideoCapture(output_file_path)  # новое видео после Wav2Lip
            fps = vcap2.get(cv2.CAP_PROP_FPS)
            new_width = vcap1.get(cv2.CAP_PROP_FRAME_WIDTH)  # float
            new_height = vcap1.get(cv2.CAP_PROP_FRAME_HEIGHT)
            out = cv2.VideoWriter('resized_video.mp4', cv2.VideoWriter_fourcc(*'mp4v'), fps,
                                  (int(new_width), int(new_height)))  # создание объекта для записи видео
            while True:
                ret, frame = vcap2.read()
                if not ret:
                    break
                # Изменение размеров кадра
                resized_frame = cv2.resize(frame, (int(new_width), int(new_height)))
                # Запись измененного кадра в новое видео
                out.write(resized_frame)
                # cv2.imwrite(resized_frame)
            # Освобождение ресурсов
            vcap1.release()
            vcap2.release()
            out.release()
            cv2.destroyAllWindows()
            print(os.path.isfile(output_file_path))
            os.remove(output_file_path)
            os.rename('resized_video.mp4', output_file_path)

        if gfpgan:
            os.makedirs("results", exist_ok=True)
            os.makedirs("results_videos", exist_ok=True)
            os.makedirs("results_mp4_videos", exist_ok=True)
            for i, timing in enumerate(timings):
                lip_fragm = path_to_lip_res + "/" + str(i) + '.mp4'
                if os.path.exists(lip_fragm):
                    print("ВОТ СЮДА ЗАХОДИМ")
                    # преобразование видео в фреймы
                    vid_stream = cv2.VideoCapture(lip_fragm)
                    fps = vid_stream.get(cv2.CAP_PROP_FPS)  # получаем fps
                    os.makedirs("vid_frames", exist_ok=True)
                    # сохранение всех кадров из видео
                    current_frame = 0
                    while True:
                        # cap.read() в ret возвращает значение типа boolean. Если frame прочитан корректно: ret = True.
                        ret, frame = vid_stream.read()
                        if ret:
                            frame_path = 'vid_frames/frame' + str(current_frame) + '.jpg'
                            cv2.imwrite(frame_path, frame)
                            # увеличение значения счётчика кадров
                            current_frame += 1
                        else:
                            break
                    vid_stream.release()
                    cv2.destroyAllWindows()
                    # улучшение кадров
                    command = ["python", "GFPGAN/inference_gfpgan.py", "-i", "vid_frames", "-o", "results", "-v", "1.3",
                               "-s", "1", "--bg_upsampler", "realesrgan"]
                    result = subprocess.run(command, capture_output=True, text=True)
                    print("STDOUT:", result.stdout)
                    if result.stderr:
                        print("STDERR:", result.stderr)
                    for f in os.listdir('vid_frames'):
                        os.remove(os.path.join('vid_frames', f))
                    # конвертирование super res frames to .avi
                    path_out = "results_videos/" + str(i) + '.avi'
                    # fps видео
                    dfunc.convert_frames_to_video('results/restored_imgs/', path_out, fps)
                    for f in os.listdir('results/restored_imgs'):
                        os.remove(os.path.join('results/restored_imgs', f))
                    # конвертирование .avi to .mp4
                    src = 'results_videos/'
                    dst = 'results_mp4_videos/'
                    for root, dirs, filenames in os.walk(src, topdown=False):
                        for filename in filenames:
                            _format = ''
                            if ".flv" in filename.lower():
                                _format = ".flv"
                            if ".mp4" in filename.lower():
                                _format = ".mp4"
                            if ".avi" in filename.lower():
                                _format = ".avi"
                            if ".mov" in filename.lower():
                                _format = ".mov"
                            inputfile = os.path.join(root, filename)
                            outputfile = os.path.join(dst, filename.lower().replace(_format, ".mp4"))
                            subprocess.call(['ffmpeg', '-i', inputfile, outputfile])
                    for f in os.listdir('results_videos'):
                        os.remove(os.path.join('results_videos', f))

            # Копирование улучшенных видео в lip_results
            for i, timing in enumerate(timings):
                lip_fragm = 'lip_results/' + str(i) + '.mp4'
                new_lip_fragm = 'results_mp4_videos/' + str(i) + '.mp4'
                shutil.copyfile(new_lip_fragm, lip_fragm)

        # Итоговая нарезка
        counter = 0
        if os.path.exists("fragments"):
            shutil.rmtree("fragments")
            os.makedirs("fragments")
        else:
            os.makedirs("fragments", exist_ok=True)
        if os.path.exists("audios"):
            shutil.rmtree("audios")
            os.makedirs("audios")
        else:
            os.makedirs("audios", exist_ok=True)
        for i, timing in enumerate(timings):
            lip_fragm = path_to_lip_res + "/" + str(i) + '.mp4'
            old_aud = path_to_auds + "/" + str(i) + '.wav'
            start = 0
            end = af.str_to_time(lines[(timing - 1) * 4 + 2][:lines[(timing - 1) * 4 + 2].find(' ')])
            out_path = 'fragments/' + str(counter) + '.mp4'
            aud_path = 'audios/' + str(counter) + '.wav'
            if len(timings) == 1:  # единственный
                command = ["ffmpeg", "-y", "-i", tf.path_to_video, "-to", str(end), "-async", "1", out_path]
                subprocess.run(command)
                audio = VideoFileClip(out_path).audio
                audio.write_audiofile(aud_path)
                counter += 1
                os.rename(lip_fragm, 'fragments/' + str(counter) + '.mp4')
                shutil.copyfile(old_aud, 'audios/' + str(counter) + '.wav')
                counter += 1
                start = af.str_to_time(lines[(timing - 1) * 4 + 2][lines[(timing - 1) * 4 + 2].rfind(' ') + 1:])
                if VideoFileClip(tf.path_to_video).duration > start:
                    out_path = 'fragments/' + str(counter) + '.mp4'
                    aud_path = 'audios/' + str(counter) + '.wav'
                    command = ["ffmpeg", "-y", "-i", tf.path_to_video, "-ss", str(start + 0.001), "-async", "1",
                               out_path]
                    subprocess.run(command)
                    audio = VideoFileClip(out_path).audio
                    audio.write_audiofile(aud_path)
            elif i == 0:  # если самый первый
                command = ["ffmpeg", "-y", "-i", tf.path_to_video, "-to", str(end), "-async", "1", out_path]
                subprocess.run(command)
                audio = VideoFileClip(out_path).audio
                audio.write_audiofile(aud_path)
                counter += 1
                os.rename(lip_fragm, 'fragments/' + str(counter) + '.mp4')
                shutil.copyfile(old_aud, 'audios/' + str(counter) + '.wav')
                counter += 1
                start = af.str_to_time(lines[(timing - 1) * 4 + 2][lines[(timing - 1) * 4 + 2].rfind(' ') + 1:])
            elif i == len(timings) - 1:  # если последний
                command = ["ffmpeg", "-y", "-i", tf.path_to_video, "-ss", str(start + 0.001), "-to", str(end), "-async",
                           "1", out_path]
                subprocess.run(command)
                audio = VideoFileClip(out_path).audio
                audio.write_audiofile(aud_path)
                counter += 1
                os.rename(lip_fragm, 'fragments/' + str(counter) + '.mp4')
                shutil.copyfile(old_aud, 'audios/' + str(counter) + '.wav')
                counter += 1
                start = af.str_to_time(lines[(timing - 1) * 4 + 2][lines[(timing - 1) * 4 + 2].rfind(' ') + 1:])
                if VideoFileClip(tf.path_to_video).duration > start:
                    out_path = 'fragments/' + str(counter) + '.mp4'
                    aud_path = 'audios/' + str(counter) + '.wav'
                    command = ["ffmpeg", "-y", "-i", tf.path_to_video, "-ss", str(start + 0.001), "-async", "1",
                               out_path]
                    subprocess.run(command)
                    audio = VideoFileClip(out_path).audio
                    audio.write_audiofile(aud_path)
            else:  # обычный
                end = af.str_to_time(lines[(timing - 1) * 4 + 2][:lines[(timing - 1) * 4 + 2].find(' ')])
                command = ["ffmpeg", "-y", "-i", tf.path_to_video, "-ss", str(start + 0.001), "-to", str(end), "-async",
                           "1", out_path]
                subprocess.run(command)
                audio = VideoFileClip(out_path).audio
                audio.write_audiofile(aud_path)
                counter += 1
                os.rename(lip_fragm, 'fragments/' + str(counter) + '.mp4')
                shutil.copyfile(old_aud, 'audios/' + str(counter) + '.wav')
                counter += 1
                start = af.str_to_time(lines[(timing - 1) * 4 + 2][lines[(timing - 1) * 4 + 2].rfind(' ') + 1:])

        fragments = ['/content/fragments/' + item for item in os.listdir('/content/fragments') if '.ipynb' not in item]
        fragments = sorted(fragments, key=dfunc.extract_number)

        loaded_video_list = []
        # склеиваем все фрагменты
        for fragment in fragments:
            loaded_video_list.append(VideoFileClip(fragment))
        concatenate_clip = concatenate_videoclips(loaded_video_list, method='compose')
        concatenate_clip.write_videofile('lips_result.mp4', logger=None)
        # Накладываем аудиодорожку
        command = ["ffmpeg", "-i", "lips_result.mp4", "-i", "aud.wav", "-c:v", "copy", "-c:a", "aac", "-strict",
                   "experimental", "-map", "0:v:0", "-map", "1:a:0", "final_video.mp4"]
        subprocess.run(command)

        return [gr.Textbox(visible=False), gr.DownloadButton(visible=True, value="final_video.mp4")]

    else:
        err_str = "You have uploaded a file that contains " + str(
            int(len(lines) / 4)) + " segments, but entered " + timings_str
        raise gr.Error(err_str)
