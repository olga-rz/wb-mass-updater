import streamlit as st
import pandas as pd
import requests
import re
import time

st.set_page_config(page_title="WB Total Armor Updater", layout="wide", page_icon="🛡️")

st.title("🛡️ Защищённый комбайн карточек Wildberries v2")
st.caption("Массовое точечное изменение характеристик по галочкам с абсолютной защитой ключевых данных по спецификации WB")

if "fetched_data" not in st.session_state:
    st.session_state.fetched_data = None
if "df_preview" not in st.session_state:
    st.session_state.df_preview = None

if "checkbox_state" not in st.session_state:
    st.session_state.checkbox_state = False

# ==============================================================================
# БОКОВАЯ ПАНЕЛЬ: УПРАВЛЕНИЕ ДОСТУПОМ И УМНЫЕ КНОПКИ
# ==============================================================================
st.sidebar.header("🔑 Доступ")
wb_token = st.sidebar.text_input("API Токен (Контент)", type="password")

st.sidebar.header("🔢 Товар")
articules_input = st.sidebar.text_area("Артикулы nmID (каждый с новой строки)", height=80, placeholder="916295595")

st.sidebar.header("🎯 Выберите поля для изменения:")

col_btn1, col_btn2 = st.sidebar.columns(2)
with col_btn1:
    if st.button("✅ Выделить всё", use_container_width=True):
        st.session_state.checkbox_state = True
        st.rerun()
with col_btn2:
    if st.button("❌ Сбросить всё", use_container_width=True):
        st.session_state.checkbox_state = False
        st.rerun()

default_val = st.session_state.checkbox_state

ch_desc = st.sidebar.checkbox("Изменить Описание", value=default_val)
ch_dims = st.sidebar.checkbox("Изменить Габариты упаковки", value=default_val)
ch_weight = st.sidebar.checkbox("Изменить Вес с упаковкой (кг)", value=default_val)
ch_tnved = st.sidebar.checkbox("Изменить Код ТН ВЭД", value=default_val)
ch_complect = st.sidebar.checkbox("Изменить Комплектацию", value=default_val)
ch_material = st.sidebar.checkbox("Изменить Материал изделия", value=default_val)
ch_nazn = st.sidebar.checkbox("Изменить Назначение держателя в авто", value=default_val)
ch_gift = st.sidebar.checkbox("Изменить Назначение подарка", value=default_val)
ch_povod = st.sidebar.checkbox("Изменить Повод", value=default_val)
ch_model = st.sidebar.checkbox("Изменить Модель", value=default_val)
ch_fragile = st.sidebar.checkbox("Изменить Хрупкость", value=default_val)
ch_kreplenie = st.sidebar.checkbox("Изменить Тип крепления", value=default_val)

st.sidebar.header("📝 Новые значения:")

new_length, new_width, new_height = 18, 14, 1
if ch_dims:
    new_length = st.sidebar.number_input("Длина упаковки (см)", min_value=1, value=18)
    new_width = st.sidebar.number_input("Ширина упаковки (см)", min_value=1, value=14)
    new_height = st.sidebar.number_input("Высота упаковки (см)", min_value=1, value=1)
new_weight_val = 0.030
if ch_weight:
    new_weight_val = st.sidebar.number_input("Вес упаковки (кг)", min_value=0.001, value=0.030, step=0.001, format="%.3f")

tnved_val = ""
if ch_tnved:
    tnved_val = st.sidebar.text_input("Код ТН ВЭД (10 цифр)", value="3926909709")

complect_val = ""
if ch_complect:
    complect_val = st.sidebar.text_area("Комплектация (через точку с запятой ';')", value="Металлическая пластина - 1 шт; Двухсторонний скотч - 1 шт")

material_val = ""
if ch_material:
    material_val = st.sidebar.text_input("Материал изделия (через запятую)", value="металл")

nazn_val = ""
if ch_nazn:
    nazn_val = st.sidebar.text_input("Назначение держателя в авто (через запятую)", value="смартфоны, для навигатора, для автодержателя, планшеты")

gift_val = ""
if ch_gift:
    gift_val = st.sidebar.text_input("Назначение подарка (через запятую)", value="любимому, любимой, другу, подруге")

povod_val = ""
if ch_povod:
    povod_val = st.sidebar.text_input("Повод (через запятую)", value="новый год, день рождения, 23 февраля")

model_val = ""
if ch_model:
    model_val = st.sidebar.text_input("Модель", value="металлическая пластина на телефон")

fragile_val = ""
if ch_fragile:
    fragile_val = st.sidebar.text_input("Хрупкость", value="не хрупкое")

kreplenie_val = ""
if ch_kreplenie:
    kreplenie_val = st.sidebar.text_input("Тип крепления (через запятую)", value="клейкая поверхность, двусторонний скотч")

def get_real_urls():
    part_a = b'https://content-'
    part_b = b'api.wildberries.ru/content/v2/get/cards/list'
    part_c = b'api.wildberries.ru/content/v2/cards/update'
    return (part_a + part_b).decode('utf-8'), (part_a + part_c).decode('utf-8')

# УМНАЯ СЛУЖБА МАССОВОЙ ВЫГРУЗКИ КАРТОЧЕК С ЦИКЛОМ ПАГИНАЦИИ ДО КРУГЛОГО КОНЦА БАЗЫ
def fetch_cards_by_ids_pure(id_chunk, token):
    headers = {"Authorization": token, "Content-Type": "application/json", "Accept": "application/json"}
    url_list, _ = get_real_urls()
    all_found_cards = []
    
    # Системные указатели для бесконечной прокрутки базы WB v2
    has_more = True
    nm_cursor = {
        "limit": 100
    }
    
    while has_more:
        payload = {
            "settings": {
                "cursor": nm_cursor,
                "filter": {"withPhoto": -1, "hideTrash": False}
            }
        }
        try:
            res = requests.post(url_list, headers=headers, json=payload, timeout=20)
            if res.status_code == 200:
                data_json = res.json()
                cards = data_json.get("cards", [])
                
                # Фильтруем пачку на лету: забираем только те, nmID которых есть в списке пользователя
                for c in cards:
                    if int(c.get("nmID", 0)) in id_chunk:
                        all_found_cards.append(c)
                        
                # Проверяем, есть ли следующая страница по меткам cursor
                res_cursor = data_json.get("cursor", {})
                updated_nm_id = res_cursor.get("nmID", 0)
                updated_updated_at = res_cursor.get("updatedAt", "")
                total_returned = res_cursor.get("total", 0)
                
                if total_returned < 100 or updated_nm_id == 0:
                    has_more = False
                else:
                    nm_cursor["nmID"] = updated_nm_id
                    nm_cursor["updatedAt"] = updated_updated_at
                    time.sleep(0.4) # Безопасная пауза перед пролистыванием страницы
            elif res.status_code == 429:
                time.sleep(15)
                continue
            else:
                has_more = False
        except Exception as e:
            has_more = False
            
    # Убираем дубли, если они проскочили
    seen_ids = set()
    final_clean_cards = []
    for card in all_found_cards:
        c_id = int(card.get("nmID"))
        if c_id not in seen_ids:
            seen_ids.add(c_id)
            final_clean_cards.append(card)
            
    return final_clean_cards
def send_update_batch(cards_payload, token):
    headers = {"Authorization": token, "Content-Type": "application/json", "Accept": "application/json"}
    _, url_update = get_real_urls()
    try:
        res = requests.post(url_update, headers=headers, json=cards_payload, timeout=20)
        return res.status_code == 200, f"Код {res.status_code}: {res.text[:150]}"
    except Exception as e:
        return False, f"Ошибка сети: {e}"

st.header("📝 Раздел: Замена описаний (Стикеры)")
new_desc_template = st.text_area(
    "Вы можете отредактировать этот текст. Переменная {print_name} автоматически заменится на имя принта из кавычек текущей карточки.",
    value="""Металлическая пластина для телефона "{print_name}" — незаменимый аксессуар для каждого водителя, обеспечивающий надежную фиксацию и стильный вид вашего гаджета.""",
    height=100
)

def text_to_wb_list_by_sep(text_data, separator=","):
    return [x.strip() for x in str(text_data).split(separator) if x.strip()]

if articules_input and wb_token:
    target_nm_ids = []
    for line in articules_input.splitlines():
        line_clean = line.strip()
        if line_clean and line_clean.isdigit():
            target_nm_ids.append(int(line_clean))
    target_nm_ids = list(set(target_nm_ids))
    
    if target_nm_ids:
        st.success(f"✅ Введено уникальных артикулов для обработки: {len(target_nm_ids)}")
        
        if st.button("🔍 Шаг 1: Проверить карточки и сопоставить характеристики", type="primary"):
            with st.spinner("Синхронизация данных с серверами Wildberries (пролистывание страниц)..."):
                all_fetched_cards = fetch_cards_by_ids_pure(target_nm_ids, wb_token)
                
                if all_fetched_cards:
                    st.session_state.fetched_data = all_fetched_cards
                    preview_rows = []
                    
                    for card in all_fetched_cards:
                        nm_id = int(card.get("nmID"))
                        old_desc = card.get("description", "")
                        
                        match = re.search(r'["«](.*?)["»]', old_desc)
                        print_name = match.group(1).strip() if match else card.get("title", "").replace("Металлическая пластина для телефона", "").strip()
                        
                        sizes_list = card.get("sizes", [])
                        barcodes_found = []
                        for sz in sizes_list:
                            barcodes_found.extend(sz.get("skus", []))
                        barcodes_str = ", ".join(barcodes_found) if barcodes_found else "—"
                        
                        row_data = {
                            "Артикул nmID (ЗАЩИЩЕН)": nm_id,
                            "Артикул продавца (ЗАЩИЩЕН)": card.get("vendorCode", ""),
                            "Название (ЗАЩИЩЕНО)": card.get("title", "—"),
                            "Бренд (ЗАЩИЩЕНО)": card.get("brand", "—"),
                            "Баркоды (ЗАЩИЩЕНО)": barcodes_str,
                            "Вытащенный принт": print_name,
                        }
                        
                        if ch_desc: row_data["Новое Описание"] = "Будет обновлено"
                        if ch_dims: row_data["Размеры упаковки"] = f"{new_length}x{new_width}x{new_height}"
                        if ch_weight: row_data["Вес упаковки (кг)"] = f"{new_weight_val:.3f}"
                        if ch_tnved: row_data["Код ТН ВЭД"] = tnved_val
                        if ch_complect: row_data["Комплектация"] = complect_val[:40] + "..." if len(complect_val) > 40 else complect_val
                        if ch_material: row_data["Материал изделия"] = material_val
                        if ch_nazn: row_data["Назначение держателя"] = nazn_val[:40] + "..."
                        if ch_gift: row_data["Назначение подарка"] = gift_val
                        if ch_povod: row_data["Повод"] = povod_val
                        if ch_model: row_data["Модель"] = model_val
                        if ch_fragile: row_data["Хрупкость"] = fragile_val
                        if ch_kreplenie: row_data["Тип крепления"] = kreplenie_val
                        
                        preview_rows.append(row_data)
                        
                    st.session_state.df_preview = pd.DataFrame(preview_rows)
                else:
                    st.warning("⚠️ Не найдено карточек. Проверьте правильность токена контента или введённых nmID.")
        if st.session_state.df_preview is not None:
            st.subheader("👀 Таблица предварительного контроля данных")
            st.markdown(f"Отображено найденных карточек в системе: {len(st.session_state.df_preview)} из {len(target_nm_ids)}")
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
                    
                    if ch_desc:
                        card["description"] = new_desc_template.format(print_name=print_name)
                    
                    if "dimensions" not in card or not card["dimensions"]:
                        card["dimensions"] = {"length": 18, "width": 14, "height": 1, "weightBrutto": 0.03}
                        
                    if ch_dims:
                        card["dimensions"]["length"] = int(new_length)
                        card["dimensions"]["width"] = int(new_width)
                        card["dimensions"]["height"] = int(new_height)
                    
                    if ch_weight:
                        card["dimensions"]["weightBrutto"] = float(new_weight_val)
                    
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
                    
                    # ПРАВИЛЬНОЕ РАСПРЕДЕЛЕНИЕ ТН ВЭД И КОМПЛЕКТАЦИИ ПО СТАНДАРТАМ КАТЕГОРИИ v2
                    if ch_tnved:
                        # ТН ВЭД передаем СТРОГО списком строк ["код"]
                        set_char_value("Код ТН ВЭД", [str(tnved_val)])
                        
                    if ch_complect: 
                        # Комплектацию делим строго через точку с запятой ';' из Excel шаблона дистрибьютора
                        set_char_value("Комплектация", text_to_wb_list_by_sep(complect_val, separator=";"))
                        
                    if ch_material: set_char_value("Материал изделия", text_to_wb_list_by_sep(material_val, separator=","))
                    if ch_nazn: set_char_value("Назначение держателя в авто", text_to_wb_list_by_sep(nazn_val, separator=","))
                    if ch_gift: set_char_value("Назначение подарка", text_to_wb_list_by_sep(gift_val, separator=","))
                    if ch_povod: set_char_value("Повод", text_to_wb_list_by_sep(povod_val, separator=","))
                    if ch_model: set_char_value("Модель", [str(model_val)])
                    if ch_fragile: set_char_value("Хрупкость", [str(fragile_val)])
                    if ch_kreplenie: set_char_value("Тип крепления", text_to_wb_list_by_sep(kreplenie_val, separator=","))
                    
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
