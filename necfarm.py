# ====================================================
#  NECaptcha Auto-Farmer - GitHub Codespaces
#  Token dikirim otomatis ke Telegram
# ====================================================

import asyncio
import cv2
import numpy as np
from playwright.async_api import async_playwright
import requests
import time

# ================== KONFIGURASI ==================
TARGET_URL = "https://necaptcha.jphgpt.f5.si/"
TELEGRAM_BOT_TOKEN = "8271211266:AAEcD8DS6ci3EvA2Xe_Xzbvy1FKIJB-WHwg"
TELEGRAM_CHAT_ID = "7284499809"
# =================================================

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        requests.post(url, data=data, timeout=10)
        print("[+] Token terkirim ke Telegram")
    except Exception as e:
        print(f"[-] Gagal kirim Telegram: {e}")

async def get_slider_bounds(page):
    selectors = [
        ".yidun_slider", ".yidun_slider_indicator", ".yidun_slider-btn",
        ".nec-captcha-slider", ".slider", "[class*='slider']", "[class*='yidun']"
    ]
    for sel in selectors:
        el = await page.query_selector(sel)
        if el:
            box = await el.bounding_box()
            if box and box["width"] > 0:
                return el, box
    return None, None

async def get_puzzle_images(page):
    bg_selectors = [
        ".yidun_bg-img", ".yidun_bg", "img.yidun_bg-img",
        ".nec-captcha-bg", "canvas.yidun_bg-img", "[class*='bg']"
    ]
    piece_selectors = [
        ".yidun_jigsaw", ".yidun_piece", ".nec-captcha-piece",
        ".yidun_jigsaw-img", "img.yidun_jigsaw", "[class*='jigsaw']", "[class*='piece']"
    ]
    
    bg_bytes = None
    for sel in bg_selectors:
        el = await page.query_selector(sel)
        if el:
            bg_bytes = await el.screenshot()
            break
    
    piece_bytes = None
    for sel in piece_selectors:
        el = await page.query_selector(sel)
        if el:
            piece_bytes = await el.screenshot()
            break
    
    return bg_bytes, piece_bytes

async def solve_slider(page):
    slider_el, slider_box = await get_slider_bounds(page)
    if not slider_el:
        print("[-] Handle slider tidak ditemukan.")
        return False
    
    bg_bytes, piece_bytes = await get_puzzle_images(page)
    if not bg_bytes or not piece_bytes:
        print("[-] Gambar puzzle tidak ditemukan.")
        return False
    
    bg = cv2.imdecode(np.frombuffer(bg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    piece = cv2.imdecode(np.frombuffer(piece_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    bg_gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)
    piece_gray = cv2.cvtColor(piece, cv2.COLOR_BGR2GRAY)
    
    result = cv2.matchTemplate(bg_gray, piece_gray, cv2.TM_CCOEFF_NORMED)
    _, _, _, max_loc = cv2.minMaxLoc(result)
    distance = max_loc[0]
    
    scale = slider_box["width"] / bg.shape[1]
    slide_distance = distance * scale
    
    start_x = slider_box["x"] + slider_box["width"] / 2
    start_y = slider_box["y"] + slider_box["height"] / 2
    
    print(f"[*] Jarak geser: {slide_distance:.1f}px")
    
    await page.mouse.move(start_x, start_y)
    await page.mouse.down()
    steps = 50
    for i in range(steps + 1):
        current_x = start_x + slide_distance * (i / steps)
        current_y = start_y + np.random.randint(-3, 3)
        await page.mouse.move(current_x, current_y)
        await asyncio.sleep(np.random.uniform(0.005, 0.02))
    
    await page.mouse.up()
    print("[+] Slider digeser.")
    return True

async def capture_token(page):
    token_captured = []
    await page.expose_function("__captureToken", lambda t: token_captured.append(t))
    
    await page.evaluate("""() => {
        if (typeof window.initNECaptcha === 'function') {
            const orig = window.initNECaptcha;
            window.initNECaptcha = function(config) {
                if (config && config.onVerify) {
                    const origVerify = config.onVerify;
                    config.onVerify = function(token) {
                        window.__captureToken(token);
                        origVerify(token);
                    };
                }
                orig(config);
            };
        }
    }""")
    
    token = None
    for _ in range(60):
        if token_captured:
            token = token_captured[0]
            break
        
        token = await page.evaluate("() => localStorage.getItem('NECaptchaValidate')")
        if token:
            break
        
        token = await page.evaluate("() => window.NECaptchaToken || window.NECaptchaValidate")
        if token:
            break
        
        await asyncio.sleep(1)
    
    return token

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()
        
        print(f"[*] Membuka {TARGET_URL}")
        await page.goto(TARGET_URL, wait_until="networkidle")
        await page.wait_for_timeout(3000)
        
        success = await solve_slider(page)
        if not success:
            print("[!] Auto-solve gagal.")
            await browser.close()
            return None
        
        await page.wait_for_timeout(2000)
        token = await capture_token(page)
        
        if token:
            print(f"[+] Token: {token}")
            send_telegram(f"NECaptcha Token:\n{token}")
        else:
            print("[-] Token tidak ditemukan.")
        
        await browser.close()
        return token

if __name__ == "__main__":
    try:
        while True:
            token = asyncio.run(main())
            time.sleep(30 if token else 10)
    except KeyboardInterrupt:
        print("Dihentikan.")