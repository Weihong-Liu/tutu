import os
from flask import Flask, render_template, request, redirect, url_for, flash
from tasks import start_reservation_task, keep_session_alive
from datetime import datetime, timedelta
from tools import get_code, get_cookie_string, get_session, store_session_data

app = Flask(__name__)
app.secret_key = os.urandom(24)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit_url', methods=['POST'])
def submit_url():
    url = request.form['url']
    try:
        # code = get_code(url)
        cookie_string = "Authorization=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJ1c2VySWQiOjQyOTI4NTExLCJzY2hJZCI6MjAwMDAsImV4cGlyZUF0IjoxNzI2NDgyNjM4LCJ0YWciOiJjb29raWUifQ.YRXR4dCzTTjp841Y00rkeXp6cRd6_me5rDW_PuHVOfScMhyh2QEXL-weMz45YGjJOQqrXkI5TRJOmzzazVdu_fTkl3C2oClAgKMjKty2Ta0RHcEXZ1G8bHGw4DmbIoxmfH3XRb1tkvOzC9gfzHvJroszSi8sMaDOMFMAFgyfZUo5LEisbTap7ImlLjSMxEzGvwp6s4128LcKfg3sBsx3HCAbbNun1A4lXwD_Ns0UbPCxztRkrXAArrho0L3e5Qp2ZoGvmDAeMQAjEK9BV7NCY_7DKsRleirMAUnRjeOqk3lePbEtrsjAcySiqIaOTh7VfPL0iwQLmOQ9S7814RvJQA; SERVERID=82967fec9605fac9a28c437e2a3ef1a4|1726475438|1726475438; SERVERID=d3936289adfff6c3874a2579058ac651|1726475438|1726475438"#get_cookie_string(code)
        print(cookie_string)
        session = get_session(cookie_string)
        session_key = 'user_session_key'  # 可以根据用户唯一标识生成
        store_session_data(session_key, session)
        # 启动保持会话活跃的任务
        keep_session_alive.apply_async(args=(session_key,))
        # 启动预约任务
        print(datetime.now())
        start_reservation_task.apply_async((session_key,), )#eta=datetime.now().replace(hour=16, minute=35, second=0)
        flash('URL提交成功，座位预约将按计划开始。', 'success')
    except Exception as e:
        flash(f'处理URL时发生错误: {e}', 'danger')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)