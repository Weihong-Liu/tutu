import os
import pytz
from flask import Flask, render_template, request, redirect, url_for, flash
from tasks import start_reservation_task, keep_session_alive
from datetime import datetime, timedelta
from tools import get_code, get_cookie_string, get_session, store_session_data

app = Flask(__name__)
app.secret_key = os.urandom(24)

shanghai_tz = pytz.timezone('Asia/Shanghai')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit_url', methods=['POST'])
def submit_url():
    url = request.form['url']
    try:
        code = get_code(url)
        cookie_string = get_cookie_string(code)
        print(cookie_string)
        session = get_session(cookie_string)
        session_key = 'user_session_key'  # 可以根据用户唯一标识生成
        store_session_data(session_key, session)
        cookie_key = 'cookie_string'
        store_session_data(cookie_key, cookie_string)
        # 启动保持会话活跃的任务
        keep_session_alive.apply_async(args=(session_key,))
        # 启动预约任务
        now = datetime.now(shanghai_tz)
        deadline = now.replace(hour=22, minute=0, second=0, microsecond=0)
        start_reservation_task.apply_async((session_key,), )#eta=deadline
        flash('URL提交成功，座位预约将按计划开始。', 'success')
    except Exception as e:
        flash(f'处理URL时发生错误: {e}', 'danger')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)