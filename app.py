# Редактор карточек Wildberries — версия в одном файле.
# Зависимости: streamlit==1.64.0, requests==2.34.2
# Запуск: python -m streamlit run app.py
from __future__ import annotations


# ========================================================================
# core.py
"""Pure validation and change planning. No network or Streamlit state."""

from copy import deepcopy
import hashlib
import json
import math
import re


class ValidationError(ValueError):
    pass


# key: (UI label, accepted exact names, separator, default)
FIELDS = {
    "tnved": ("Код ТН ВЭД", ("Код ТН ВЭД", "ТНВЭД", "ТН ВЭД"), ",", "3926909709"),
    "complect": ("Комплектация", ("Комплектация",), ";", "Металлическая пластина - 1 шт; Двухсторонний скотч - 1 шт"),
    "material": ("Материал изделия", ("Материал изделия",), ",", "металл"),
    "nazn": ("Назначение держателя в авто", ("Назначение держателя в авто",), ",", "смартфоны"),
    "gift": ("Назначение подарка", ("Назначение подарка",), ",", "любимому, любимой"),
    "povod": ("Повод", ("Повод",), ",", "день рождения"),
    "model": ("Модель", ("Модель",), None, "металлическая пластина на телефон"),
    "fragile": ("Хрупкость", ("Хрупкость",), None, "не хрупкое"),
    "kreplenie": ("Тип крепления", ("Тип крепления",), ",", "двусторонний скотч"),
}
LABELS = {"description": "Описание", "dimensions": "Габариты упаковки", "weight": "Вес с упаковкой", **{k: v[0] for k, v in FIELDS.items()}}
DEFAULT_DESCRIPTION = 'Металлическая пластина для телефона "{print_name}" — аксессуар для крепления телефона к магнитному держателю.'


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def parse_ids(text):
    tokens = re.split(r"[\s,;]+", text.strip()) if text.strip() else []
    invalid = [t for t in tokens if not re.fullmatch(r"[0-9]{1,18}", t) or int(t) <= 0]
    if invalid:
        raise ValidationError("Некорректные артикулы: " + ", ".join(invalid[:10]))
    ids = list(dict.fromkeys(int(t) for t in tokens))
    if not ids:
        raise ValidationError("Введите хотя бы один артикул nmID.")
    if len(ids) > 10000:
        raise ValidationError("За одну операцию можно выбрать до 10 000 артикулов.")
    return ids


def normalized_name(text):
    return re.sub(r"[^\w]", "", str(text).casefold().replace("ё", "е"))


def suggest_characteristic(key, schema):
    names = {normalized_name(n) for n in FIELDS[key][1]}
    matches = [int(c["charcID"]) for c in schema if normalized_name(c.get("name", "")) in names]
    return matches[0] if len(matches) == 1 else None


def print_name(card):
    match = re.search(r'«([^»]+)»|"([^"]+)"|“([^”]+)”', card.get("description", ""))
    if match:
        return next(group for group in match.groups() if group is not None).strip()
    return re.sub(r"^Металлическая пластина для телефона\s*", "", card.get("title", ""), flags=re.I).strip()


def characteristic_value(key, text, definition):
    if not str(text).strip():
        raise ValidationError(f"{FIELDS[key][0]}: новое значение не может быть пустым.")
    if key == "tnved" and not re.fullmatch(r"[0-9]{10}", str(text).strip()):
        raise ValidationError("ТН ВЭД должен содержать ровно 10 цифр.")
    if definition.get("charcType") == 4:
        try:
            value = float(str(text).replace(",", "."))
        except ValueError:
            raise ValidationError(f"{definition['name']}: WB ожидает одно число.") from None
        if not math.isfinite(value):
            raise ValidationError("Число должно быть конечным.")
        return int(value) if value.is_integer() else value
    if definition.get("charcType") not in (None, 0, 1):
        raise ValidationError(f"{definition['name']}: неизвестный тип характеристики {definition['charcType']}.")
    sep = FIELDS[key][2]
    values = list(dict.fromkeys(x.strip() for x in (str(text).split(sep) if sep else [str(text)]) if x.strip()))
    max_count = int(definition.get("maxCount") or 0)
    if max_count > 0 and len(values) > max_count:
        raise ValidationError(f"{definition['name']}: WB допускает до {max_count} значений, введено {len(values)}.")
    return values


def update_payload(card):
    """Project a read response onto writable fields, retaining existing values."""
    required = ("nmID", "vendorCode", "title", "brand", "description", "sizes", "characteristics")
    missing = [key for key in required if key not in card or card[key] is None]
    if missing:
        raise ValidationError(f"Карточка {card.get('nmID')}: неполный ответ WB ({', '.join(missing)}). Обновление заблокировано.")
    payload = {k: deepcopy(card[k]) for k in ("nmID", "vendorCode", "title", "brand", "description")}
    for key in ("wholesale", "kizMarked", "documents"):
        if key in card and card[key] is not None:
            payload[key] = deepcopy(card[key])
    if card.get("dimensions") is not None:
        payload["dimensions"] = {k: deepcopy(v) for k, v in card["dimensions"].items() if k in ("length", "width", "height", "weightBrutto")}
    if not isinstance(card["characteristics"], list) or not isinstance(card["sizes"], list) or not card["sizes"]:
        raise ValidationError(f"Карточка {card['nmID']}: отсутствуют размеры или повреждены характеристики.")
    chars, seen = [], set()
    for char in card["characteristics"]:
        if not isinstance(char.get("id"), int) or "value" not in char or char["id"] in seen:
            raise ValidationError(f"Карточка {card['nmID']}: характеристика без ID/значения или с повторным ID.")
        seen.add(char["id"])
        chars.append({"id": char["id"], "value": deepcopy(char["value"])})
    payload["characteristics"] = chars
    sizes = []
    for size in card["sizes"]:
        if not size.get("chrtID") or not isinstance(size.get("skus"), list) or not size["skus"]:
            raise ValidationError(f"Карточка {card['nmID']}: размер без chrtID/баркодов. Обновление заблокировано.")
        sizes.append({k: deepcopy(v) for k, v in size.items() if k in ("chrtID", "techSize", "wbSize", "skus")})
    payload["sizes"] = sizes
    return payload


def normalized_payload(payload):
    result = deepcopy(payload)
    for char in result.get("characteristics", []):
        if isinstance(char["value"], list):
            char["value"] = sorted(char["value"], key=str)
    result["characteristics"] = sorted(result.get("characteristics", []), key=lambda x: x["id"])
    for size in result.get("sizes", []):
        size["skus"] = sorted(size["skus"])
    result["sizes"] = sorted(result.get("sizes", []), key=lambda x: x["chrtID"])
    return result


def snapshot(card):
    return fingerprint({"payload": normalized_payload(update_payload(card)), "updatedAt": card.get("updatedAt"), "subjectID": card.get("subjectID"), "needKiz": card.get("needKiz")})


def prepare_card(card, edits, schemas, mappings, marked_confirmed=False):
    original = update_payload(card)
    payload = deepcopy(original)
    changes = []

    def record(label, before, after):
        if before != after:
            changes.append({"nmID": card["nmID"], "Поле": label, "Было": deepcopy(before), "Станет": deepcopy(after)})

    if "description" in edits:
        text = str(edits["description"])
        # Literal replacement leaves all unrelated braces intact.
        if "{print_name}" in text and not print_name(card):
            raise ValidationError(f"{card['nmID']}: не удалось определить имя принта.")
        text = text.replace("{print_name}", print_name(card))
        if not text.strip() or len(text) > 5000:
            raise ValidationError("Описание должно содержать от 1 до 5000 символов; у категории WB может быть меньший лимит.")
        record("Описание", payload["description"], text)
        payload["description"] = text
    if "dimensions" in edits or "weight" in edits:
        dims = payload.setdefault("dimensions", {})
        if "dimensions" in edits:
            for key, label in (("length", "Длина, см"), ("width", "Ширина, см"), ("height", "Высота, см")):
                value = edits["dimensions"][key]
                if not isinstance(value, int) or value < 1:
                    raise ValidationError("Габариты должны быть целыми положительными числами в сантиметрах.")
                record(label, dims.get(key), value)
                dims[key] = value
        if "weight" in edits:
            value = float(edits["weight"])
            if not math.isfinite(value) or value <= 0:
                raise ValidationError("Вес должен быть положительным числом в килограммах.")
            record("Вес с упаковкой, кг", dims.get("weightBrutto"), value)
            dims["weightBrutto"] = value
    selected = [key for key in FIELDS if key in edits]
    if selected:
        subject = int(card["subjectID"])
        schema = {int(c["charcID"]): c for c in schemas[subject]}
        used = set()
        current = {c["id"]: c for c in payload["characteristics"]}
        for key in selected:
            char_id = mappings.get(subject, {}).get(key)
            if char_id not in schema:
                raise ValidationError(f"{card['nmID']}: выберите характеристику «{FIELDS[key][0]}» для категории {subject}.")
            if char_id in used:
                raise ValidationError(f"Два выбранных поля сопоставлены с одной характеристикой: {schema[char_id]['name']}.")
            used.add(char_id)
            value = characteristic_value(key, edits[key], schema[char_id])
            before = current.get(char_id, {}).get("value")
            record(schema[char_id]["name"], before, value)
            if char_id in current:
                current[char_id]["value"] = value
            else:
                current[char_id] = {"id": char_id, "value": value}
                payload["characteristics"].append(current[char_id])
    if changes and card.get("needKiz") and payload.get("kizMarked") is not True:
        if not marked_confirmed:
            raise ValidationError(f"{card['nmID']}: WB требует подтверждение обязательной маркировки. Отметьте подтверждение только если код действительно нанесён.")
        record("Код обязательной маркировки нанесён", payload.get("kizMarked"), True)
        payload["kizMarked"] = True
    return {"nmID": card["nmID"], "baseline": snapshot(card), "payload": payload, "changes": changes}


def verify_card(actual, expected):
    current = normalized_payload(update_payload(actual))
    wanted = normalized_payload(expected)
    # Compare every field sent, including the fields the user did not change.
    return [key for key, value in wanted.items() if current.get(key) != value]


def make_batches(plans, max_cards=100, max_bytes=9_000_000):
    batch = []
    for plan in plans:
        candidate = [*batch, plan]
        size = len(json.dumps([p["payload"] for p in candidate], ensure_ascii=False).encode("utf-8"))
        if batch and (len(candidate) > max_cards or size > max_bytes):
            yield batch
            batch = []
        if len(json.dumps([plan["payload"]], ensure_ascii=False).encode("utf-8")) > max_bytes:
            raise ValidationError(f"Карточка {plan['nmID']} превышает допустимый размер запроса.")
        batch.append(plan)
    if batch:
        yield batch


# ========================================================================
# wb_api.py
"""WB Content API client. Writes require an explicit UI action."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import threading
import time

import requests

BASE = "https://content-api.wildberries.ru"
LIST = "/content/v2/get/cards/list"
UPDATE = "/content/v2/cards/update"
ERRORS = "/content/v2/cards/error/list"
_LOCK = threading.Lock()
_LAST = {}


class APIError(RuntimeError):
    def __init__(self, message, uncertain=False):
        super().__init__(message)
        self.uncertain = uncertain


def pace(token_key, group, interval):
    # Shared across sessions of this server process, without storing tokens.
    with _LOCK:
        now = time.monotonic()
        key = (token_key, group)
        wait = max(0, _LAST.get(key, now - interval) + interval - now)
        _LAST[key] = now + wait
        if len(_LAST) > 10000:
            for old in [k for k, t in _LAST.items() if t < now - 3600]:
                del _LAST[old]
    if wait:
        time.sleep(wait)


def retry_delay(headers, attempt):
    raw = headers.get("X-Ratelimit-Retry") or headers.get("Retry-After")
    if raw:
        try:
            return max(1.0, float(raw))
        except ValueError:
            try:
                return max(1.0, (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError):
                pass
    return min(2 ** (attempt + 1), 16)


class WBClient:
    def __init__(self, token, session=None, throttle=pace, sleeper=time.sleep):
        self._token = token.strip()
        if not self._token:
            raise APIError("Введите API-токен категории «Контент».")
        self._key = hashlib.sha256(self._token.encode()).hexdigest()
        self.session = session or requests.Session()
        self.throttle, self.sleep = throttle, sleeper
        self.schemas = {}

    def close(self):
        self.session.close()

    def request(self, method, path, payload=None, params=None, write=False):
        group, interval = ("update", 6.2) if path == UPDATE else (("errors", 6.2) if path == ERRORS else ("content", 0.65))
        for attempt in range(4):
            self.throttle(self._key, group, interval)
            try:
                response = self.session.request(method, BASE + path,
                    headers={"Authorization": self._token, "Accept": "application/json"},
                    json=payload, params=params, timeout=(10, 35), allow_redirects=False)
            except requests.RequestException:
                if write:
                    raise APIError("Связь прервалась при отправке. Результат неизвестен: проверьте карточки, не отправляйте запрос повторно вслепую.", uncertain=True) from None
                if attempt < 3:
                    self.sleep(2 ** (attempt + 1))
                    continue
                raise APIError("Не удалось связаться с WB после четырёх попыток. Проверьте сеть и повторите чтение.") from None
            status = response.status_code
            if status == 429:
                delay = retry_delay(response.headers, attempt)
                if attempt < 3 and delay <= 60:
                    self.sleep(delay)
                    continue
                raise APIError(f"WB ограничил частоту запросов (429). Повторите операцию позднее; ожидание WB: {delay:g} с.")
            if status >= 500:
                if write:
                    raise APIError(f"WB вернул {status} при отправке. Результат неизвестен — сначала проверьте сохранение.", uncertain=True)
                if attempt < 3:
                    self.sleep(2 ** (attempt + 1))
                    continue
            try:
                body = response.json()
            except ValueError:
                raise APIError(f"WB вернул ответ не в формате JSON (HTTP {status}).", uncertain=write and status < 300) from None
            detail = str(body.get("errorText") or body.get("detail") or body.get("title") or body.get("message") or "") if isinstance(body, dict) else ""
            detail = detail.replace(self._token, "[токен скрыт]")[:1200]
            if status not in (200, 201):
                friendly = {401: "Токен недействителен или истёк.", 403: "У токена нет нужного доступа.", 402: "WB требует оплаты доступа.", 413: "Слишком большой пакет данных."}.get(status, "Запрос отклонён WB.")
                raise APIError(f"HTTP {status}. {friendly} {detail}")
            if not isinstance(body, dict):
                raise APIError("WB вернул неожиданный формат ответа.", uncertain=write)
            if body.get("error") or body.get("errorText") or body.get("additionalErrors"):
                extra = str(body.get("additionalErrors") or "").replace(self._token, "[токен скрыт]")[:1200]
                raise APIError(f"Ошибка WB: {detail} {extra}", uncertain=write)
            return body
        raise APIError("Исчерпаны попытки запроса.")

    def _pages(self, search=None):
        cursor, visited = {"limit": 100}, set()
        for _ in range(10000):
            filters = {"withPhoto": -1}
            if search is not None:
                filters["textSearch"] = str(search)
            body = self.request("POST", LIST, {"settings": {"sort": {"ascending": True}, "filter": filters, "cursor": cursor}})
            cards = body.get("cards")
            if not isinstance(cards, list):
                raise APIError("В ответе WB отсутствует список cards.")
            yield cards
            next_cursor = body.get("cursor", {})
            total = next_cursor.get("total", len(cards))
            if total < 100:
                return
            marker = (next_cursor.get("updatedAt"), next_cursor.get("nmID"))
            if not all(marker) or marker in visited:
                raise APIError("WB вернул повторный или неполный курсор. Загрузка остановлена.")
            visited.add(marker)
            cursor = {"limit": 100, "updatedAt": marker[0], "nmID": marker[1]}
        raise APIError("Превышен лимит страниц каталога. Уменьшите список артикулов.")

    def fetch_cards(self, ids, progress=None, mode="auto"):
        targets = set(ids)
        found, scanned = {}, 0
        exact = mode == "exact" or (mode == "auto" and len(targets) <= 30)
        searches = list(dict.fromkeys(ids)) if exact else [None]
        for search in searches:
            for cards in self._pages(search):
                scanned += len(cards)
                for card in cards:
                    nm_id = card.get("nmID")
                    if nm_id in targets:
                        found[nm_id] = card
                if progress:
                    progress(len(found), len(targets), scanned)
                if targets <= found.keys():
                    return [found[i] for i in ids], []
                if exact and search in found:
                    break
        return [found[i] for i in ids if i in found], [i for i in ids if i not in found]

    def characteristics(self, subject_id):
        if subject_id not in self.schemas:
            body = self.request("GET", f"/content/v2/object/charcs/{int(subject_id)}", params={"locale": "ru"})
            data = body.get("data")
            if not isinstance(data, list) or any(not isinstance(c, dict) or "charcID" not in c or "name" not in c for c in data):
                raise APIError("WB вернул некорректный справочник характеристик.")
            self.schemas[subject_id] = data
        return self.schemas[subject_id]

    def update(self, payload):
        return self.request("POST", UPDATE, payload, write=True)

    def errors_for(self, vendor_codes):
        wanted, result, seen = set(vendor_codes), [], set()
        cursor = {"limit": 100}
        for _ in range(1000):
            body = self.request("POST", ERRORS, {"cursor": cursor, "order": {"ascending": True}})
            data = body.get("data")
            if not isinstance(data, dict) or not isinstance(data.get("items"), list):
                raise APIError("Неожиданный формат списка ошибок WB.")
            for item in data["items"]:
                for vendor, messages in item.get("errors", {}).items():
                    if vendor in wanted:
                        result.append({"Артикул продавца": vendor, "Ошибки WB": messages, "Дата WB": item.get("updatedAt"), "Пакет WB": item.get("batchUUID")})
            page = data.get("cursor", {})
            if page.get("next") is False:
                return result
            marker = (page.get("updatedAt"), page.get("batchUUID"))
            if not all(marker) or marker in seen:
                raise APIError("Некорректный курсор списка ошибок WB.")
            seen.add(marker)
            cursor = {"limit": 100, "updatedAt": marker[0], "batchUUID": marker[1]}
        raise APIError("Слишком много страниц ошибок WB; проверка остановлена.")


# ========================================================================
# workflow.py
"""Review, preflight, submission and read-back verification."""
from copy import deepcopy
from datetime import datetime, timezone



def utc_now():
    return datetime.now(timezone.utc).isoformat()


def preflight(client, plans, progress=None):
    cards, missing = client.fetch_cards([p["nmID"] for p in plans], progress=progress)
    if missing:
        raise ValidationError("Перед отправкой не найдены карточки: " + ", ".join(map(str, missing)))
    current = {c["nmID"]: c for c in cards}
    conflicts = [p["nmID"] for p in plans if snapshot(current[p["nmID"]]) != p["baseline"]]
    if conflicts:
        raise ValidationError("После предпросмотра карточки изменились в WB: " + ", ".join(map(str, conflicts)) + ". Загрузите карточки и сформируйте предпросмотр заново.")


def submit(client, plans, report, progress=None):
    """report is saved in session BEFORE calling, preserving partial results."""
    batches = list(make_batches(plans))
    for batch in batches:
        for plan in batch:
            report[plan["nmID"]] = {"nmID": plan["nmID"], "status": "unknown", "message": "Отправка начата; результат пока неизвестен", "sent_at": utc_now()}
        try:
            client.update([deepcopy(p["payload"]) for p in batch])
        except APIError as error:
            for plan in batch:
                report[plan["nmID"]].update(status="unknown" if error.uncertain else "rejected", message=str(error))
            # Leave remaining batches unsent; do not blindly retry writes.
            break
        else:
            for plan in batch:
                report[plan["nmID"]].update(status="accepted", message="WB принял запрос. Сохранение ещё не подтверждено.")
        if progress:
            progress(sum(r["status"] != "not_sent" for r in report.values()), len(plans))


def verify(client, plans, report, progress=None):
    eligible = [p for p in plans if report[p["nmID"]]["status"] in ("accepted", "pending", "unknown", "verified")]
    if not eligible:
        return
    cards, missing = client.fetch_cards([p["nmID"] for p in eligible], progress=progress)
    actual = {c["nmID"]: c for c in cards}
    for plan in eligible:
        row = report[plan["nmID"]]
        row["checked_at"] = utc_now()
        if plan["nmID"] in missing:
            row.update(status="pending", message="Карточка пока не найдена при проверке.")
            continue
        try:
            differences = verify_card(actual[plan["nmID"]], plan["payload"])
        except ValidationError as error:
            row.update(status="pending", message=str(error))
            continue
        if differences:
            row.update(status="pending", message="Данные пока отличаются: " + ", ".join(differences))
        else:
            row.update(status="verified", message="Повторное чтение WB подтвердило все отправленные поля.")


# ========================================================================
# demo.py
"""Entirely local, deterministic demonstration. Never contacts WB."""
from copy import deepcopy

DEMO_IDS = [100000001, 100000002, 100000003]
SCHEMA = [
    {"charcID": 100 + n, "name": name, "charcType": 1, "maxCount": count}
    for n, (name, count) in enumerate([
        ("ТНВЭД", 1), ("Комплектация", 6), ("Материал изделия", 3),
        ("Назначение держателя в авто", 4), ("Назначение подарка", 5),
        ("Повод", 5), ("Модель", 1), ("Хрупкость", 1), ("Тип крепления", 3),
    ])
]


def demo_cards():
    return [
        {"nmID": nm_id, "subjectID": 999, "subjectName": "Демонстрационная категория",
         "vendorCode": f"DEMO-{n + 1:03}", "title": f"Металлическая пластина для телефона {name}",
         "brand": "Пример", "description": f'Пластина "{name}" для магнитного держателя.',
         "dimensions": {"length": 12, "width": 8, "height": 1, "weightBrutto": 0.02, "isValid": True},
         "characteristics": [{"id": 102, "name": "Материал изделия", "value": ["сталь"]}, {"id": 106, "name": "Модель", "value": [name]}],
         "sizes": [{"chrtID": 500 + n, "techSize": "0", "wbSize": "", "skus": [f"DEMO-BC-{n}"]}],
         "updatedAt": "2026-01-01T00:00:00Z", "needKiz": False}
        for n, (nm_id, name) in enumerate(zip(DEMO_IDS, ["Космос", "Лиса", "Волна"]))
    ]


class DemoClient:
    def __init__(self):
        self.cards = {c["nmID"]: c for c in demo_cards()}

    def close(self):
        pass

    def fetch_cards(self, ids, progress=None, mode="auto"):
        found = [deepcopy(self.cards[i]) for i in ids if i in self.cards]
        if progress:
            progress(len(found), len(ids), len(self.cards))
        return found, [i for i in ids if i not in self.cards]

    def characteristics(self, subject_id):
        return deepcopy(SCHEMA)

    def update(self, payload):
        for card in payload:
            self.cards[card["nmID"]].update(deepcopy(card))
        return {"error": False}

    def errors_for(self, vendor_codes):
        return []


# ========================================================================
# app.py

from copy import deepcopy
import csv
import io
import os
import hmac

import streamlit as st


st.set_page_config(page_title="WB · Редактор карточек", page_icon="🛡️", layout="wide")


def clear_plan():
    st.session_state.pop("plan", None)
    st.session_state["confirm_changes"] = False


def clear_loaded():
    clear_plan()
    for key in ("loaded", "operation", "schema"):
        st.session_state.pop(key, None)


def select_fields(value):
    for key in LABELS:
        st.session_state[f"check_{key}"] = value
    clear_plan()


def switch_demo():
    st.session_state["ids"] = "\n".join(map(str, DEMO_IDS)) if st.session_state["demo"] else ""
    clear_loaded()


def enable_demo():
    st.session_state["demo"] = True
    switch_demo()


def as_text(value):
    if value is None:
        return "—"
    return json_text(value) if isinstance(value, (list, dict)) else str(value)


def diff_rows(plans):
    return [{**row, "nmID": str(row["nmID"]), "Было": as_text(row["Было"]), "Станет": as_text(row["Станет"])} for p in plans for row in p["changes"]]


def csv_bytes(rows):
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        for row in rows:
            # Prevent spreadsheet formula execution when users open exported text.
            writer.writerow({k: ("'" + str(v) if str(v).lstrip().startswith(("=", "+", "-", "@")) else v) for k, v in row.items()})
    return output.getvalue().encode("utf-8-sig")


def read_progress(placeholder):
    return lambda found, total, scanned: placeholder.caption(f"Найдено {found} из {total}. Просмотрено карточек: {scanned}.")


def main():
    # Optional deployment password; the seller token is never stored in files.
    password = os.environ.get("WB_APP_PASSWORD", "")
    try:
        password = st.secrets.get("WB_APP_PASSWORD", password)
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        pass
    if password and not st.session_state.get("logged_in"):
        st.title("Вход в редактор карточек")
        with st.form("login"):
            entered = st.text_input("Пароль приложения", type="password")
            if st.form_submit_button("Войти"):
                if hmac.compare_digest(entered.encode(), str(password).encode()):
                    st.session_state["logged_in"] = True
                    st.rerun()
                else:
                    st.error("Неверный пароль.")
        return

    st.title("Карточки Wildberries")
    st.caption("Массовое редактирование · предпросмотр · проверка сохранения")
    st.sidebar.header("Подключение")
    demo = st.sidebar.toggle("Деморежим", value=False, key="demo", on_change=switch_demo)
    token = st.sidebar.text_input("API-токен «Контент»", type="password", key="token", disabled=demo,
                                  help="Для загрузки нужен доступ на чтение, для отправки — на запись. Токен хранится только в памяти текущего сеанса.").strip()
    raw_ids = st.sidebar.text_area("Артикулы WB (nmID)", key="ids", height=150,
                                  placeholder="Каждый с новой строки, через пробел или запятую")
    strategy = st.sidebar.selectbox("Поиск карточек", ["Автоматически", "По каждому артикулу", "Весь каталог"],
                                    help="Автоматически: до 30 артикулов — точечный поиск, больше — проход по каталогу с остановкой после нахождения всех.")
    mode = {"Автоматически": "auto", "По каждому артикулу": "exact", "Весь каталог": "catalog"}[strategy]
    if st.sidebar.button("Очистить сеанс", use_container_width=True):
        if st.session_state.get("client"):
            st.session_state["client"].close()
        for key in list(st.session_state):
            del st.session_state[key]
        st.rerun()
    if demo:
        st.info("Деморежим: три вымышленных товара. Все изменения происходят только в памяти; запросов в WB нет.")
    ids, input_error = [], None
    try:
        ids = parse_ids(raw_ids)
    except ValidationError as error:
        input_error = str(error)
    identity = fingerprint([demo, "demo" if demo else token])
    binding = fingerprint([identity, ids, input_error, mode])
    if st.session_state.get("binding") != binding:
        clear_loaded()
        st.session_state["binding"] = binding
    if st.session_state.get("identity") != identity:
        old = st.session_state.pop("client", None)
        if old:
            old.close()
        st.session_state["identity"] = identity
        st.session_state["client"] = DemoClient() if demo else (WBClient(token) if token else None)
    client = st.session_state.get("client")
    if not demo and not token:
        st.info("Введите токен и артикулы слева. Можно сначала проверить работу на демонстрационных товарах.")
        st.button("Открыть деморежим", on_click=enable_demo)
    if raw_ids and input_error:
        st.error(input_error)

    st.subheader("1. Загрузите товары")
    if st.button("Загрузить карточки", type="primary", disabled=not client or bool(input_error)):
        clear_loaded()
        message = st.empty()
        try:
            with st.spinner("Получаем карточки из WB…" if not demo else "Загружаем примеры…"):
                cards, missing = client.fetch_cards(ids, progress=read_progress(message), mode=mode)
            st.session_state["loaded"] = {"cards": cards, "missing": missing, "time": utc_now()}
        except (APIError, ValidationError) as error:
            st.error(str(error))
    loaded = st.session_state.get("loaded")
    if not loaded:
        return
    cards = loaded["cards"]
    if loaded["missing"]:
        st.error("Не найдены артикулы: " + ", ".join(map(str, loaded["missing"])) + ". Исправьте список и загрузите его повторно. Отправка неполного списка заблокирована.")
    if not cards:
        st.warning("Карточки не найдены. Проверьте артикулы и кабинет продавца.")
        return
    st.caption(f"Загружено {len(cards)} из {len(ids)} карточек.")
    st.dataframe([{"nmID": str(c["nmID"]), "Артикул продавца": c.get("vendorCode"), "Название": c.get("title"), "Бренд": c.get("brand"), "Категория": c.get("subjectName"), "Баркоды": ", ".join(str(s) for size in c.get("sizes", []) for s in size.get("skus", []))} for c in cards], hide_index=True, use_container_width=True)
    st.download_button("Скачать исходные карточки (JSON)", json_text({"exported_at": loaded["time"], "demo": demo, "cards": cards}),
                       "wb-original-cards.json", "application/json")

    st.subheader("2. Выберите изменения")
    st.caption("Название, бренд, артикул продавца и баркоды сохраняются. Неотмеченные поля берутся из исходных карточек.")
    buttons = st.columns([1, 1, 3])
    buttons[0].button("Выбрать все поля", on_click=select_fields, args=(True,))
    buttons[1].button("Снять все галочки", on_click=select_fields, args=(False,))
    columns = st.columns(3)
    selected = {}
    for n, (key, label) in enumerate(LABELS.items()):
        selected[key] = columns[n % 3].checkbox(label, key=f"check_{key}", on_change=clear_plan)
    edits = {}
    if selected["description"]:
        edits["description"] = st.text_area("Новое описание", value=DEFAULT_DESCRIPTION, height=150, key="new_description", on_change=clear_plan)
        st.caption("{print_name} подставляет имя принта из кавычек текущего описания, а при его отсутствии — из названия. Итоговый текст виден в предпросмотре.")
    dims = st.columns(4)
    if selected["dimensions"]:
        edits["dimensions"] = {key: dims[n].number_input(label, min_value=1, value=default, step=1, key=f"new_{key}", on_change=clear_plan)
                                for n, (key, label, default) in enumerate([( "length", "Длина, см", 18), ("width", "Ширина, см", 14), ("height", "Высота, см", 1)])}
    if selected["weight"]:
        edits["weight"] = dims[3].number_input("Вес с упаковкой, кг", min_value=0.001, value=0.030, step=0.001, format="%.3f", key="new_weight", on_change=clear_plan)
    for key, (label, aliases, sep, default) in FIELDS.items():
        if selected[key]:
            hint = "Разделяйте значения точкой с запятой" if sep == ";" else ("Разделяйте значения запятой" if sep else "Одно значение")
            edits[key] = st.text_input(label + " — новое значение", value=default, help=hint, key=f"new_{key}", on_change=clear_plan)

    schemas, mappings, schema_error = {}, {}, False
    char_keys = [key for key in FIELDS if selected[key]]
    if char_keys:
        with st.expander("Сопоставление характеристик по категориям", expanded=True):
            st.caption("Идентификаторы получены из справочника WB. Если название не совпало, выберите нужную характеристику вручную.")
            try:
                subjects = sorted({int(c["subjectID"]) for c in cards})
                for subject in subjects:
                    schema = client.characteristics(subject)
                    schemas[subject], mappings[subject] = schema, {}
                    names = {int(c["charcID"]): c["name"] for c in schema}
                    st.markdown(f"**Категория {subject}**")
                    for key in char_keys:
                        suggested = suggest_characteristic(key, schema)
                        options = [None, *sorted(names, key=lambda i: names[i])]
                        char_id = st.selectbox(FIELDS[key][0], options=options, index=options.index(suggested),
                            format_func=lambda v, names=names: "— Выберите характеристику —" if v is None else f"{names[v]} · ID {v}",
                            key=f"mapping_{identity[:12]}_{subject}_{key}", on_change=clear_plan)
                        mappings[subject][key] = char_id
            except (APIError, KeyError, ValueError) as error:
                schema_error = True
                st.error("Не удалось загрузить справочник категории: " + str(error))
    need_mark = any(c.get("needKiz") and c.get("kizMarked") is not True for c in cards)
    marked_confirmed = False
    if need_mark:
        st.warning("В списке есть товары с обязательной маркировкой. WB требует подтверждение нанесения кода при редактировании.")
        marked_confirmed = st.checkbox("Подтверждаю, что на выбранные товары нанесён обязательный код маркировки", key="marked_confirmed", on_change=clear_plan)
    signature = fingerprint([binding, edits, mappings, marked_confirmed])
    if st.session_state.get("plan", {}).get("signature") not in (None, signature):
        clear_plan()
    operation = st.session_state.get("operation")
    if operation:
        st.info("Для этих загруженных данных отправка уже запускалась. Проверьте результат ниже. Для новой операции загрузите карточки заново.")
    if st.button("Показать изменения", disabled=not edits or bool(loaded["missing"]) or schema_error or bool(operation), type="primary"):
        clear_plan()
        try:
            plans = [prepare_card(c, edits, schemas, mappings, marked_confirmed) for c in cards]
            plans = [p for p in plans if p["changes"]]
            if not plans:
                st.info("Выбранные значения уже совпадают с карточками. Отправлять нечего.")
            else:
                list(make_batches(plans))  # Validate all packet sizes before offering submission.
                st.session_state["plan"] = {"signature": signature, "plans": plans, "created_at": utc_now()}
        except (ValidationError, KeyError, TypeError, ValueError) as error:
            st.error("Предпросмотр не сформирован: " + str(error))

    plan = st.session_state.get("plan")
    if plan and not operation:
        st.subheader("3. Проверьте и отправьте")
        plans = plan["plans"]
        rows = diff_rows(plans)
        st.write(f"Изменятся карточки: **{len(plans)}**. Изменений полей: **{len(rows)}**.")
        st.dataframe(rows, hide_index=True, use_container_width=True)
        with st.expander("Полные значения без сокращений"):
            for row in rows:
                st.markdown(f"**{row['nmID']} · {row['Поле']}**")
                cols = st.columns(2)
                cols[0].text("Было\n" + row["Было"])
                cols[1].text("Станет\n" + row["Станет"])
        st.download_button("Скачать таблицу изменений (CSV)", csv_bytes(rows), "wb-changes.csv", "text/csv")
        backup = {"created_at": plan["created_at"], "demo": demo, "original_cards": cards, "updates": [p["payload"] for p in plans], "changes": rows}
        st.download_button("Скачать резервную копию и план (JSON)", json_text(backup), "wb-backup-and-plan.json", "application/json")
        confirmed = st.checkbox("Проверил список товаров и значения «Станет»", key="confirm_changes")
        label = "Применить в деморежиме" if demo else f"Отправить изменения в WB · {len(plans)} карточек"
        if st.button(label, type="primary", disabled=not confirmed):
            message = st.empty()
            try:
                with st.spinner("Повторно читаем карточки перед отправкой…"):
                    preflight(client, plans, read_progress(message))
            except (APIError, ValidationError) as error:
                clear_plan()
                st.error(str(error))
                return
            operation = {"plans": deepcopy(plans), "created_at": utc_now(), "demo": demo,
                         "report": {p["nmID"]: {"nmID": p["nmID"], "status": "not_sent", "message": "Пакет ещё не отправлялся"} for p in plans}}
            st.session_state["operation"] = operation
            with st.spinner("Отправляем изменения…"):
                submit(client, plans, operation["report"], lambda done, total: message.caption(f"Обработано {done} из {total} карточек."))
            try:
                with st.spinner("Проверяем результат повторным чтением…"):
                    verify(client, plans, operation["report"], read_progress(message))
            except (APIError, ValidationError) as error:
                operation["verification_error"] = str(error)
            st.rerun()

    operation = st.session_state.get("operation")
    if operation:
        st.subheader("Результат операции")
        st.caption("WB может применять изменения до 30 минут. Статус «Подтверждено» появляется только после повторного чтения всех отправленных полей.")
        if st.button("Проверить сохранение ещё раз"):
            message = st.empty()
            try:
                with st.spinner("Сверяем данные WB…"):
                    verify(client, operation["plans"], operation["report"], read_progress(message))
                operation.pop("verification_error", None)
            except (APIError, ValidationError) as error:
                operation["verification_error"] = str(error)
        if operation.get("verification_error"):
            st.warning("Проверка не завершена: " + operation["verification_error"])
        labels = {"not_sent": "Не отправлено", "unknown": "Результат неизвестен", "accepted": "Принято WB", "rejected": "Отклонено WB", "pending": "Пока не подтверждено", "verified": "Подтверждено"}
        report_rows = [{"nmID": str(r["nmID"]), "Статус": labels[r["status"]], "Подробности": ("Данные деморежима совпадают с планом." if demo and r["status"] == "verified" else r["message"])} for r in operation["report"].values()]
        verified = sum(r["status"] == "verified" for r in operation["report"].values())
        if verified == len(report_rows):
            st.success(f"{'Демопроверка' if demo else 'Проверка WB'}: подтверждено {verified} из {len(report_rows)} карточек.")
        else:
            st.warning(f"Подтверждено {verified} из {len(report_rows)} карточек. Остальные результаты указаны в таблице.")
        st.dataframe(report_rows, hide_index=True, use_container_width=True)
        st.download_button("Скачать отчёт об операции (JSON)", json_text(operation), "wb-operation-report.json", "application/json")
        if st.button("Получить ошибки карточек из WB"):
            try:
                with st.spinner("Читаем журнал ошибок WB…"):
                    errors = client.errors_for([p["payload"]["vendorCode"] for p in operation["plans"]])
                st.caption("Журнал может содержать ошибки более ранних операций; сопоставляйте дату и артикул. Отсутствие ошибок не подтверждает сохранение.")
                if errors:
                    st.dataframe([{**r, "Ошибки WB": as_text(r["Ошибки WB"])} for r in errors], use_container_width=True, hide_index=True)
                else:
                    st.info("Для этих артикулов в журнале ошибок WB ничего не найдено.")
            except APIError as error:
                st.error(str(error))


main()
