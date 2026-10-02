import streamlit as st
import pandas as pd
import requests
import re
import time

st.set_page_config(page_title="WB Total Armor Updater", layout="wide", page_icon="🛡️")

st.title("🛡️ Защищённый комбайн карточек Wildberries v2")
st.caption("Массовое точечное изменение характеристик по галочкам с абсолютной защитой ключевых данных")

if "fetched_data" not in st.session_state:
    st.session_state.fetched_data = None
if "df_preview" not in st.session_state:
    st.session_state.df_preview = None

# ==============================================================================
# БОКОВАЯ ПАНЕЛЬ: СИСТЕМА УПРАВЛЕНИЯ ГАЛОЧКАМИ
# ==============================================================================
st.sidebar.header("🔑 Доступ")
wb_token = st.sidebar.text_input("API Токен (Контент)", type="password")

st.sidebar.header("🔢 Товар")
articules_input = st.sidebar.text_area("Артикулы nmID (каждый с новой строки)", height=80, placeholder="916295595")

st.sidebar.header("🎯 Выберите поля для изменения:")
ch_desc = st.sidebar.checkbox("Изменить Описание", value=True)
ch_dims = st.sidebar.checkbox("Изменить Габариты упаковки", value=False)
ch_weight = st.sidebar.checkbox("Изменить Вес с упаковкой (кг)", value=False)
ch_tnved = st.sidebar.checkbox("Изменить ТН ВЭД / ТНВЭД", value=False)
ch_group = st.sidebar.checkbox("Изменить Группу (объединение)", value=False)
ch_complect = st.sidebar.checkbox("Изменить Комплектацию", value=False)
ch_material = st.sidebar.checkbox("Изменить Материал изделия", value=False)
ch_nazn = st.sidebar.checkbox("Изменить Назначение товара", value=False) # ИСПРАВЛЕНО НАЗВАНИЕ ПО СФЕРЕ WB
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
                        
                        sizes_list = card.get("sizes", [])
                        barcodes_found = []
                        for sz in sizes_list:
                            barcodes_found.extend(sz.get("skus", []))
                        barcodes_str = ", ".join(barcodes_found) if barcodes_found else "—"
                        
                        dimensions_old = card.get("dimensions", {})
                        old_dims_str = f"{dimensions_old.get('length', '—')}x{dimensions_old.get('width', '—')}x{dimensions_old.get('height', '—')}"
                        
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
                        if ch_tnved: row_data["Код ТН ВЭД / ТНВЭД"] = tnved_val
                        if ch_group: row_data["Группа (Объединение)"] = group_val
                        if ch_complect: row_data["Комплектация"] = complect_val[:40] + "..." if len(complect_val) > 40 else complect_val
                        if ch_material: row_data["Материал изделия"] = material_val
                        if ch_nazn: row_data["Назначение товара"] = nazn_val
                        if ch_gift: row_data["Назначение подарка"] = gift_val
                        if ch_povod: row_data["Повод"] = povod_val
                        if ch_item_dims: row_data["Размеры предмета"] = f"В:{item_height_val} x Ш:{item_width_val}"
                        if ch_model: row_data["Модель"] = model_val
                        if ch_fragile: row_data["Хрупкость"] = fragile_val
                        
                        preview_rows.append(row_data)
                        
                    st.session_state.df_preview = pd.DataFrame(preview_rows)
                else:
                    st.warning("⚠️ Не найдено карточек. Проверьте правильность токена контента или введённых nmID.")
        if st.session_state.df_preview is not None:
            st.subheader("👀 Таблица предварительного контроля данных")
            st.markdown("Внимательно проверьте параметры карточки. Всё, что не отмечено галочками, останется БЕЗ изменений. Артикулы, Название, Баркоды, Артикул продавца и Бренд полностью защищены от удаления.")
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
                    
                    if ch_dims:
                        card["dimensions"] = {
                            "length": int(new_length),
                            "width": int(new_width),
                            "height": int(new_height)
                        }
                    
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
                    
                    # ПРЯМАЯ ПЕРЕДАЧА ЧИСЕЛ БЕЗ ТЕКСТОВЫХ КАВЫЧЕК ДЛЯ ВЕСА И РАЗМЕРОВ ТОВАРА
                    if ch_weight:
                        # Вес передаем как число с плавающей точкой
                        set_char_value("Вес с упаковкой (кг)", [float(new_weight_val)])
                        set_char_value("Вес с упаковкой (кг)", [float(new_weight_val)])
                        try:
                            # Перевод в граммы как целое число (если требует старая схема WB)
                            grams_val = int(float(new_weight_val) * 1000)
                            set_char_value("Вес товара с упаковкой (г)", [grams_val])
                        except:
                            pass
                            
                    if ch_tnved:
                        set_char_value("Код ТН ВЭД", [str(tnved_val)])
                        set_char_value("ТНВЭД", [str(tnved_val)])
                    if ch_complect: set_char_value("Комплектация", text_to_wb_list(complect_val))
                    if ch_material: set_char_value("Материал изделия", text_to_wb_list(material_val))
                    if ch_nazn: set_char_value("Назначение товара", text_to_wb_list(nazn_val))
                    if ch_gift: set_char_value("Назначение подарка", text_to_wb_list(gift_val))
                    if ch_povod: set_char_value("Повод", text_to_wb_list(povod_val))
                    
                    # Размеры предмета передаем строго как числа
                    if ch_item_dims:
                        set_char_value("Высота предмета (см)", [int(item_height_val)])
                        set_char_value("Ширина предмета (см)", [int(item_width_val)])
                        
                    if ch_model: set_char_value("Модель", [str(model_val)])
                    if ch_fragile: set_char_value("Хрупкость", [str(fragile_val)])
                    
                    if ch_group:
                        card["targetUrl"] = str(group_val)
                    
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
