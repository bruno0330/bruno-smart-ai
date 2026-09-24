#!/usr/bin/env python3
"""產生智能策展部三個分頁的密碼閘門設定檔（smart-curation/gate-config.js）。

只輸出「鹽」與「PBKDF2 雜湊」，不含密碼本身。密碼請在自己的終端機輸入，
不要貼給任何人或 AI，也不要寫進檔案。

  互動模式：python3 scripts/make_gate_config.py
  非互動（測試用）：BSA_PW_GVM=... BSA_PW_ESG=... BSA_PW_MAIL=... python3 scripts/make_gate_config.py --out /tmp/x.js

注意：這道門只擋誤闖，擋不住資料檔直接下載（資料檔網址是公開的）。
"""
import argparse
import base64
import getpass
import hashlib
import json
import os
import sys
import unicodedata

TABS = [('gvm', '線上讀', 'BSA_PW_GVM'), ('esg', '共好圈', 'BSA_PW_ESG'), ('mail', '會員溝通信件', 'BSA_PW_MAIL')]
MIN_LEN, WARN_LEN = 8, 12


def derive(password, salt, iterations):
    pw = unicodedata.normalize('NFC', password).encode('utf-8')
    return hashlib.pbkdf2_hmac('sha256', pw, salt, iterations, dklen=32)


def check_length(pw, label):
    if len(pw) < MIN_LEN:
        sys.exit('「%s」密碼至少 %d 個字元。' % (label, MIN_LEN))
    if len(pw) < WARN_LEN:
        print('警告：「%s」密碼少於 %d 個字元，建議加長。' % (label, WARN_LEN), file=sys.stderr)


def ask(label, default_pw):
    while True:
        prompt = '「%s」分頁密碼%s：' % (label, '' if default_pw is None else '（直接 Enter＝與線上讀相同）')
        pw = getpass.getpass(prompt)
        if not pw and default_pw is not None:
            return default_pw
        if not pw:
            print('第一組密碼必填。')
            continue
        if getpass.getpass('再輸入一次確認：') != pw:
            print('兩次輸入不一致，請重來。')
            continue
        check_length(pw, label)
        return pw


def collect():
    passwords = {}
    if sys.stdin.isatty():
        for key, label, _ in TABS:
            passwords[key] = ask(label, passwords.get('gvm'))
    else:
        first = os.environ.get('BSA_PW_GVM', '')
        if not first:
            sys.exit('非互動模式需要環境變數 BSA_PW_GVM。')
        for key, label, env in TABS:
            passwords[key] = os.environ.get(env) or first
            check_length(passwords[key], label)
    return passwords


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument('--out', default=os.path.join(root, 'smart-curation', 'gate-config.js'))
    ap.add_argument('--iterations', type=int, default=600000)
    args = ap.parse_args()

    tabs = {}
    for key, pw in collect().items():
        salt = os.urandom(16)
        tabs[key] = {
            'salt': base64.b64encode(salt).decode('ascii'),
            'hash': base64.b64encode(derive(pw, salt, args.iterations)).decode('ascii'),
        }
    cfg = {'v': 1, 'iterations': args.iterations, 'tabs': tabs}
    with open(args.out, 'w', encoding='utf-8') as f:
        f.write('// 由 scripts/make_gate_config.py 產生：只含鹽與雜湊，不含密碼。\n')
        f.write('window.BSA_GATE = ' + json.dumps(cfg, indent=2) + ';\n')
    print('已寫入 ' + args.out)


if __name__ == '__main__':
    main()
