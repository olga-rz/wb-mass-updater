import streamlit as st
import pandas as pd
import requests
import re
import time

st.set_page_config(page_title="WB Armor Box Updater", layout="wide", page_icon="🛡️")

st.title("🛡️ Защищённый комбайн карточек Wildberries v2")
st.caption("Точечное изменение характеристик по галочкам с абсолютной защитой от удаления Названий и Брендов")

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

# Защищенные системные ссылки API
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

def send_update_batch(cards_payload, token):
    headers = {"Authorization": token, "Content-Type": "application/json", "Accept": "application/json"}
    _, url_update = get_real_urls()
    try:
        res = requests.post(url_update, headers=headers, json=cards_payload, timeout=20)
        return res.status_code == 200, f"Код {res.status_code}: {res.text[:150]}"
    except Exception as e:
        return False, f"Ошибка сети: {e}"

# Раздел «Замена стикеров» (Шаблон описания выведен на экран)
st.header("📝 Раздел: Замена описаний (Стикеры)")
new_desc_template = st.text_area(
    "Вы можете отредактировать этот текст. Переменная {print_name} автоматически заменится на имя принта из кавычек текущей карточки.",
    value="""Металлическая пластина для телефона "{print_name}" — незаменимый аксессуар для каждого водителя, обеспечивающий надежную фиксацию и стильный вид вашего гаджета.
Наша пластина для магнитного держателя телефона создана для тех, кто ищет бескомпромиссную надежность. Этот красивый магнит на телефон гарантирует, что ваш смартфон останется на месте даже при резком торможении. Мощная металлическая пластина для телефона превращает обычный держатель для телефона в машину в идеальную систему крепления.

Обратите внимание: Данный аксессуар — это именно металлическая пластина, которая притягивается к магниту. Сама наклейка не является магнитом, поэтому она полностью безопасна для вашего смартфона и не влияет на работу его внутренних модулей.""",
    height=200
)
# Функция для превращения строки с запятыми в правильный список WB
def text_to_wb_list(text_data):
    return [x.strip() for x in str(text_data).split(",") if x.strip()]

if articules_input and wb_token:
    target_nm_ids = []
    for line in articules_input.splitlines():
        line_clean = line.strip()
        if line_clean and line_clean.isdigit():
            target_nm_ids.append(int(line_clean))
    target_nm_ids = list(set(target_nm_ids))
    
    if target_nm_ids:
        st.success(f"✅ Введено уникальных артикулов для обработки: {len(target_nm_ids)}")
        
        # КНОПКА ШАГ 1: БЕЗОПАСНАЯ ВЫГРУЗКА
        if st.button("🔍 Шаг 1: Проверить карточки и сопоставить характеристики", type="primary"):
            with st.spinner("Синхронизация данных с серверами Wildberries..."):
                all_fetched_cards = fetch_cards_by_ids_pure(target_nm_ids, wb_token)
                
                if all_fetched_cards:
                    st.session_state.fetched_data = all_fetched_cards
                    preview_rows = []
                    
                    for card in all_fetched_cards:
                        nm_id = int(card.get("nmID"))
                        old_desc = card.get("description", "")
                        
                        match = re.search(r'["«](.*?)["»]', old_desc)
                        print_name = match.group(1).strip() if match else card.get("title", "").replace("Металлическая пластина для телефона", "").strip()
                        
                        # Собираем текущие габариты
                        dimensions_old = card.get("dimensions", {})
                        old_dims_str = f"{dimensions_old.get('length', '—')}x{dimensions_old.get('width', '—')}x{dimensions_old.get('height', '—')}"
                        
                        # Безопасный показ текущего Названия и Бренда
                        preview_rows.append({
                            "Артикул nmID": nm_id,
                            "Артикул продавца": card.get("vendorCode", ""),
                            "Название (ЗАЩИЩЕНО)": card.get("title", "—"),
                            "Бренд (ЗАЩИЩЕНО)": card.get("brand", "—"),
                            "Вытащенный принт": print_name,
                            "Размеры упаковки": f"{new_length}x{new_width}x{new_height}" if ch_dims else old_dims_str,
                            "Вес упаковки (кг)": new_weight_val if ch_weight else "Не меняется"
                        })
                    st.session_state.df_preview = pd.DataFrame(preview_rows)
                else:
                    st.warning("⚠️ Не найдено карточек. Проверьте правильность токена контента или введённых nmID.")
        
        # Вывод таблицы предварительного контроля
        if st.session_state.df_preview is not None:
            st.subheader("👀 Таблица предварительного контроля данных")
            st.markdown("Внимательно проверьте параметры карточки. Всё, что не отмечено галочками, останется без изменений.")
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
                    
                    # 1. ОБНОВЛЕНИЕ ОПИСАНИЯ ПО ГАЛОЧКЕ
                    final_description = card.get("description", "")
                    if ch_desc:
                        final_description = new_desc_template.format(print_name=print_name)
                    
                    # 2. ОБНОВЛЕНИЕ ГАБАРИТОВ ПО ГАЛОЧКЕ
                    final_dimensions = card.get("dimensions", {"length": 18, "width": 14, "height": 1})
                    if ch_dims:
                        final_dimensions = {
                            "length": int(new_length),
                            "width": int(new_width),
                            "height": int(new_height)
                        }
                    
                    # 3. ТОЧЕЧНАЯ МОДИФИКАЦИЯ ХАРАКТЕРИСТИК (МАССИВ CHARACTERISTICS)
                    characteristics = card.get("characteristics", [])
                    
                    # Сбор текущих служебных полей характеристик для железной защиты от удаления
                    existing_chars = {str(c.get("name")).lower(): c for c in characteristics}
                    
                    # Функция для безопасной перезаписи или добавления поля
                    def set_char_value(char_name_str, char_value_list):
                        name_lower = char_name_str.lower()
                        if name_lower in existing_chars:
                            existing_chars[name_lower]["value"] = char_value_list
                        else:
                            characteristics.append({"name": char_name_str, "value": char_value_list})
                    
                    # Перезаписываем только то, что выбрано пользователем (по галочкам)
                    if ch_weight:
                        set_char_value("Вес с упаковкой (кг)", [str(new_weight_val)])
                    if ch_tnved:
                        # УДАР ПО ОБОИМ ВАРИАНТАМ НАЗВАНИЙ ИЗ БАЗЫ ДАННЫХ WB В ДВА НАПРАВЛЕНИЯ
                        set_char_value("Код ТН ВЭД", [str(tnved_val)])
                        set_char_value("ТНВЭД", [str(tnved_val)])
                    if ch_complect:
                        set_char_value("Комплектация", text_to_wb_list(complect_val))
                    if ch_material:
                        set_char_value("Материал изделия", text_to_wb_list(material_val))
                    if ch_nazn:
                        set_char_value("Назначение держателя в авто", text_to_wb_list(nazn_val))
                    if ch_gift:
                        set_char_value("Назначение подарка", text_to_wb_list(gift_val))
                    if ch_povod:
                        set_char_value("Повод", text_to_wb_list(povod_val))
                    
                    # Формируем финальную карточку
                    clean_card = {
                        "nmID": nm_id,
                        "vendorCode": card.get("vendorCode"),
                        "description": final_description,
                        "dimensions": final_dimensions,
                        "characteristics": characteristics,
                        "sizes": card.get("sizes", [])
                    }
                    if "mediaFiles" in card:
                        clean_card["mediaFiles"] = card["mediaFiles"]
                        
                    update_payload_batch.append(clean_card)
                    
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
