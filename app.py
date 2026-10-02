import streamlit as st
import pandas as pd
import requests
import re
import time

st.set_page_config(page_title="WB Smart Box Updater", layout="wide", page_icon="📦")

st.title("📦 Умное обновление карточек Wildberries v2")
st.caption("Массовая автозамена описаний через текстовое поле с сохранением принтов в кавычках и защитой брендов")

if "fetched_data" not in st.session_state:
    st.session_state.fetched_data = None
if "df_preview" not in st.session_state:
    st.session_state.df_preview = None

st.sidebar.header("🔑 Настройки подключения")
wb_token = st.sidebar.text_input("API Токен (категорияindex Контент)", type="password", help="Вставьте ваш токен контента Wildberries")

st.sidebar.header("📐 Габариты упаковки (см)")
new_length = st.sidebar.number_input("Длина упаковки", min_value=1, value=15)
new_width = st.sidebar.number_input("Ширина упаковки", min_value=1, value=11)
new_height = st.sidebar.number_input("Высота упаковки", min_value=1, value=1)

PACK_TRIGGERS = {
    "длина упаковки": str(new_length),
    "ширина упаковки": str(new_width),
    "высота упаковки": str(new_height),
    "глубина упаковки": str(new_length)
}

st.sidebar.header("🔢 Ввод артикулов")
articules_input = st.sidebar.text_area("Вставьте список nmID (каждый артикул с новой строки)", height=150, placeholder="916295595")

def get_real_urls():
    part_a = b'https://content-'
    part_b = b'api.wildberries.ru/content/v2/get/cards/list'
    part_c = b'api.wildberries.ru/content/v2/cards/update'
    return (part_a + part_b).decode('utf-8'), (part_a + part_c).decode('utf-8')

def fetch_cards_by_ids_pure(id_chunk, token):
    headers = {"Authorization": token, "Content-Type": "application/json", "Accept": "application/json"}
    url_list, _ = get_real_urls()
    payload = {
        "settings": {
            "cursor": {"limit": 100},
            "filter": {
                "withPhoto": -1,
                "hideTrash": False,
                "nmIDs": [int(x) for x in id_chunk]
            }
        }
    }
    try:
        res = requests.post(url_list, headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            cards = res.json().get("cards", [])
            # ИСПРАВЛЕНО: Жёстко фильтруем ответ WB, оставляя только те артикулы, которые запросил пользователь
            return [c for c in cards if int(c.get("nmID", 0)) in id_chunk]
        elif res.status_code == 429:
            time.sleep(15)
            return fetch_cards_by_ids_pure(id_chunk, token)
    except:
        pass
    return []

def send_update_batch(cards_payload, token):
    headers = {"Authorization": token, "Content-Type": "application/json", "Accept": "application/json"}
    _, url_update = get_real_urls()
    try:
        res = requests.post(url_update, headers=headers, json=cards_payload, timeout=20)
        return res.status_code == 200, f"Код {res.status_code}: {res.text[:150]}"
    except Exception as e:
        return False, f"Ошибка сети: {e}"
# Поле для редактирования общего шаблона описания прямо на экране
st.header("📝 Шаблон общего нового описания")
new_desc_template = st.text_area(
    "Вы можете отредактировать этот текст прямо здесь. Переменная {print_name} автоматически заменится на имя принта из кавычек текущей карточки.",
    value="""Металлическая пластина для телефона "{print_name}" — незаменимый аксессуар для каждого водителя, обеспечивающий надежную фиксацию и стильный вид вашего гаджета.
Наша пластина для магнитного держателя телефона создана для тех, кто ищет бескомпромиссную надежность. Этот красивый магнит на телефон гарантирует, что ваш смартфон останется на месте даже при резком торможении. Мощная металлическая пластина для телефона превращает обычный держатель для телефона в машину в идеальную систему крепления.

Обратите внимание: Данный аксессуар — это именно металлическая пластина, которая притягивается к магниту. Сама наклейка не является магнитом, поэтому она полностью безопасна для вашего смартфона и не влияет на работу его внутренних модулей.

Почему выбирают наши магнитные наклейки на телефон?
• Железная фиксация: Качественный магнит в машину требует прямого контакта. Наша магнит пластина для телефона выполнена из металла, что дает в разы больше силы притяжения, чем стандартные наклейки на телефон.
• Стильный дизайн: Если вы искали магнит на телефон для держателя в машину с приколом или лаконичный принт — это современный выбор. Наши магнитные стикеры для телефона выглядят гораздо эстетественнее, чем обычные наклейки или пустые железки.
• Универсальные аксессуары в авто: Эти магниты для чехла телефона подходят для любых смартфонов: iPhone (Айфон), Samsung, Xiaomi и других. Пластина идеально дополняет любой автомобильный держатель или автодержатель.

Простота и надежность:
Наклейка на чехол (стикер) не оставляет следов после снятия и не портит поверхность.

Кому подойдет?
Это отличный подарок мужу, парню, другу или коллеге на любой праздник. Стильная пластина также может использоваться как декоративный элемент на ноутбук или планшет.

Важно по установке:
Чтобы ваш автомобильный аксессуар держал максимально крепко, приклейте его на внешнюю сторону чехла. Перед установкой обязательно OpenCV обезжирьте поверхность.""",
    height=250
)

# Разбор введенных артикулов
if articules_input and wb_token:
    target_nm_ids = []
    for line in articules_input.splitlines():
        line_clean = line.strip()
        if line_clean and line_clean.isdigit():
            target_nm_ids.append(int(line_clean))
    target_nm_ids = list(set(target_nm_ids))
    
    if target_nm_ids:
        st.success(f"✅ Введено уникальных артикулов для обработки: {len(target_nm_ids)}")
        
        # КНОПКА ШАГ 1
        if st.button("🔍 Шаг 1: Проверить карточки и сопоставить описания", type="primary"):
            with st.spinner("Синхронизация данных с серверами Wildberries..."):
                all_fetched_cards = fetch_cards_by_ids_pure(target_nm_ids, wb_token)
                
                if all_fetched_cards:
                    st.session_state.fetched_data = all_fetched_cards
                    preview_rows = []
                    
                    for card in all_fetched_cards:
                        nm_id = int(card.get("nmID"))
                        vendor_code = card.get("vendorCode", "")
                        title = card.get("title", "—")
                        brand = card.get("brand", "—")
                        old_desc = card.get("description", "")
                        
                        match = re.search(r'["«](.*?)["»]', old_desc)
                        print_name = match.group(1).strip() if match else card.get("title", "").replace("Металлическая пластина для телефона", "").strip()
                        
                        final_desc_preview = new_desc_template.format(print_name=print_name)
                        dimensions_old = card.get("dimensions", {})
                        old_dims_str = f"{dimensions_old.get('length', '—')}x{dimensions_old.get('width', '—')}x{dimensions_old.get('height', '—')}"
                        
                        preview_rows.append({
                            "Артикул nmID": nm_id,
                            "Артикул продавца": vendor_code,
                            "Текущее Название (БЕЗОПАСНО)": title,
                            "Текущий Бренд (БЕЗОПАСНО)": brand,
                            "Вытащенный принт": print_name,
                            "Новое описание для отправки": final_desc_preview[:120] + "...",
                            "Размеры упаковки": f"{new_length}x{new_width}x{new_height}"
                        })
                    st.session_state.df_preview = pd.DataFrame(preview_rows)
                else:
                    st.warning("⚠️ Не найдено карточек. Проверьте правильность токена контента или введённых nmID.")
        
        # Вывод интерактивного окна предпросмотра
        if st.session_state.df_preview is not None:
            st.subheader("👀 Таблица предварительного контроля данных")
            st.markdown("Внимательно проверьте данные. В таблице ниже отображаются только те артикулы, которые вы ввели вручную.")
            st.dataframe(st.session_state.df_preview, use_container_width=True)
            
            st.subheader("🚀 Массовое сохранение изменений")
            if st.button("🔥 Шаг 2: Отправить общее описание и габариты в Wildberries", type="secondary"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                cards_to_update = st.session_state.fetched_data
                total_cards = len(cards_to_update)
                update_payload_batch = []
                success_count = 0
                
                for index, card in enumerate(cards_to_update, 1):
                    nm_id = int(card.get("nmID"))
                    old_desc = card.get("description", "")
                    
                    match = re.search(r'["«](.*?)["»]', old_desc)
                    print_name = match.group(1).strip() if match else card.get("title", "").replace("Металлическая пластина для телефона", "").strip()
                    
                    final_description = new_desc_template.format(print_name=print_name)
                    
                    if len(final_description) > 5000:
                        st.warning(f"⚠️ Артикул {nm_id}: Текст превышает 5000 символов. Пропущен.")
                        continue
                    
                    characteristics = card.get("characteristics", [])
                    for char in characteristics:
                        char_name = str(char.get("name", "")).lower()
                        for trigger_word, new_val in PACK_TRIGGERS.items():
                            if trigger_word == char_name:
                                char["value"] = [str(new_val)]
                    
                    clean_card = {
                        "nmID": nm_id,
                        "vendorCode": card.get("vendorCode"),
                        "description": final_description,
                        "dimensions": {
                            "length": int(new_length),
                            "width": int(new_width),
                            "height": int(new_height)
                        },
                        "characteristics": characteristics,
                        "sizes": card.get("sizes", [])
                    }
                    if "mediaFiles" in card:
                        clean_card["mediaFiles"] = card["mediaFiles"]
                        
                    update_payload_batch.append(clean_card)
                    
                    if len(update_payload_batch) == 100 or index == total_cards:
                        status_text.text(f"Синхронизация пачки изменений ({index}/{total_cards})...")
                        success, msg = send_update_batch(update_payload_batch, wb_token)
                        if success:
                            success_count += len(update_payload_batch)
                        else:
                            st.error(f"Ошибка WB: {msg}")
                        update_payload_batch = []
                        if index < total_cards:
                            time.sleep(8)
                    progress_bar.progress(index / total_cards)
                
                status_text.empty()
                st.success(f"🎉 Процесс полностью завершен! Успешно и безопасно обновлено карточек: {success_count} из {total_cards}")
                st.session_state.fetched_data = None
                st.session_state.df_preview = None
else:
    st.info("💡 Укажите API-токен контента слева на боковой панели, вставьте список артикулов nmID (каждый с новой строки) и проверьте шаблон описания.")
