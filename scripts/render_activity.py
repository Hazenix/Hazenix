import re
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET


SVG = "http://www.w3.org/2000/svg"
INSIGHTS = (
    "https://yourinsights.vercel.app/api/insight?username=Hazenix"
    "&profile=false&summary=false&header=true&stats=true&languages=true"
    "&streak=true&graph=false"
)
CALENDAR = "https://ghchart.rshah.org/Hazenix"
ASSETS = Path(__file__).resolve().parents[1] / "assets"
STATIC_ELEMENTS = {
    f"{{{SVG}}}{tag}" for tag in (
        "svg", "title", "desc", "defs", "style", "g", "rect", "circle", "line",
        "path", "text", "clipPath", "linearGradient", "stop",
    )
}


def read_svg(url):
    request = Request(url, headers={"User-Agent": "curl/8.0", "Accept": "image/svg+xml"})
    with urlopen(request, timeout=25) as response:
        svg = ET.fromstring(response.read(256_000))
    if svg.tag != f"{{{SVG}}}svg":
        raise ValueError(f"Expected an SVG from {url}")
    # 外部图片只允许静态 SVG 元素和图片内部的渐变、裁剪引用。
    for node in svg.iter():
        values = [node.text or "", *node.attrib.values()]
        if node.tag not in STATIC_ELEMENTS or any(
            key.lower().startswith("on") or key.rsplit("}", 1)[-1] == "href"
            for key in node.attrib
        ) or any(re.search(r"@import|url\(\s*(?!#)", value, re.IGNORECASE) for value in values):
            raise ValueError(f"Unexpected SVG content from {url}")
    return svg


def render_activity(theme, calendar):
    card = read_svg(f"{INSIGHTS}&theme=github_{theme}")
    frame = card.find(f"{{{SVG}}}rect")
    if (
        card.get("aria-label") != "GitHub Insights for @Hazenix"
        or frame is None
        or not frame.get("stroke", "").startswith("url(#border-")
    ):
        raise ValueError("GitHub Insights returned a card without the expected gradient frame")

    card_width, card_height = int(card.attrib["width"]), int(card.attrib["height"])
    calendar_width, calendar_height = int(calendar.attrib["width"]), int(calendar.attrib["height"])
    inset = 40  # 和统计卡的左右留白对齐。
    scale = (card_width - 2 * inset) / calendar_width
    calendar_top = card_height - 14
    height = round(calendar_top + calendar_height * scale + 30)

    # 延长现有背景和渐变描边，让格子图也在同一个圆角框内。
    card.set("height", str(height))
    card.set("viewBox", f"0 0 {card_width} {height}")
    frame.set("height", str(height - 2))
    card.set("aria-label", f"{card.attrib['aria-label']} and annual contribution calendar")
    graph = ET.SubElement(card, f"{{{SVG}}}g", {
        "transform": f"translate({inset}, {calendar_top}) scale({scale:.6f})",
    })
    graph.extend(calendar)
    ET.indent(card, space="  ")
    return ET.tostring(card, encoding="utf-8") + b"\n"


if __name__ == "__main__":
    ET.register_namespace("", SVG)
    calendar = read_svg(CALENDAR)
    if not any(cell.get("data-date") for cell in calendar.findall(f"{{{SVG}}}rect")):
        raise ValueError("Contribution calendar has no dated cells")

    # 两个主题都生成成功后才覆盖现有图片。
    cards = {theme: render_activity(theme, calendar) for theme in ("light", "dark")}
    for theme, svg in cards.items():
        output = ASSETS / f"github-activity-{theme}.svg"
        output.write_bytes(svg)
        print(f"Rendered {output.name}")
