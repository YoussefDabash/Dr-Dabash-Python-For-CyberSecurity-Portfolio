#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Tool Name : ReconVault - HTTP Log Recon & Loot Database Manager
# Author    : Youssef Tamer Dabash (Dr. Dabash)
# Purpose   : Extract subdomains, emails, and leaked API keys from raw HTTP logs
#             and store the loot safely in a local SQLite database.

import os
import re
import sqlite3
import string
import random
import datetime
from time import time

# تحديد مسار الفولدر الحالي عشان الملفات تتكريت جنبه أياً كان نظام التشغيل
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_LOG_FILE = os.path.join(BASE_DIR, "access_dump.log")
LOOT_DB_FILE = os.path.join(BASE_DIR, "recon_vault.db")
REPORT_TXT_FILE = os.path.join(BASE_DIR, "final_engagement_report.txt")


# Decorator لقياس سرعة تنفيذ الفحص بدون تكرار كود الوقت جوه كل دالة
def execution_timer(func):
    def wrapper(*args, **kwargs):
        t_start = time()
        result = func(*args, **kwargs)
        print(f"[*] Task '{func.__name__}' finished in {time() - t_start:.4f} sec.")
        return result
    return wrapper


# توليد كود مرجعي عشوائي للعملية باستخدام موديول string و random
def generate_session_token(length=8):
    '''توليد كود عشوائي من حروف وأرقام لتمييز كل جلسة فحص'''
    pool = string.ascii_uppercase + string.digits
    token_chars = []
    while length > 0:
        token_chars.append(pool[random.randint(0, len(pool) - 1)])
        length -= 1
    return "OP-" + "".join(token_chars)


# تجهيز ملف لوج تجريبي لو مش موجود عشان السكريبت يشتغل معاك من أول مرة
def create_dummy_log_if_missing(log_path):
    if os.path.exists(log_path):
        return
    raw_logs = [
        "192.168.1.45 - GET https://portal.horus-corp.eg:8443/login?user=admin@horus-corp.eg [200]\n",
        "10.10.14.22 - POST http://dev.horus-corp.eg:8080/api/v1/auth?key=AKIA9876543210ZYX [401]\n",
        "172.16.0.99 - GET https://vpn.horus-corp.eg:443/reset?mail=dr.dabash@redteam.org [200]\n",
        "192.168.1.45 - GET http://mail.horus-corp.eg:80/inbox?user=admin@horus-corp.eg [200]\n",
        "CORRUPTED_LINE_WITHOUT_VALID_DATA_###\n",
        "10.10.14.88 - POST https://api.horus-corp.eg:8443/debug?token=AKIA1122334455ABC&mail=soc@horus-corp.eg [500]\n"
    ]
    f = open(log_path, "w", encoding="utf-8")
    f.writelines(raw_logs)
    f.close()


# الكلاس الأب (Base Class) لحفظ بيانات الفاحص والهدف الأساسية
class BaseAuditSession:
    restricted_targets = ("localhost", "127.0.0.1", "gov.eg")

    def __init__(self, operator_name, target_org="Unknown_Target", *scope_tags):
        self.operator = operator_name.strip().title()
        self.target_org = target_org.strip().replace(" ", "_")
        self.session_id = generate_session_token(8)
        self.start_date = datetime.datetime.now()
        # تحويل الـ Tuple الممرر عبر *args إلى Set لحذف أي تاج مكرر تلقائياً
        self.tags = set(scope_tags) if len(scope_tags) > 0 else {"general-recon"}

    def format_timestamp(self):
        return self.start_date.strftime("%Y-%m-%d %H:%M:%S (%A)")


# الكلاس الابن: يرث من BaseAuditSession ويضيف تحليل الـ RegEx وحفظ الـ SQLite
class LogReconAnalyzer(BaseAuditSession):
    def __init__(self, operator_name, target_org, log_file_path, db_path, *scope_tags):
        super().__init__(operator_name, target_org, *scope_tags)
        self.log_file_path = log_file_path
        self.db_path = db_path
        self.found_ips = []
        self.unique_emails = set()
        self.unique_subdomains = set()
        self.leaked_keys = set()
        self.parsed_endpoints = []

    # Generator بـ yield لقراءة ملفات اللوج الضخمة سطراً بسطر بدون استهلاك الرامات
    def stream_log_lines(self):
        log_file = None
        try:
            log_file = open(self.log_file_path, "r", encoding="utf-8")
            for line in log_file:
                clean_line = line.strip()
                if not clean_line or clean_line.startswith("CORRUPTED"):
                    continue  # تخطي السطور الفارغة أو التالفة
                yield clean_line
        except FileNotFoundError:
            print(f"[!] Error: Log file not found at {self.log_file_path}")
        finally:
            if log_file is not None:
                log_file.close()

    @execution_timer
    def run_regex_extraction(self):
        # أنماط الـ RegEx لاستخراج الـ IP، الإيميل، مفتاح الـ API، وتفكيك الرابط بـ Groups
        ip_pattern = r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"
        email_pattern = r"[A-z0-9\._-]+@[A-z0-9-]+\.(?:com|org|net|eg)"
        key_pattern = r"AKIA[A-Z0-9]{13}"
        url_group_pattern = r"(https?)://([a-z0-9\.-]+):?(\d+)?(/[^\s]+)?"

        for idx, line in enumerate(self.stream_log_lines(), 1):
            ips = re.findall(ip_pattern, line)
            if len(ips) > 0:
                self.found_ips.append(ips[0])

            # استخراج الإيميلات ومفاتيح الـ API وإضافتها للـ Set لمنع التكرار
            self.unique_emails.update(re.findall(email_pattern, line, re.IGNORECASE))
            self.leaked_keys.update(re.findall(key_pattern, line))

            # تفكيك الرابط لـ 4 أجزاء (بروتوكول، دومين، بورت، مسار) بـ .groups()
            url_match = re.search(url_group_pattern, line, re.IGNORECASE)
            if url_match:
                proto, full_host, port, path = url_match.groups()
                actual_port = int(port) if port else (443 if proto == "https" else 80)
                self.unique_subdomains.add(full_host.lower())
                self.parsed_endpoints.append((idx, full_host, actual_port, path))

    # حفظ النتائج في SQLite بأمان ضد ثغرة SQL Injection باستخدام علامة (?)
    def save_loot_to_sqlite(self):
        db = None
        try:
            db = sqlite3.connect(self.db_path)
            cr = db.cursor()
            cr.execute("""
                CREATE TABLE IF NOT EXISTS endpoints_loot (
                    line_num INTEGER, session_id TEXT, subdomain TEXT, port INTEGER, url_path TEXT
                )
            """)
            cr.execute("DELETE FROM endpoints_loot WHERE session_id = ?", (self.session_id,))

            for item in self.parsed_endpoints:
                row_data = (item[0], self.session_id, item[1], item[2], item[3])
                cr.execute("INSERT INTO endpoints_loot VALUES(?, ?, ?, ?, ?)", row_data)

            db.commit()
            print(f"[+] Saved {len(self.parsed_endpoints)} endpoints safely to SQLite DB.")
        except sqlite3.Error as db_err:
            print(f"[!] Database Error: {db_err}")
        finally:
            if db:
                db.close()

    # دمج الإحصائيات بـ zip والدوال المدمجة وتصدير التقرير النهائي لملف نصي
    def export_summary_report(self, report_path, **extra_notes):
        unique_ips = sorted(list(set(self.found_ips)))
        ip_hit_counts = [self.found_ips.count(ip) for ip in unique_ips]
        ip_summary_pairs = list(zip(unique_ips, ip_hit_counts))

        ports_only = [ep[2] for ep in self.parsed_endpoints]
        has_leaked_keys = any(self.leaked_keys)
        all_valid_ports = all([0 < p <= 65535 for p in ports_only])

        lines = [
            "=" * 68,
            f" RECONVAULT ENGAGEMENT REPORT | {self.session_id} ".center(68, "="),
            "=" * 68,
            f"Operator      : {self.operator} | Target: {self.target_org}",
            f"Timestamp     : {self.format_timestamp()} | Tags: {', '.join(self.tags)}",
            "-" * 68,
            f"  - Unique Subdomains ({len(self.unique_subdomains)}) : {sorted(list(self.unique_subdomains))}",
            f"  - Discovered Emails ({len(self.unique_emails)}) : {sorted(list(self.unique_emails))}",
            f"  - Leaked API Keys   ({len(self.leaked_keys)}) : {list(self.leaked_keys) if has_leaked_keys else 'None'}",
            f"  - IP Traffic (IP, Hits) : {ip_summary_pairs}",
            f"  - Port Metrics (Valid={all_valid_ports}) : Min={min(ports_only)} | Max={max(ports_only)} | Hits={sum(ip_hit_counts)}"
        ]

        if len(extra_notes) > 0:
            lines.append("-" * 68)
            for k, v in extra_notes.items():
                lines.append(f"  * {k.replace('_', ' ').title()}: {v}")

        lines.append("=" * 68)
        final_text = "\n".join(lines)

        out_file = open(report_path, "w", encoding="utf-8")
        out_file.write(final_text + "\n")
        out_file.close()
        print("\n" + final_text)


# تشغيل الأداة مباشرة (ولن يعمل هذا الجزء تلقائياً لو استوردت الملف داخل سكريبت آخر)
if __name__ == "__main__":
    create_dummy_log_if_missing(SAMPLE_LOG_FILE)
    recon_job = LogReconAnalyzer(
        "Youssef Tamer Dabash (Dr. Dabash)", "Horus Financial Corp", SAMPLE_LOG_FILE, LOOT_DB_FILE,
        "web-recon", "log-audit", "red-team", "web-recon"
    )
    recon_job.run_regex_extraction()
    recon_job.save_loot_to_sqlite()
    recon_job.export_summary_report(
        REPORT_TXT_FILE,
        finding_severity="High (AWS AKIA Keys Exposed in GET/POST Query)",
        recommended_fix="Rotate compromised keys and move tokens to Authorization headers."
    )