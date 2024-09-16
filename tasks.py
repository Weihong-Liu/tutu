import time
import pytz
from celery import Celery
from celery.schedules import crontab
from datetime import datetime, timedelta

from tools import (
    load_session_data, 
    store_session_data,
    reserve_seat, 
    reserve_cancel, 
    keep_session, 
    get_index_data, 
    get_often_seat, 
    check_in
)
import constants


app = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

# 其他配置（可选）
app.conf.timezone = 'Asia/Shanghai'
app.conf.enable_utc = False

# 定义上海时区
shanghai_tz = pytz.timezone('Asia/Shanghai')


app.conf.beat_schedule = {
    'keep-session-alive-every-2-minutes': {
        'task': 'tasks.keep_session_alive',
        'schedule': 120.0,  # 每 2 分钟执行一次
        'args': ('user_session_key',)
    },
}


@app.task
def keep_session_alive(session_key):
    session = load_session_data(session_key)
    if session:
        try:
            res = session.post(constants.URL, json=constants.KEEP_SESSION_BODY)
            result = res.json()
            if result.get("errors"):
                print("Session expired.")
            else:
                print("Session is active.")
                # 更新会话数据
                store_session_data(session_key, session)
        except Exception as e:
            print(f"Error keeping session alive: {e}")
    else:
        print("No session data found.")



@app.task
def start_reservation_task(session_key):
    session = load_session_data(session_key)
    if not session:
        print("Session expired or not found.")
        return
    # 预约座位逻辑
    success = True#reserve_seat(session)
    if success:
        print("座位预约成功！")
        # 调度下一步任务
         # 获取当前时间
        now = datetime.now(shanghai_tz)
        # 计算第二天的 8:49
        next_day = now + timedelta(days=1)  # 增加一天
        deadline = next_day.replace(hour=8, minute=49, second=0, microsecond=0)
        reserve_and_check_in_task.apply_async((session_key,), eta=deadline)
    else:
        print("预约座位失败，请稍后重试。")



@app.task
def reserve_and_check_in_task(session_key):
    """
    任务：在 8:49 取消预约并重新预约，如果签到成功任务结束，未签到则重新预约并循环检查签到。
    """
    session = load_session_data(session_key)
    if not session:
        print("Session expired or not found.")
        return

    # 检查是否已经签到
    if check_in(session):
        print("签到成功！任务结束。")
        return  # 签到成功，任务终止

    # 没有签到，取消预约并重新预约
    print("尚未签到，取消当前预约并重新预约。")
    success_cancel = reserve_cancel(session)
    if success_cancel:
        print("当前预约已取消，正在重新预约...")

        index_data = get_index_data(session)
        often_seat = get_often_seat(index_data)
        success_reserve = reserve_seat(session, often_seat)
        if success_reserve:
            print("重新预约成功！")
            # 记录当前预约的时间，调度 1 小时 - 1 分钟后的签到检查任务
            reservation_time = datetime.now(shanghai_tz)
            check_in_deadline = reservation_time + timedelta(hours=1, minutes=-1) 
            check_in_task.apply_async((session_key, reservation_time), eta=check_in_deadline)
        else:
            print("重新预约失败，请稍后重试。")
    else:
        print("取消预约失败，请稍后重试。")


@app.task
def check_in_task(session_key, reservation_time):
    """
    任务：检查是否签到，如果未签到则取消当前预约并重新预约，直到签到成功为止。
    """
    session = load_session_data(session_key)
    if not session:
        print("Session expired or not found.")
        return

    # 检查是否已签到
    if check_in(session):
        print("签到成功！任务结束。")
        return  # 任务结束

    # 如果还没有签到，重新预约
    print(f"未在 {reservation_time + timedelta(hours=1)} 前签到，重新预约中...")
    reserve_and_check_in_task.apply_async((session_key,), countdown=5)