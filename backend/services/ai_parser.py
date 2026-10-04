import re
import json
import time
import requests
import difflib
from datetime import datetime

VTES_SYSTEM_INSTRUCTION = """Extract expenses from the message and return a JSON LIST.
STRICT CATEGORIZATION RULES:
1. You MUST use EXACTLY the Category and Subcategory names provided in the JSON list below.
2. Pay extreme attention to EXACT MATCHES: If a user's text exactly matches a Category Name (like "Parents"), you MUST map it to that matched Category Name, instead of a subcategory in a different parent.
3. Identify the best matching subcategory first, then use its EXACT parent category.

Description Formatting:
- Translate any Tamil or Tanglish descriptions into clear English (e.g. "kaikari" -> "Vegetables", "paal" -> "Milk", "sappadu" -> "Meals/Food").
- Format the final description in Title Case (e.g. "Bought Coffee").

If a message mentions a specific date (e.g., "spent on 19-02-2026"), use that date. Otherwise use the provided 'Today' date.

Split rules: 
1. If multiple items are mentioned, extract each as a separate JSON object.
2. Even without commas, if you see [item] [amount] [item] [amount], split them.
3. Do not split when multiple goods are connected by "and" (or "&") but only one amount appears at the end; treat it as one combined expense. E.g., "tea and juice 90" should be a single object.

Each object MUST have:
"date": "YYYY-MM-DD",
"category": "Matched Category",
"subcategory": "Matched Subcategory",
"description": "Clean Description",
"amount": 100.0,
"payment_mode": "UPI",
"notes": ""

Default payment_mode: UPI
Categories & Subcategories:
{{CATEGORIES}}

Return ONLY valid JSON array of objects. No markdown backticks, no comments."""

def fast_regex_parse(text: str, categories_dict: dict = None):
    """Attempt fast regex parsing on single or multi-line text."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    parsed_items = []
    
    for line in lines:
        # Pattern 1: amount then description (e.g. "500 for milk", "Rs. 1200 petrol")
        m1 = re.search(r'(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?)\s+(?:for|on)\s+([a-zA-Z0-9\s&]+)', line, re.IGNORECASE)
        if m1:
            amount = float(m1.group(1))
            desc = m1.group(2).strip().title()
            cat, sub = match_category(desc, categories_dict)
            parsed_items.append({
                "amount": amount,
                "description": desc,
                "category": cat,
                "subcategory": sub,
                "confidence": 0.95,
                "parser": "regex"
            })
            continue

        # Pattern 2: description then amount (e.g. "Mutton 1kg 1000", "Vegetables 120", "Tuition 600")
        m2 = re.search(r'^([a-zA-Z0-9\s&]+?)\s+(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?)$', line, re.IGNORECASE)
        if m2:
            desc = m2.group(1).strip().title()
            amount = float(m2.group(2))
            cat, sub = match_category(desc, categories_dict)
            parsed_items.append({
                "amount": amount,
                "description": desc,
                "category": cat,
                "subcategory": sub,
                "confidence": 0.95,
                "parser": "regex"
            })
            continue

    return parsed_items

def match_category(description: str, categories_dict: dict = None):
    """Map a description to the closest category and subcategory."""
    if not categories_dict:
        categories_dict = {
            "Home & Living": ["Groceries", "Vegetables", "Milk", "Household", "EB Bill", "Rent"],
            "Food": ["Hotel", "Restaurant", "Tea", "Coffee", "Snacks", "Lunch", "Dinner"],
            "Transport": ["Petrol", "Diesel", "Bus", "Auto", "Taxi", "Uber", "Ola"],
            "Medical": ["Pharmacy", "Medicine", "Doctor", "Hospital"],
            "Education": ["Tuition", "Fees", "Books", "School", "College"],
            "Family": ["Kids", "Parents", "Gifts", "Functions"],
            "Savings": ["SIP", "RD", "General"],
            "Miscellaneous": ["General"]
        }

    desc_lower = description.lower()
    
    # Direct Tamil / English keyword mapping
    keyword_map = {
        "milk": ("Home & Living", "Milk"),
        "paal": ("Home & Living", "Milk"),
        "grocery": ("Home & Living", "Groceries"),
        "grossary": ("Home & Living", "Groceries"),
        "mutton": ("Home & Living", "Groceries"),
        "vegetable": ("Home & Living", "Vegetables"),
        "kaikari": ("Home & Living", "Vegetables"),
        "onion": ("Home & Living", "Vegetables"),
        "water": ("Home & Living", "Water"),
        "eb": ("Home & Living", "EB Bill"),
        "current bill": ("Home & Living", "EB Bill"),
        "rent": ("Home & Living", "Rent"),
        "tution": ("Education", "Tuition"),
        "tuition": ("Education", "Tuition"),
        "phonics": ("Education", "Tuition"),
        "vidhuran": ("Family", "Kids"),
        "kids": ("Family", "Kids"),
        "parents": ("Family", "Parent Support"),
        "sip": ("Savings", "SIP"),
        "savings": ("Savings", "General"),
        "rd": ("Savings", "General"),
        "petrol": ("Transport", "Petrol"),
        "diesel": ("Transport", "Diesel"),
        "tea": ("Food", "Tea"),
        "coffee": ("Food", "Coffee"),
        "snack": ("Food", "Snacks"),
    }

    for kw, mapping in keyword_map.items():
        if kw in desc_lower:
            return mapping

    # Fuzzy match
    best_cat = "Miscellaneous"
    best_sub = "General"
    best_score = 0.0

    for cat, subs in categories_dict.items():
        for sub in subs:
            score = difflib.SequenceMatcher(None, desc_lower, sub.lower()).ratio()
            if score > best_score and score > 0.55:
                best_score = score
                best_cat = cat
                best_sub = sub

    return best_cat, best_sub

def call_gemini_parser(text: str, api_keys: list, categories_dict: dict, today_str: str):
    """Google Gemini AI extraction with multi-key rotation and priority models."""
    if not api_keys:
        return None

    cat_json = json.dumps(categories_dict, indent=2)
    sys_instr = VTES_SYSTEM_INSTRUCTION.replace("{{CATEGORIES}}", cat_json)
    
    # Updated current Google Gemini models
    models = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-2.5-pro"]

    for key in api_keys:
        key_str = str(key).strip()
        if not key_str:
            continue
        key_failed = False
        for model in models:
            if key_failed:
                break
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key_str}"
                payload = {
                    "systemInstruction": {
                        "parts": [{"text": sys_instr}]
                    },
                    "contents": [
                        {"parts": [{"text": f"Today's Date: {today_str}\n\nExpense text:\n{text}"}]}
                    ],
                    "generationConfig": {
                        "temperature": 0.1,
                        "responseMimeType": "application/json"
                    }
                }
                resp = requests.post(url, json=payload, timeout=12)
                if resp.status_code == 200:
                    data_obj = resp.json()
                    candidates = data_obj.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            raw_text = parts[0].get("text", "").strip()
                            raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
                            raw_text = re.sub(r'```$', '', raw_text).strip()
                            data = json.loads(raw_text)
                            if isinstance(data, list):
                                for item in data:
                                    item["parser"] = f"gemini ({model})"
                                return data
                            elif isinstance(data, dict):
                                data["parser"] = f"gemini ({model})"
                                return [data]
                elif resp.status_code == 400:
                    # Key is completely invalid; skip all models for this key
                    key_failed = True
                    break
                elif resp.status_code in (404, 429):
                    # Model not found or rate limited, try next model
                    continue
            except Exception as e:
                continue

    return None

def call_openrouter_parser(text: str, api_key: str, model: str, categories_dict: dict, today_str: str):
    """OpenRouter AI extraction."""
    if not api_key:
        return None

    cat_json = json.dumps(categories_dict, indent=2)
    prompt = VTES_SYSTEM_INSTRUCTION.replace("{{CATEGORIES}}", cat_json) + f"\nToday's Date: {today_str}\n\nMessage to parse:\n{text}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5001",
        "X-Title": "Expense Manager"
    }

    payload = {
        "model": model or "google/gemini-2.0-flash-001",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1
    }

    try:
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"].strip()
            content = re.sub(r'^```(?:json)?\s*', '', content)
            content = re.sub(r'```$', '', content).strip()
            data = json.loads(content)
            if isinstance(data, list):
                for item in data:
                    item["parser"] = f"openrouter ({model})"
                return data
            elif isinstance(data, dict):
                data["parser"] = f"openrouter ({model})"
                return [data]
    except Exception as e:
        print(f"[AI Parser] OpenRouter call error: {e}")
    return None

def call_local_llm_parser(text: str, url: str, model: str, categories_dict: dict, today_str: str):
    """Local LLM endpoint (Ollama / llama.cpp / vLLM)."""
    if not url:
        return None

    cat_json = json.dumps(categories_dict, indent=2)
    prompt = VTES_SYSTEM_INSTRUCTION.replace("{{CATEGORIES}}", cat_json) + f"\nToday's Date: {today_str}\n\nMessage to parse:\n{text}"

    # Ollama format
    payload = {
        "model": model or "llama3",
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }

    try:
        resp = requests.post(url, json=payload, timeout=20)
        if resp.status_code == 200:
            raw = resp.json().get("response", "")
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'```$', '', raw).strip()
            data = json.loads(raw)
            if isinstance(data, list):
                for item in data:
                    item["parser"] = "local_llm"
                return data
    except Exception as e:
        print(f"[AI Parser] Local LLM call error: {e}")
    return None

def parse_expense_text(text: str, config: dict = None, categories_dict: dict = None, prefer_ai: bool = False):
    """Unified expense parsing orchestrator with AI priority and regex fallback."""
    if not text or not text.strip():
        return []

    today_str = datetime.now().strftime("%Y-%m-%d")

    # If prefer_ai is True or message looks like natural language, try AI first
    if prefer_ai or (config and (config.get("use_gemini", True) or config.get("use_openrouter", False)) and not config.get("use_regex_shortcut", True)):
        # 1. Google Gemini AI with Key Rotation
        if config is None or config.get("use_gemini", True):
            api_keys = (config or {}).get("gemini_api_keys", [])
            if api_keys:
                res = call_gemini_parser(text, api_keys, categories_dict, today_str)
                if res:
                    return res

        # 2. OpenRouter AI
        if config and config.get("use_openrouter", False):
            api_keys = config.get("openrouter_api_keys", [])
            if api_keys:
                key = api_keys[0] if isinstance(api_keys, list) else api_keys
                model = config.get("openrouter_model", "google/gemini-2.0-flash-001")
                res = call_openrouter_parser(text, key, model, categories_dict, today_str)
                if res:
                    return res

    # 3. Fast Regex Shortcut (if enabled or default)
    if config is None or config.get("use_regex_shortcut", True):
        # If it's a very simple string with exactly 1 number, regex is fast
        regex_items = fast_regex_parse(text, categories_dict)
        if regex_items:
            return regex_items

    # 4. Standard AI Workflow if not yet attempted
    if config is None or config.get("use_gemini", True):
        api_keys = (config or {}).get("gemini_api_keys", [])
        if api_keys:
            res = call_gemini_parser(text, api_keys, categories_dict, today_str)
            if res:
                return res

    # 5. OpenRouter AI Fallback
    if config and config.get("use_openrouter", False):
        api_keys = config.get("openrouter_api_keys", [])
        if api_keys:
            key = api_keys[0] if isinstance(api_keys, list) else api_keys
            model = config.get("openrouter_model", "google/gemini-2.0-flash-001")
            res = call_openrouter_parser(text, key, model, categories_dict, today_str)
            if res:
                return res

    # 6. Local LLM
    if config and config.get("use_local_llm", False):
        url = config.get("local_llm_url", "http://localhost:11434/api/generate")
        model = config.get("local_llm_model", "llama3")
        res = call_local_llm_parser(text, url, model, categories_dict, today_str)
        if res:
            return res

    # 7. Final Regex Fallback
    return fast_regex_parse(text, categories_dict)

def analyze_single_expense(text: str, categories_dict: dict = None, config: dict = None):
    """Analyze a single expense text description and return structured fields for Add Expense form."""
    parsed = parse_expense_text(text, config=config, categories_dict=categories_dict, prefer_ai=True)
    if parsed and len(parsed) > 0:
        item = parsed[0]
        return {
            "success": True,
            "description": item.get("description", text.strip().title()),
            "amount": float(item.get("amount", 0.0)),
            "category": item.get("category", "Miscellaneous"),
            "subcategory": item.get("subcategory", "General"),
            "payment_mode": item.get("payment_mode", "UPI"),
            "date": item.get("date", datetime.now().strftime("%Y-%m-%d")),
            "notes": item.get("notes", ""),
            "parser": item.get("parser", "AI")
        }
    
    # Fallback default
    cat, sub = match_category(text, categories_dict)
    amounts = re.findall(r"(\d+(?:\.\d+)?)", text)
    amt = float(amounts[0]) if amounts else 0.0
    return {
        "success": True,
        "description": text.strip().title(),
        "amount": amt,
        "category": cat,
        "subcategory": sub,
        "payment_mode": "UPI",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "notes": "",
        "parser": "heuristic"
    }
