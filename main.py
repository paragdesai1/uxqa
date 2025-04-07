from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
import requests
import uvicorn
import os
import asyncio
from playwright.async_api import async_playwright
from PIL import Image, ImageChops

app = FastAPI()

# Root route for Render test
@app.get("/")
def read_root():
    return {"message": "UX QA Tool is running"}

# Serve screenshots and diff images
app.mount("/static", StaticFiles(directory="."), name="static")

# Allow CORS for dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FIGMA_TOKEN = os.getenv("FIGMA_TOKEN", "figd_jHWWTRa9WEGSQIaKvKgYSx3hyh8omAN6AtDWP_lL")

def fetch_figma_file_data(file_key: str):
    headers = {"X-Figma-Token": FIGMA_TOKEN}
    url = f"https://api.figma.com/v1/files/{file_key}"
    response = requests.get(url, headers=headers)
    return response.json() if response.status_code == 200 else {"error": "Figma API error"}

def extract_figma_styles(figma_json):
    styles = []
    try:
        for page in figma_json.get("document", {}).get("children", []):
            for node in page.get("children", []):
                styles.append({
                    "name": node.get("name"),
                    "type": node.get("type"),
                    "fontFamily": node.get("style", {}).get("fontFamily"),
                    "fontSize": node.get("style", {}).get("fontSize"),
                    "color": node.get("fills", [{}])[0].get("color"),
                    "width": node.get("absoluteBoundingBox", {}).get("width"),
                    "height": node.get("absoluteBoundingBox", {}).get("height")
                })
    except Exception as e:
        print("Figma parse error:", str(e))
    return styles

async def capture_page_screenshot_and_styles(url: str, output_path: str = "screenshot.png"):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url)
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path=output_path, full_page=True)
        styles = await page.evaluate("""
            () => Array.from(document.querySelectorAll('*')).map(el => {
                const c = getComputedStyle(el);
                return {
                    tag: el.tagName,
                    class: el.className,
                    id: el.id,
                    fontSize: c.fontSize,
                    fontFamily: c.fontFamily,
                    color: c.color,
                    backgroundColor: c.backgroundColor,
                    padding: c.padding,
                    margin: c.margin,
                    width: c.width,
                    height: c.height
                };
            })
        """)
        await browser.close()
        return output_path, styles

def compare_styles(figma_styles, dom_styles):
    font_differences, color_mismatches, spacing_issues = [], [], []
    for figma in figma_styles:
        f_font = f"{figma.get('fontFamily')} {figma.get('fontSize')}"
        f_color = figma.get('color')
        f_w, f_h = figma.get('width'), figma.get('height')

        for dom in dom_styles:
            d_font = f"{dom.get('fontFamily')} {dom.get('fontSize')}"
            if f_font and d_font and f_font != d_font:
                font_differences.append({
                    "element": dom.get("tag"),
                    "expected": f_font,
                    "actual": d_font
                })

            if f_color and 'r' in f_color:
                rgb = f"rgb({int(f_color['r']*255)}, {int(f_color['g']*255)}, {int(f_color['b']*255)})"
                if rgb != dom.get("color"):
                    color_mismatches.append({
                        "element": dom.get("tag"),
                        "expected": rgb,
                        "actual": dom.get("color")
                    })

            if f_w and f_h:
                d_w = float(dom.get("width", "0px").replace("px", ""))
                d_h = float(dom.get("height", "0px").replace("px", ""))
                if f_w != d_w or f_h != d_h:
                    spacing_issues.append({
                        "element": dom.get("tag"),
                        "expected_width": f_w,
                        "actual_width": d_w,
                        "expected_height": f_h,
                        "actual_height": d_h
                    })

    return font_differences, color_mismatches, spacing_issues

def compare_images(image1_path, image2_path):
    try:
        img1 = Image.open(image1_path).convert("RGB")
        img2 = Image.open(image2_path).convert("RGB")
        diff = ImageChops.difference(img1, img2)
        diff_path = "diff_output.png"
        diff.save(diff_path)
        return diff_path
    except Exception as e:
        print("Image compare error:", str(e))
        return None

@app.post("/api/compare")
async def compare(
    figmaUrl: Optional[str] = Form(None),
    pageUrl: Optional[str] = Form(None),
    screenshot: Optional[UploadFile] = File(None),
):
    figma_data, figma_styles = {}, []
    if figmaUrl:
        try:
            file_key = figmaUrl.split("/file/")[1].split("/")[0]
            figma_data = fetch_figma_file_data(file_key)
            figma_styles = extract_figma_styles(figma_data)
        except Exception as e:
            figma_data = {"error": str(e)}

    dom_styles, live_shot_path = [], None
    if pageUrl:
        try:
            live_shot_path, dom_styles = await capture_page_screenshot_and_styles(pageUrl)
        except Exception as e:
            print("Live page error:", str(e))

    uploaded_path = None
    if screenshot:
        uploaded_path = f"uploaded_{screenshot.filename}"
        with open(uploaded_path, "wb") as f:
            f.write(await screenshot.read())

    diff_path = compare_images(uploaded_path, live_shot_path) if uploaded_path and live_shot_path else None
    font_diffs, color_diffs, spacing_diffs = compare_styles(figma_styles, dom_styles)

    return JSONResponse(content={
        "figma_data_preview": figma_data.get("name", "N/A"),
        "page_screenshot": live_shot_path,
        "uploaded_screenshot": uploaded_path,
        "visual_diff_image": diff_path,
        "font_differences": font_diffs,
        "color_mismatches": color_diffs,
        "spacing_issues": spacing_diffs
    })
