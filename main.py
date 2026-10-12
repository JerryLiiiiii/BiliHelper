# coding: utf-8
"""
B站会员购(show.bilibili.com)演出抢票脚本

功能:
1. 首次运行/登录失效时, 弹出哔哩哔哩扫码登录, 登录状态保存到 cookies.pkl
2. 循环监控目标演出的余票(回流票), 一旦出现可购买票档, 自动选择场次/票档/数量并进入确认订单页
3. 确认订单页自动勾选实名观演人(购买人), 可按配置自动点击“下一步支付”完成下单(支付仍需人工完成)

说明:
- 售罄时脚本会持续监控, 捡漏回流票, 这是本脚本的主要使用场景
- auto_pay 为 true 时脚本会自动创建订单(进入待支付), 请确认 buyer_names 填写正确
"""
from json import loads
from os import access, X_OK
from os.path import exists
from pickle import dump, load
from random import randint, uniform
from re import search as re_search
from socket import create_connection
from subprocess import run as run_cmd
from time import sleep, strftime, time
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, SessionNotCreatedException, TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36")
API_DETAIL = "https://show.bilibili.com/api/ticket/project/getV2?version=134&id={id}&project_id={id}"
COOKIE_FILE = "cookies.pkl"


class BiliTicker(object):
    def __init__(self, item_id, sess, price, ticket_num, buyer_names, auto_pay, poll_interval, driver_path,
                 jitter=0.5, proxy=""):
        self.item_id = str(item_id)
        self.sess = sess  # 场次优先级(页面场次序号, 从1开始)
        self.price = price  # 票档优先级(页面价格序号, 从1开始, 1=价格最低那档)
        self.ticket_num = ticket_num  # 购买票数
        self.buyer_names = buyer_names or []  # 需要勾选的实名观演人(购买人)姓名
        self.auto_pay = auto_pay  # 到达确认订单页后是否自动点击“下一步支付”
        self.poll_interval = poll_interval  # 余票轮询间隔(秒)
        self.jitter = jitter  # 轮询波动上限(秒): 实际间隔在 poll_interval ~ poll_interval+jitter 之间随机
        self.driver_path = driver_path
        self.proxy = (proxy or "").strip()  # 代理地址, 如 "http://127.0.0.1:7890"; 留空=强制直连
        if self.proxy:
            handler = ProxyHandler({"http": self.proxy, "https": self.proxy})
        else:
            # 传空字典给 ProxyHandler: 忽略环境变量里的 http(s)_proxy, 保证轮询始终直连
            handler = ProxyHandler({})
        self.opener = build_opener(handler)
        self.driver = None
        self.detail_url = "https://show.bilibili.com/platform/detail.html?id=%s" % self.item_id

    # ---------------- 浏览器 ----------------

    def build_service(self):
        # driver_path 指向解压后的 chromedriver 可执行文件时直接使用;
        # 否则返回 None,交由 Selenium 自动匹配本机 Chrome 版本
        if self.driver_path and exists(self.driver_path) and access(self.driver_path, X_OK):
            return Service(self.driver_path)
        if self.driver_path:
            print("***提示: driver_path 需要填写解压后的 chromedriver 可执行文件路径***")
        return None

    def build_options(self):
        options = webdriver.ChromeOptions()
        # 隐藏自动化特征,降低被风控拦截的概率
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_argument('--log-level=3')
        if self.proxy:
            options.add_argument("--proxy-server=%s" % self.proxy)
        else:
            # 强制浏览器直连,即使系统开启了代理(如 Clash 系统代理/TUN)也不走代理
            options.add_argument("--no-proxy-server")
        return options

    def create_driver(self, options=None):
        service = self.build_service()
        try:
            driver = webdriver.Chrome(service=service, options=options)
        except SessionNotCreatedException:
            if service is None:
                raise
            print("***提示: 本地 ChromeDriver 与 Chrome 版本不匹配,自动改用 Selenium 匹配驱动***")
            driver = webdriver.Chrome(options=options)
        try:
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            })
        except Exception:
            pass
        driver.set_window_size(1440, 900)
        return driver

    # ---------------- 登录 ----------------

    def is_logged_in(self):
        try:
            self.driver.find_element(By.CSS_SELECTOR, ".user-info .profile-img")
            return True
        except Exception:
            return False

    def notify(self, title, message):
        """发送 macOS 系统通知(抢票成功/需要人工处理时提醒)"""
        print("###系统通知: %s - %s###" % (title, message))
        try:
            run_cmd(
                ["osascript",
                 "-e", "on run argv",
                 "-e", 'display notification (item 2 of argv) with title (item 1 of argv) sound name "Glass"',
                 "-e", "end run",
                 title, message],
                timeout=10)
        except Exception as e:
            print("***系统通知发送失败(不影响抢票):***", e)

    def load_cookies(self):
        try:
            for c in load(open(COOKIE_FILE, "rb")):
                try:
                    self.driver.add_cookie({
                        "name": c.get("name"), "value": c.get("value"),
                        "domain": ".bilibili.com", "path": "/"})
                except Exception:
                    pass
        except Exception as e:
            print("***读取登录状态失败:***", e)

    def ensure_login(self):
        print("###检查登录状态###")
        self.driver.get(self.detail_url)
        sleep(3)
        if exists(COOKIE_FILE):
            self.load_cookies()
            self.driver.refresh()
            sleep(3)
            if self.is_logged_in():
                print("###已使用本地保存的登录状态###")
                return
            print("###本地登录状态已失效,需要重新扫码登录###")
        else:
            print("###首次使用,需要扫码登录###")
        self.qr_login()

    def qr_login(self):
        for sel in (".nav-header-regis-login", ".nav-header-login"):
            try:
                self.driver.find_element(By.CSS_SELECTOR, sel).click()
                break
            except Exception:
                continue
        else:
            try:
                self.driver.find_element(By.XPATH, "//*[contains(text(),'登录')]").click()
            except Exception:
                pass
        print("###请使用哔哩哔哩APP扫描页面上的二维码登录(最多等待5分钟)###")
        try:
            initial_sess = next((c["value"] for c in self.driver.get_cookies() if c["name"] == "SESSDATA"), None)
        except Exception:
            initial_sess = None
        deadline = time() + 300
        while time() < deadline:
            try:
                cur_sess = next((c["value"] for c in self.driver.get_cookies() if c["name"] == "SESSDATA"), None)
            except Exception:
                cur_sess = None
            if self.is_logged_in() or (cur_sess and cur_sess != initial_sess):
                self.driver.refresh()
                sleep(3)
                if self.is_logged_in():
                    break
                # 登录信息未生效, 重新弹出二维码继续等
                for sel in (".nav-header-regis-login", ".nav-header-login"):
                    try:
                        self.driver.find_element(By.CSS_SELECTOR, sel).click()
                        break
                    except Exception:
                        continue
            sleep(2)
        else:
            raise Exception("***登录超时,请重新运行脚本***")
        dump(self.driver.get_cookies(), open(COOKIE_FILE, "wb"))
        print("###登录成功,登录状态已保存到 cookies.pkl###")

    # ---------------- 余票监控 ----------------

    def fetch_screens(self):
        req = Request(API_DETAIL.format(id=self.item_id),
                      headers={"User-Agent": UA, "Referer": self.detail_url})
        with self.opener.open(req, timeout=10) as resp:
            data = loads(resp.read().decode("utf-8"))
        if data.get("code") != 0:
            raise Exception("接口返回异常: %s %s" % (data.get("code"), data.get("message")))
        return (data.get("data") or {}).get("screen_list") or []

    def pick_available(self, screens):
        # 按 场次优先级 -> 票档优先级 找第一个可购票档
        for si in self.sess:
            if si < 1 or si > len(screens):
                continue
            screen = screens[si - 1]
            tickets = screen.get("ticket_list") or []
            for pi in self.price:
                if pi < 1 or pi > len(tickets):
                    continue
                sku = tickets[pi - 1]
                if sku.get("clickable") and sku.get("sale_flag_number") != 4:
                    return si, pi, str(screen.get("name", "")).strip(), str(sku.get("desc", ""))
        return None

    # ---------------- 抢票动作 ----------------

    def try_grab(self, sess_idx, price_idx):
        print("###发现余票! 尝试锁定 第%s场次 第%s票档###" % (sess_idx, price_idx))
        try:
            self.driver.get(self.detail_url)
            WebDriverWait(self.driver, 10, 0.1).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".product-buy-wrapper")))
            sleep(0.3)

            tabs = self.driver.find_elements(By.CSS_SELECTOR, ".screens .selectable-option")
            if sess_idx <= len(tabs):
                tab = tabs[sess_idx - 1]
                cls = tab.get_attribute("class") or ""
                if "unable" in cls:
                    print("---场次暂不可选(可能已被抢完),继续监控---")
                    return False
                if "active" not in cls:
                    tab.click()
                    sleep(0.4)

            options = self.driver.find_elements(By.CSS_SELECTOR, ".tickets .selectable-option")
            if price_idx > len(options):
                print("---票档列表异常,继续监控---")
                return False
            opt = options[price_idx - 1]
            selected = False
            for _ in range(4):
                cls = opt.get_attribute("class") or ""
                if "active" in cls:
                    selected = True
                    break
                if "unable" in cls:
                    break
                opt.click()
                sleep(0.3)
            if not selected:
                print("---票档选中失败(可能已被抢完),继续监控---")
                return False

            for _ in range(self.ticket_num - 1):
                try:
                    self.driver.find_element(By.CSS_SELECTOR, ".count-plus.active").click()
                except Exception:
                    break
                sleep(0.1)

            try:
                self.driver.find_element(By.CSS_SELECTOR, ".product-buy.enable").click()
            except NoSuchElementException:
                print("---购买按钮不可用,继续监控---")
                return False

            WebDriverWait(self.driver, 10, 0.2).until(EC.url_contains("confirmOrder"))
            return True
        except TimeoutException:
            # 如果是登录状态失效,页面会弹出登录窗,给出明确提示
            try:
                modal = self.driver.find_element(By.CSS_SELECTOR, ".bili-mini-login-wrapper")
                if modal.is_displayed():
                    print("***警告: 登录状态已失效,请停止脚本并重新运行以扫码登录***")
            except Exception:
                pass
            print("---操作超时(可能已被抢完),继续监控---")
            return False

    def confirm_order(self):
        print("###已进入确认订单页###")
        WebDriverWait(self.driver, 15, 0.2).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".confirm-paybtn")))
        sleep(0.5)

        if self.buyer_names:
            cards = self.driver.find_elements(By.CSS_SELECTOR, ".card-item-container.user-card-item")
            chosen = 0
            for name in self.buyer_names:
                for card in cards:
                    try:
                        nm = card.find_element(By.CSS_SELECTOR, ".item-name").text.strip()
                    except Exception:
                        continue
                    if nm == name:
                        if "checked" not in (card.get_attribute("class") or ""):
                            card.click()
                            sleep(0.2)
                        chosen += 1
                        break
            print("###购买人勾选完成: %s/%s###" % (chosen, len(self.buyer_names)))
            if chosen < len(self.buyer_names):
                print("***警告: 有购买人未在页面上找到,请手动核对***")

        try:
            icon = self.driver.find_element(By.CSS_SELECTOR, ".service-term .check-icon")
            if "checked" not in (icon.get_attribute("class") or ""):
                self.driver.find_element(By.CSS_SELECTOR, ".service-term").click()
                sleep(0.2)
        except Exception:
            pass

        status = ""
        try:
            status = self.driver.find_element(By.CSS_SELECTOR, ".buyer-title-text").text.replace("\n", " ")
        except Exception:
            pass
        print("###当前购买人状态: %s###" % (status or "未知"))

        m = re_search(r"\((\d+)/(\d+)\)", status or "")
        ready = bool(m) and m.group(1) == m.group(2) == str(self.ticket_num)
        if self.auto_pay and ready:
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, ".confirm-paybtn")
                if "active" in (btn.get_attribute("class") or ""):
                    btn.click()
                    sleep(2.5)
                    if "confirmOrder" not in self.driver.current_url:
                        print("###订单已创建,请尽快在浏览器中完成支付!###")
                        self.notify("B站抢票成功", "订单已创建,请尽快完成支付!")
                    else:
                        print("***已点击支付,但页面仍在确认页(可能下单失败,如余票不足),请手动核对***")
                        self.notify("B站抢票提醒", "自动下单可能未成功,请手动核对确认页!")
                else:
                    print("***支付按钮暂不可用,请手动处理***")
                    self.notify("B站抢票提醒", "已到达确认订单页,请手动处理!")
            except Exception as e:
                print("***自动提交失败,请手动处理:***", e)
                self.notify("B站抢票提醒", "自动提交失败,请手动处理!")
        elif self.auto_pay:
            print("***购买人数量未达到%s人,未自动提交,请手动核对后点击【下一步支付】***" % self.ticket_num)
            self.notify("B站抢票提醒", "已到达确认订单页,但购买人未勾选完整,请手动处理!")
        else:
            print("###请核对订单信息与购买人,手动点击【下一步支付】完成下单###")
            self.notify("B站抢票", "已到达确认订单页,请尽快支付!")
        input("###处理完成后按回车退出脚本(浏览器会保持打开以便支付)###")

    # ---------------- 主流程 ----------------

    def check_proxy(self):
        # 配置了代理但本地代理软件没开时, 自动回退为直连, 避免脚本完全不能用
        if not self.proxy:
            return
        u = urlparse(self.proxy)
        try:
            with create_connection((u.hostname or "127.0.0.1", u.port or 80), timeout=3):
                pass
            print("###代理连接正常: %s###" % self.proxy)
        except Exception:
            print("***代理 %s 连不上,本次自动改用直连(如需代理请先启动代理软件)***" % self.proxy)
            self.proxy = ""
            self.opener = build_opener(ProxyHandler({}))

    def run(self):
        self.check_proxy()
        self.driver = self.create_driver(self.build_options())
        self.ensure_login()
        print("###开始监控余票###")
        print("###网络模式: %s###" % (self.proxy if self.proxy else "直连(不使用代理)"))
        print("###目标演出: %s | 场次优先级: %s | 票档优先级: %s | 数量: %s###"
              % (self.item_id, self.sess, self.price, self.ticket_num))
        n = 0
        errs = 0
        last_report = time()
        next_long_pause = randint(120, 300)  # 每 120~300 次轮询后来一次随机长停顿
        while True:
            n += 1
            try:
                screens = self.fetch_screens()
                errs = 0
                target = self.pick_available(screens)
                if target:
                    si, pi, sname, pname = target
                    print("###[%s] 发现可购票档: %s / %s###" % (strftime("%H:%M:%S"), sname, pname))
                    if self.try_grab(si, pi):
                        self.confirm_order()
                        return
                elif time() - last_report > 30:
                    total = sum(len(s.get("ticket_list") or []) for s in screens)
                    watched = 0
                    for si in self.sess:
                        if 1 <= si <= len(screens):
                            tickets = screens[si - 1].get("ticket_list") or []
                            watched += sum(1 for pi in self.price if 1 <= pi <= len(tickets))
                    print("---[%s] 监控中(第%s次): 接口共%s个票档 | 本脚本盯着 %s 个候选(场次%s × 票档%s), 全部无票,继续等待---"
                          % (strftime("%H:%M:%S"), n, total, watched, self.sess, self.price))
                    last_report = time()
            except (URLError, OSError, ValueError) as e:
                errs += 1
                wait = min(3 + errs * 2, 15)
                print("***监控请求异常,%s秒后重试:***" % wait, e)
                sleep(wait)
                continue
            except Exception as e:
                errs += 1
                wait = min(3 + errs * 2, 15)
                print("***监控异常,%s秒后重试:***" % wait, e)
                sleep(wait)
                continue
            # 随机波动间隔,避免固定频率请求被风控识别
            sleep(uniform(self.poll_interval, self.poll_interval + self.jitter))
            if n >= next_long_pause:
                pause = uniform(2.0, 6.0)
                print("---[%s] 随机停顿 %.1f 秒(模拟人工节奏)---" % (strftime("%H:%M:%S"), pause))
                sleep(pause)
                next_long_pause = n + randint(120, 300)


if __name__ == '__main__':
    try:
        with open('./config.json', 'r', encoding='utf-8') as f:
            config = loads(f.read())
        ticker = BiliTicker(config['item_id'], config['sess'], config['price'], config['ticket_num'],
                            config.get('buyer_names'), config.get('auto_pay', False),
                            config.get('poll_interval', 0.8), config['driver_path'],
                            config.get('jitter', 0.5), config.get('proxy', ''))
        ticker.run()
    except KeyboardInterrupt:
        print("###已手动停止###")
    except Exception as e:
        print(e)
        exit(1)
