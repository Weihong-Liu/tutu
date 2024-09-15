from celery import Celery
from datetime import datetime, timedelta
from tools import get_session, reserve_seat, reserve_cancel, keep_session, check_in
import time

# 配置 Celery
app = Celery('tasks', broker='redis://localhost:6379/0')

@app.task
def start_reservation_task(cookie_string):
    """
    任务：前一天晚上 22:00 预约座位，并在第二天 8:49 调度重新预约或签到检查任务。
    """
    session = get_session(cookie_string)

    # 保持 session 的活跃
    keep_session(session)

    # 预约座位逻辑
    success = reserve_seat(session)
    if success:
        print("前一天晚上 22:00 座位预约成功！")
        # 调度第二天早上 8:49 检查是否签到或重新预约
        reserve_and_check_in_task.apply_async((cookie_string,), eta=datetime.now().replace(hour=17, minute=3, second=0))
    else:
        print("预约座位失败，请稍后重试。")


@app.task
def reserve_and_check_in_task(cookie_string):
    """
    任务：在 8:49 取消预约并重新预约，如果签到成功任务结束，未签到则重新预约并循环检查签到。
    """
    session = get_session(cookie_string)

    # 保持 session 的活跃
    keep_session(session)

    # 检查是否已经签到
    if check_in(session):
        print("签到成功！任务结束。")
        return  # 签到成功，任务终止

    # 没有签到，取消预约并重新预约
    print("尚未签到，取消当前预约并重新预约。")
    success_cancel = reserve_cancel(session)
    if success_cancel:
        print("当前预约已取消，正在重新预约...")
        success_reserve = reserve_seat(session)
        if success_reserve:
            print("重新预约成功！")
            # 记录当前预约的时间，调度 1 小时 - 1 分钟后的签到检查任务
            reservation_time = datetime.now()
            check_in_deadline = reservation_time + timedelta(minutes=1)#hours=1, minutes=-1
            check_in_task.apply_async((cookie_string, reservation_time), eta=check_in_deadline)
        else:
            print("重新预约失败，请稍后重试。")
    else:
        print("取消预约失败，请稍后重试。")


@app.task
def check_in_task(cookie_string, reservation_time):
    """
    任务：检查是否签到，如果未签到则取消当前预约并重新预约，直到签到成功为止。
    """
    session = get_session(cookie_string)

    # 保持 session 的活跃
    keep_session(session)

    # 检查是否已签到
    if check_in(session):
        print("签到成功！任务结束。")
        return  # 任务结束

    # 如果还没有签到，重新预约
    print(f"未在 {reservation_time + timedelta(hours=1)} 前签到，重新预约中...")
    reserve_and_check_in_task.apply_async((cookie_string,), countdown=60)