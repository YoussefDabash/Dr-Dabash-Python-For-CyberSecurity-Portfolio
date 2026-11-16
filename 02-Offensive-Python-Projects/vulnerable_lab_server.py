#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local Vulnerable Lab Target Server (Port 5000) for Testing Projects #3, #4, and #5
Author: Youssef Tamer Dabash (Dr. Dabash)
Warning: Intentionally vulnerable to Form Brute-Force & Blind SQL Injection. Run locally only!
"""

import sqlite3
from flask import Flask, request

app = Flask(__name__)
DB_MEM = sqlite3.connect(":memory:", check_same_thread=False)


def init_lab_db():
    cr = DB_MEM.cursor()
    cr.execute("CREATE TABLE IF NOT EXISTS user (id INTEGER PRIMARY KEY, username TEXT, password TEXT)")
    cr.execute("DELETE FROM user")
    # نفس الهاشات والحسابات الموجودة في لقطات الشاشة الرسمية للمشاريع 3 و 4 و 5
    users = [
        (0, "admin", "71232f297a57a5a743894a0e4a801fc3"),
        (1, "user", "098f6bcd4621d373cade4e832627b4f6"),
        (2, "test", "9830ec78efba77129b561f62fed5f652330ea4bb589ab1ab21fee99bdf20e98c"),
    ]
    cr.executemany("INSERT INTO user (id, username, password) VALUES (?, ?, ?)", users)
    DB_MEM.commit()


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        # دعم حساب test:test لمشروع تخمين الويب رقم 3
        if username == "test" and password == "test":
            return "Welcome back, test!", 200

        # استعلام مصاب عمداً بثغرة Blind SQL Injection لاختبار المشروعين 4 و 5
        query = f"SELECT id, username FROM user WHERE username = '{username}'"
        try:
            cr = DB_MEM.cursor()
            row = cr.execute(query).fetchone()
            if row:
                return "Welcome back!", 200
        except sqlite3.Error:
            pass
        return "Invalid credentials.", 200

    return "Dr. Dabash Local SQLi & Brute-Force Lab Target is Running on Port 5000.", 200


if __name__ == "__main__":
    init_lab_db()
    print("[*] Starting Dr. Dabash Local Lab Server on http://127.0.0.1:5000 ...")
    app.run(host="127.0.0.1", port=5000, debug=False)
