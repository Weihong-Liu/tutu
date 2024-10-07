import http.cookies
import requests
import json
import time
import urllib.request
import urllib.parse
import http.cookiejar
import copy
import threading
from loguru import logger
import pickle
import redis
import websocket

import constants


redis_client = redis.Redis(host='localhost', port=6379, db=0)


def store_cookie_str(key, value):
    redis_client.set(key, value)


def load_cookie_str(key):
    return redis_client.get(key).decode()


def store_session_data(session_key, session):
    session_data = pickle.dumps(session.cookies)
    redis_client.set(session_key, session_data)


def load_session_data(session_key):
    session_data = redis_client.get(session_key)
    if session_data:
        cookies = pickle.loads(session_data)
        session = requests.Session()
        session.cookies.update(cookies)
        return session
    else:
        return None


def get_code(url):
    """
    从 URL 中提取 code 参数

    @param url: 包含 code 参数的 URL
    @type url: str
    @return: 提取到的 code
    @rtype: str
    @raise ValueError: 当 URL 中不包含 code 参数时抛出异常
    """
    logger.info(f"Parsing code from URL: {url}")
    query = urllib.parse.urlparse(url).query
    codes = urllib.parse.parse_qs(query).get('code')
    if codes:
        logger.info("Code found.")
        return codes.pop()
    else:
        logger.error("Code not found in URL")
        raise ValueError("Code not found in URL")


def get_cookie_string(code):
    """
    使用提供的 code 获取 cookie 字符串

    @param code: 从 URL 中提取的 code
    @type code: str
    @return: 获取的 cookie 字符串
    @rtype: str
    """
    logger.info(f"Getting cookie string with code: {code}")
    cookiejar = http.cookiejar.MozillaCookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookiejar))
    response = opener.open(
        "http://wechat.v2.traceint.com/index.php/urlNew/auth.html?" + urllib.parse.urlencode({
            "r": "https://web.traceint.com/web/index.html",
            "code": code,
            "state": 1
        })
    )
    cookie_items = []
    for cookie in cookiejar:
        cookie_items.append(f"{cookie.name}={cookie.value}")
    cookie_string = '; '.join(cookie_items)
    logger.info("Cookie string obtained.")
    return cookie_string


def main():
    """
    主程序，获取 URL 并从中提取 code，随后获取 cookie 字符串并输出
    """
    url = input("Please enter the URL: ")
    try:
        code = get_code(url)
        cookie_string = get_cookie_string(code)
        logger.info("Cookie string successfully retrieved.")
        print("\nCookie string: \n")
        print(cookie_string)
    except Exception as e:
        logger.error(f"An error occurred in main: {e}")


def get_session(cookie_string):
    """
    使用 cookie 字符串创建会话

    @param cookie_string: 从 get_cookie_string 返回的 cookie 字符串
    @type cookie_string: str
    @return: 包含设置好的 cookies 的 requests 会话
    @rtype: requests.Session
    """
    logger.info("Creating session from cookie string.")
    session = requests.Session()
    cookie = http.cookies.SimpleCookie()
    cookie.load(cookie_string)
    for key, morsel in cookie.items():
        session.cookies.set(key, morsel)
    logger.info("Session created.")
    return session


def check_session_status(session):
    """
    检查当前 session 的状态，如果 session 失效则返回 False, 否则返回 True。

    @param session: 当前的 requests.Session 会话
    @type session: requests.Session
    @return: True 表示 session 有效，False 表示 session 失效
    @rtype: bool
    """
    try:
        logger.info("Checking session status.")
        response = session.post(constants.URL, json=constants.KEEP_SESSION_BODY)
        response_data = response.json()
        if response_data.get("errors") and response_data["errors"][0].get("code") != 0:
            logger.warning("Session expired!")
            return False
        logger.info("Session is active.")
        return True
    except json.decoder.JSONDecodeError as e:
        logger.error(f"JSON Decode Error: {e}")
        return False
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return False



def keep_session_by_minute(session, minute=50):
    start_time = time.time()  # 记录开始时间
    max_duration = minute * 60  # 最大运行时长，单位为秒
    
    while time.time() - start_time < max_duration:
        logger.info("Keeping session alive.")
        if len(session.cookies.keys()) > 1 and "Authorization" in session.cookies.keys():
            session.cookies.set("Authorization", domain="", value=None)
        res = session.post(constants.URL, json=constants.KEEP_SESSION_BODY)
        try:
            result = res.json()
        except json.decoder.JSONDecodeError as err:
            logger.error(f"JSON Decode Error: {err}")
            break  # 发生 JSON 解析错误时退出循环
        if result.get("errors") and result.get("errors")[0].get("code") != 0:
            logger.warning("Session expired!")
            break  # Session 失效时退出循环
        logger.info("Session OK.")
        time.sleep(60)  # 每 60 秒执行一次，防止过度请求
    
    logger.info("Session keeping ended after specified time.")


def keep_session(session):
    """
    保持登录状态，防止 session 过期。在一个独立的线程中运行。
    """
    def run_keep_session():
        while True:
            logger.info("Keeping session alive.")
            if len(session.cookies.keys()) > 1 and "Authorization" in session.cookies.keys():
                session.cookies.set("Authorization", domain="", value=None)
            res = session.post(constants.URL, json=constants.KEEP_SESSION_BODY)
            try:
                result = res.json()
            except json.decoder.JSONDecodeError as err:
                logger.error(f"JSON Decode Error: {err}")
                break  # 发生 JSON 解析错误时退出循环
            if result.get("errors") and result.get("errors")[0].get("code") != 0:
                logger.warning("Session expired!")
                break  # Session 失效时退出循环
            logger.info("Session OK.")
            time.sleep(60 * 2)  # 每 120 秒执行一次，防止过度请求

    # 启动线程来保持 session
    keep_session_thread = threading.Thread(target=run_keep_session)
    keep_session_thread.daemon = True  # 设置为守护线程，主线程结束时它会自动结束
    keep_session_thread.start()



def get_index_data(session):
    """
    获取首页数据

    @param session: 当前的 requests.Session 会话
    @type session: requests.Session
    @return: 返回首页数据
    @rtype: dict 或 None
    """
    logger.info("Fetching index data.")
    if check_session_status(session):
        res = session.post(constants.URL, json=constants.INDEX_BODY)
        try:
            result = res.json()
        except json.decoder.JSONDecodeError as err:
            logger.error(f"Error fetching index data: {err}")
            return None
        if result.get("errors") and result.get("errors")[0].get("code") != 0:
            logger.warning("Failed to get index data!")
            return None
        logger.info("Index data retrieved successfully.")
        return result


def get_resverve_stoken(index_data):
    """
    获取预约座位的 stoken

    @param index_data: get_index_data 返回的结果
    @type index_data: dict
    @return: 获取的 stoken
    @rtype: str
    """
    logger.info("Getting reservation token (stoken).")
    return index_data['data']['userAuth']['reserve']['getSToken']


def get_often_seat(index_data, index=0):
    """
    获取常用座位信息

    @param index_data: get_index_data 返回的结果
    @type index_data: dict
    @param index: 常用座位的索引，默认第一个
    @type index: int
    @return: 常用座位信息
    @rtype: dict
    """
    logger.info(f"Fetching often used seat at index {index}.")
    return index_data["data"]["userAuth"]["oftenseat"]["list"][index]


def get_often_seat_status(often_seat):
    """
    获取常用座位信息状态

    @param index_data: get_often_seat 返回的结果
    @type index_data: dict
    @return: True 表示有空位，False 表示无空位
    @rtype: bool
    """
    return False if often_seat["status"] else True


def reserve_seat(session, seat):
    """
    预约座位

    @param session: 当前的 requests.Session 会话
    @type session: requests.Session
    @param seat: 要预约的座位信息
    @type seat: dict
    @return: True 表示预约成功，False 表示预约失败
    @rtype: bool
    """
    logger.info("Reserving seat.")
    if check_session_status(session) and get_often_seat_status(seat):
        reserve_seat_body = copy.deepcopy(constants.RESERVE_SEAT_BODY)
        reserve_seat_body["variables"]["seatKey"] = seat["seat_key"]
        reserve_seat_body["variables"]["libId"] = seat["lib_id"]

        res = session.post(constants.URL, json=reserve_seat_body)
        try:
            result = res.json()
        except json.decoder.JSONDecodeError as err:
            logger.error(f"Error reserving seat: {err}")
            return False
        if result.get("errors") and result.get("errors")[0].get("code") != 0:
            logger.warning("Failed to reserve seat!")
            return False
        logger.info("Seat reserved successfully.")
        return True


def reserve_cancel(session):
    """
    取消座位预约

    @param session: 当前的 requests.Session 会话
    @type session: requests.Session
    @return: True 表示取消成功，False 表示取消失败
    @rtype: bool
    """
    logger.info("Canceling reservation.")
    if check_session_status(session):
        index_data = get_index_data(session)
        if not index_data:
            logger.warning("Failed to get index data!")
            return False
        
        sToken = get_resverve_stoken(index_data)
        constants.RESERVE_CANCLE_BODY['variables'].update({'sToken': sToken})
        res = session.post(constants.URL, json=constants.RESERVE_CANCLE_BODY)
        try:
            result = res.json()
        except json.decoder.JSONDecodeError as err:
            logger.error(f"Error canceling reservation: {err}")
            return False
        if result.get("errors") and "主动退座成功" in result.get("errors")[0].get("msg"):
            logger.info("Reservation canceled successfully.")
            return True
        else:
            logger.warning(result.get("errors")[0].get("msg"))
            return False


def pass_queue():
    logger.info("开始排队...")

    queue_header = {
        "Host": "wechat.v2.traceint.com",
        "Pragma": "no-cache",
        "Accept": "*/*",
        "Sec-WebSocket-Key": "oXNRrZUmWXsDDq1Ay3ceUg==",
        "Sec-Fetch-Site": "same-site",
        "Sec-WebSocket-Version": "13",
        "Sec-WebSocket-Extensions": "permessage-deflate",
        "Cache-Control": "no-cache",
        "Sec-Fetch-Mode": "websocket",
        "Accept-Language": "zh-CN,zh-Hans;q=0.9",
        "Origin": "https://web.traceint.com",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50(0x1800323d) NetType/WIFI Language/zh_CN",
        "Connection": "Upgrade",
        "Accept-Encoding": "gzip, deflate",
        "Upgrade": "websocket",
        "Sec-Fetch-Dest": "websocket",
        'Cookie': ""
    }

    try:
        ws = websocket.WebSocket()
        # 获取 cookies 并转换为字符串
        cookie_string = load_cookie_str("cookie_string")
        queue_header['Cookie'] = cookie_string
        # 尝试连接 WebSocket
        ws.connect('wss://wechat.v2.traceint.com/ws?ns=prereserve/queue', header=queue_header, verify=False)

        if ws.connected:
            logger.info("WebSocket 连接成功，开始排队...")

            while True:
                # 发送排队请求
                ws.send('{"ns":"prereserve/queue","msg":""}')
                response = ws.recv()

                # 检查排队成功或抢座成功的返回消息
                if 'u6392' in response:  # 排队成功
                    logger.info("排队成功！")
                    break
                elif 'u6210' in response:  # 抢座成功
                    msg = json.loads(response).get("msg", "抢座成功，消息未找到")
                    logger.info(f"抢座成功，消息: {msg}")
                    time.sleep(5)
                    break

                logger.info(f"排队中，响应: {response}")
                # time.sleep(0.01)  # 如果需要延迟，可以在这里启用

        else:
            logger.error("WebSocket 连接失败。")

    except Exception as e:
        logger.error(f"排队过程中发生错误: {e}")

    finally:
        # 关闭 WebSocket 连接
        if ws.connected:
            ws.close()

    logger.info("排队结束...")


def pre_reservation(session, seat, retry=1, time_interval=2):
    """
    前一天晚上22:00提前预订座位
    """
    # try:
    #     pass_queue()
    #     pass_queue()

    #     print('test pass queue ==> ok!')
    #     # 重要！如果不是放在常用座位，需要先请求对应的阅览室的所有座位，libLayout！！
    #     # requests.post(url=url, headers=pre_header, json=data_lib_chosen, verify=False)
    #     # 抢座的post请求，core code

    #     pre_reserve_seat_body = copy.deepcopy(constants.PRE_RESERVE_SEAT_BODY)
    #     pre_reserve_seat_body["variables"]["key"] = seat["seat_key"]
    #     pre_reserve_seat_body["variables"]["libid"] = seat["lib_id"]
    #     res = session.post(url=constants.URL, json=pre_reserve_seat_body, verify=False)
    #     print('test request ==> ok!')
    #     print(res.text)
    #     text_Res = session.post(url=constants.URL, json=constants.PRE_RESERVE_BODY, verify=False).text
    #     unicode = str(res.text).encode('utf-8').decode('unicode_escape')
    #     text_uni = str(text_Res).encode('utf-8').decode('unicode_escape')
    #     print(text_uni)
    #     print(unicode)
    #     if str(res.text).count("true") and text_Res.count('user_mobile'):
    #         print("******************************")
    #         print("恭喜你！预定成功！程序即将结束......")
    #         print("******************************\n")
    #         return True
    #     else:
    #         # print('---睡眠0.3s---')
    #         pass_queue()
    #         pass_queue()
    #         time.sleep(0.3)
    #         return False
    # except Exception as e:
    #     time.sleep(0.3)
    #     print(e)
    #     return False


    try:
        if check_session_status(session):
            logger.info("开始预约流程...")
            for _ in range(retry):
                # 排队两次
                pass_queue()
                pass_queue()

                logger.info("排队通过，准备发起抢座请求...")
                # 请求阅览室的所有座位，准备抢座
                # logger.info("请求对应阅览室的所有座位...")
                # session.post(url=url, headers=headers, json=data_lib_chosen, verify=False)

                # 发起抢座请求
                logger.info("发起抢座请求...")

                pre_reserve_seat_body = copy.deepcopy(constants.PRE_RESERVE_SEAT_BODY)
                pre_reserve_seat_body["variables"]["key"] = seat["seat_key"]
                pre_reserve_seat_body["variables"]["libid"] = seat["lib_id"]
                res = session.post(url=constants.URL, json=pre_reserve_seat_body, verify=False)
                text_Res = session.post(url=constants.URL, json=constants.PRE_RESERVE_BODY, verify=False).text

                # 将返回的 JSON 数据转换为可读的字符串格式
                unicode = str(res.text).encode('utf-8').decode('unicode_escape')
                text_uni = str(text_Res).encode('utf-8').decode('unicode_escape')

                logger.info(f"抢座响应：{unicode}")
                logger.info(f"用户数据响应：{text_uni}")

                # 检查预约成功
                if str(res.text).count("true") and text_Res.count('user_mobile'):
                    logger.info("******************************")
                    logger.info("恭喜你！预定成功......")
                    logger.info("******************************\n")
                    return True

                # 如果没有成功，继续排队并等待
                logger.warning("预约未成功，重新排队...")
                pass_queue()
                pass_queue()
                # 睡眠 0.3 秒后继续尝试
                time.sleep(0.3)

    except Exception as e:
        logger.error(f"预约过程中发生错误: {e}")
        time.sleep(time_interval)  # 出现异常时，延迟 0.3 秒后继续
        return False



def check_in(session):
    return False