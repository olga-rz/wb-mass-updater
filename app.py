import streamlit as st
import pandas as pd
import requests
import re
import time
import io

st.set_page_config(page_title="WB Smart Excel Updater", layout="wide", page_icon="📦")

st.title("📦 Умное Excel-обновление карточек Wildberries v2")
st.caption("Массовая автозамена уникальных описаний из Excel с сохранением принтов в кавычках и защитой брендов/названий")

if "fetched_data" not in st.session_state:
    st.session_state.fetched_data = None
if "df_preview" not in st.session_state:
    st.session_state.df_preview = None
if "excel_mapping" not in st.session_state:
    st.session_state.excel_mapping = None

st.sidebar.header("🔑 Настройки подключения")
wb_token = st.sidebar.text_input("API Токен (категория Контент)", type="password", help="Вставьте ваш токен контента Wildberries")

st.sidebar.header("📐 Габариты упаковки (см)")
new_length = st.sidebar.number_input("Длина упаковки", min_value=1, value=11)
new_width = st.sidebar.number_input("Ширина упаковки", min_value=1, value=11)
new_height = st.sidebar.number_input("Высота упаковки", min_value=1, value=1)

PACK_TRIGGERS = {
    "длина упаковки": str(new_length),
    "ширина упаковки": str(new_width),
    "высота упаковки": str(new_height),
    "глубина упаковки": str(new_length)
}

st.sidebar.header("📂 Загрузка Excel-таблицы")
uploaded_file = st.sidebar.file_uploader("Выберите файл таблицы (.xlsx)", type=["xlsx"])

def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def fetch_cards_by_ids(id_chunk, token):
    headers = {"Authorization": token, "Content-Type": "application/json", "Accept": "application/json"}
    url = "https://wildberries.ru"
    
    # ИСПРАВЛЕНО: Добавлен hideTrash: False, чтобы WB выдавал товары, которых нет в наличии
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
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            return res.json().get("cards", [])
        elif res.status_code == 429:
            time.sleep(15)
            return fetch_cards_by_ids(id_chunk, token)
    except Exception as e:
        st.error(f"Ошибка сети: {e}")
    return []

def send_update_batch(cards_payload, token):
    headers = {"Authorization": token, "Content-Type": "application/json", "Accept": "application/json"}
    url = "https://wildberries.ru"
    try:
        res = requests.post(url, headers=headers, json=cards_payload, timeout=20)
        return res.status_code == 200, f"Код {res.status_code}: {res.text[:150]}"
    except Exception as e:
        return False, f"Ошибка сети: {e}"
if uploaded_file and wb_token:
    try:
        df_excel = pd.read_excel(uploaded_file)
        df_excel.columns = [str(c).strip().lower() for c in df_excel.columns]
        
        nm_col = next((c for c in df_excel.columns if 'nmid' in c or 'артикул' in c), None)
        desc_col = next((c for c in df_excel.columns if 'описание' in c or 'текст' in c), None)
        
        if not nm_col or not desc_col:
            st.error("❌ Ошибка структуры Excel: В таблице обязательно должны быть колонки 'nmID' и 'Описание'.")
        else:
            df_excel = df_excel.dropna(subset=[nm_col, desc_col])
            df_excel[nm_col] = pd.to_numeric(df_excel[nm_col], errors='coerce').dropna().astype(int)
            
            excel_mapping = dict(zip(df_excel[nm_col], df_excel[desc_col]))
            st.session_state.excel_mapping = excel_mapping
            target_nm_ids = list(excel_mapping.keys())
            
            st.success(f"✅ Из Excel успешно загружено уникальных описаний для артикулов: {len(target_nm_ids)}")
            
            if st.button("🔍 Шаг 1: Проверить карточки и сопоставить описания из Excel", type="primary"):
                with st.spinner("Синхронизация данных с серверами Wildberries..."):
                    all_fetched_cards = []
                    chunks = list(chunk_list(target_nm_ids, 100))
                    for chunk in chunks:
                        cards = fetch_cards_by_ids(chunk, wb_token)
                        all_fetched_cards.extend(cards)
                    
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
                            
                            excel_template = excel_mapping.get(nm_id, "")
                            final_desc_preview = excel_template.format(print_name=print_name) if "{print_name}" in str(excel_template) else str(excel_template)
                            
                            dimensions_old = card.get("dimensions", {})
                            old_dims_str = f"{dimensions_old.get('length', '—')}x{dimensions_old.get('width', '—')}x{dimensions_old.get('height', '—')}"
                            
                            preview_rows.append({
                                "Артикул nmID": nm_id,
                                "Артикул продавца": vendor_code,
                                "Текущее Название (БЕЗОПАСНО)": title,
                                "Текущий Бренд (БЕЗОПАСНО)": brand,
                                "Вытащенный принт": print_name,
                                "Сгенерированный текст из Excel": final_desc_preview[:120] + "..." if len(final_desc_preview) > 120 else final_desc_preview,
                                "Размеры упаковки": f"{new_length}x{new_width}x{new_height}"
                            })
                        st.session_state.df_preview = pd.DataFrame(preview_rows)
                    else:
                        st.warning("⚠️ Не найдено карточек. Проверьте правильность токена контента или nmID в Excel.")
            
            if st.session_state.df_preview is not None:
                st.subheader("👀 Таблица предварительного контроля данных")
                st.markdown("Внимательно проверьте **Текущее Название и Текущий Бренд** — они взяты из вашей действующей базы WB. Если всё на месте и новые тексты сопоставлены верно, можно отправлять пачку в работу.")
                st.dataframe(st.session_state.df_preview, use_container_width=True)
                
                st.subheader("🚀 Массовое сохранение изменений")
                if st.button("🔥 Шаг 2: Отправить уникальные описания и габариты в Wildberries"):
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
                        
                        raw_excel_text = st.session_state.excel_mapping.get(nm_id, "")
                        final_description = raw_excel_text.format(print_name=print_name) if "{print_name}" in str(raw_excel_text) else str(raw_excel_text)
                        
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
                            status_text.text(f"Синхронизация пачки уникальных изменений ({index}/{total_cards})...")
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
    except Exception as e:
        st.error(f"Не удалось распознать Excel файл: {e}")
else:
    st.info("💡 Укажите API-токен контента слева на боковой панели и загрузите вашу заполненную таблицу Excel (`.xlsx`) с колонками nmID и Описание.")
