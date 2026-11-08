#!/usr/bin/env python3
"""Ban nhieu request checkout dong thoi va in ra ket qua thuc te (dap an) o phia client.

Cach dung:  python3 scripts/load_checkout.py [so_request] [seed]
"""
import json
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

USER_SERVICE = "http://localhost:8081"
ORDER_SERVICE = "http://localhost:8082"

TOTAL = int(sys.argv[1]) if len(sys.argv) > 1 else 20
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 42

# (phuong thuc thanh toan, so tien)
SCENARIOS = [
    ("CARD", 1200000),
    ("WALLET", 350000),
    ("BANK_TRANSFER", 900000),
    ("BROKEN_GATEWAY", 500000),  # cong thanh toan loi -> 502
    ("CARD", 60000000),          # vuot han muc -> bi tu choi (402)
]

OUTCOMES = {201: "OK", 402: "DECLINED", 502: "GATEWAY_ERROR"}


def call(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def ensure_users(count):
    """Dam bao co it nhat `count` user, tra ve danh sach id."""
    _, body = call("GET", USER_SERVICE + "/api/users")
    ids = [u["id"] for u in json.loads(body)]
    i = 0
    while len(ids) < count:
        i += 1
        email = f"load{int(time.time())}{i}@storex.local"
        _, created = call("POST", USER_SERVICE + "/api/users",
                          {"fullName": f"Load User {i}", "email": email})
        ids.append(json.loads(created)["id"])
    return ids[:count]


def main():
    random.seed(SEED)
    user_ids = ensure_users(5)

    jobs = []
    for n in range(1, TOTAL + 1):
        method, amount = random.choice(SCENARIOS)
        jobs.append({"n": n, "userId": random.choice(user_ids),
                     "method": method, "amount": amount})

    results = {}
    lock = threading.Lock()
    barrier = threading.Barrier(TOTAL)

    def run(job):
        barrier.wait()  # tat ca request duoc ban cung luc
        status, _ = call("POST", ORDER_SERVICE + "/api/checkout", {
            "userId": job["userId"],
            "productName": f"Product-{job['n']}",
            "quantity": 1,
            "amount": job["amount"],
            "paymentMethod": job["method"],
        })
        with lock:
            results[job["n"]] = status

    start = datetime.now(timezone.utc)
    threads = [threading.Thread(target=run, args=(j,)) for j in jobs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    end = datetime.now(timezone.utc)

    print(f"Da ban {TOTAL} request checkout dong thoi (seed={SEED}).")
    print(f"Khoang thoi gian (UTC): {start:%H:%M:%S} -> {end:%H:%M:%S}\n")
    print(f"{'#':>3}  {'userId':>6}  {'method':<15} {'amount':>10}  {'HTTP':>4}  ket qua")
    failed = []
    for job in jobs:
        status = results[job["n"]]
        outcome = OUTCOMES.get(status, "UNKNOWN")
        print(f"{job['n']:>3}  {job['userId']:>6}  {job['method']:<15} {job['amount']:>10}  {status:>4}  {outcome}")
        if status != 201:
            failed.append(job)

    print(f"\nSo giao dich that bai (dap an that): {len(failed)}/{TOTAL}")
    by_user = {}
    for job in failed:
        by_user[job["userId"]] = by_user.get(job["userId"], 0) + 1
    for uid in sorted(by_user):
        print(f"  userId={uid}: {by_user[uid]} giao dich that bai")


if __name__ == "__main__":
    main()
