import os

import psycopg2
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

    return render_template(
        '/url_info.html',
        url=result[0],
        messages=get_flashed_messages(with_categories=True),
    )


@app.get('/urls')
def show_urls():
    conn = connect()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT *
        FROM urls
        ORDER BY created_at DESC
        """,
                   )
    urls = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('/urls.html', urls=urls)
