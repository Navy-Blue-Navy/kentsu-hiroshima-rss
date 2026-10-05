import time
import re
import json
import requests
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = "https://digital.kentsu.co.jp"
WAR_PATH = "/api/war/change"
NEWS_PATH = "/articles/artcl_sublist"


def make_aegis(timestamp, path):
    s1 = "Kentsu_2025"
    s2 = "ProField_2025"
    s3 = "#nEWS_20_API_25_SeCReT#"

    data = f"{timestamp}{path}{s1}{s2}{s3}".encode("utf-8")

    def uint32(x):
        return x & 0xFFFFFFFF

    def int32(x):
        x &= 0xFFFFFFFF
        return x if x < 0x80000000 else x - 0x100000000

    def js_lshift(x, n):
        return int32(uint32(x) << n)

    def js_urshift(x, n):
        return uint32(x) >> n

    r = 21845

    for n, e in enumerate(data):
        left = js_lshift(r, 5)
        right = js_urshift(r, 27)

        rotated = int32(left | right)

        o = int32(
            int32(rotated - int32(r) + e) ^ int32(127 * n)
        )

        r = int32(
            js_lshift(o, 13) | js_urshift(o, 19)
        )

    s = format(r, "x") if r >= 0 else "-" + format(-r, "x")
    return s.rjust(8, "0")


# -------------------------
# 広島版を取得
# -------------------------

session = requests.Session()

timestamp = int(time.time() * 1000)

headers = {
    "Accept": "application/json",
    "SimplePage-Hermes": str(timestamp),
    "SimplePage-Aegis": make_aegis(timestamp, WAR_PATH),
    "Origin": BASE,
    "Referer": BASE + NEWS_PATH,
}

response = session.post(
    BASE + WAR_PATH,
    files={"war": (None, "8")},
    headers=headers,
)

response.raise_for_status()

news_response = session.get(BASE + NEWS_PATH)
news_response.raise_for_status()


# -------------------------
# 埋め込み記事データを抽出
# -------------------------

match = re.search(
    r'window\.__remixContext\.streamController\.enqueue\((.+?)\);',
    news_response.text,
    re.DOTALL,
)

if not match:
    raise RuntimeError("記事データをHTMLから取得できませんでした。")

decoded = json.loads(match.group(1))
data = json.loads(decoded)

article_refs = data[31]

articles = []

for ref_no in article_refs:
    ref = data[ref_no]
    article = {}

    for key_ref, value_ref in ref.items():
        key = data[int(key_ref[1:])]
        value = data[value_ref]
        article[key] = value

    articles.append(article)


# -------------------------
# RSS 2.0を作成
# -------------------------

rss = ET.Element("rss", version="2.0")
channel = ET.SubElement(rss, "channel")

ET.SubElement(channel, "title").text = "建通新聞電子版・広島"
ET.SubElement(channel, "link").text = BASE + NEWS_PATH
ET.SubElement(channel, "description").text = "建通新聞電子版の広島地域ニュース"
ET.SubElement(channel, "language").text = "ja"

for article in articles:
    item = ET.SubElement(channel, "item")

    title = article.get("title", "")
    summary = article.get("summary", "")
    link = article.get("link", "")
    cd = article.get("cd", "")

    if link.startswith("/"):
        link = BASE + link

    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "link").text = link
    ET.SubElement(item, "description").text = summary

    guid = ET.SubElement(item, "guid")
    guid.set("isPermaLink", "false")
    guid.text = cd


# -------------------------
# デスクトップにXML保存
# -------------------------

tree = ET.ElementTree(rss)
ET.indent(tree, space="  ")

output_path = Path.home() / "Desktop" / "kentsu_hiroshima.xml"

tree.write(
    output_path,
    encoding="utf-8",
    xml_declaration=True,
)

print("RSS作成成功")
print("記事件数:", len(articles))
print("保存先:", output_path)