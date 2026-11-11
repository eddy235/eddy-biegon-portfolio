"""Regression tests for Maison Sanaa hospitality ordering and inventory."""
from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

temporary = tempfile.TemporaryDirectory(prefix="maison-sanaa-tests-")
os.environ["HOSPITALITY_DB"] = str(Path(temporary.name) / "test.db")
os.environ["HOSPITALITY_ADMIN_PASSWORD"] = "test-private-password"
os.environ["HOSPITALITY_COOKIE_SECURE"] = "0"
module = importlib.import_module("hospitality.app")
client = TestClient(module.app)

class HospitalityTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        client.close()
        temporary.cleanup()

    def test_01_public_pages_and_menu(self):
        for path in ("/", "/order", "/staff", "/health", "/manifest.webmanifest", "/sw.js", "/assets/app.js", "/assets/styles.css"):
            response = client.get(path)
            self.assertEqual(response.status_code, 200, path)
        products = client.get("/api/menu").json()
        self.assertEqual(len(products), 14)
        self.assertTrue(all(p["available"] for p in products))
        self.assertIn("Coastal breakfast", [p["name"] for p in products])

    def test_02_staff_access_control(self):
        self.assertEqual(client.get("/api/staff/snapshot").status_code, 401)
        self.assertEqual(client.post("/api/staff/login", json={"password":"wrong"}).status_code, 401)
        response = client.post("/api/staff/login", json={"password":"test-private-password"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("maison_staff", client.cookies)
        self.assertEqual(client.get("/api/staff/snapshot").status_code, 200)

    def test_03_server_calculated_order_and_stock_deduction(self):
        old = {item["id"]: item["quantity"] for item in client.get("/api/staff/snapshot").json()["stock"]}
        response = client.post("/api/orders", json={
            "guest_name":"Test Guest", "delivery_type":"room", "location":"204",
            "items":[{"id":"swahili-breakfast","quantity":2}]
        })
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["total"], 2500)
        self.assertEqual(response.json()["status"], "received")
        code = response.json()["code"]
        tracked = client.get("/api/orders/" + code)
        self.assertEqual(tracked.status_code, 200)
        self.assertEqual(tracked.json()["items"][0]["quantity"], 2)
        snapshot = client.get("/api/staff/snapshot").json()
        eggs = next(item for item in snapshot["stock"] if item["id"] == "eggs")
        self.assertEqual(eggs["quantity"], old["eggs"] - 4)
        self.assertEqual(snapshot["stats"]["orders"], 1)
        self.assertEqual(snapshot["stats"]["revenue"], 2500)

    def test_04_invalid_order_does_not_modify_stock(self):
        before = client.get("/api/staff/snapshot").json()["stock"]
        response = client.post("/api/orders", json={
            "guest_name":"Test Guest", "delivery_type":"room","location":"204",
            "items":[{"id":"not-a-real-menu-item","quantity":1}]
        })
        self.assertEqual(response.status_code, 422)
        self.assertEqual(before, client.get("/api/staff/snapshot").json()["stock"])

    def test_045_blank_guest_name(self):
        response = client.post("/api/orders", json={
            "guest_name":"   ", "delivery_type":"room","location":"204",
            "items":[{"id":"swahili-breakfast","quantity":1}]
        })
        self.assertEqual(response.status_code, 422)

    def test_05_order_status_transitions(self):
        record = client.get("/api/staff/snapshot").json()["orders"][0]
        path = "/api/staff/orders/" + str(record["id"]) + "/status"
        self.assertEqual(client.post(path, json={"status":"served"}).status_code, 409)
        for value in ("preparing", "ready", "served"):
            response = client.post(path, json={"status":value})
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(client.post(path, json={"status":"received"}).status_code, 409)

    def test_06_inventory_adjustment_and_bounds(self):
        before = {x["id"]:x["quantity"] for x in client.get("/api/staff/snapshot").json()["stock"]}
        path = "/api/staff/inventory/milk"
        self.assertEqual(client.post(path, json={"delta":-1000,"reason":"Test excessive use"}).status_code, 409)
        self.assertEqual(client.post(path, json={"delta":5,"reason":"Test replenishment"}).status_code, 200)
        after = {x["id"]:x["quantity"] for x in client.get("/api/staff/snapshot").json()["stock"]}
        self.assertEqual(after["milk"], before["milk"] + 5)

    def test_07_logout(self):
        self.assertEqual(client.post("/api/staff/logout").status_code, 200)
        self.assertEqual(client.get("/api/staff/snapshot").status_code, 401)

if __name__ == "__main__":
    unittest.main()
