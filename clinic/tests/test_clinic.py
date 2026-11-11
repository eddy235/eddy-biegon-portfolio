"""Tulia Care API / queue authorization and correctness regression tests."""
from __future__ import annotations
import os
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

testdir=tempfile.TemporaryDirectory()
os.environ["CLINIC_DB"]=str(Path(testdir.name)/"clinic_test.sqlite")
os.environ["CLINIC_STAFF_PASSWORD"]="test-demo-reception-password"
os.environ["CLINIC_COOKIE_SECURE"]="0"
os.environ["CLINIC_SEED_DEMO"]="0"
from clinic import app as clinic

class ClinicTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(clinic.app)
        clinic.ATTEMPTS.clear()
        with clinic.db(write=True) as con:
            con.execute("DELETE FROM visits")
            con.execute("DELETE FROM patients")

    def register(self,name="Demo Alex"):
        response=self.client.post("/api/patients",json={"display_name":name,"accepted_demo_terms":True})
        self.assertEqual(response.status_code,201,response.text)
        return response.json()["access_token"]

    def staff(self):
        response=self.client.post("/api/staff/login",json={"password":"test-demo-reception-password"})
        self.assertEqual(response.status_code,200,response.text)

    def test_01_pages_services_and_headers(self):
        for path in ("/","/register","/my-visit","/reception"):
            response=self.client.get(path)
            self.assertEqual(response.status_code,200,response.text)
            self.assertIn("Tulia Care",response.text)
        services=self.client.get("/api/services")
        self.assertEqual(len(services.json()),6)
        self.assertEqual(services.headers["cache-control"],"no-store")
        self.assertIn("default-src 'self'",services.headers["content-security-policy"])
        self.assertFalse(self.client.get("/health").json()["production_ready"])

    def test_02_registration_consent_and_no_identity_data(self):
        self.assertEqual(self.client.post("/api/patients",json={"display_name":"Name","accepted_demo_terms":False}).status_code,422)
        self.assertEqual(self.client.post("/api/patients",json={"display_name":" ","accepted_demo_terms":True}).status_code,422)
        token=self.register()
        result=self.client.get("/api/me",headers={"X-Patient-Token":token})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()["display_name"],"Demo Alex")
        self.assertIsNone(result.json()["visit"])
        self.assertEqual(self.client.get("/api/me",headers={"X-Patient-Token":"invalid"}).status_code,401)

    def test_03_precheck_arrive_and_live_position(self):
        token=self.register()
        h={"X-Patient-Token":token}
        r=self.client.post("/api/visits",headers=h,json={"service_id":"general","onsite":False})
        self.assertEqual(r.status_code,201,r.text)
        self.assertEqual(r.json()["visit"]["status"],"prechecked")
        self.assertEqual(self.client.get("/api/me",headers=h).json()["visit"]["status"],"prechecked")
        self.assertEqual(self.client.post("/api/visits",headers=h,json={"service_id":"lab","onsite":True}).status_code,409)
        arrived=self.client.post("/api/visits/arrive",headers=h)
        self.assertEqual(arrived.status_code,200,arrived.text)
        self.assertEqual(arrived.json()["visit"]["position"],1)
        self.assertEqual(self.client.post("/api/visits/arrive",headers=h).status_code,409)
        counts=self.client.get("/api/public/queue").json()
        self.assertEqual(next(s for s in counts if s["id"]=="general")["waiting"],1)
        self.assertNotIn("display_name",str(counts))

    def test_04_private_tokens_and_no_ticket_enumeration(self):
        first=self.register("Visitor One")
        second=self.register("Visitor Two")
        self.client.post("/api/visits",headers={"X-Patient-Token":first},
                         json={"service_id":"wellness","onsite":True})
        second_data=self.client.get("/api/me",headers={"X-Patient-Token":second}).json()
        self.assertIsNone(second_data["visit"])
        other=self.client.get("/api/me",headers={"X-Patient-Token":first}).json()
        self.assertEqual(other["visit"]["position"],1)
        self.assertNotIn("access_token",str(self.client.get("/api/staff/overview").text))

    def test_05_staff_call_next_and_queue_transitions(self):
        first=self.register("First Guest"); second=self.register("Second Guest")
        for token in (first,second):
            self.client.post("/api/visits",headers={"X-Patient-Token":token},
                             json={"service_id":"wellness","onsite":True})
        self.assertEqual(self.client.post("/api/staff/call-next",json={"service_id":"wellness"}).status_code,401)
        self.staff()
        first_call=self.client.post("/api/staff/call-next",json={"service_id":"wellness"})
        self.assertEqual(first_call.status_code,200,first_call.text)
        self.assertEqual(first_call.json()["ticket"],"WEL-001")
        self.assertEqual(self.client.post("/api/staff/call-next",json={"service_id":"wellness"}).status_code,409)
        overview=self.client.get("/api/staff/overview").json()
        first_row=next(v for v in overview["visits"] if v["ticket"]=="WEL-001")
        self.assertEqual(first_row["status"],"called")
        bad=self.client.post(f"/api/staff/visits/{first_row['id']}/status",json={"status":"waiting"})
        self.assertEqual(bad.status_code,409)
        done=self.client.post(f"/api/staff/visits/{first_row['id']}/status",json={"status":"completed"})
        self.assertEqual(done.status_code,200,done.text)
        self.assertEqual(self.client.post("/api/staff/call-next",json={"service_id":"wellness"}).json()["ticket"],"WEL-002")
        overview=self.client.get("/api/staff/overview").json()
        second_row=next(v for v in overview["visits"] if v["ticket"]=="WEL-002")
        missed=self.client.post(f"/api/staff/visits/{second_row['id']}/status",json={"status":"missed"})
        self.assertEqual(missed.status_code,200)
        restored=self.client.post(f"/api/staff/visits/{second_row['id']}/status",json={"status":"waiting"})
        self.assertEqual(restored.status_code,200)
        self.assertEqual(self.client.get("/api/me",headers={"X-Patient-Token":second}).json()["visit"]["position"],1)

    def test_06_staff_security(self):
        self.assertEqual(self.client.get("/api/staff/overview").status_code,401)
        self.assertEqual(self.client.post("/api/staff/login",json={"password":"wrong"}).status_code,401)
        self.staff()
        self.assertEqual(self.client.get("/api/staff/overview").status_code,200)
        fail=self.client.post("/api/staff/call-next",json={"service_id":"general"},headers={"Origin":"https://other.example"})
        self.assertEqual(fail.status_code,403)
        self.assertEqual(self.client.post("/api/staff/logout").status_code,200)
        self.assertEqual(self.client.get("/api/staff/overview").status_code,401)

    def test_07_queue_scoping_and_duplicate_ticket_prevention(self):
        a=self.register("First Unique")
        b=self.register("Second Unique")
        for t in (a,b):
            r=self.client.post("/api/visits",headers={"X-Patient-Token":t},
                  json={"service_id":"dental","onsite":True})
            self.assertEqual(r.status_code,201)
        tickets=[self.client.get("/api/me",headers={"X-Patient-Token":t}).json()["visit"]["ticket"] for t in (a,b)]
        self.assertEqual(tickets,["DEN-001","DEN-002"])
        self.assertEqual(self.client.get("/api/me",headers={"X-Patient-Token":b}).json()["visit"]["people_ahead"],1)
        self.assertEqual(self.client.post("/api/visits",headers={"X-Patient-Token":a},json={"service_id":"bogus"}).status_code,422)

if __name__=="__main__":unittest.main()
