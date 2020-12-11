import os
# env = {"PYPPETEER_DOWNLOAD_HOST": "https://npm.taobao.org/mirrors", "PYPPETEER_CHROMIUM_REVISION": "800071"}
# os.environ.update(env)
# from pyppeteer.command import install
# install()
import asyncio
import pyppeteer
import time, json, hashlib, base64, re, gc, sys

nt = 'nt' in os.name
chrome_path = nt and r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" or "/opt/google/chrome/chrome"
proxy = '' if nt else "proxy01v.jcpt.zzt.360es.cn:3128"
debug = nt or False
logger = None
sha1 = lambda s: hashlib.sha1(s).hexdigest()
ensurePath = lambda p: True if os.path.exists(p) else os.mkdir(p)

#网址取域名加时间当名字
def url2name(url):
    ret = time.strftime("_%Y%m%d%H%M%S")
    rs = re.findall(r"^(https?:)?//([^/:#?\\]+)([/:#?\\]|$)", url)  #更新于2020/11/17，参考tldextract
    if rs:
        ret = rs[0][1].rstrip(".") + ret
    return ret

#日志记录器
def getLogger(name=__name__, filename=None):
    import logging
    from logging import handlers
    logger = logging.getLogger(name)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s:%(lineno)d %(message)s")
    filename = filename or name + ".log"
    #按时间回滚
    tfh = handlers.TimedRotatingFileHandler(filename, when="MIDNIGHT", interval=1, backupCount=30, encoding="utf-8")
    tfh.suffix += ".log"
    tfh.setFormatter(fmt)
    logger.addHandler(tfh)
    #控制台输出
    logger.addHandler(logging.StreamHandler())
    logger.setLevel("INFO")
    return logger

ensurePath("log")
logger = getLogger("ppet", filename="log/ppet.log")

class Tree:
    def __init__(self, url, type=None):
        self.url = url
        self.type = type
        self.child = []

    def appendChild(self, tree):
        self.child.append(tree)

    def __repr__(self):
        return str(self.__dict__)

class NetReq:
    def __init__(self, requestId, url, _type, initiator, documentURL, referer, redirectResponse):
        self.requestId = requestId
        self.url = url
        self.type = _type
        self.initiator = initiator
        self.documentURL = documentURL
        self.referer = referer
        self.redirectResponse = redirectResponse

class Initiator:
    def __init__(self):
        self.durl = None
        self.reqs = list()
        self.visited = set()
        self.initiated = dict()

    def _reqByUrl(self, url):
        for req in self.reqs:
            if req.url == url:
                return req

    def _initiatorGraphForRequest(self):
        for req in self.reqs:
            _type = req.type
            iurl = req.initiator.get("url")
            if req.redirectResponse:
                iurl = req.redirectResponse["url"]
                _type = "Redirect"
            elif not iurl:
                stack = req.initiator.get("stack", {}).get("callFrames")
                if stack:
                    for i in stack:
                        iurl = i["url"]
                        if iurl:
                            break
                else:
                    if not self.durl and req.documentURL == req.url:
                        self.durl = req
                        continue
                    elif req.referer:
                        iurl = req.referer
                    else:
                        if debug:
                            print(req.type, req.url)
                    iurl = iurl or req.documentURL
            req.type = _type
            self.initiated[req] = self._reqByUrl(iurl)

    def _depthFirstSearchTreeBuilder(self, initiated, parentElement, parentRequest):
        for request in initiated.keys():
            if (initiated.get(request) == parentRequest):
                treeElement = Tree(request.url, request.type)
                parentElement.appendChild(treeElement)
                if (request not in self.visited):
                    self.visited.add(request)
                    self._depthFirstSearchTreeBuilder(initiated, treeElement, request)

    def buildRequestChainTree(self):
        self._initiatorGraphForRequest()
        root = Tree(self.durl.url, self.durl.type)
        self._depthFirstSearchTreeBuilder(self.initiated, root, self.durl)
        return root

    def event(self, parm):
        self.reqs.append(
            NetReq(parm["requestId"], parm["request"]["url"], parm["type"], parm["initiator"], parm["documentURL"],
                   parm["request"]["headers"].get("Referer"), parm.get("redirectResponse")))

    @staticmethod
    def dumps(tree, **kwds):
        return json.dumps(tree, default=lambda x: x.__dict__, **kwds)

async def info(browser, page):
    ver = await browser.version()
    host = browser.wsEndpoint.split('/')[2]
    id = page.mainFrame._id
    ws = f"ws://{host}/devtools/page/{id}"
    inspect = f"http://{host}/devtools/inspector.html?ws={host}/devtools/page/{id}"
    logger.info("%s, %s, %s", ver, ws, inspect)

async def getChain(page, url, phone=False, timeout=7000, obj=False):
    res = None
    title = None
    status = None
    initiator = Initiator()
    page._client.on('Network.requestWillBeSent', initiator.event)
    page.on("dialog", lambda x: x.accept() if x.type == "beforeunload" else x.dismiss())
    # yapf: disable
    iphonex={"name": "iPhone X","userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 11_0 like Mac OS X) AppleWebKit/604.1.38 (KHTML, like Gecko) Version/11.0 Mobile/15A372 Safari/604.1","viewport": {"width": 414,"height": 736,"deviceScaleFactor": 2,"isMobile": True,"hasTouch": True,"isLandscape": False}}
    # yapf: enable
    if phone:
        await page.emulate(iphonex)
    await page.evaluateOnNewDocument("() =>{ Object.defineProperties(navigator,{ webdriver:{ get: () => false } }) }")
    retcode = -1
    t0 = time.time()
    try:
        logger.info("---Url: %s", url)
        res = await asyncio.wait_for(page.goto(url, {
            'waitUntil': 'networkidle0',
            "timeout": timeout
        }), timeout / 1000 + 1)
        if res:
            status = res.status
        retcode = 0
        title = await page.title()
    except Exception as e:
        await page._client.send("Page.stopLoading")
        errname = type(e).__name__
        errval = str(e) or "Waitfor Timeout!"
        if errname == "TimeoutError" and "Navigation" in errval:
            logger.warning("%s: %s", errname, errval)
            retcode = 1
            try:
                title = await asyncio.wait_for(page.title(),2)
            except:
                retcode = -2
                logger.critical("This page is not working.")
        else:
            logger.error("%s: %s", errname, errval)
    t1 = time.time()
    logger.info("Use time: %.3fs" % (t1 - t0))
    if retcode < 0:
        return
    # await page.screenshot(path="_temp.jpeg")
    if debug:
        with open("reqs.json", "w", encoding="u8") as f:
            json.dump(initiator.reqs, f, indent=1, default=lambda x: x.__dict__)
    root = initiator.buildRequestChainTree()
    root.retcode = retcode
    root.status = status
    root.title = title
    root.currentUrl = page.url
    del initiator
    if obj:
        return root
    chain = Initiator.dumps(root, indent=2, ensure_ascii=False)
    return chain

async def getResourceTree(page):
    rt = {}
    task = []
    await page._client.send("Page.enable")
    restree = await page._client.send("Page.getResourceTree")
    if debug:
        with open("resTree.json", "w", encoding="u8") as f:
            json.dump(restree, f, indent=1)
    stack = [restree['frameTree']]
    while len(stack) > 0:
        top = stack.pop()
        task += [(top["frame"]["id"], i["url"], i["contentSize"]) for i in top["resources"]]
        if top.get("childFrames"):
            for i in top.get("childFrames"):
                stack.append(i)
    for i in task:
        size = i[2]
        dhash = ''
        try:
            ret = await page._client.send("Page.getResourceContent", {"frameId": i[0], "url": i[1]})
            data = ret['content']
            if data:
                if ret['base64Encoded']:
                    data = base64.b64decode(data)
                if isinstance(data, str):
                    data = data.encode("utf-8")
                dhash = sha1(data)
            else:
                if debug:
                    print("Empty", i[1])
        except Exception as e:
            if debug:
                print(e, i[1])
        rt[i[1]] = (size, dhash)
    return rt

def merge(chain, rt):
    def preorderTraversal(root, func):
        stack = [root]
        while stack:
            top = stack.pop()
            func(top)
            if top.child:
                for i in top.child:
                    stack.append(i)

    def func(node):
        url = node.url
        if url in rt:
            node.size = rt[url][0]
            node.hash = rt[url][1]

    preorderTraversal(chain, func)

def maxDepth(root):
    stack = []
    if root is not None:
        stack.append((1, root))
    depth = 0
    while stack:
        current_depth, root = stack.pop()
        depth = max(depth, current_depth)
        if root.child:
            for i in root.child:
                stack.append((current_depth + 1, i))
    return depth

async def getpage():
    args = ['--no-sandbox', '--window-size=1280,720', '--disable-features=TranslateUI']
    if proxy:
        args.append('--proxy-server={}'.format(proxy))
    browser = await pyppeteer.launch(headless=not nt,
                                     args=args,
                                     autoClose=False,
                                     dumpio=True,
                                     logLevel='ERROR',
                                     ignoreHTTPSErrors=True,
                                     executablePath=chrome_path,
                                     ignoreDefaultArgs=["--disable-popup-blocking"],
                                     defaultViewport={
                                         "width": 1280,
                                         "height": 720
                                     })
    page = (await browser.pages())[0]
    return page, browser

#生成一个文件迭代器
def file_iter(fp):
    f = open(fp, encoding="utf-8")
    line = f.readline().strip()
    while line:
        yield line
        line = f.readline().strip()
    f.close()

async def test(url="url.txt"):
    global debug
    debug = False
    if os.path.exists(url):
        urls = file_iter(url)
    elif url.startswith("http"):
        urls = [url]
    else:
        urls = input("Please input http/https url: ").split(",")
    page, browser = await getpage()
    await info(browser, page)
    path = "./ppet_download/"
    ensurePath(path)
    for url in urls:
        page = await browser.newPage()
        chain = await getChain(page, url, obj=True)
        if chain:
            chain.maxDepth = maxDepth(chain)
            rt = await getResourceTree(page)
            merge(chain, rt)
            fpath = path + "test/"
            ensurePath(fpath)
            fn = url2name(url) + ".json"
            logger.info("File: %s\t%d", fn, len(await browser.pages()))
            with open(fpath + fn, "w", encoding="utf-8") as f:
                f.write(Initiator.dumps(chain, ensure_ascii=False, indent=1))
            del rt, chain
            gc.collect()
        await page.close()
    await browser.close()

async def main():
    page, browser = await getpage()
    await info(browser, page)
    path = "./ppet_download/"
    ensurePath(path)
    while not nt:
        with os.popen("flock -x .ppet.lock -c ./UrlProvider.sh") as p:
            url = p.read().strip()
        if not url:
            logger.critical("Error: url is empty!")
            await asyncio.sleep(1)
            continue
        page = await browser.newPage()
        chain = await getChain(page, url, obj=True)
        if chain:
            rt = await getResourceTree(page)
            chain.maxDepth = maxDepth(chain)
            merge(chain, rt)
            fpath = path + time.strftime("%Y-%m-%d/")
            ensurePath(fpath)
            fn = url2name(url) + ".json"
            logger.info("File: %s\t%d", fn, len(await browser.pages()))
            with open(fpath + fn, "w", encoding="utf-8") as f:
                f.write(Initiator.dumps(chain, ensure_ascii=False))
            del rt, chain
            gc.collect()
        await page.close()
    if nt:
        chain = await getChain(page, "http://mpa.xinjiang.gov.cn.7h7726.icu/", phone=False, obj=True, timeout=7000)
        if chain:
            rt = await getResourceTree(page)
            chain.maxDepth = maxDepth(chain)
            merge(chain, rt)
            with open("reqChain.json", "w", encoding="u8") as f:
                f.write(Initiator.dumps(chain, indent=1, ensure_ascii=False))
        logger.info("ok")
        while not page.isClosed():
            await asyncio.sleep(0.5)
    await browser.close()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    a = sys.argv
    istest = False
    arg = ''
    if len(a) >= 2:
        name = a[1]
        if name.startswith("http"):
            arg = name
            istest = True
        elif name == "test":
            arg = a[2] if len(a) >= 3 else 'url.txt'
            istest = True
        else:
            logger = getLogger(name, filename="log/%s.log" % name)
    try:
        if istest:
            loop.run_until_complete(test(arg))
        else:
            loop.run_until_complete(main())
    except Exception as e:
        logger.exception(e)
