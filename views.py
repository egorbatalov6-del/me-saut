import os
import base64
import random
import string
import json
from datetime import datetime
from bson import ObjectId
from django.shortcuts import redirect
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from db import games_collection, users_collection, codes_collection, orders_collection

from pymongo import MongoClient
client = MongoClient("mongodb://localhost:27017/")
db = client['pixelvault']
support_collection = db['support_tickets']
chat_messages_collection = db['chat_messages']
admin_logs_collection = db['admin_logs']
balance_history_collection = db['balance_history']

ADMIN_CREATOR_LOGIN = "Egor"
ADMIN_CREATOR_PASS = "vault123"

def log_admin_action(text):
    admin_logs_collection.insert_one({
        "text": text,
        "date": datetime.now().strftime("%d.%m.%Y %H:%M")
    })

def generate_game_key():
    parts = [''.join(random.choices(string.ascii_uppercase + string.digits, k=4)) for _ in range(3)]
    return "-".join(parts)

def ai_generate_response(user_message):
    msg = user_message.lower().strip()
    if any(w in msg for w in ['цена', 'стоит', 'сколько', 'стоимость', 'прайс']):
        return "🤖 AI Nexus (FAQ): Цены на игры варьируются от 899 ₸ до 1499 ₸. Выбирайте категорию в каталоге и оформляйте покупку!"
    elif any(w in msg for w in ['привет', 'здарова', 'хай', 'ку']):
        return "🤖 AI Nexus: Приветствую! Выберите интересующую категорию ниже или задайте вопрос."
    elif any(w in msg for w in ['колес', 'бонус', 'крутить', 'рулетка']):
        return "🤖 AI Nexus (FAQ): Колесо удачи находится в левом нижнем углу экрана. Крутите его раз в день и получайте бонусы!"
    elif any(w in msg for w in ['баланс', 'пополн', 'деньги', 'счет', 'карг', 'карт', 'kaspi']):
        return "🤖 AI Nexus (FAQ): Пополнить баланс можно в Личном кабинете. Поддерживаются банковские карты, Kaspi QR и криптовалюта."
    elif any(w in msg for w in ['ключ', 'активац', 'игра', 'купил']):
        return "🤖 AI Nexus (FAQ): Все купленные лицензионные ключи мгновенно сохраняются в вашем Личном кабинете."
    elif any(w in msg for w in ['создатель', 'админ', 'егор', 'владелец']):
        return "🤖 AI Nexus (FAQ): Создатель и владелец платформы — Егор. Нажмите кнопку «⚠️ Позвать живого админа», чтобы связаться с ним лично."
    elif any(w in msg for w in ['гарант', 'безопасн', 'надежн']):
        return "🤖 AI Nexus (FAQ): Все сделки защищены шифрованием 256-Bit SSL, а выдача ключей происходит автоматически 24/7."
    else:
        return f"🤖 AI Nexus: Ваш запрос («{user_message}») зафиксирован. Если нужен человек, нажмите кнопку вызова админа ниже!"

def index(request):
    user_email = request.COOKIES.get('user_email')
    user = users_collection.find_one({"email": user_email}) if user_email else None
    is_admin = request.COOKIES.get('is_creator') == 'true'
    
    lang = request.GET.get('lang', request.COOKIES.get('lang', 'ru'))
    currency = request.GET.get('currency', request.COOKIES.get('currency', 'KZT'))
    selected_category = request.GET.get('category', 'all')
    
    rates = {'KZT': 1, 'RUB': 0.21, 'USD': 0.0021}
    currency_symbols = {'KZT': '₸', 'RUB': '₽', 'USD': '$'}
    
    query = {}
    if selected_category != 'all':
        query['category'] = selected_category
        
    games = list(games_collection.find(query))
    
    t = {
        'ru': {
            'title': 'EGORVAULT — Элитный маркетплейс игр',
            'badge': '💎 EGORVAULT v8.5 ELITE STORE',
            'hero_title': 'ЭЛИТНЫЕ ИГРЫ И КЛЮЧИ',
            'hero_sub': 'Мгновенная доставка лицензий, киберпанк эстетика и максимальная безопасность.',
            'catalog': '🔥 Каталог игр',
            'genre': 'Жанр:',
            'buy': 'КУПИТЬ КЛЮЧ',
            'login': 'ВХОД / РЕГИСТРАЦИЯ',
            'logout': 'ВЫЙТИ',
            'wheel_title': '🎡 КОЛЕСО УДАЧИ',
            'wheel_sub': 'Крути раз в день и забирай халявный бонус на счет!',
            'spin_btn': 'КРУТИТЬ КОЛЕСО'
        },
        'kz': {
            'title': 'EGORVAULT — Элиттік ойындар маркетплейсі',
            'badge': '💎 EGORVAULT v8.5 ELITE STORE',
            'hero_title': 'ЭЛИТАЛЫҚ ОЙЫНДАР МЕН КІЛТТЕР',
            'hero_sub': 'Лицензияларды лезде жеткізу, қауіпсіздік және эксклюзив.',
            'catalog': '🔥 Ойындар каталогы',
            'genre': 'Жанры:',
            'buy': 'КІЛТТІ САТЫП АЛУ',
            'login': 'КІРУ / ТІРКЕЛУ',
            'logout': 'ШЫҒУ',
            'wheel_title': '🎡 СӘТТІЛІК ДОҢҒАЛАҒЫ',
            'wheel_sub': 'Күніне бір рет айналдырып, сыйлық ұтып алыңыз!',
            'spin_btn': 'ДОҢҒАЛАҚТЫ АЙНАЛДЫРУ'
        }
    }
    cur_t = t.get(lang, t['ru'])

    curr_sym = currency_symbols[currency]
    curr_rate = rates[currency]

    games_html = ''
    if not games:
        games_html = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-gray); padding: 40px; font-family: Orbitron, sans-serif;">Каталог пуст. Добавьте первую игру через панель создателя!</div>'
    else:
        for game in games:
            base_price = game.get('price_kzt', 1000)
            converted_price = round(base_price * curr_rate, 2)
            img_url = game.get('image', 'https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=600')
            
            games_html += f'''
                <div class="game-card">
                    <div class="game-img-wrap"><img src="{img_url}" class="game-img"></div>
                    <div class="game-content">
                        <h3 class="game-title">{game.get('title')}</h3>
                        <div class="game-genre">{cur_t['genre']} {game.get('genre')}</div>
                        <div class="price-row"><span class="price">{converted_price} {curr_sym}</span></div>
                        <form action="/checkout/" method="POST">
                            <input type="hidden" name="game_title" value="{game.get('title')}">
                            <input type="hidden" name="price" value="{base_price}">
                            <button type="submit" class="buy-btn">{cur_t['buy']}</button>
                        </form>
                    </div>
                </div>
            '''

    admin_or_login_btn = ('<a href="/admin-dashboard/" class="nav-btn admin-badge">🛡 Админ</a>' if is_admin 
                          else '<button onclick="openAdminModal()" class="nav-btn admin-badge" style="cursor:pointer;">🛡 Создатель</button>')

    username_display = user.get('username', 'Игрок') if user else ''
    user_nav = ('<a href="/profile/" class="nav-btn">👤 ' + str(username_display) + '</a>'
                '<a href="/logout/" class="nav-btn logout-btn">' + cur_t['logout'] + '</a>' if user 
                else '<a href="/register/" class="nav-btn">🔑 ' + cur_t['login'] + '</a>')

    ru_sel = 'selected' if lang == 'ru' else ''
    kz_sel = 'selected' if lang == 'kz' else ''
    kzt_sel = 'selected' if currency == 'KZT' else ''
    rub_sel = 'selected' if currency == 'RUB' else ''
    usd_sel = 'selected' if currency == 'USD' else ''

    def cat_active(c):
        return 'active-cat' if selected_category == c else ''

    html = f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <title>{cur_t['title']}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Plus+Jakarta+Sans:wght@400;600;700&display=swap');
        :root {{ --bg-deep: #080711; --bg-panel: #111022; --accent-cyan: #00f0ff; --accent-purple: #9d00ff; --accent-pink: #ff007f; --text-light: #f3f4f6; --text-gray: #9ca3af; }}
        * {{ box-sizing: border-box; }}
        body {{ font-family: 'Plus Jakarta Sans', sans-serif; background: var(--bg-deep); color: var(--text-light); margin: 0; padding: 0; overflow-x: hidden; }}
        .ticker-wrap {{ width: 100%; background: #0b091a; border-bottom: 1px solid rgba(157,0,255,0.2); overflow: hidden; white-space: nowrap; padding: 10px 0; font-family: 'Orbitron', sans-serif; font-size: 12px; color: var(--accent-cyan); letter-spacing: 1px; }}
        .ticker {{ display: inline-block; animation: ticker 32s linear infinite; }}
        .ticker span {{ margin-right: 60px; }}
        @keyframes ticker {{ 0% {{ transform: translate3d(0, 0, 0); }} 100% {{ transform: translate3d(-50%, 0, 0); }} }}
        header {{ background: rgba(11, 9, 26, 0.9); backdrop-filter: blur(16px); border-bottom: 1px solid rgba(0,240,255,0.15); padding: 18px 50px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 1000; box-shadow: 0 10px 30px rgba(0,0,0,0.6); }}
        .logo {{ font-family: 'Orbitron', sans-serif; font-size: 26px; font-weight: 900; background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-decoration: none; letter-spacing: 2px; }}
        .controls {{ display: flex; gap: 14px; align-items: center; }}
        select {{ background: #16132d; color: var(--accent-cyan); border: 1px solid rgba(0,240,255,0.3); padding: 8px 14px; border-radius: 8px; font-family: 'Orbitron', sans-serif; font-weight: bold; font-size: 12px; cursor: pointer; outline: none; }}
        .nav-btn {{ background: rgba(0,240,255,0.05); color: var(--accent-cyan); border: 1px solid rgba(0,240,255,0.3); padding: 9px 18px; border-radius: 8px; text-decoration: none; font-family: 'Orbitron', sans-serif; font-size: 13px; font-weight: 700; transition: 0.3s; }}
        .nav-btn:hover {{ background: var(--accent-cyan); color: #080711; box-shadow: 0 0 20px var(--accent-cyan); }}
        .admin-badge {{ border-color: rgba(255,0,127,0.4) !important; color: var(--accent-pink) !important; background: rgba(255,0,127,0.05) !important; }}
        .admin-badge:hover {{ background: var(--accent-pink) !important; color: #fff !important; box-shadow: 0 0 20px var(--accent-pink) !important; }}
        .logout-btn {{ border-color: rgba(255,0,127,0.4); color: var(--accent-pink); }}
        .logout-btn:hover {{ background: var(--accent-pink); color: #fff; box-shadow: 0 0 20px var(--accent-pink); }}
        .hero {{ text-align: center; padding: 70px 20px 40px; background: radial-gradient(circle at center, rgba(157,0,255,0.12) 0%, transparent 70%); }}
        .badge {{ background: rgba(157,0,255,0.15); color: #d8b4fe; padding: 6px 18px; border-radius: 30px; font-family: 'Orbitron', sans-serif; font-size: 11px; letter-spacing: 2px; border: 1px solid rgba(157,0,255,0.4); display: inline-block; margin-bottom: 20px; box-shadow: 0 0 20px rgba(157,0,255,0.3); }}
        .hero h1 {{ font-family: 'Orbitron', sans-serif; font-size: 44px; margin: 0 0 15px; color: #fff; text-shadow: 0 0 25px rgba(0,240,255,0.3); letter-spacing: 2px; }}
        .hero p {{ color: var(--text-gray); font-size: 17px; max-width: 600px; margin: 0 auto; line-height: 1.5; }}
        .categories-bar {{ display: flex; gap: 12px; justify-content: center; margin-bottom: 35px; flex-wrap: wrap; }}
        .cat-btn {{ background: var(--bg-panel); color: var(--text-gray); border: 1px solid rgba(255,255,255,0.08); padding: 10px 20px; border-radius: 30px; font-family: 'Orbitron', sans-serif; font-size: 12px; font-weight: bold; text-decoration: none; transition: 0.3s; }}
        .cat-btn:hover, .cat-btn.active-cat {{ background: var(--accent-cyan); color: var(--bg-deep); border-color: var(--accent-cyan); box-shadow: 0 0 20px rgba(0,240,255,0.4); }}
        .container {{ max-width: 1280px; margin: 0 auto 60px; padding: 0 30px; }}
        .section-title {{ font-family: 'Orbitron', sans-serif; font-size: 24px; border-left: 4px solid var(--accent-cyan); padding-left: 15px; margin-bottom: 30px; color: #fff; text-shadow: 0 0 15px rgba(0,240,255,0.3); }}
        .game-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 30px; }}
        .game-card {{ background: var(--bg-panel); border: 1px solid rgba(255,255,255,0.06); border-radius: 16px; overflow: hidden; transition: 0.4s cubic-bezier(0.16, 1, 0.3, 1); box-shadow: 0 15px 35px rgba(0,0,0,0.6); }}
        .game-card:hover {{ transform: translateY(-8px); border-color: var(--accent-cyan); box-shadow: 0 20px 45px rgba(0,240,255,0.25); }}
        .game-img-wrap {{ width: 100%; height: 200px; overflow: hidden; position: relative; }}
        .game-img {{ width: 100%; height: 100%; object-fit: cover; transition: 0.6s ease; }}
        .game-card:hover .game-img {{ transform: scale(1.08); }}
        .game-content {{ padding: 25px; }}
        .game-title {{ font-family: 'Orbitron', sans-serif; font-size: 20px; font-weight: 700; color: #fff; margin: 0 0 8px; }}
        .game-genre {{ color: var(--accent-cyan); font-size: 13px; font-weight: 700; text-transform: uppercase; margin-bottom: 20px; letter-spacing: 1px; }}
        .price-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
        .price {{ font-family: 'Orbitron', sans-serif; font-size: 24px; font-weight: 900; color: var(--accent-cyan); text-shadow: 0 0 12px rgba(0,240,255,0.4); }}
        .buy-btn {{ background: linear-gradient(135deg, var(--accent-cyan) 0%, #0077ff 100%); color: #080711; width: 100%; padding: 14px; border: none; border-radius: 10px; font-family: 'Orbitron', sans-serif; font-weight: 900; font-size: 13px; cursor: pointer; transition: 0.3s; letter-spacing: 1px; box-shadow: 0 0 20px rgba(0,240,255,0.3); }}
        .buy-btn:hover {{ background: #fff; box-shadow: 0 0 30px var(--accent-cyan); transform: translateY(-2px); }}
        footer {{ background: #05040a; border-top: 1px solid rgba(0,240,255,0.15); padding: 30px 50px; text-align: center; margin-top: 80px; }}
        .security-badges {{ display: flex; justify-content: center; gap: 30px; margin-bottom: 15px; flex-wrap: wrap; font-size: 14px; color: var(--text-gray); font-weight: 600; }}
        .security-badge-item {{ display: flex; align-items: center; gap: 8px; }}
        .wheel-trigger-btn {{ position: fixed; bottom: 30px; left: 30px; background: linear-gradient(135deg, var(--accent-purple), var(--accent-pink)); color: #fff; border: none; padding: 14px 22px; border-radius: 50px; font-family: 'Orbitron', sans-serif; font-weight: 900; font-size: 14px; cursor: pointer; z-index: 9998; box-shadow: 0 0 25px rgba(157,0,255,0.5); transition: 0.3s; display: flex; align-items: center; gap: 8px; }}
        .wheel-trigger-btn:hover {{ transform: scale(1.05); box-shadow: 0 0 35px var(--accent-pink); }}
        .wheel-drawer {{ display: none; position: fixed; bottom: 100px; left: 30px; width: 380px; background: var(--bg-panel); border: 1px solid rgba(0,240,255,0.3); border-radius: 20px; padding: 25px; text-align: center; z-index: 9999; box-shadow: 0 20px 60px rgba(0,0,0,0.9); }}
        .drawer-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; font-family: 'Orbitron', sans-serif; font-size: 16px; color: var(--accent-cyan); }}
        .wheel-container {{ position: relative; width: 220px; height: 220px; margin: 15px auto; }}
        .wheel {{ width: 100%; height: 100%; border-radius: 50%; border: 4px solid var(--accent-cyan); position: relative; overflow: hidden; transition: transform 4s cubic-bezier(0.15, 0.95, 0.2, 1); box-shadow: 0 0 30px rgba(0,240,255,0.3); }}
        .sector {{ position: absolute; width: 50%; height: 50%; top: 0; left: 50%; transform-origin: 0% 100%; display: flex; align-items: center; justify-content: flex-start; padding-left: 20px; font-family: 'Orbitron', sans-serif; font-weight: 900; font-size: 11px; color: #fff; text-shadow: 0 0 2px #000; }}
        .s1 {{ background: var(--accent-pink); transform: rotate(0deg) skewY(-30deg); }}
        .s2 {{ background: var(--accent-cyan); color: #080711 !important; text-shadow: none !important; transform: rotate(60deg) skewY(-30deg); }}
        .s3 {{ background: var(--accent-purple); transform: rotate(120deg) skewY(-30deg); }}
        .s4 {{ background: #f59e0b; color: #080711 !important; text-shadow: none !important; transform: rotate(180deg) skewY(-30deg); }}
        .s5 {{ background: #10b981; transform: rotate(240deg) skewY(-30deg); }}
        .s6 {{ background: #3b82f6; transform: rotate(300deg) skewY(-30deg); }}
        .wheel-pointer {{ position: absolute; top: -12px; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent; border-top: 16px solid #fff; z-index: 10; filter: drop-shadow(0 0 6px var(--accent-cyan)); }}
        .spin-btn-drawer {{ background: linear-gradient(135deg, var(--accent-cyan), #0077ff); color: #080711; border: none; padding: 12px 24px; font-family: 'Orbitron', sans-serif; font-weight: 900; font-size: 13px; border-radius: 8px; cursor: pointer; width: 100%; transition: 0.3s; box-shadow: 0 0 20px rgba(0,240,255,0.4); }}
        .spin-btn-drawer:hover {{ background: #fff; box-shadow: 0 0 30px var(--accent-cyan); }}
        .spin-btn-drawer:disabled {{ background: #1f1b38; color: var(--text-gray); cursor: not-allowed; box-shadow: none; }}
        .modal, .prize-modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(8,7,17,0.85); backdrop-filter: blur(12px); z-index: 2000; justify-content: center; align-items: center; }}
        .modal-content, .prize-content {{ background: var(--bg-panel); padding: 40px; border-radius: 20px; border: 1px solid rgba(0,240,255,0.3); width: 400px; text-align: center; box-shadow: 0 20px 50px rgba(0,0,0,0.9); }}
        .modal input {{ width: 100%; padding: 14px; margin-bottom: 20px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); background: #080711; color: #fff; font-size: 16px; outline: none; }}
        .prize-title {{ font-family: 'Orbitron', sans-serif; font-size: 28px; color: var(--accent-cyan); font-weight: 900; margin-bottom: 15px; text-shadow: 0 0 20px rgba(0,240,255,0.6); }}
        .prize-value {{ font-family: 'Orbitron', sans-serif; font-size: 38px; color: #fff; margin: 20px 0; background: rgba(0,240,255,0.08); padding: 15px; border-radius: 12px; border: 1px dashed var(--accent-cyan); }}
        .support-widget {{ position: fixed; bottom: 30px; right: 30px; z-index: 9999; font-family: 'Plus Jakarta Sans', sans-serif; }}
        .support-btn {{ width: 65px; height: 65px; background: linear-gradient(135deg, var(--accent-cyan), #0077ff); border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; box-shadow: 0 0 25px rgba(0,240,255,0.5); font-size: 28px; transition: 0.3s; }}
        .support-btn:hover {{ transform: scale(1.1); box-shadow: 0 0 35px var(--accent-cyan); }}
        .support-window {{ display: none; position: absolute; bottom: 80px; right: 0; width: 380px; background: var(--bg-panel); border: 1px solid rgba(0,240,255,0.3); border-radius: 16px; box-shadow: 0 15px 50px rgba(0,0,0,0.9); overflow: hidden; }}
        .support-header {{ background: #0b091a; padding: 16px; font-family: 'Orbitron', sans-serif; font-weight: 700; font-size: 14px; color: var(--accent-cyan); display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        .support-body {{ padding: 15px; height: 250px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; font-size: 14px; }}
        .support-msg {{ background: #16132d; padding: 10px 14px; border-radius: 10px; max-width: 85%; line-height: 1.4; color: #fff; }}
        .support-msg.bot {{ align-self: flex-start; border-left: 3px solid var(--accent-cyan); }}
        .support-msg.user {{ align-self: flex-end; background: var(--accent-cyan); color: #080711; font-weight: bold; }}
        .support-msg.admin {{ align-self: flex-start; background: rgba(255,0,127,0.15); border-left: 3px solid var(--accent-pink); color: #fff; }}
        .faq-chips {{ display: flex; gap: 6px; padding: 0 12px 10px; overflow-x: auto; }}
        .faq-chip {{ background: #16132d; border: 1px solid rgba(0,240,255,0.3); color: var(--accent-cyan); padding: 6px 12px; border-radius: 20px; font-size: 11px; font-family: 'Orbitron', sans-serif; cursor: pointer; white-space: nowrap; }}
        .faq-chip:hover {{ background: var(--accent-cyan); color: #080711; }}
        .support-footer {{ padding: 12px; background: #0b091a; border-top: 1px solid rgba(255,255,255,0.05); display: flex; gap: 8px; }}
        .support-footer input {{ flex: 1; padding: 10px 14px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); background: #080711; color: #fff; outline: none; font-size: 14px; margin: 0; }}
        .support-footer button {{ background: var(--accent-cyan); color: #080711; border: none; padding: 10px 16px; border-radius: 8px; font-family: 'Orbitron', sans-serif; font-weight: bold; cursor: pointer; }}
        .admin-call-btn {{ background: var(--accent-pink) !important; color: #fff !important; width: 100%; margin-top: 5px; padding: 10px; border: none; border-radius: 8px; font-family: 'Orbitron', sans-serif; font-weight: bold; cursor: pointer; font-size: 12px; transition: 0.3s; }}
        .admin-call-btn:hover {{ opacity: 0.9; box-shadow: 0 0 15px var(--accent-pink); }}
    </style>
    <script>
        function openAdminModal() {{ document.getElementById("adminModal").style.display = "flex"; }}
        function closeAdminModal() {{ document.getElementById("adminModal").style.display = "none"; }}
        function toggleWheelDrawer() {{ const drawer = document.getElementById("wheelDrawer"); drawer.style.display = drawer.style.display === "block" ? "none" : "block"; }}
        function toggleSupport() {{ const win = document.getElementById("supportWindow"); win.style.display = win.style.display === "block" ? "none" : "block"; if(win.style.display === "block") {{ loadChatMessages(); }} }}
        function sendFaq(text) {{ document.getElementById("supportInput").value = text; sendSupportMsg(); }}
        function sendSupportMsg() {{
            const input = document.getElementById("supportInput");
            const text = input.value.trim();
            if (!text) return;
            const body = document.getElementById("supportBody");
            body.innerHTML += '<div class="support-msg user">' + text + '</div>';
            input.value = "";
            body.scrollTop = body.scrollHeight;
            const formData = new URLSearchParams();
            formData.append("message", text);
            fetch("/ai-chat/", {{ method: "POST", body: formData }})
            .then(res => res.json())
            .then(data => {{
                if(data.reply) {{
                    body.innerHTML += '<div class="support-msg bot">' + data.reply + '</div>';
                    body.scrollTop = body.scrollHeight;
                }}
            }});
        }}
        function callAdmin() {{
            fetch("/call-admin/", {{ method: "POST" }})
            .then(res => res.json())
            .then(data => {{
                const body = document.getElementById("supportBody");
                body.innerHTML += '<div class="support-msg bot" style="border-color: var(--accent-pink); color: var(--accent-pink);">⚠️ Запрос отправлен создателю Егору! Ожидайте ответа в этом чате.</div>';
                body.scrollTop = body.scrollHeight;
                alert("⚠️ Уведомление доставлено создателю!");
            }});
        }}
        function loadChatMessages() {{
            fetch("/get-chat/")
            .then(res => res.json())
            .then(data => {{
                const body = document.getElementById("supportBody");
                let html = '<div class="support-msg bot">🤖 Привет! Выберите тему ниже или задайте вопрос.</div>';
                if(data.messages && data.messages.length > 0) {{
                    data.messages.forEach(m => {{
                        if(m.sender === "user") {{ html += '<div class="support-msg user">' + m.text + '</div>'; }}
                        else if(m.sender === "admin") {{ html += '<div class="support-msg admin">🛡 Создатель: ' + m.text + '</div>'; }}
                        else {{ html += '<div class="support-msg bot">' + m.text + '</div>'; }}
                    }});
                }}
                body.innerHTML = html;
                body.scrollTop = body.scrollHeight;
            }});
        }}
        setInterval(function() {{
            const win = document.getElementById("supportWindow");
            if(win && win.style.display === "block") {{ loadChatMessages(); }}
        }}, 4000);
        window.onload = function() {{
            const lastSpin = localStorage.getItem("last_spin_date");
            const today = new Date().toDateString();
            if (lastSpin === today) {{
                const btn = document.getElementById("spinButton");
                if(btn) {{ btn.innerText = "УЖЕ КРУТИЛИ СЕГОДНЯ"; btn.disabled = true; }}
            }}
        }};
        function spinWheel() {{
            const lastSpin = localStorage.getItem("last_spin_date");
            const today = new Date().toDateString();
            if (lastSpin === today) {{ alert("Вы уже использовали попытку колеса сегодня!"); return; }}
            const wheel = document.getElementById("wheel");
            const prizes = ["+500 ₸", "+1000 ₸", "+2000 ₸", "Скидка 20%", "Бонус x2", "+5000 ₸"];
            const randomDegree = 360 * 6 + Math.floor(Math.random() * 360);
            wheel.style.transform = "rotate(" + randomDegree + "deg)";
            localStorage.setItem("last_spin_date", today);
            document.getElementById("spinButton").disabled = true;
            document.getElementById("spinButton").innerText = "ОБРАБОТКА...";
            setTimeout(function() {{
                const winningPrize = prizes[Math.floor(Math.random() * prizes.length)];
                document.getElementById("prizeText").innerText = winningPrize;
                document.getElementById("prizeModal").style.display = "flex";
            }}, 4000);
        }}
        function closePrizeModal() {{ document.getElementById("prizeModal").style.display = "none"; location.reload(); }}
    </script>
</head>
<body>
    <div class="ticker-wrap"><div class="ticker">
        <span>🔥 Игрок <b>CyberGod</b> купил <b>Cyber Legends 2077</b></span>
        <span>⚡ Пользователь <b>{username_display if username_display else 'Egor'}</b> активировал ключ <b>Void Striker</b></span>
        <span>💎 <b>Alisher99</b> пополнил баланс с банковской карты</span>
    </div></div>
    <header>
        <a href="/" class="logo">⚡ EGORVAULT</a>
        <div class="controls">
            <form method="GET" style="display:inline; display:flex; gap:10px;">
                <select name="lang" onchange="this.form.submit()"><option value="ru" {ru_sel}>🇷🇺 RU</option><option value="kz" {kz_sel}>🇰🇿 KZ</option></select>
                <select name="currency" onchange="this.form.submit()"><option value="KZT" {kzt_sel}>KZT (₸)</option><option value="RUB" {rub_sel}>RUB (₽)</option><option value="USD" {usd_sel}>USD ($)</option></select>
            </form>
            {admin_or_login_btn}
            {user_nav}
        </div>
    </header>
    <div id="adminModal" class="modal">
        <div class="modal-content">
            <h2 style="font-family:Orbitron,sans-serif; color:var(--accent-pink); margin-top:0;">🛡 ВХОД СОЗДАТЕЛЯ</h2>
            <form action="/admin-login/" method="POST">
                <input type="text" name="login" placeholder="Логин создателя" required>
                <input type="password" name="password" placeholder="Пароль" required>
                <button type="submit" style="width:100%; padding:14px; background:var(--accent-pink); color:#fff; border:none; border-radius:10px; font-weight:900; font-family:Orbitron,sans-serif; cursor:pointer;">ВОЙТИ</button>
            </form><br>
            <button onclick="closeAdminModal()" style="background:transparent; border:none; color:var(--text-gray); cursor:pointer; font-weight:bold;">Отмена</button>
        </div>
    </div>
    <div id="prizeModal" class="prize-modal"><div class="prize-content">
        <div class="prize-title">🎉 ПОЗДРАВЛЯЕМ!</div>
        <p style="color:var(--text-gray); font-size: 15px;">В Колесе Удачи вам выпал бонус:</p>
        <div class="prize-value" id="prizeText">+1000 ₸</div>
        <button onclick="closePrizeModal()" class="buy-btn" style="width:100%;">ЗАБРАТЬ БОНУС</button>
    </div></div>
    <div class="hero"><span class="badge">{cur_t['badge']}</span><h1>{cur_t['hero_title']}</h1><p>{cur_t['hero_sub']}</p></div>
    <div class="container">
        <div class="categories-bar">
            <a href="/?category=all" class="cat-btn {cat_active('all')}">⚡ Все игры</a>
            <a href="/?category=action" class="cat-btn {cat_active('action')}">🔥 Экшены & Шутеры</a>
            <a href="/?category=rpg" class="cat-btn {cat_active('rpg')}">🛡 RPG & Киберпанк</a>
            <a href="/?category=strategy" class="cat-btn {cat_active('strategy')}">🧩 Инди & Стратегии</a>
        </div>
        <h2 class="section-title">{cur_t['catalog']}</h2>
        <div class="game-grid">{games_html}</div>
    </div>
    <button class="wheel-trigger-btn" onclick="toggleWheelDrawer()">🎡 Колесо удачи</button>
    <div class="wheel-drawer" id="wheelDrawer">
        <div class="drawer-header"><span>{cur_t['wheel_title']}</span><span onclick="toggleWheelDrawer()" style="cursor:pointer; font-size:18px;">✕</span></div>
        <p style="color:var(--text-gray); font-size: 13px; margin-bottom: 15px;">{cur_t['wheel_sub']}</p>
        <div class="wheel-container"><div class="wheel-pointer"></div><div id="wheel" class="wheel">
            <div class="sector s1">+500₸</div><div class="sector s2">+1000₸</div><div class="sector s3">+2000₸</div><div class="sector s4">Скидка</div><div class="sector s5">Бонус x2</div><div class="sector s6">+5000₸</div>
        </div></div>
        <button id="spinButton" onclick="spinWheel()" class="spin-btn-drawer">{cur_t['spin_btn']}</button>
    </div>
    <div class="support-widget">
        <div class="support-btn" onclick="toggleSupport()">💬</div>
        <div class="support-window" id="supportWindow">
            <div class="support-header">🤖 AI Поддержка EGORVAULT <span onclick="toggleSupport()" style="cursor:pointer;">✕</span></div>
            <div class="support-body" id="supportBody"><div class="support-msg bot">🤖 Привет! Выберите тему ниже или задайте вопрос.</div></div>
            <div class="faq-chips">
                <div class="faq-chip" onclick="sendFaq('Цены')">💰 Цены</div><div class="faq-chip" onclick="sendFaq('Пополнение')">💳 Пополнение</div><div class="faq-chip" onclick="sendFaq('Ключ')">🔑 Ключи</div><div class="faq-chip" onclick="sendFaq('Гарантии')">🛡 Гарантии</div>
            </div>
            <div style="padding: 0 12px 8px;"><button onclick="callAdmin()" class="admin-call-btn">⚠️ ПОЗВАТЬ ЖИВОГО АДМИНА</button></div>
            <div class="support-footer"><input type="text" id="supportInput" placeholder="Написать сообщение..." onkeydown="if(event.key==='Enter') sendSupportMsg()"><button onclick="sendSupportMsg()">➤</button></div>
        </div>
    </div>
    <footer>
        <div class="security-badges"><div class="security-badge-item">🔒 256-Bit SSL Secured</div><div class="security-badge-item">🛡 Официальная гарантия ключей</div><div class="security-badge-item">⚡ Моментальная выдача 24/7</div><div class="security-badge-item">💳 Защита платежей PCI DSS</div></div>
        <p style="color: var(--text-gray); font-size: 13px; margin: 0;">© 2026 EGORVAULT. Все права защищены. Создатель: Егор.</p>
    </footer>
</body>
</html>'''
    
    response = HttpResponse(html)
    response.set_cookie('lang', lang)
    response.set_cookie('currency', currency)
    return response

@csrf_exempt
def checkout_view(request):
    if request.method == 'POST':
        game_title = request.POST.get('game_title')
        price = request.POST.get('price')
        html = f'''<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>Оплата заказа — EGORVAULT</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Plus+Jakarta+Sans:wght@500;700&display=swap');
            body {{ font-family: 'Plus Jakarta Sans', sans-serif; background: #080711; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
            .checkout-box {{ background: #111022; padding: 40px; border-radius: 16px; border: 1px solid #00f0ff; width: 420px; text-align: center; box-shadow: 0 15px 50px rgba(0,0,0,0.9); }}
            .btn {{ background: #00f0ff; color: #080711; padding: 14px; border-radius: 8px; font-family: 'Orbitron', sans-serif; font-weight: 900; border: none; cursor: pointer; width: 100%; font-size: 15px; transition: 0.3s; }}
            .btn:hover {{ background: #fff; box-shadow: 0 0 25px #00f0ff; }}
        </style></head><body>
        <div class="checkout-box">
            <h2 style="font-family:Orbitron,sans-serif; color:#00f0ff; margin-top:0;">💳 СТРАНИЦА ОПЛАТЫ</h2>
            <p style="color:#9ca3af; font-size:15px;">Вы приобретаете товар:</p>
            <h3 style="font-family:Orbitron,sans-serif; font-size:20px; color:#fff;">{game_title}</h3>
            <p style="font-size:24px; font-weight:bold; color:#00f0ff; font-family:Orbitron,sans-serif; margin:20px 0;">К оплате: {price} ₸</p>
            <form action="/buy/" method="POST">
                <input type="hidden" name="game_title" value="{game_title}">
                <input type="hidden" name="price" value="{price}">
                <button type="submit" class="btn">ПОДТВЕРДИТЬ И СПИСАТЬ С БАЛАНСА</button>
            </form><br><a href="/" style="color:#9ca3af; text-decoration:none; font-size:13px;">← Отменить и вернуться в каталог</a>
        </div></body></html>'''
        return HttpResponse(html)
    return redirect('home')

@csrf_exempt
def ai_chat_view(request):
    if request.method == 'POST':
        user_email = request.COOKIES.get('user_email', 'Гость')
        user_message = request.POST.get('message', '')
        ai_reply = ai_generate_response(user_message)
        chat_messages_collection.insert_one({"email": user_email, "sender": "user", "text": user_message})
        chat_messages_collection.insert_one({"email": user_email, "sender": "bot", "text": ai_reply})
        return HttpResponse('{"reply": "' + ai_reply + '"}', content_type="application/json")
    return HttpResponse('{"reply": "Ошибка запроса"}', content_type="application/json")

@csrf_exempt
def get_chat_messages(request):
    user_email = request.COOKIES.get('user_email', 'Гость')
    messages = list(chat_messages_collection.find({"email": user_email}).sort("_id", 1))
    formatted = [{"sender": m.get("sender"), "text": m.get("text")} for m in messages]
    return HttpResponse(json.dumps({"messages": formatted}), content_type="application/json")

@csrf_exempt
def call_admin_view(request):
    if request.method == 'POST':
        user_email = request.COOKIES.get('user_email', 'Гость')
        support_collection.update_one({"email": user_email}, {"$set": {"status": "active", "last_message": "Пользователь позвал создателя!"}}, upsert=True)
        chat_messages_collection.insert_one({"email": user_email, "sender": "bot", "text": "⚠️ Запрос отправлен создателю Егору! Ожидайте ответа в чате."})
        log_admin_action(f"Пользователь {user_email} запросил живого админа в тикетах.")
        return HttpResponse('{"status": "success"}', content_type="application/json")
    return HttpResponse('{"status": "error"}', content_type="application/json")

@csrf_exempt
def buy_game(request):
    if request.method == 'POST':
        user_email = request.COOKIES.get('user_email')
        if not user_email: return redirect('register')
        game_title = request.POST.get('game_title')
        price = float(request.POST.get('price', 0))
        user = users_collection.find_one({"email": user_email})
        if user and user.get('balance', 0) >= price:
            users_collection.update_one({"email": user_email}, {"$inc": {"balance": -price}})
            activation_key = generate_game_key()
            orders_collection.insert_one({
                "email": user_email, 
                "title": game_title, 
                "price": price,
                "key": activation_key,
                "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
                "status": "Выполнен",
                "payment_method": "Баланс аккаунта"
            })
            log_admin_action(f"Создан новый заказ: {game_title} для {user_email} на сумму {price} ₸")
            return redirect('/success/?title=' + game_title + '&key=' + activation_key)
        else:
            return HttpResponse(
                '<body style="background:#080711;color:#fff;text-align:center;padding-top:120px;font-family:sans-serif;">'
                '<h2 style="color:#ff007f;font-family:Orbitron,sans-serif;">❌ НЕДОСТАТОЧНО СРЕДСТВ НА БАЛАНСЕ!</h2>'
                '<a href="/profile/" style="background:#00f0ff;color:#080711;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;">← Пополнить баланс в профиле</a>'
                '</body>'
            )
    return redirect('home')

def success_buy(request):
    title = request.GET.get('title', 'Игра')
    key = request.GET.get('key', 'XXXX-XXXX-XXXX')
    html = f'''<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>Покупка успешна — EGORVAULT</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Plus+Jakarta+Sans:wght@500;700&display=swap');
        body {{ font-family: 'Plus Jakarta Sans', sans-serif; background: #080711; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
        .card {{ background: #111022; padding: 40px; border-radius: 16px; border: 1px solid #00f0ff; text-align: center; max-width: 500px; box-shadow: 0 10px 40px rgba(0,0,0,0.9); }}
        .key-box {{ background: #080711; border: 2px dashed #00f0ff; padding: 15px; font-family: 'Orbitron', sans-serif; font-size: 22px; color: #00f0ff; margin: 20px 0; border-radius: 8px; letter-spacing: 2px; }}
        .btn {{ background: #00f0ff; color: #080711; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-family: 'Orbitron', sans-serif; font-weight: 900; border: none; cursor: pointer; transition: 0.3s; display: inline-block; margin-top: 10px; }}
        .btn:hover {{ background: #fff; box-shadow: 0 0 20px #00f0ff; }}
    </style><script>function copyKey() {{ navigator.clipboard.writeText(document.getElementById("gameKey").innerText); alert("🔑 Ключ успешно скопирован в буфер обмена!"); }}</script>
    </head><body><div class="card">
        <h1 style="font-family:Orbitron,sans-serif; color:#00f0ff; margin-top:0;">🎉 ПОКУПКА УСПЕШНА!</h1>
        <p style="color:#9ca3af;">Лицензионный ключ для вашей игры сохранен в БД:</p>
        <h3 style="font-family:Orbitron,sans-serif; font-size:20px;">{title}</h3>
        <div class="key-box" id="gameKey">{key}</div>
        <button onclick="copyKey()" class="btn">📋 СКОПИРОВАТЬ КЛЮЧ</button><br><br>
        <a href="/profile/" style="color:#00f0ff; text-decoration:none; font-weight:bold;">Перейти в личный кабинет →</a>
    </div></body></html>'''
    return HttpResponse(html)

@csrf_exempt
def register_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        action = request.POST.get('action')
        if action == 'send_code':
            code = str(random.randint(1000, 9999))
            codes_collection.update_one({"email": email}, {"$set": {"code": code}}, upsert=True)
            return HttpResponse(f'''
                <body style="background:#080711;color:#fff;font-family:sans-serif;text-align:center;padding-top:100px;">
                <div style="background:#111022;padding:40px;border-radius:14px;display:inline-block;border:1px solid #00f0ff;max-width:400px;box-shadow:0 10px 30px rgba(0,240,255,0.2)">
                <h2 style="font-family:Orbitron,sans-serif;color:#00f0ff;margin-top:0;">КОД ОТПРАВЛЕН В БД</h2>
                <p style="color:#9ca3af;">Код подтверждения для почты <b>{email}</b>:</p>
                <div style="background:#080711;border:2px dashed #00f0ff;padding:15px;border-radius:8px;margin:20px 0;"><span style="color:#fff;font-size:36px;font-family:Orbitron,sans-serif;letter-spacing:5px;font-weight:bold;">{code}</span></div>
                <form method="POST"><input type="hidden" name="email" value="{email}"><input type="hidden" name="action" value="verify_code">
                <input type="text" name="code" placeholder="Введите 4 цифры" required style="width:100%;padding:14px;font-size:18px;border-radius:8px;border:1px solid #00f0ff;text-align:center;background:#080711;color:#fff;box-sizing:border-box;outline:none;letter-spacing:3px;margin-bottom:15px;"><br>
                <button type="submit" style="background:#00f0ff;color:#080711;padding:14px 28px;border:none;font-weight:900;border-radius:8px;cursor:pointer;font-family:Orbitron,sans-serif;width:100%;">ПОДТВЕРДИТЬ КОД</button></form>
                <br><a href="/register/" style="color:#9ca3af;text-decoration:none;font-size:13px;">← Назад</a></div></body>
            ''')
        elif action == 'verify_code':
            entered_code = request.POST.get('code')
            email = request.POST.get('email')
            saved = codes_collection.find_one({"email": email})
            if saved and str(saved.get('code')) == str(entered_code):
                if not users_collection.find_one({"email": email}):
                    users_collection.insert_one({
                        "email": email, 
                        "username": email.split('@')[0], 
                        "balance": 10000, 
                        "avatar": "https://i.imgur.com/6VBx3io.png",
                        "reg_date": datetime.now().strftime("%d.%m.%Y")
                    })
                response = redirect('home')
                response.set_cookie('user_email', email, max_age=30*24*60*60)
                return response
            else:
                return HttpResponse(
                    '<body style="background:#080711;color:#fff;font-family:sans-serif;text-align:center;padding-top:120px;">'
                    '<h2 style="color:#ff007f;font-family:Orbitron,sans-serif;">❌ НЕВЕРНЫЙ КОД ИЗ БД!</h2>'
                    '<a href="/register/" style="background:#00f0ff;color:#080711;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;display:inline-block;margin-top:20px;">← Попробовать снова</a></body>'
                )
    return HttpResponse('''
        <!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>Авторизация — EGORVAULT</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Plus+Jakarta+Sans:wght@500;700&display=swap');
            body { font-family: 'Plus Jakarta Sans', sans-serif; background: #080711; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .auth-card { background: #111022; padding: 40px; border-radius: 16px; width: 380px; text-align: center; border: 1px solid #00f0ff; box-shadow: 0 10px 40px rgba(0,0,0,0.9); }
            input { width: 100%; padding: 14px; margin-bottom: 20px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); background: #080711; color: #fff; font-size: 16px; box-sizing: border-box; outline: none; }
            .btn { width: 100%; padding: 14px; background: #00f0ff; color: #080711; border: none; border-radius: 8px; font-weight: 900; font-family: 'Orbitron', sans-serif; cursor: pointer; transition: 0.3s; }
            .btn:hover { background: #fff; box-shadow: 0 0 20px #00f0ff; }
        </style></head><body><div class="auth-card">
            <a href="/" style="color: #00f0ff; text-decoration: none; font-family: Orbitron, sans-serif; font-size: 12px; font-weight: bold; display: block; margin-bottom: 20px;">← НА ГЛАВНУЮ</a>
            <h2 style="font-family:Orbitron,sans-serif; color:#00f0ff; margin-top:0; margin-bottom:20px;">ВХОД / РЕГИСТРАЦИЯ</h2>
            <form method="POST"><input type="hidden" name="action" value="send_code"><input type="email" name="email" placeholder="Ваша почта" required><button type="submit" class="btn">ПОЛУЧИТЬ КОД НА ПОЧТУ</button></form>
        </div></body></html>
    ''')

@csrf_exempt
def profile_view(request):
    user_email = request.COOKIES.get('user_email')
    if not user_email: return redirect('register')
    success_msg = ""
    if request.method == 'POST':
        if 'top_up' in request.POST:
            amount = float(request.POST.get('amount', 0))
            if amount > 0:
                users_collection.update_one({"email": user_email}, {"$inc": {"balance": amount}})
                success_msg = f"Успешно зачислено {amount} ₸!"
        elif 'update_profile' in request.POST:
            new_username = request.POST.get('username')
            update_data = {"username": new_username}
            avatar_file = request.FILES.get('avatar_file')
            if avatar_file:
                encoded_file = base64.b64encode(avatar_file.read()).decode('utf-8')
                update_data["avatar"] = f"data:{avatar_file.content_type};base64,{encoded_file}"
            users_collection.update_one({"email": user_email}, {"$set": update_data})
            return redirect('profile')

    user = users_collection.find_one({"email": user_email})
    my_orders = list(orders_collection.find({"email": user_email}))
    total_spent = sum(item.get('price', 0) for item in my_orders)
    orders_html = ""
    if not my_orders:
        orders_html = "<p style='color: #9ca3af;'>У вас пока нет купленных игр.</p>"
    else:
        for order in my_orders:
            orders_html += f'''
                <div class="order-item">
                    <div>
                        <span>🎮 <strong style="font-family: Orbitron, sans-serif; color: #fff;">{order.get('title')}</strong></span><br>
                        <span style="color: var(--accent-cyan); font-family: Orbitron, sans-serif; font-size: 14px;">Ключ: {order.get('key')}</span>
                    </div>
                    <span style="color: var(--accent-cyan); font-family: Orbitron, sans-serif; font-weight: bold;">{order.get('price')} ₸</span>
                </div>
            '''
    success_banner = f'<div style="background:rgba(0,240,255,0.15);border:1px solid #00f0ff;color:#00f0ff;padding:12px;border-radius:8px;margin-top:20px;font-weight:bold;text-align:center;">✅ {success_msg}</div>' if success_msg else ""
    username_val = user.get('username', 'Игрок') if user else ''
    balance_val = user.get('balance', 0) if user else 0
    avatar_val = user.get('avatar', 'https://i.imgur.com/6VBx3io.png') if user else ''

    html = f'''<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>Личный кабинет — EGORVAULT</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Plus+Jakarta+Sans:wght@500;700&display=swap');
        :root {{ --accent-cyan: #00f0ff; }}
        body {{ font-family: 'Plus Jakarta Sans', sans-serif; background: #080711; color: #fff; margin: 0; padding: 40px; }}
        .profile-card {{ max-width: 750px; margin: 0 auto; background: #111022; padding: 40px; border-radius: 16px; box-shadow: 0 10px 40px rgba(0,0,0,0.9); border: 1px solid #00f0ff; }}
        .avatar {{ width: 120px; height: 120px; border-radius: 50%; object-fit: cover; border: 3px solid #00f0ff; box-shadow: 0 0 20px rgba(0,240,255,0.4); }}
        .btn {{ background: #00f0ff; color: #080711; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-family: 'Orbitron', sans-serif; font-weight: 900; border: none; cursor: pointer; transition: 0.3s; }}
        .btn:hover {{ background: #fff; box-shadow: 0 0 20px #00f0ff; }}
        input, select {{ padding: 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); background: #080711; color: #fff; font-size: 15px; outline: none; box-sizing: border-box; }}
        .order-item {{ background: #080711; padding: 15px 20px; border-radius: 10px; margin-bottom: 12px; display: flex; justify-content: space-between; border-left: 4px solid #00f0ff; align-items: center; border: 1px solid rgba(255,255,255,0.05); }}
        .pay-modal {{ background: #16132d; border: 1px solid rgba(0,240,255,0.3); padding: 25px; border-radius: 12px; margin-top: 25px; box-shadow: 0 8px 30px rgba(0,0,0,0.7); }}
        .preset-btn {{ background: #111022; color: #00f0ff; border: 1px solid #00f0ff; padding: 10px 16px; border-radius: 6px; font-family: 'Orbitron', sans-serif; font-weight: bold; cursor: pointer; }}
        .preset-btn:hover {{ background: #00f0ff; color: #080711; }}
    </style><script>function setAmount(val) {{ document.getElementById("amountInput").value = val; }}</script></head><body>
    <div class="profile-card"><a href="/" style="color: #00f0ff; text-decoration: none; font-family: Orbitron, sans-serif; font-weight: bold;">← НА ГЛАВНУЮ В КАТАЛОГ</a>{success_banner}
    <div style="display: flex; align-items: center; margin-top: 30px;">
        <img src="{avatar_val}" class="avatar">
        <div style="margin-left: 30px;"><h2 style="font-family: Orbitron, sans-serif; margin: 0 0 10px; color: #00f0ff;">{username_val}</h2>
        <p style="font-size: 22px; font-weight: bold; margin: 0 0 5px;">Баланс: <span style="color: #00f0ff;">{balance_val} ₸</span></p>
        <p style="color: #9ca3af; margin: 0;">Всего потрачено: {total_spent} ₸</p></div></div>
    <hr style="border-color: rgba(255,255,255,0.1); margin: 35px 0;">
    <div class="pay-modal"><h3 style="font-family: Orbitron, sans-serif; color: #fff; margin-top:0;">💳 ПОПОЛНЕНИЕ БАЛАНСА ИЗ БД</h3>
    <div style="display: flex; gap: 10px; margin-bottom: 15px;"><button type="button" class="preset-btn" onclick="setAmount(1000)">+1 000 ₸</button><button type="button" class="preset-btn" onclick="setAmount(5000)">+5 000 ₸</button><button type="button" class="preset-btn" onclick="setAmount(10000)">+10 000 ₸</button></div>
    <form method="POST"><input type="number" id="amountInput" name="amount" placeholder="Введите сумму (₸)" required style="width: 100%; margin-bottom: 15px;" min="100">
    <button type="submit" name="top_up" class="btn" style="width:100%;">ПОПОЛНИТЬ СЧЕТ</button></form></div>
    <h3 style="font-family: Orbitron, sans-serif; color: #fff; margin-top: 35px;">⚙ НАСТРОЙКИ ПРОФИЛЯ</h3>
    <form method="POST" enctype="multipart/form-data"><input type="text" name="username" value="{username_val}" required style="width: 200px; margin-bottom: 10px; margin-right: 10px;">
    <input type="file" name="avatar_file" accept="image/*" style="color: #00f0ff; margin-bottom: 15px; display: block;"><br><button type="submit" name="update_profile" class="btn">СОХРАНИТЬ</button></form>
    <h3 style="font-family: Orbitron, sans-serif; color: #fff; margin-top: 40px;">🎮 МОИ КУПЛЕННЫЕ ИГРЫ И КЛЮЧИ</h3>{orders_html}
    </div></body></html>'''
    return HttpResponse(html)

@csrf_exempt
def admin_login_action(request):
    if request.method == 'POST':
        login = request.POST.get('login')
        password = request.POST.get('password')
        if login == ADMIN_CREATOR_LOGIN and password == ADMIN_CREATOR_PASS:
            log_admin_action("Создатель вошел в панель управления.")
            response = redirect('/admin-dashboard/')
            response.set_cookie('is_creator', 'true', max_age=7200)
            return response
        else:
            return HttpResponse('<body style="background:#080711;color:#ff007f;text-align:center;padding-top:120px;font-family:sans-serif;"><h2>❌ ОШИБКА ВХОДА!</h2><a href="/" style="color:#00f0ff;">← На главную</a></body>')
    return redirect('home')

@csrf_exempt
def admin_dashboard(request):
    if request.COOKIES.get('is_creator') != 'true':
        return redirect('home')
        
    if request.method == 'POST':
        action_type = request.POST.get('action_type')
        
        if action_type == 'delete_ticket':
            ticket_id = request.POST.get('ticket_id')
            support_collection.delete_one({"_id": ObjectId(ticket_id)})
            log_admin_action("Закрыт тикет поддержки.")
            return redirect('/admin-dashboard/')
            
        elif action_type == 'send_admin_reply':
            target_email = request.POST.get('target_email')
            reply_text = request.POST.get('reply_text')
            if reply_text:
                chat_messages_collection.insert_one({"email": target_email, "sender": "admin", "text": reply_text})
                log_admin_action(f"Отправлен ответ пользователю {target_email} в тикетах.")
            return redirect('/admin-dashboard/')
            
        elif action_type == 'give_bonus':
            target_email = request.POST.get('target_email')
            bonus_amount = float(request.POST.get('bonus_amount', 0))
            reason = request.POST.get('reason', 'Бонус от администратора')
            users_collection.update_one({"email": target_email}, {"$inc": {"balance": bonus_amount}})
            balance_history_collection.insert_one({
                "email": target_email,
                "amount": bonus_amount,
                "reason": reason,
                "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
                "admin": "Егор"
            })
            log_admin_action(f"Пользователю {target_email} начислено {bonus_amount} ₸. Причина: {reason}")
            return redirect('/admin-dashboard/')
            
        elif action_type == 'update_order_status':
            order_id = request.POST.get('order_id')
            new_status = request.POST.get('status')
            orders_collection.update_one({"_id": ObjectId(order_id)}, {"$set": {"status": new_status}})
            log_admin_action(f"Изменен статус заказа ID {order_id} на «{new_status}»")
            return redirect('/admin-dashboard/')
            
        elif action_type == 'add_game':
            title = request.POST.get('title')
            price_kzt = float(request.POST.get('price_kzt', 0))
            genre = request.POST.get('genre')
            category = request.POST.get('category', 'action')
            developer = request.POST.get('developer', 'Unknown')
            publisher = request.POST.get('publisher', 'Unknown')
            year = request.POST.get('year', '2026')
            platform = request.POST.get('platform', 'PC')
            description = request.POST.get('description', '')
            
            image_url = "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=600"
            image_file = request.FILES.get('image_file')
            if image_file:
                encoded_file = base64.b64encode(image_file.read()).decode('utf-8')
                image_url = f"data:{image_file.content_type};base64,{encoded_file}"
            
            games_collection.insert_one({
                "title": title, "price_kzt": price_kzt, "genre": genre, "category": category,
                "developer": developer, "publisher": publisher, "year": year, "platform": platform,
                "description": description, "image": image_url
            })
            log_admin_action(f"Добавлена новая игра: {title} ({price_kzt} ₸)")
            return redirect('/admin-dashboard/')

    total_users = users_collection.count_documents({})
    total_games = games_collection.count_documents({})
    all_orders = list(orders_collection.find())
    total_orders = len(all_orders)
    total_revenue = sum(o.get('price', 0) for o in all_orders)
    
    today_str = datetime.now().strftime("%d.%m.%Y")
    sales_today = sum(o.get('price', 0) for o in all_orders if str(o.get('date', '')).startswith(today_str))
    
    current_month_str = datetime.now().strftime(".%m.%Y")
    sales_month = sum(o.get('price', 0) for o in all_orders if current_month_str in str(o.get('date', '')))

    tickets = list(support_collection.find({"status": "active"}))
    users_list = list(users_collection.find())
    logs_list = list(admin_logs_collection.find().sort("_id", -1).limit(20))
    balance_history_list = list(balance_history_collection.find().sort("_id", -1).limit(15))

    search_q = request.GET.get('search', '').lower()
    cat_f = request.GET.get('cat_filter', 'all')
    sort_f = request.GET.get('sort', 'default')

    game_query = {}
    if search_q:
        game_query['title'] = {'$regex': search_q, '$options': 'i'}
    if cat_f != 'all':
        game_query['category'] = cat_f

    games_cursor = games_collection.find(game_query)
    if sort_f == 'price_asc':
        games = sorted(list(games_cursor), key=lambda x: x.get('price_kzt', 0))
    elif sort_f == 'price_desc':
        games = sorted(list(games_cursor), key=lambda x: x.get('price_kzt', 0), reverse=True)
    elif sort_f == 'title':
        games = sorted(list(games_cursor), key=lambda x: str(x.get('title', '')))
    else:
        games = list(games_cursor)

    user_search = request.GET.get('user_search', '').lower()
    if user_search:
        users_list = [u for u in users_list if user_search in u.get('email', '').lower() or user_search in u.get('username', '').lower()]

    games_rows = ""
    for g in games:
        g_id = str(g.get('_id'))
        img = g.get('image', '')
        games_rows += f'''
            <div class="admin-game-card">
                <img src="{img}" class="admin-game-img">
                <div class="admin-game-info"><div class="admin-game-title">{g.get('title')}</div>
                <div class="admin-game-meta">{g.get('genre')} &bull; <b>{g.get('category', 'action')}</b> &bull; <span style="color:var(--accent-cyan)">{g.get('price_kzt')} ₸</span></div></div>
                <div class="admin-game-actions">
                <button onclick="openEditModal('{g_id}', '{g.get('title')}', {g.get('price_kzt')}, '{g.get('genre')}', '{g.get('category', 'action')}')" class="btn-sm btn-edit">✏ Изменить</button>
                <button onclick="confirmDelete('{g_id}', '{g.get('title')}')" class="btn-sm btn-del">🗑 Удалить</button>
                </div>
            </div>
        '''

    tickets_rows = ""
    if not tickets:
        tickets_rows = '<div class="empty-state">📭 Нет активных тикетов от пользователей. Всё под контролем!</div>'
    else:
        for t in tickets:
            t_id = str(t.get('_id'))
            t_email = str(t.get('email'))
            last_msgs = list(chat_messages_collection.find({"email": t_email}).sort("_id", -1).limit(4))
            chat_history_html = ""
            for m in reversed(last_msgs):
                if m.get("sender") == "user": chat_history_html += f'<div class="chat-line user">👤 <b>Игрок:</b> {m.get("text")}</div>'
                elif m.get("sender") == "admin": chat_history_html += f'<div class="chat-line admin">🛡 <b>Вы:</b> {m.get("text")}</div>'
                else: chat_history_html += f'<div class="chat-line bot">🤖 <b>Бот:</b> {m.get("text")}</div>'

            tickets_rows += f'''
                <div class="ticket-card"><div class="ticket-header"><span>🚨 Тикет: <strong style="color:var(--accent-cyan)">{t_email}</strong></span>
                <form method="POST" style="margin:0;"><input type="hidden" name="action_type" value="delete_ticket"><input type="hidden" name="ticket_id" value="{t_id}">
                <button type="submit" class="btn-close-ticket">ЗАКРЫТЬ ТИКЕТ</button></form></div>
                <div class="ticket-body">{(chat_history_html if chat_history_html else '<i>Нет сообщений</i>')}</div>
                <form method="POST" class="ticket-reply-form"><input type="hidden" name="action_type" value="send_admin_reply"><input type="hidden" name="target_email" value="{t_email}">
                <input type="text" name="reply_text" placeholder="Ответ пользователю..." required><button type="submit" class="btn-reply">ОТВЕТИТЬ</button></form></div>
            '''

    orders_rows = ""
    for o in all_orders:
        o_id = str(o.get('_id'))
        status = o.get('status', 'Выполнен')
        orders_rows += f'''
            <tr>
                <td><code>{o_id[-6:]}</code></td>
                <td>{o.get('email')}</td>
                <td><b>{o.get('title')}</b></td>
                <td style="color:var(--accent-cyan)">{o.get('price')} ₸</td>
                <td>{o.get('date', 'Н/Д')}</td>
                <td>{o.get('payment_method', 'Баланс')}</td>
                <td>
                    <form method="POST" style="display:inline;">
                        <input type="hidden" name="action_type" value="update_order_status">
                        <input type="hidden" name="order_id" value="{o_id}">
                        <select name="status" onchange="this.form.submit()" style="padding:6px; font-size:12px; margin:0; width:auto; background:#080711; color:var(--accent-cyan);">
                            <option value="Новый" {'selected' if status=='Новый' else ''}>Новый</option>
                            <option value="Ожидает оплаты" {'selected' if status=='Ожидает оплаты' else ''}>Ожидает оплаты</option>
                            <option value="Оплачен" {'selected' if status=='Оплачен' else ''}>Оплачен</option>
                            <option value="Выполнен" {'selected' if status=='Выполнен' else ''}>Выполнен</option>
                            <option value="Отменён" {'selected' if status=='Отменён' else ''}>Отменён</option>
                        </select>
                    </form>
                </td>
            </tr>
        '''

    users_rows = ""
    for u in users_list:
        u_email = u.get('email')
        u_orders = list(orders_collection.find({"email": u_email}))
        u_spent = sum(ord.get('price', 0) for ord in u_orders)
        users_rows += f'''
            <tr>
                <td><b>{u.get('username', 'Игрок')}</b><br><span style="color:var(--text-gray); font-size:12px;">{u_email}</span></td>
                <td style="color:var(--accent-cyan)">{u.get('balance', 0)} ₸</td>
                <td>{len(u_orders)} шт.</td>
                <td>{u_spent} ₸</td>
                <td>{u.get('reg_date', '2026')}</td>
            </tr>
        '''

    logs_rows = ""
    for l in logs_list:
        logs_rows += f'<div class="log-item"><span style="color:var(--accent-cyan); font-family:Orbitron; font-size:11px;">[{l.get("date")}]</span> {l.get("text")}</div>'

    balance_history_rows = ""
    for bh in balance_history_list:
        balance_history_rows += f'<tr><td>{bh.get("email")}</td><td style="color:var(--accent-cyan)">+{bh.get("amount")} ₸</td><td>{bh.get("reason")}</td><td>{bh.get("date")}</td><td>{bh.get("admin")}</td></tr>'

    html = f'''<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>Панель создателя EGORVAULT CMS</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Plus+Jakarta+Sans:wght@400;600;700&display=swap');
        :root {{ --bg-deep: #05040a; --bg-panel: #0d0c1d; --bg-card: #13112a; --accent-cyan: #00f0ff; --accent-purple: #9d00ff; --accent-pink: #ff007f; --text-light: #f3f4f6; --text-gray: #9ca3af; }}
        * {{ box-sizing: border-box; }}
        body {{ font-family: 'Plus Jakarta Sans', sans-serif; background: var(--bg-deep); color: var(--text-light); margin: 0; padding: 20px; }}
        .admin-wrap {{ max-width: 1400px; margin: 0 auto; }}
        .admin-nav-tabs {{ display: flex; gap: 10px; margin-bottom: 30px; flex-wrap: wrap; background: var(--bg-panel); padding: 15px; border-radius: 16px; border: 1px solid rgba(0,240,255,0.2); }}
        .tab-btn {{ background: #080711; border: 1px solid rgba(255,255,255,0.1); color: var(--text-gray); padding: 10px 20px; border-radius: 10px; font-family: 'Orbitron', sans-serif; font-size: 13px; font-weight: bold; cursor: pointer; transition: 0.3s; text-decoration: none; }}
        .tab-btn:hover, .tab-btn.active {{ background: var(--accent-cyan); color: #080711; border-color: var(--accent-cyan); box-shadow: 0 0 20px rgba(0,240,255,0.4); }}
        .admin-header {{ display: flex; justify-content: space-between; align-items: center; background: linear-gradient(135deg, rgba(255,0,127,0.08), rgba(157,0,255,0.08)); padding: 25px 35px; border-radius: 20px; border: 1px solid rgba(255,0,127,0.3); box-shadow: 0 15px 40px rgba(0,0,0,0.8); margin-bottom: 35px; }}
        .admin-title {{ font-family: 'Orbitron', sans-serif; font-size: 24px; color: var(--accent-pink); margin: 0; letter-spacing: 1.5px; text-shadow: 0 0 20px rgba(255,0,127,0.5); }}
        .home-link {{ font-family: 'Orbitron', sans-serif; color: var(--accent-cyan); text-decoration: none; font-weight: 700; font-size: 13px; border: 1px solid rgba(0,240,255,0.4); padding: 12px 24px; border-radius: 10px; transition: 0.3s; background: rgba(0,240,255,0.05); }}
        .home-link:hover {{ background: var(--accent-cyan); color: #080711; box-shadow: 0 0 25px var(--accent-cyan); }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 35px; }}
        .stat-box {{ background: var(--bg-panel); border: 1px solid rgba(255,255,255,0.08); padding: 25px; border-radius: 18px; text-align: center; position: relative; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5); transition: 0.3s; }}
        .stat-box:hover {{ transform: translateY(-3px); border-color: var(--accent-cyan); }}
        .stat-box::before {{ content: ''; position: absolute; top: 0; left: 0; width: 5px; height: 100%; background: var(--accent-cyan); }}
        .stat-box.pink::before {{ background: var(--accent-pink); }}
        .stat-label {{ color: var(--text-gray); font-size: 12px; font-weight: 700; text-transform: uppercase; font-family: 'Orbitron', sans-serif; letter-spacing: 1px; }}
        .stat-value {{ font-family: 'Orbitron', sans-serif; font-size: 30px; font-weight: 900; color: #fff; margin-top: 10px; text-shadow: 0 0 20px rgba(0,240,255,0.4); }}
        .stat-box.pink .stat-value {{ color: var(--accent-pink); text-shadow: 0 0 20px rgba(255,0,127,0.5); }}
        .section-panel {{ background: var(--bg-panel); border: 1px solid rgba(255,255,255,0.08); padding: 35px; border-radius: 20px; box-shadow: 0 15px 40px rgba(0,0,0,0.6); margin-bottom: 35px; display: none; }}
        .section-panel.active {{ display: block; }}
        .section-panel h3 {{ font-family: 'Orbitron', sans-serif; font-size: 18px; color: var(--accent-cyan); margin-top: 0; margin-bottom: 25px; display: flex; align-items: center; gap: 12px; letter-spacing: 1px; }}
        input, select, textarea {{ width: 100%; padding: 14px 18px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.12); background: #080711; color: #fff; font-size: 15px; outline: none; margin-bottom: 20px; box-sizing: border-box; transition: 0.3s; }}
        input:focus, select:focus, textarea:focus {{ border-color: var(--accent-cyan); box-shadow: 0 0 20px rgba(0,240,255,0.25); background: #0c0a1a; }}
        label {{ font-size: 12px; color: var(--text-gray); display: block; margin-bottom: 8px; font-weight: 700; font-family: 'Orbitron', sans-serif; letter-spacing: 0.5px; }}
        .btn-action {{ background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple)); color: #fff; border: none; width: 100%; padding: 16px; border-radius: 12px; font-family: 'Orbitron', sans-serif; font-weight: 900; font-size: 14px; cursor: pointer; transition: 0.3s; box-shadow: 0 0 25px rgba(255,0,127,0.4); letter-spacing: 1px; }}
        .btn-action:hover {{ opacity: 0.95; box-shadow: 0 0 35px var(--accent-pink); transform: translateY(-2px); }}
        .btn-action.cyan {{ background: linear-gradient(135deg, var(--accent-cyan), #0077ff); color: #080711; box-shadow: 0 0 25px rgba(0,240,255,0.4); }}
        .btn-action.cyan:hover {{ background: #fff; box-shadow: 0 0 35px var(--accent-cyan); }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; background: #080711; border-radius: 12px; overflow: hidden; }}
        th, td {{ padding: 16px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 14px; }}
        th {{ background: #13112a; font-family: 'Orbitron', sans-serif; color: var(--accent-cyan); font-size: 12px; letter-spacing: 1px; }}
        tr:hover {{ background: rgba(0,240,255,0.02); }}
        .ticket-card {{ background: var(--bg-card); border: 1px solid rgba(255,0,127,0.35); border-radius: 16px; padding: 25px; margin-bottom: 20px; }}
        .ticket-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; font-size: 15px; font-weight: bold; }}
        .btn-close-ticket {{ background: rgba(255,0,127,0.15); color: var(--accent-pink); border: 1px solid rgba(255,0,127,0.5); padding: 8px 16px; border-radius: 8px; font-family: 'Orbitron', sans-serif; font-size: 11px; font-weight: bold; cursor: pointer; transition: 0.3s; }}
        .btn-close-ticket:hover {{ background: var(--accent-pink); color: #fff; box-shadow: 0 0 20px var(--accent-pink); }}
        .ticket-body {{ background: #080711; border: 1px solid rgba(255,255,255,0.06); padding: 18px; border-radius: 12px; max-height: 200px; overflow-y: auto; margin-bottom: 15px; display: flex; flex-direction: column; gap: 10px; }}
        .chat-line {{ font-size: 14px; padding: 10px 14px; border-radius: 10px; max-width: 85%; }}
        .chat-line.user {{ background: #1a1638; align-self: flex-start; color: #fff; border-left: 3px solid var(--accent-cyan); }}
        .chat-line.admin {{ background: rgba(0,240,255,0.12); align-self: flex-end; color: var(--accent-cyan); border-right: 3px solid var(--accent-cyan); }}
        .chat-line.bot {{ background: rgba(157,0,255,0.15); align-self: flex-start; color: #d8b4fe; border-left: 3px solid var(--accent-purple); }}
        .ticket-reply-form {{ display: flex; gap: 12px; margin: 0; }}
        .ticket-reply-form input {{ margin: 0; padding: 12px 16px; font-size: 14px; flex: 1; }}
        .btn-reply {{ background: var(--accent-cyan); color: #080711; border: none; padding: 0 24px; border-radius: 10px; font-family: 'Orbitron', sans-serif; font-weight: 900; font-size: 12px; cursor: pointer; transition: 0.3s; white-space: nowrap; }}
        .btn-reply:hover {{ background: #fff; box-shadow: 0 0 25px var(--accent-cyan); }}
        .admin-game-card {{ background: var(--bg-card); border: 1px solid rgba(255,255,255,0.08); padding: 18px 25px; border-radius: 14px; margin-bottom: 15px; display: flex; align-items: center; justify-content: space-between; gap: 20px; transition: 0.3s; }}
        .admin-game-card:hover {{ border-color: rgba(0,240,255,0.4); }}
        .admin-game-img {{ width: 75px; height: 50px; object-fit: cover; border-radius: 10px; border: 1px solid var(--accent-cyan); }}
        .admin-game-info {{ flex: 1; }}
        .admin-game-title {{ font-family: 'Orbitron', sans-serif; font-size: 16px; font-weight: 700; color: #fff; margin-bottom: 6px; }}
        .admin-game-meta {{ font-size: 13px; color: var(--text-gray); }}
        .admin-game-actions {{ display: flex; gap: 10px; }}
        .btn-sm {{ padding: 10px 18px; border-radius: 8px; text-decoration: none; font-family: 'Orbitron', sans-serif; font-size: 12px; font-weight: bold; transition: 0.3s; cursor: pointer; border: none; }}
        .btn-edit {{ background: rgba(0,240,255,0.1); color: var(--accent-cyan); border: 1px solid rgba(0,240,255,0.3); }}
        .btn-edit:hover {{ background: var(--accent-cyan); color: #080711; box-shadow: 0 0 20px var(--accent-cyan); }}
        .btn-del {{ background: rgba(255,0,127,0.1); color: var(--accent-pink); border: 1px solid rgba(255,0,127,0.3); }}
        .btn-del:hover {{ background: var(--accent-pink); color: #fff; box-shadow: 0 0 20px var(--accent-pink); }}
        .modal-overlay {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(5,4,10,0.85); backdrop-filter: blur(8px); z-index: 3000; justify-content: center; align-items: center; }}
        .modal-box {{ background: var(--bg-panel); border: 1px solid var(--accent-cyan); padding: 40px; border-radius: 20px; width: 480px; max-width: 95%; box-shadow: 0 20px 60px rgba(0,0,0,0.9); }}
        .log-item {{ background: #080711; padding: 12px 16px; border-radius: 8px; margin-bottom: 10px; border-left: 3px solid var(--accent-purple); font-size: 13px; }}
    </style>
    <script>
        function switchTab(tabId) {{
            document.querySelectorAll(".section-panel").forEach(p => p.classList.remove("active"));
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            document.getElementById(tabId).classList.add("active");
            event.target.classList.add("active");
            localStorage.setItem("active_admin_tab", tabId);
        }}
        window.onload = function() {{
            const savedTab = localStorage.getItem("active_admin_tab");
            if(savedTab && document.getElementById(savedTab)) {{
                document.querySelectorAll(".section-panel").forEach(p => p.classList.remove("active"));
                document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
                document.getElementById(savedTab).classList.add("active");
            }}
        }};
        function confirmDelete(gameId, gameTitle) {{
            document.getElementById("deleteGameTitle").innerText = gameTitle;
            document.getElementById("deleteConfirmBtn").href = "/admin-delete/" + gameId + "/";
            document.getElementById("deleteModal").style.display = "flex";
        }}
        function closeDeleteModal() {{ document.getElementById("deleteModal").style.display = "none"; }}
        function openEditModal(id, title, price, genre, cat) {{
            document.getElementById("editGameId").value = id;
            document.getElementById("editTitle").value = title;
            document.getElementById("editPrice").value = price;
            document.getElementById("editGenre").value = genre;
            document.getElementById("editCat").value = cat;
            document.getElementById("editForm").action = "/admin-edit/" + id + "/";
            document.getElementById("editModal").style.display = "flex";
        }}
        function closeEditModal() {{ document.getElementById("editModal").style.display = "none"; }}
        function previewImage(event) {{
            const reader = new FileReader();
            reader.onload = function(){{
                const output = document.getElementById("imgPreview");
                output.src = reader.result;
                output.style.display = "block";
            }};
            reader.readAsDataURL(event.target.files[0]);
        }}
    </script>
</head>
<body>
    <div class="admin-wrap">
        <div class="admin-header">
            <h1 class="admin-title">🛡 EGORVAULT CMS v8.5</h1>
            <a href="/" class="home-link">← В КАТАЛОГ САЙТА</a>
        </div>
        <div class="admin-nav-tabs">
            <button class="tab-btn active" onclick="switchTab('tab-dashboard')">📊 Дашборд</button>
            <button class="tab-btn" onclick="switchTab('tab-games')">🎮 Игры</button>
            <button class="tab-btn" onclick="switchTab('tab-orders')">🧾 Заказы</button>
            <button class="tab-btn" onclick="switchTab('tab-users')">👥 Пользователи</button>
            <button class="tab-btn" onclick="switchTab('tab-balance')">💰 Баланс</button>
            <button class="tab-btn" onclick="switchTab('tab-analytics')">📈 Аналитика</button>
            <button class="tab-btn" onclick="switchTab('tab-settings')">⚙️ Настройки</button>
        </div>
        <div id="tab-dashboard" class="section-panel active">
            <div class="stats-grid">
                <div class="stat-box"><div class="stat-label">👥 Пользователи</div><div class="stat-value">{total_users}</div></div>
                <div class="stat-box"><div class="stat-label">🎮 Игры в БД</div><div class="stat-value">{total_games}</div></div>
                <div class="stat-box pink"><div class="stat-label">📦 Всего заказов</div><div class="stat-value">{total_orders}</div></div>
                <div class="stat-box"><div class="stat-label">💰 Общая выручка</div><div class="stat-value">{total_revenue} ₸</div></div>
                <div class="stat-box pink"><div class="stat-label">⚡ Продажи за сегодня</div><div class="stat-value">{sales_today} ₸</div></div>
            </div>
            <h3>🚨 АКТИВНЫЕ ТИКЕТЫ И ПОДДЕРЖКА</h3>{tickets_rows}
        </div>
        <div id="tab-games" class="section-panel">
            <h3>➕ ДОБАВИТЬ НОВУЮ ИГРУ</h3>
            <form method="POST" enctype="multipart/form-data" style="background:#080711; padding:25px; border-radius:14px; border:1px solid rgba(0,240,255,0.2); margin-bottom:30px;">
                <input type="hidden" name="action_type" value="add_game">
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
                    <div><label>Название игры:</label><input type="text" name="title" placeholder="Cyber Legends 2077" required></div>
                    <div><label>Цена (₸):</label><input type="number" name="price_kzt" placeholder="1499" required min="0"></div>
                    <div><label>Жанр:</label><input type="text" name="genre" placeholder="RPG / Cyberpunk" required></div>
                    <div><label>Категория:</label><select name="category" required><option value="action">🔥 Экшены & Шутеры</option><option value="rpg">🛡 RPG & Киберпанк</option><option value="strategy">🧩 Инди & Стратегии</option></select></div>
                    <div><label>Разработчик:</label><input type="text" name="developer" placeholder="Mundfish"></div>
                    <div><label>Издатель:</label><input type="text" name="publisher" placeholder="EGORVAULT Publishing"></div>
                    <div><label>Год выпуска:</label><input type="text" name="year" value="2026"></div>
                    <div><label>Платформа:</label><input type="text" name="platform" value="PC / Steam"></div>
                </div>
                <label>Описание игры:</label><textarea name="description" placeholder="Подробное описание игры..." rows="3"></textarea>
                <label>Обложка (изображение):</label><input type="file" name="image_file" accept="image/*" onchange="previewImage(event)" style="color:var(--accent-cyan); padding:10px;" required>
                <img id="imgPreview" style="display:none; width:150px; height:100px; object-fit:cover; border-radius:8px; margin-bottom:15px; border:1px solid var(--accent-cyan);">
                <button type="submit" class="btn-action">ОПУБЛИКОВАТЬ В БАЗУ ДАННЫХ</button>
            </form>
            <h3>🎮 УПРАВЛЕНИЕ ИГРАМИ В БАЗЕ</h3>
            <form method="GET" style="display:flex; gap:15px; margin-bottom:20px;">
                <input type="text" name="search" placeholder="Поиск по названию игры..." value="{search_q}" style="margin:0; flex:2;">
                <select name="cat_filter" style="margin:0; flex:1;"><option value="all">Все категории</option><option value="action" {'selected' if cat_f=='action' else ''}>Экшены</option><option value="rpg" {'selected' if cat_f=='rpg' else ''}>RPG</option><option value="strategy" {'selected' if cat_f=='strategy' else ''}>Стратегии</option></select>
                <select name="sort" style="margin:0; flex:1;"><option value="default">Сортировка</option><option value="price_asc">Цена по возрастанию</option><option value="price_desc">Цена по убыванию</option><option value="title">По названию (А-Я)</option></select>
                <button type="submit" class="btn-action cyan" style="width:auto; padding:0 25px; margin:0;">НАЙТИ</button>
            </form>
            <div style="max-height: 500px; overflow-y: auto; padding-right: 5px;">{(games_rows if games_rows else '<div style="color:var(--text-gray); text-align:center; padding:30px;">Игры не найдены</div>')}</div>
        </div>
        <div id="tab-orders" class="section-panel">
            <h3>🧾 УПРАВЛЕНИЕ ЗАКАЗАМИ И КЛЮЧАМИ</h3>
            <div style="overflow-x:auto;"><table>
                <tr><th>ID</th><th>Покупатель</th><th>Игра</th><th>Сумма</th><th>Дата</th><th>Оплата</th><th>Статус</th></tr>{orders_rows}
            </table></div>
        </div>
        <div id="tab-users" class="section-panel">
            <h3>👥 БАЗА ПОЛЬЗОВАТЕЛЕЙ EGORVAULT</h3>
            <form method="GET" style="display:flex; gap:15px; margin-bottom:20px;">
                <input type="text" name="user_search" placeholder="Поиск пользователя по email или имени..." value="{user_search}" style="margin:0;">
                <button type="submit" class="btn-action cyan" style="width:auto; padding:0 25px; margin:0;">ПОИСК</button>
            </form>
            <div style="overflow-x:auto;"><table>
                <tr><th>Пользователь / Email</th><th>Баланс</th><th>Покупок</th><th>Потрачено</th><th>Регистрация</th></tr>{users_rows}
            </table></div>
        </div>
        <div id="tab-balance" class="section-panel">
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:30px;">
                <div>
                    <h3>💎 ВЫДАТЬ БАЛАНС ПОЛЬЗОВАТЕЛЮ</h3>
                    <form method="POST">
                        <input type="hidden" name="action_type" value="give_bonus">
                        <label>Email пользователя:</label><input type="email" name="target_email" placeholder="user@gmail.com" required>
                        <label>Сумма бонуса (₸):</label><input type="number" name="bonus_amount" placeholder="1000" required min="1">
                        <label>Причина начисления:</label><input type="text" name="reason" placeholder="Победа в турнире / Компенсация" required>
                        <button type="submit" class="btn-action cyan" style="margin-top: 5px;">ЗАЧИСЛИТЬ НА СЧЕТ</button>
                    </form>
                </div>
                <div>
                    <h3>📜 ИСТОРИЯ НАЧИСЛЕНИЙ БАЛАНСА</h3>
                    <div style="max-height: 320px; overflow-y: auto;"><table>
                        <tr><th>Email</th><th>Сумма</th><th>Причина</th><th>Дата</th><th>Админ</th></tr>{balance_history_rows}
                    </table></div>
                </div>
            </div>
        </div>
        <div id="tab-analytics" class="section-panel">
            <h3>📈 АНАЛИТИКА И ФИНАНСЫ EGORVAULT</h3>
            <div class="stats-grid">
                <div class="stat-box"><div class="stat-label">💰 Общая выручка</div><div class="stat-value">{total_revenue} ₸</div></div>
                <div class="stat-box pink"><div class="stat-label">⚡ Продажи за сегодня</div><div class="stat-value">{sales_today} ₸</div></div>
                <div class="stat-box"><div class="stat-label">📅 Продажи за месяц</div><div class="stat-value">{sales_month} ₸</div></div>
                <div class="stat-box pink"><div class="stat-label">📦 Всего заказов</div><div class="stat-value">{total_orders}</div></div>
            </div>
            <div style="background:#080711; padding:30px; border-radius:16px; border:1px solid rgba(0,240,255,0.2); text-align:center;">
                <h4 style="font-family:Orbitron; color:var(--accent-cyan); margin-top:0;">📊 ГРАФИК ПРОДАЖ ЗА ПОСЛЕДНИЕ 7 ДНЕЙ</h4>
                <p style="color:var(--text-gray);">Динамика транзакций и выдачи цифровых лицензий в реальном времени:</p>
                <div style="display:flex; justify-content:space-around; align-items:flex-end; height:180px; padding:20px 10px 0; border-bottom:2px solid rgba(0,240,255,0.3);">
                    <div style="background:var(--accent-cyan); width:35px; height:60%; border-radius:6px 6px 0 0; box-shadow:0 0 15px var(--accent-cyan);"><span style="font-size:10px; display:block; margin-top:-20px; color:#fff;">Пн</span></div>
                    <div style="background:var(--accent-cyan); width:35px; height:80%; border-radius:6px 6px 0 0; box-shadow:0 0 15px var(--accent-cyan);"><span style="font-size:10px; display:block; margin-top:-20px; color:#fff;">Вт</span></div>
                    <div style="background:var(--accent-pink); width:35px; height:45%; border-radius:6px 6px 0 0; box-shadow:0 0 15px var(--accent-pink);"><span style="font-size:10px; display:block; margin-top:-20px; color:#fff;">Ср</span></div>
                    <div style="background:var(--accent-cyan); width:35px; height:95%; border-radius:6px 6px 0 0; box-shadow:0 0 15px var(--accent-cyan);"><span style="font-size:10px; display:block; margin-top:-20px; color:#fff;">Чт</span></div>
                    <div style="background:var(--accent-cyan); width:35px; height:70%; border-radius:6px 6px 0 0; box-shadow:0 0 15px var(--accent-cyan);"><span style="font-size:10px; display:block; margin-top:-20px; color:#fff;">Пт</span></div>
                    <div style="background:var(--accent-pink); width:35px; height:100%; border-radius:6px 6px 0 0; box-shadow:0 0 15px var(--accent-pink);"><span style="font-size:10px; display:block; margin-top:-20px; color:#fff;">Сб</span></div>
                    <div style="background:var(--accent-cyan); width:35px; height:85%; border-radius:6px 6px 0 0; box-shadow:0 0 15px var(--accent-cyan);"><span style="font-size:10px; display:block; margin-top:-20px; color:#fff;">Вс</span></div>
                </div>
            </div>
        </div>
        <div id="tab-settings" class="section-panel">
            <h3>⚙️ ИСТОРИЯ ДЕЙСТВИЙ АДМИНИСТРАТОРА (ЛОГИ)</h3>
            <div style="max-height: 400px; overflow-y: auto;">{(logs_rows if logs_rows else '<div style="color:var(--text-gray);">Логи пока пусты</div>')}</div>
        </div>
    </div>
    <div id="deleteModal" class="modal-overlay">
        <div class="modal-box" style="text-align:center;">
            <h3 style="color:var(--accent-pink); font-family:Orbitron; margin-top:0;">⚠️ ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ</h3>
            <p style="color:var(--text-gray); font-size:15px;">Вы действительно хотите удалить игру <br><b id="deleteGameTitle" style="color:#fff;"></b>?<br>Это действие нельзя отменить.</p>
            <div style="display:flex; gap:15px; margin-top:30px;">
                <button onclick="closeDeleteModal()" class="btn-action cyan" style="flex:1;">ОТМЕНА</button>
                <a id="deleteConfirmBtn" href="#" class="btn-action" style="flex:1; text-decoration:none; display:flex; align-items:center; justify-content:center;">УДАЛИТЬ</a>
            </div>
        </div>
    </div>
    <div id="editModal" class="modal-overlay">
        <div class="modal-box">
            <h3 style="color:var(--accent-cyan); font-family:Orbitron; margin-top:0;">✏ РЕДАКТИРОВАТЬ ИГРУ</h3>
            <form id="editForm" method="POST" enctype="multipart/form-data">
                <input type="hidden" id="editGameId" name="game_id">
                <label>Название:</label><input type="text" id="editTitle" name="title" required>
                <label>Цена (₸):</label><input type="number" id="editPrice" name="price_kzt" required>
                <label>Жанр:</label><input type="text" id="editGenre" name="genre" required>
                <label>Категория:</label><select id="editCat" name="category"><option value="action">Экшены</option><option value="rpg">RPG</option><option value="strategy">Стратегии</option></select>
                <label>Новая обложка (опционально):</label><input type="file" name="image_file" accept="image/*" style="color:var(--accent-cyan); padding:8px;">
                <div style="display:flex; gap:15px; margin-top:20px;">
                    <button type="button" onclick="closeEditModal()" class="btn-action cyan" style="flex:1;">ОТМЕНА</button>
                    <button type="submit" class="btn-action" style="flex:1;">СОХРАНИТЬ</button>
                </div>
            </form>
        </div>
    </div>
</body></html>'''
    return HttpResponse(html)

@csrf_exempt
def admin_edit_game(request, game_id):
    if request.COOKIES.get('is_creator') != 'true':
        return redirect('home')
    game = games_collection.find_one({"_id": ObjectId(game_id)})
    if not game: return redirect('admin_dashboard')
    if request.method == 'POST':
        new_title = request.POST.get('title')
        new_price = float(request.POST.get('price_kzt', 0))
        new_genre = request.POST.get('genre')
        new_category = request.POST.get('category', 'action')
        update_data = {"title": new_title, "price_kzt": new_price, "genre": new_genre, "category": new_category}
        image_file = request.FILES.get('image_file')
        if image_file:
            encoded_file = base64.b64encode(image_file.read()).decode('utf-8')
            update_data["image"] = f"data:{image_file.content_type};base64,{encoded_file}"
        games_collection.update_one({"_id": ObjectId(game_id)}, {"$set": update_data})
        log_admin_action(f"Игра «{new_title}» успешно обновлена.")
        return redirect('/admin-dashboard/')
    return redirect('admin_dashboard')

def admin_delete_game(request, game_id):
    if request.COOKIES.get('is_creator') != 'true':
        return redirect('home')
    game = games_collection.find_one({"_id": ObjectId(game_id)})
    if game:
        games_collection.delete_one({"_id": ObjectId(game_id)})
        log_admin_action(f"Удалена игра: {game.get('title')}")
    return redirect('/admin-dashboard/')

def logout_view(request):
    response = redirect('home')
    response.delete_cookie('user_email')
    return response