import os

from bs4 import BeautifulSoup
import psycopg2
import requests
from flask import (
    Flask,
    render_template,
    url_for,
    redirect,
    request,
    flash,
    get_flashed_messages
)
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from validators import url as validate_url

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')


def connect():
    return psycopg2.connect(DATABASE_URL)


@app.route('/')
def index():
    return render_template(
        'index.html',
        messages=get_flashed_messages(with_categories=True)
    )


@app.post('/urls')
def add_url():
    form_input = request.form.to_dict()
    url = form_input.get('url')
    if not validate_url(url):
        flash('Некорректный URL', 'attention')
        return render_template(
            'index.html',
            url=form_input,
            messages=get_flashed_messages(with_categories=True)
        ), 422
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id FROM urls WHERE urls.name = %s LIMIT 1',
        (url,),
    )
    result = cursor.fetchall()
    if not result:
        cursor.execute('INSERT INTO urls (name) VALUES (%s)', (url,))
        conn.commit()
        flash('Страница успешно добавлена', 'success')

        cursor.execute(
            'SELECT id FROM urls WHERE urls.name = %s LIMIT 1',
            (url,),
        )
        url_id = cursor.fetchall()[0][0]
        cursor.close()
        conn.close()
    else:
        flash('Страница уже существует', 'info')
        conn.close()
        url_id = result[0][0]
    return redirect(url_for('show_url', url_id=url_id))


@app.get('/urls/<int:url_id>')
def show_url(url_id):
    conn = connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
                    SELECT
                        id, name, created_at::date
                        FROM urls
                        WHERE urls.id = %s
                        LIMIT 1""",
                   (url_id,)
                   )
    result = cursor.fetchall()
    if not result:
        cursor.close()
        conn.close()
        return render_template('/404.html'), 404

    cursor.execute("""
                    SELECT
                        id, status_code, h1, title,
                        description, created_at::date
                    FROM url_checks
                    WHERE url_checks.url_id = %s
                    ORDER BY id DESC;
                    """,
                   (url_id,)
                   )
    checks = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template(
        '/url_info.html',
        url=result[0],
        checks=checks,
        messages=get_flashed_messages(with_categories=True),
    )


@app.get('/urls')
def show_urls():
    conn = connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT
            urls.id,
            urls.name,
            coalesce(checks.created_at::date::text, '') as created_at,
            coalesce(checks.status_code::text, '') as status_code
        FROM urls
        LEFT JOIN (
            SELECT
                url_id,
                created_at,
                status_code
                FROM url_checks
                ) as checks
            ON urls.id = checks.url_id
            AND checks.created_at =
                (SELECT MAX(created_at) FROM url_checks
            WHERE url_id = urls.id)
        ORDER BY urls.created_at DESC
        """,
                   )
    urls = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('/urls.html', urls=urls)


@app.post('/urls/<int:url_id>/checks')
def check_url(url_id):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM urls WHERE id = %s LIMIT 1', (url_id,))
    url_for_check = cursor.fetchall()[0][0]
    try:
        response = requests.get(url_for_check)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        conn.close()
        flash('произошла ошибка при проверке', 'danger')
        return redirect(url_for('show_url', url_id=url_id))

    status_code = response.status_code
    parsed_page = BeautifulSoup(response.text, 'html.parser')
    title = parsed_page.title.text if parsed_page.find('title') else ''
    h1 = parsed_page.h1.text if parsed_page.find('h1') else ''
    description = parsed_page.find('meta', attrs={'name': 'description'})
    description = description.get('content') if description else ''

    cursor.execute("""
        INSERT INTO url_checks
            (url_id, status_code, title, h1, description)
        VALUES (%s, %s, %s, %s, %s)
        """,
                   (url_id, status_code, title, h1, description),
                   )
    conn.commit()
    conn.close()
    flash('Страница успешно проверена', 'success')
    return redirect(url_for('show_url', url_id=url_id))
