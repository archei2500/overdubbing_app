from datetime import timedelta
import re

def str_to_time(s):
  return int(s[6:8]) + 60 * int(s[3:5]) + 3600 * int(s[:2]) + float('0.' + s[9:12])


def time_to_str(time):
  hours = int(time // 3600)
  minutes = int((time - 3600 * hours) // 60)
  seconds = time - 60 * minutes
  str_sec = str(round(seconds, 3)).replace('.', ',')
  return str(hours).zfill(2) + ':' + str(minutes).zfill(2) + ':' + str_sec[:str_sec.find(',')].zfill(2) + ',' + str_sec[str_sec.find(',') + 1:].ljust(3, '0')


# whsiper openai result
def write_result_to_file(res, path_to_text):
  file = open(path_to_text, 'w')
  text_massive = []
  segments = res['segments']
  for segment in segments:
    fract1 = str(round(segment['start'] % 1, 3))
    fract2 = str(round(segment['end'] % 1, 3))
    start_time = str(0) + str(timedelta(seconds=int(segment['start']))) + ',' + fract1[fract1.find('.') + 1:].ljust(3, '0')
    end_time = str(0) + str(timedelta(seconds=int(segment['end']))) + ',' + fract2[fract2.find('.') + 1:].ljust(3, '0')
    text = segment['text']
    id = segment['id']
    seg = f"{id + 1}\n{start_time} --> {end_time}\n{text[1:] if text and text[0] == ' ' else 'EMPTY' if text == '' else text}"
    text_massive.append(seg)
  file.write(text_massive[0] + '\n')
  for txt_str in text_massive[1:-1]:
    file.write('\n' + txt_str + '\n')
  file.write('\n' + text_massive[-1])
  file.close()


# faster-whisper result
def faster_result_to_file(segments, path_to_text, timestamps, path_to_words=None):
  file = open(path_to_text, 'w')
  text_massive = []
  if timestamps:
    word_massive = []
    index_shift = 0
  for segment in segments:
    fract1 = str(round(segment.start % 1, 3))
    fract2 = str(round(segment.end % 1, 3))
    start_time = str(0) + str(timedelta(seconds=int(segment.start))) + ',' + fract1[fract1.find('.') + 1:].ljust(3, '0')
    end_time = str(0) + str(timedelta(seconds=int(segment.end))) + ',' + fract2[fract2.find('.') + 1:].ljust(3, '0')
    text = segment.text
    id = segment.id
    seg = f"{id + 1}\n{start_time} --> {end_time}\n{text[1:] if text and text[0] == ' ' else 'EMPTY' if text == '' else text}"
    text_massive.append(seg)
    if timestamps:
      words = segment.words
      for idx, word in enumerate(words):
        fract1 = str(round(word.start % 1, 3))
        fract2 = str(round(word.end % 1, 3))
        start_time = str(0) + str(timedelta(seconds = int(word.start))) + ',' + fract1[fract1.find('.') + 1:].ljust(3, '0')
        end_time = str(0) + str(timedelta(seconds = int(word.end))) + ',' + fract1[fract1.find('.') + 1:].ljust(3, '0')
        text = word.word
        seg = f"{index_shift + idx + 1}\n{start_time} --> {end_time}\n{text[1:] if text and text[0] == ' ' else 'EMPTY' if text == '' else text}"
        word_massive.append(seg)
      index_shift += idx
  file.write(text_massive[0] + '\n')
  for txt_str in text_massive[1:-1]:
    file.write('\n' + txt_str + '\n')
  file.write('\n' + text_massive[-1])
  file.close()
  if timestamps:
    file = open(path_to_words, 'w')
    file.write(word_massive[0] + '\n')
    for txt_str in word_massive[1:-1]:
      file.write('\n' + txt_str + '\n')
    file.write('\n' + word_massive[-1])
    file.close()


# openai whisper
def write_words_to_file(res, path_to_text):
  file = open(path_to_text, 'w')
  text_massive = []
  segments = res['segments']
  index_shift = 0
  for segment in segments:
    words = segment['words']
    for idx, word in enumerate(words):
      fract1 = str(round(word['start'] % 1, 3))
      fract2 = str(round(word['end'] % 1, 3))
      start_time = str(0) + str(timedelta(seconds = int(word['start']))) + ',' + fract1[fract1.find('.') + 1:].ljust(3, '0')
      end_time = str(0) + str(timedelta(seconds = int(word['end']))) + ',' + fract1[fract1.find('.') + 1:].ljust(3, '0')
      text = word['word']
      seg = f"{index_shift + idx + 1}\n{start_time} --> {end_time}\n{text[1:] if text and text[0] == ' ' else 'EMPTY' if text == '' else text}"
      text_massive.append(seg)
    index_shift += idx
  file.write(text_massive[0] + '\n')
  for txt_str in text_massive[1:-1]:
    file.write('\n' + txt_str + '\n')
  file.write('\n' + text_massive[-1])
  file.close()


def check_punctuation_percent(path, lang, subtitles):
  punct = '.:!?,-—'
  ok = True
  punct_symbols = 0
  other_symbols = 0

  if not subtitles:
    with open(path, 'r') as txtfile:
      text = txtfile.read()
    for char in text:
      if char in punct:
        punct_symbols += 1
      else:
        other_symbols += 1
  else:
    with open(path, 'r') as txtfile:
      lines = [''] + txtfile.read().split('\n')
    for i in range(3, len(lines), 4):
      for char in lines[i]:
        if char in punct:
          punct_symbols += 1
        else:
          other_symbols += 1

  percent = punct_symbols / other_symbols * 100
  if lang == 'en':
    if percent < 1.3:
      ok = False
  elif lang == 'ru':
    if percent < 2:
      ok = False
  return ok


# важные глобальные переменные для нижеприведённых функций
part_1 = 12 # до какого символа первая часть тайминга (не включительно)
part_2 = 17 # с какого символа начинается вторая часть тайминга


# среднее время без использования меток слов
def compromise_time(time1, time2, s1, s2):
  coef = len(s1) / len(s1 + s2)
  return time_to_str(str_to_time(time1) + (str_to_time(time2) - str_to_time(time1)) * coef)


# восстановление временных меток по словам
def words_time(time1, time2, s1, s2, word_lines, last):
  time1_time = str_to_time(time1)
  time2_time = str_to_time(time2)
  space1 = s1.rfind(' ')
  space2 = s2.find(' ')
  word1 = s1[space1 + 1:] if space1 != -1 else s1
  word2 = s2[:space2] if space2 != -1 else s2
  # исключительный случай, в файле со словами они разделены
  if '-' in word1:
    word1 = s1[s1.rfind('-'):]
  if '-' in word2:
    word2 = s2[:s2.find('-')]
  print(word1)
  print(word2)

  new_end = 0
  new_start = 0

  for i in range(0, len(word_lines), 4):
    if i + 1 < len(word_lines):
      if word_lines[i+3] == word1 and word_lines[i+7] == word2:
        # проверка на принадлежность граничных слов данному сегменту
        start_2_word_time = str_to_time(word_lines[i+6][:part_1])
        if start_2_word_time > time1_time:
          end_1_word_time = str_to_time(word_lines[i+2][part_2:])
          # может быть случай, что конец первого слова будет позже начала второго, проверяем
          if end_1_word_time > start_2_word_time:
            start_1_word_time = str_to_time(word_lines[i+2][:part_1])
            new_end = start_1_word_time
          else:
            new_end = end_1_word_time
          new_start = start_2_word_time
          # обрезаем первоначальный массив до следующего сегмента
          # при условии, что эта часть преложения последняя
          if last:
              words_num = len(s2.split()) # подсчёт количества слов
              word_lines = word_lines[i + (words_num + 1) * 4:]
          break
        else:
          continue

  if not new_end:
    print('Возник исключительный случай. Скорее всего, попалось нестандартное слово!')
    print('Рекомендуется исправить вручную между ', time1, ' и ', time2)
    print('Временные метки заменены нулевыми.')

  return time_to_str(new_end), time_to_str(new_start), word_lines


def sep_segment(str, start, end, symbols, count, limit, word_lines=None):
  sent_array = [] # массив кортежей из таймингов и предложений
  buff1 = ""
  buff2 = ""
  last = False
  for i in range(count): # есть опасность дойти до конца
    index = min((str.find(char) for char in symbols if char in str)) #default=-1
    if i == count - 1: # отметить последнюю часть, на которую разделился сегмент
        last = True
    if index != len(str) - 1: # если не последним оказался знак препинания
      buff1 = str[:index + 1]
      buff2 = str[index + 2:]
      if word_lines:
        # используем файл со словами
        new_end, new_start, word_lines = words_time(start, end, buff1, buff2, word_lines, last)
      else:
        # рассчитываем промежуточную метку
        pass # позже это добавлю
      sent_array.append((start + ' --> ' + new_end, buff1)) # просто добавляем
      start = new_start
      str = buff2
    else:
      sent_array.append((new_start + ' --> ' + end, str)) # последнюю часть просто записываем
      str = ''
  # случай, когда сегмент не кончается знаком окончания
  if str:
      sent_array.append((new_start + ' --> ' + end, str))

  return sent_array


def replace_consecutive_punctuation(input_string):
    pattern = r'([!?.])\1+'
    replaced_string = re.sub(pattern, lambda x: x.group()[0], input_string)
    return replaced_string


# функция обработки всего файла с субтитрами
def process_text(file_path, max_sent_dur, word_lines=None):
    with open(file_path, 'r') as txtfile:
        lines = [''] + txtfile.read().split('\n')
        print(lines)

    new_lines = []
    current_sentence = ""
    symbols = '.!?'
    start_timing = ''

    id = 1

    for i in range(0, len(lines), 4):
      if i + 1 < len(lines):
        time_match = re.match(r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}', lines[i+2])
        text_match = re.match(r'.*[.?!]$', lines[i+3])

        # обработка, например, случая с многоточием и подобных, когда подряд несколько знаков пунктуации
        lines[i+3] = replace_consecutive_punctuation(lines[i+3])
        # Подсчёт знаков окончания предложения
        punct_ct = sum(lines[i+3].count(char) for char in symbols)

        if time_match:
          # первый случай
          if text_match and not start_timing: # целое предложение или потерянная часть предложения (не было начала)
              if punct_ct > 1:  # предложений в составе 2 и более
                  if str_to_time(lines[i+2][part_2:]) - str_to_time(lines[i+2][:part_1]) <= max_sent_dur:
                    new_lines.append('\n' + str(id) + '\n' + lines[i + 2] + '\n' + lines[i+3])  # просто добавляется
                    id += 1
                  else: # уже надо делить, так как не укладывается в продолжительность
                    sent_arr = sep_segment(lines[i+3], lines[i+2][:part_1], lines[i+2][part_2:], symbols, punct_ct,
                                           max_sent_dur, word_lines)
                    buff = ''
                    for timing, sentence in sent_arr:
                        if not buff:
                            buff = sentence
                            start_buff = timing[:part_1]
                            end_buff = timing[part_2:]
                            continue
                        if str_to_time(timing[part_2:]) - str_to_time(start_buff) <= max_sent_dur:
                            buff += ' ' + sentence
                            end_buff = timing[part_2:]
                        else:
                            new_lines.append('\n' + str(id) + '\n' + start_buff + ' --> ' + end_buff + '\n' + buff)
                            id += 1
                            buff = ''
                    if buff: # если после цикла осталось недобавленное предложение
                        new_lines.append('\n' + str(id) + '\n' + start_buff + ' --> ' + end_buff + '\n' + buff)
                        id += 1
              else: # только одно предложение
                  new_lines.append('\n' + str(id) + '\n' + lines[i+2] + '\n' + lines[i+3])  # просто добавляется
                  id += 1

          # второй случай - концовка, которую нужно добавить
          elif text_match and start_timing:
              # проверка на то, что мы можем прибавить - будет нормально по времени
              if str_to_time(lines[i+2][part_2:]) - str_to_time(start_timing) <= max_sent_dur:
                  new_lines.append('\n' + str(id) + '\n' + start_timing + ' --> ' + lines[i + 2][part_2:] + '\n' +
                                   current_sentence + ' ' + lines[i+3])
                  id += 1
              else:
                  if punct_ct > 1:
                      sent_arr = sep_segment(lines[i + 3], lines[i + 2][:part_1], lines[i + 2][part_2:], symbols,
                                             punct_ct, max_sent_dur, word_lines)
                      end_buff = lines[i-2][part_2:]  # время конца предыдущего сегмента
                      for timing, sentence in sent_arr:
                          if not current_sentence:
                              current_sentence = sentence
                              start_timing = timing[:part_1]
                              end_buff = timing[part_2:]
                              continue
                          if str_to_time(timing[part_2:]) - str_to_time(start_timing) <= max_sent_dur:
                              current_sentence += ' ' + sentence
                              end_buff = timing[part_2:]
                          else:
                              new_lines.append(
                                  '\n' + str(id) + '\n' + start_timing + ' --> ' + end_buff + '\n' + current_sentence)
                              id += 1
                              current_sentence = ''
                              start_timing = ''
                      if current_sentence:  # если после цикла осталось недобавленное предложение
                          new_lines.append('\n' + str(id) + '\n' + start_timing + ' --> ' + end_buff + '\n' +
                                           current_sentence)
                          id += 1
                  else:
                      new_lines.append('\n' + str(id) + '\n' + start_timing + ' --> ' +
                                       lines[i-2][part_2:] + '\n' + current_sentence)  # добавляем предыдущие части
                      id += 1
                      # добавляем эту часть
                      new_lines.append('\n' + str(id) + '\n' + lines[i+2][:part_1] + ' --> ' + lines[i+2][part_2:] +
                                       '\n' + lines[i+3])
              current_sentence = ''
              start_timing = ''

          # третий случай - средняя часть, которую нужно добавить
          elif start_timing:
              if punct_ct > 0:
                  # делим на отдельные предложения / части
                  sent_arr = sep_segment(lines[i + 3], lines[i + 2][:part_1], lines[i + 2][part_2:], symbols, punct_ct,
                                         max_sent_dur, word_lines)
                  #print(sent_arr)
                  # проверяем первую завершающую часть
                  if str_to_time(sent_arr[0][0][part_2:]) - str_to_time(start_timing) <= max_sent_dur:
                      new_lines.append('\n' + str(id) + '\n' + start_timing + ' --> ' + sent_arr[0][0][part_2:] + '\n'
                                       + current_sentence + ' ' + sent_arr[0][1])
                      id += 1
                  else:
                      new_lines.append('\n' + str(id) + '\n' + start_timing + ' --> ' + lines[i-2][part_2:] + '\n'
                                       + current_sentence)
                      new_lines.append('\n' + str(id + 1) + '\n' + sent_arr[0][0] + '\n' + sent_arr[0][1])
                      id += 2
                  sent_arr.pop(0)  # из списка предложений удаляем эту часть
                  current_sentence = ''
                  start_timing = ''
                  # далее обрабатываем оставшиеся, последнее считается за отдельный случай
                  if len(sent_arr) > 1: # если осталось больше 1 части
                      for timing, sentence in sent_arr[:-1]:
                          if not current_sentence:
                              current_sentence = sentence
                              start_timing = timing[:part_1]
                              end_buff = timing[part_2:]
                              continue
                          if str_to_time(timing[part_2:]) - str_to_time(start_timing) <= max_sent_dur:
                              current_sentence += ' ' + sentence
                              end_buff = timing[part_2:]
                          else:
                              new_lines.append('\n' + str(id) + '\n' + start_timing + ' --> ' + end_buff + '\n' +
                                               current_sentence)
                              id += 1
                              current_sentence = ''
                              start_timing = ''
                      if current_sentence:  # если после цикла осталось недобавленное предложение
                          new_lines.append('\n' + str(id) + '\n' + start_timing + ' --> ' + end_buff + '\n' +
                                           current_sentence)
                          id += 1
                  # берём как начальный фрагмент
                  current_sentence = sent_arr[-1][1]
                  start_timing = sent_arr[-1][0][:part_1]
              else:
                  if str_to_time(lines[i+2][part_2:]) - str_to_time(start_timing) <= max_sent_dur:
                      current_sentence += ' ' + lines[i+3]
                  else:  # но фраза оказазалась длиннее, чем надо => не можем добавить
                      new_lines.append('\n' + str(id) + '\n' + start_timing + ' --> ' +
                                       lines[i-2][part_2:] + '\n' + current_sentence)  # добавляем предыдущие части
                      id += 1
                      # Будем прибавлять к текущему сегменту последующие
                      start_timing = lines[i+2][:part_1]
                      current_sentence = lines[i+3]

          # последний случай - возможно, начало предложения
          else:
              if punct_ct > 0:  # если есть хотя бы 1 такой символ
                  sent_arr = sep_segment(lines[i+3], lines[i+2][:part_1], lines[i+2][part_2:], symbols, punct_ct,
                                         max_sent_dur, word_lines)
                  buff = ''
                  for timing, sentence in sent_arr:
                      if not buff:
                          buff = sentence
                          start_buff = timing[:part_1]
                          end_buff = timing[part_2:]
                          continue
                      if str_to_time(timing[part_2:]) - str_to_time(start_buff) <= max_sent_dur and (sentence.endswith('.') or sentence.endswith('!') or sentence.endswith('?')):
                          buff += ' ' + sentence
                          end_buff = timing[part_2:]
                      else:
                          new_lines.append('\n' + str(id) + '\n' + start_buff + ' --> ' + end_buff + '\n' + buff)
                          id += 1
                          buff = ''
                  if buff:  # если после цикла осталось недобавленное предложение
                      new_lines.append('\n' + str(id) + '\n' + start_buff + ' --> ' + end_buff + '\n' + buff)
                      id += 1
                  current_sentence = sent_arr[-1][1]
                  start_timing = sent_arr[-1][0][:part_1]  # первая часть тайминга из кортежа
              else:
                  start_timing = lines[i+2][:part_1]  # начало тайминга, ожидается добавление
                  current_sentence = lines[i+3]

    return new_lines


def correct_timings(path_to_text):
    txt_file = open(path_to_text, 'r')
    lines = [''] + txt_file.read().split('\n')
    txt_file.close()

    for i in range(len(lines)):
        if i % 4 == 1:
            lines[i] = str(int(i / 4 + 1))
    txt_file = open(path_to_text, 'w')
    for line in lines[1:-1]:
        txt_file.write(line + '\n')
    txt_file.write(lines[-1])
    txt_file.close()