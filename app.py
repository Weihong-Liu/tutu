import os
from flask import Flask, render_template, request, redirect, url_for, flash
from tasks import start_reservation_task
from datetime import datetime, timedelta
from tools import get_code, get_cookie_string

app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit_url', methods=['POST'])
def submit_url():
    url = request.form['url']
    try:
        code = get_code(url)
        cookie_string = get_cookie_string(code)
        # 调用 Celery 任务开始预约流程
        print(cookie_string)
        start_reservation_task.apply_async((cookie_string,))#, eta=datetime.now().replace(hour=16, minute=52, second=0)
        flash('URL submitted successfully, seat reservation will start as scheduled.', 'success')
    except Exception as e:
        flash(f'Error processing URL: {e}', 'danger')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)