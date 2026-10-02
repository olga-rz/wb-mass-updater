import streamlit as st
import pandas as pd
import requests
import re
import time

st.set_page_config(page_title="WB Armor Box Updater", layout="wide", page_icon="🛡️")

st.title("🛡️ Защищённый комбайн карточек Wildberries v2")
st.caption("Точечное изменение характеристик по галочкам с абсолютной защитой от удаления Названий, Брендов и Артикулов")

if "fetched_data" not in st.session_state:
    st.session_state.fetched_data = None
if "df_preview" not in st.session_state:
    st.session_state.df_preview = None

# ==============================================================================
# БОКОВАЯ ПАНЕЛЬ: ВЫБОР ТОГО, ЧТО МЫ ХОТИМ ИЗМЕНИТЬ
# ==============================================================================
st.sidebar.header("🔑 Доступ")
wb_token = st.sidebar.text_input("API Токен (Контент)", type="password")

st.sidebar.header("🔢 Товар")
articules_input = st.sidebar.text_area("Артикулы nmID (каждый с новой строки)", height=80, placeholder="916295595")

st.sidebar.header("🎯 Выберите поля для изменения:")
ch_desc = st.sidebar.checkbox("Изменить Описание", value=True)
ch_dims = st.sidebar.checkbox("Изменить Габариты упаковки", value=False)
ch_weight = st.sidebar.checkbox("Изменить Вес с упаковкой", value=False)
ch_tnved = st.sidebar.checkbox("Изменить ТН ВЭД", value=False)
ch_complect = st.sidebar.checkbox("Изменить Комплектацию", value=False)
ch_material = st.sidebar.checkbox("Изменить Материал изделия", value=False)
ch_nazn = st.sidebar.checkbox("Изменить Назначение держателя", value=False)
ch_gift = st.sidebar.checkbox("Изменить Назначение подарка", value=False)
ch_povod = st.sidebar.checkbox("Изменить Повод", value=False)
ch_item_dims = st.sidebar.checkbox("Изменить Размеры предмета", value=False)
ch_model = st.sidebar.checkbox("Изменить Модель", value=False)
ch_fragile = st.sidebar.checkbox("Изменить Хрупкость", value=False)

st.sidebar.header("📝 Новые значения:")

new_length, new_width, new_height = 18, 14, 1
if ch_dims:
    new_length = st.sidebar.number_input("Длина упаковки (см)", min_value=1, value=18)
    new_width = st.sidebar.number_input("Ширина упаковки (см)", min_value=1, value=14)
    new_height = st.sidebar.number_input("Высота упаковки (см)", min_value=1, value=1)
new_weight_val = "0.03"
if ch_weight:
    new_weight_val = st.sidebar.text_input("Вес упаковки (кг, через точку)", value="0.03")

tnved_val = ""
if ch_tnved:
    tnved_val = st.sidebar.text_input("Код ТН ВЭД (10 цифр)", value="3926909709")

complect_val = ""
if ch_complect:
    complect_val = st.sidebar.text_area("Комплектация (через запятую)", value="Металлическая пластина - 1 шт, Двухсторонний скотч - 1 шт")

material_val = ""
if ch_material:
    material_val = st.sidebar.text_input("Материал изделия (через запятую)", value="металл")

nazn_val = ""
if ch_nazn:
    nazn_val = st.sidebar.text_input("Назначение держателя в авто", value="смартфоны, для навигатора")

gift_val = ""
if ch_gift:
    gift_val = st.sidebar.text_input("Назначение подарка (через запятую)", value="любимому, любимой, другу, подруге")

povod_val = ""
if ch_povod:
    povod_val = st.sidebar.text_input("Повод (через запятую)", value="новый год, день рождения, 23 февраля")

item_height_val, item_width_val = 6, 4
if ch_item_dims:
    item_height_val = st.sidebar.number_input("Высота предмета (см)", min_value=1, value=6)
    item_width_val = st.sidebar.number_input("Ширина предмета (см)", min_value=1, value=4)

model_val = ""
if ch_model:
    model_val = st.sidebar.text_input("Модель", value="металлическая пластина на телефон")

fragile_val = ""
if ch_fragile:
    fragile_val = st.sidebar.text_input("Хрупкость", value="не хрупкое")

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
            "filter": {"withPhoto": -1, "hideTrash": False, "nmIDs": [int(x) for x in id_chunk]}
        }
    }
    try:
        res = requests.post(url_list, headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            cards = res.json().get("cards", [])
            return [c for c in cards if int(c.get("nmID", 0)) in id_chunk]
        elif res.status_code == 429:
            time.sleep(15)
            return fetch_cards_by_ids_pure(id_chunk, token)
    except:
        pass
    return []
        # Вывод таблицы предварительного контроля
        if st.session_state.df_preview is not None:
            st.subheader("👀 Таблица предварительного контроля данных")
            st.markdown("Внимательно проверьте параметры карточки. Всё, что не отмечено галочками, останется БЕЗ изменений. Артикулы, Название, Баркоды и Бренд полностью защищены от удаления.")
            st.dataframe(st.session_state.df_preview, use_container_width=True)
            
            st.subheader("🚀 Массовое сохранение изменений")
            if st.button("🔥 Шаг 2: Отправить выбранные изменения в Wildberries", type="secondary"):
                progress_bar = st.progress(0)
                cards_to_update = st.session_state.fetched_data
                total_cards = len(cards_to_update)
                update_payload_batch = []
                success_count = 0
                
                for index, card in enumerate(cards_to_update, 1):
                    nm_id = int(card.get("nmID"))
                    old_desc = card.get("description", "")
                    
                    match = re.search(r'["«](.*?)["»]', old_desc)
                    print_name = match.group(1).strip() if match else card.get("title", "").replace("Металлическая пластина для телефона", "").strip()
                    
                    # ИСПОЛЬЗУЕМ СУПЕР-ЗАЩИТУ: Модифицируем ТОЛЬКО ОРИГИНАЛЬНЫЙ СКАЧАННЫЙ МАССИВ WB
                    # Если галочка снята, то поля "description" и "dimensions" летят в WB в исходном, родном виде!
                    if ch_desc:
                        card["description"] = new_desc_template.format(print_name=print_name)
                    
                    if ch_dims:
                        card["dimensions"] = {
                            "length": int(new_length),
                            "width": int(new_width),
                            "height": int(new_height)
                        }
                    
                    # ТОЧЕЧНАЯ МОДИФИКАЦИЯ ВНУТРЕННИХ ХАРАКТЕРИСТИК (МАССИВ CHARACTERISTICS)
                    if "characteristics" not in card:
                        card["characteristics"] = []
                        
                    characteristics = card["characteristics"]
                    existing_chars = {str(c.get("name")).lower(): c for c in characteristics}
                    
                    def set_char_value(char_name_str, char_value_list):
                        name_lower = char_name_str.lower()
                        if name_lower in existing_chars:
                            existing_chars[name_lower]["value"] = char_value_list
                        else:
                            characteristics.append({"name": char_name_str, "value": char_value_list})
                    
                    # Модифицируем характеристики строго по галочкам. Неотмеченные летят обратно нетронутыми!
                    if ch_weight: set_char_value("Вес с упаковкой (кг)", [str(new_weight_val)])
                    if ch_tnved:
                        set_char_value("Код ТН ВЭД", [str(tnved_val)])
                        set_char_value("ТНВЭД", [str(tnved_val)])
                    if ch_complect: set_char_value("Комплектация", text_to_wb_list(complect_val))
                    if ch_material: set_char_value("Материал изделия", text_to_wb_list(material_val))
                    if ch_nazn: set_char_value("Назначение держателя в авто", text_to_wb_list(nazn_val))
                    if ch_gift: set_char_value("Назначение подарка", text_to_wb_list(gift_val))
                    if ch_povod: set_char_value("Повод", text_to_wb_list(povod_val))
                    if ch_item_dims:
                        set_char_value("Высота предмета (см)", [str(item_height_val)])
                        set_char_value("Ширина предмета (см)", [str(item_width_val)])
                    if ch_model: set_char_value("Модель", [str(model_val)])
                    if ch_fragile: set_char_value("Хрупкость", [str(fragile_val)])
                    
                    update_payload_batch.append(card)
                    
                    if len(update_payload_batch) == 100 or index == total_cards:
                        success, msg = send_update_batch(update_payload_batch, wb_token)
                        if success:
                            success_count += len(update_payload_batch)
                        else:
                            st.error(f"Ошибка WB при сохранении: {msg}")
                        update_payload_batch = []
                        if index < total_cards:
                            time.sleep(8)
                    progress_bar.progress(index / total_cards)
                
                st.success(f"🎉 Процесс полностью завершен! Успешно изменено карточек: {success_count} из {total_cards}")
                st.session_state.fetched_data = None
                st.session_state.df_preview = None
else:
    st.info("💡 Настройте токен контента и артикулы на левой панели. Отметьте нужные галочки для точечного изменения.")
