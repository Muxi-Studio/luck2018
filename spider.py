from bs4 import BeautifulSoup
import asyncio
import aiohttp
import random
from db import cur, select_user_viacid, insert_students
import os
import base64
import time

PROXY1 = os.getenv("PROXY1")
PROXY2 = os.getenv("PROXY2")
####
AUTH = os.getenv("AUTH")
PROXY = str(os.getenv("PROXY"))

accounturl = "https://account.ccnu.edu.cn/cas/login"
account_jurl = "https://account.ccnu.edu.cn/cas/login;jsessionid="
info_url = "http://xpcx.ccnu.edu.cn/page.php?cid="

headers = {
        "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.75 Safari/537.36"
}

#### Proxy
async def get_proxy():
    ipheader = {
            "Authorization": AUTH
    }
    async with aiohttp.ClientSession(cookie_jar = aiohttp.CookieJar(unsafe=True),
                headers = ipheader) as session:
        async with session.get(PROXY) as resp:
            item = await resp.json()
            proxy = "http://" + str(item["IP"] +":"+item["port"])
            # 检查一下
            async with session.get("https://account.ccnu.edu.cn/cas/css/addstyle.css", proxy = proxy) as r:
                if r.status == 200:
                    return proxy
                else:
                    proxylist = [PROXY1, PROXY2]
                    _proxy = random.randint(0, len(proxylist)-1)
                    return proxylist[_proxy]
#### 

#login util 获得Cookie
async def getjid(setcookie):
    start = setcookie.find("=") + 1
    end = setcookie.find(";")
    return setcookie[start:end]

#login util 获得登录用页面信息
async def getltid(html):
    soup = BeautifulSoup(html)

    # 内网条件下为
    ltid = soup.find_all('input')[2]['value']
    execution = soup.find_all('input')[3]['value']
    if len(execution) is not 4:
        ltid = soup.find_all('input')[3]['value']
        execution = soup.find_all('input')[4]['value']
    return ltid, execution

#模拟登录Account.ccnu.edu.cn
async def login_xxmh(sid, pswd, _proxy):
    _cookie_jar = None
    #GET PROXY
    myproxy = await get_proxy()
    async with aiohttp.ClientSession(cookie_jar = aiohttp.CookieJar(unsafe=True), headers = headers) as session:
        async with session.get(accounturl, timeout = 15, proxy = myproxy) as response:
            ltid, execution = await getltid(await response.text())
            jid = await getjid(response.headers['set-cookie'])
            payload = {
                "username":sid,
                "password":pswd,
                "lt":ltid,
                "execution":execution,
                "_eventId":"submit",
                "submit":"LOGIN"
            }
            async with session.post(account_jurl + jid, data = payload, timeout = 8) as res2:
                if "CASTGC" in res2.cookies:
                    return True
                else:
                    return False

#获取学生信息
async def getinfo(sid, _proxy):
    myproxy = await get_proxy()

    # 先看数据库中有无
    info = select_user_viacid(sid, cur)
    if info is not None:
        name = info[2]
        gender = info[5]
        college = info[3]
        return (name, gender, college)
    
    # 若无则继续访问 xpcx 现场获得
    async with aiohttp.ClientSession(headers = headers) as session:
        async with session.get(info_url + str(sid), timeout = 15, proxy = myproxy) as response:
            html = await response.text()
            soup = BeautifulSoup(html)
            contents = soup.find_all('td', class_ = "cont")
            cont = []
            for item in contents:
                item = item.string
                cont.append(item)
            
            # 若还是没找到返回空
            if len(cont) is 0:
                return ("", "", "")

            # 加入到数据库中
            stu = []
            stu.append(cont)
            insert_students(stu, cur)

            # 返回找到的东西
            return (cont[1], cont[2], cont[4])

async def login_ccnu(sid, pswd):
    _proxy = await get_proxy()
    status = await login_xxmh(sid, pswd, _proxy)
    if status:
        name, gender, college = await getinfo(sid, _proxy)
        return {
            "name":name,
            "gender": gender,
            "college": college,
        }
    else:
        return {
            "msg":"failed"        
        }

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(login_ccnu(2016, "pass"))
    loop.close()
