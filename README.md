# Система автоматизации производственного процесса обслуживания и учета газовых баллонов

Запускаем проект на своей машине: 

1. Клонируем репозиторий `git clone https://github.com/AvectisDev/PinskGNS.git`
2. Переходим в папку с проектом `cd GNS` (здесь и далее приводятся команды в терминале на машине под windows)
3. Устанавливаем виртуальное окружение `python -m venv env`
4. Запускаем виртуальное окружение `source env/Scripts/activate`
5. Обновляем pip `python -m pip install --upgrade pip`
6. Устанавливаем в виртуальном окружении зависимости для проекта `python -m pip install --no-cache-dir -r requirements.txt`
7. Делаем миграции для создания базы данных `python manage.py makemigrations && python manage.py migrate`
8. Заполняем данными модели `Capital` и `auth.user` &mdash; `python manage.py loaddata db.json`
9. Запускаем локальный сервер `python manage.py runserver`
10. По адресу `http://localhost:8000` будет доступна главная страница с архивом баллонов.
11. По адресу `http://localhost:8000/api/swagger` будет доступно описание API для проекта.
