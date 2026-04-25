from backend.agent.g_agent.agent.loop import AgentLoop

text = """aku nggak bisa langsung cek inbox Gmail kamu (nggak punya akses ke akun/email kamu), jadi aku juga nggak bisa memastikan ada berapa thread atau judul-judul emailnya.

kalau kamu mau, aku bisa bantu rangkum “email masuk hari ini” dengan cepat lewat salah satu cara ini:
1) Kirim screenshot inbox (bagian subject + pengirim + jam, info sensitif boleh disensor), atau
2) Copy-paste daftar subject/pengirimnya, atau
3) Export/forward beberapa email yang kamu anggap penting.

sambil itu, kamu bisa filter email “hari ini” di Gmail pakai pencarian:
newer_than:1d (24 jam terakhir)
atau after:2026/03/05 before:2026/03/06 (sesuaikan tanggal)

kirim daftar/screenshotnya, nanti aku tandai mana yang paling urgent + langkah actionable-nya."""

# Mock missing dependencies
class MockContext: pass
class MockRuntime: pass
class MockSessions: pass
class MockMetrics: pass

class MockAgentLoop(AgentLoop):
    def __init__(self):
        self._IDENTITY_DENIAL_PATTERNS = AgentLoop._IDENTITY_DENIAL_PATTERNS

import logging
logging.basicConfig(level=logging.DEBUG)

# Just run the filter function (it's a static/class method behavior)
loop = MockAgentLoop.__new__(MockAgentLoop)
print("--- ORIGINAL ---")
print(text)
print("--- FILTERED ---")
print(loop._filter_identity_violations(text))
