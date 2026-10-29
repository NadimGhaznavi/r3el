---
title: "Імена файлів"
author_profile: true
layout: single
lang: uk
locale: uk
language_name: Українська
translation_key: r3el-file-naming
permalink: /uk/pages/file-naming/
---

[До змісту документації](/uk/)

Кореневим каталогом є вихідний каталог пакета. Кожен визначений фільм отримує папку `Title (Year)` відповідно до правил нормалізації нижче. Відеофайл має таке саме ім'я та початкове розширення. Наприклад, для вихідного каталогу `/exports/disk1/archive/media/movies`:

```text
/exports/disk1/archive/media/movies/Title (2020)/Title (2020).mkv
```

Постери й фонові зображення завантажуються в цю папку та згадуються в каталозі. Назву й рік фільму беруть із прийнятого запису TMDB.

Стандартний вихідний каталог — `/exports/disk1/archive/media/movies`. Для фільму з двох частин використовуються імена `Title (Year) Part 1.ext` та `Title (Year) Part 2.ext`. Відповідні субтитри SRT мають основу назви відео, наприклад `Title (Year) Part 1.srt`. Файли переміщуються в межах однієї файлової системи без копіювання вмісту. Дивіться [імпорт і очищення](/uk/pages/import-cleanup/).

Якщо одному фільму TMDB відповідають декілька форматів, залишається перший доступний у такому порядку пріоритетності: `mkv`, `mp4`, `m4v`, `avi`, `mov`, `wmv`, `flv`, `mpg`/`mpeg`. Регістр розширення не враховується; `mpg` і `mpeg` мають однаковий пріоритет, і при рівності перемагає вже зареєстрована копія. Це перевага **контейнера**, а не оцінка роздільної здатності чи якості кодування.

Після збереження кращого відео версії з нижчим пріоритетом видаляються, а їхні зв'язки з каталогом прибираються. Це стосується і кращого формату, що надійшов у пізнішому пакеті. Очищення має контрольні точки для повторних спроб і реєструється як File / Delete. Для файлів з однаковим розширенням діє звичайний захист від колізій; політика форматів не видаляє їх автоматично.

Наведена нижче функція Python нормалізує назву файлу. Коментарі залишено в оригіналі, щоб приклад можна було скопіювати без змін.

```python
import re
import unicodedata


def movie_filename(title: str, year: int, extension: str) -> str:
    title = unicodedata.normalize("NFKC", title)

    replacements = {
        ":": " - ",
        "/": " - ",
        "\\": " - ",
        "#": "",
        "%": " percent ",
        '"': "",
        "*": "",
        "?": "",
        "<": "",
        ">": "",
        "|": "",
    }

    for old, new in replacements.items():
        title = title.replace(old, new)

    # Normalize curly apostrophes/quotes.
    title = title.replace("’", "'")
    title = title.replace("‘", "'")
    title = title.replace("“", "")
    title = title.replace("”", "")

    # Collapse whitespace and tidy separators.
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"\s*-\s*", " - ", title)
    title = title.strip(" .-")

    extension = extension.lstrip(".")

    return f"{title} ({year}).{extension}"
```
