from tools import *

def check_in(session):
    # 座位签到，未实现
    return False

def main(url):
    cookie_string = get_cookie_string(get_code(url))
    # 将cookie_string提交到celery中
    session = get_session(cookie_string)
    while True:
        # 获取首页数据
        index_data = get_index_data(session)
        often_seat = get_often_seat(index_data)
        # get_often_seat_status(often_seat)
        if reserve_seat(session, often_seat):
            print("预约成功")
        else:
            print("预约失败")
        
        keep_session(session, minute=50)
        # 如果没签到
        if not check_in(session):
            reserve_cancel(session)
            # 重新预约
            index_data = get_index_data(session)
            often_seat = get_often_seat(index_data)
            reserve_seat(session, often_seat)
        else:
            break
