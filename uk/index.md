---
title: "R3el: впорядкування фільмів і серіалів"
author_profile: true
layout: single
lang: uk
locale: uk
language_name: Українська
translation_key: r3el-home
permalink: /uk/
---

![Головна сторінка каталогу R3el](/pages/images/main-page.uk.svg)

**R3el** використовує локально розміщену [велику мовну модель (LLM)](https://uk.wikipedia.org/wiki/Велика_мовна_модель), щоб упорядковувати файли з фільмами та серіалами.

Я використав штучний інтелект, щоб зіставити велику колекцію медіафайлів і каталогів із записами [The Movie Database (TMDB)](https://www.themoviedb.org/). Після цього R3el завантажує постери, інформацію про акторів, епізоди та інші метадані у власну базу даних. Для перегляду й пошуку я створив вебінтерфейс.

Архітектура та код проєкту спираються на мій [проєкт Ax3l](https://ax3l.osoyalce.com/).

![Архітектура R3el](/pages/images/architecture.uk.svg)

## Пакетна обробка

- [Схеми пакетної обробки й окремих файлів](/uk/pages/flowchart/) — обробка пакета та ідентифікація елементів.
- [Імпорт серіалів](/uk/pages/tv-shows/) — визначення серіалів, відповідність епізодів і каталоги призначення.
- [Шаблони каталогів](/uk/pages/directory-patterns/) — фільми з двох частин, окремі фільми з датами та субтитри SRT.
- [Імпорт і очищення джерела](/uk/pages/import-cleanup/) — переміщення, транзакції, конфлікти та очищення.
- [Поведінка під час роботи](/uk/pages/runtime-behaviour/) — запуск, зупинка й завершення пакетів.

## Використання та адміністрування R3el

- [Керування, каталог і журнал подій](/uk/pages/control-server/)
- [Сервер ідентифікації та встановлення](/uk/pages/one-batch-identification/)
- [Оголошення CMDB і конфігурація](/uk/pages/configuration/)
- [Імена файлів і пріоритет форматів](/uk/pages/file-naming/)

## Технічна документація

- [Постійна робоча область і стани](/uk/pages/file-states/)
- [Схема каталогу](/uk/pages/schema/)
- [Повідомлення ZeroMQ](/uk/pages/zmq-messages/)
- [Правила розробки](/uk/pages/coding-guidelines/)

## Інформація про проєкт

- [README українською](/uk/pages/readme/)
- [CHANGELOG (англійською)](/changelog/)
- [Інструкції для агентів українською](/uk/pages/agents/)

<footer style="margin-top: 3rem; text-align: center; font-size: 0.75em;">
  На основі даних <a href="https://www.themoviedb.org/"><img src="{{ '/pages/images/tmdb.svg' | relative_url }}" alt="TMDB" width="100" style="vertical-align: middle;"></a>
</footer>
