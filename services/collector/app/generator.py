"""Network-flow generator.

Two sources, transparent to the caller:
  1. Replay of real labelled NSL-KDD KDDTest+ flows (preferred — gives ground
     truth so live accuracy is a genuine measurement).
  2. A synthetic generator (fallback when the dataset can't be fetched).

Logic is lifted from the original monolith. Replay needs the model's
``feature_names`` (column order), which the collector fetches from the inference
service; until that arrives, the synthetic generator is used.
"""

from __future__ import annotations

import random

import httpx

PROTOCOLS = ["tcp", "udp", "icmp"]
SERVICES = [
    "http", "ftp", "smtp", "ssh", "dns", "ftp_data", "eco_i",
    "other", "private", "domain_u", "auth", "finger", "telnet",
]
SERVICE_PORTS: dict[str, int] = {
    "http": 80, "ftp": 21, "smtp": 25, "ssh": 22, "dns": 53,
    "ftp_data": 20, "eco_i": 7, "other": 0, "private": 0,
    "domain_u": 53, "auth": 113, "finger": 79, "telnet": 23,
}
LABEL_DIST = [
    ("normal", 0.55),
    ("neptune", 0.10), ("smurf", 0.05), ("portsweep", 0.05),
    ("ipsweep", 0.04), ("nmap", 0.03), ("satan", 0.03),
    ("back", 0.03), ("teardrop", 0.02), ("pod", 0.02),
    ("guess_passwd", 0.02), ("buffer_overflow", 0.02),
    ("warezclient", 0.02), ("warezmaster", 0.01), ("rootkit", 0.01),
]
_LABELS, _WEIGHTS = zip(*LABEL_DIST, strict=True)
CATEGORICAL_COLS = ("protocol_type", "service", "flag")


def _rand_ip(private: bool = True) -> str:
    if private:
        return f"192.168.{random.randint(0, 50)}.{random.randint(1, 254)}"
    return (
        f"{random.randint(1, 223)}.{random.randint(0, 255)}."
        f"{random.randint(0, 255)}.{random.randint(1, 254)}"
    )


class TrafficGenerator:
    def __init__(self, real_traffic_sample: int, kdd_test_url: str) -> None:
        self.real_traffic_sample = real_traffic_sample
        self.kdd_test_url = kdd_test_url
        self.feature_names: list[str] = []
        self._real_records: list[dict] = []
        self._real_by_label: dict[str, list[dict]] = {}

    @property
    def has_real_traffic(self) -> bool:
        return bool(self._real_records)

    def set_feature_names(self, names: list[str]) -> None:
        self.feature_names = names

    # ── real KDDTest+ replay ──────────────────────────────────────────────────
    def _row_to_raw(self, fields: list[str]) -> dict | None:
        if len(fields) < len(self.feature_names) + 1:
            return None
        raw: dict = {}
        for i, col in enumerate(self.feature_names):
            v = fields[i]
            if col in CATEGORICAL_COLS:
                raw[col] = v
            else:
                try:
                    raw[col] = int(v)
                except ValueError:
                    try:
                        raw[col] = float(v)
                    except ValueError:
                        raw[col] = 0
        label = fields[len(self.feature_names)].strip().lower()
        is_attack = label != "normal"
        raw["_label"] = label
        raw["_src_ip"] = _rand_ip(private=not is_attack)
        raw["_dst_ip"] = _rand_ip(private=True)
        raw["_src_port"] = random.randint(1024, 65535)
        raw["_dst_port"] = SERVICE_PORTS.get(raw.get("service", ""), random.randint(1, 1024))
        return raw

    def load_real_traffic(self) -> bool:
        """Best-effort download of KDDTest+. Requires feature_names to be set."""
        if not self.feature_names:
            return False
        try:
            with httpx.Client(timeout=20) as c:
                r = c.get(self.kdd_test_url)
                r.raise_for_status()
                text = r.text
        except Exception:
            return False

        records = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            raw = self._row_to_raw(line.split(","))
            if raw:
                records.append(raw)
        if not records:
            return False

        random.shuffle(records)
        self._real_records = records[: self.real_traffic_sample]
        by_label: dict[str, list[dict]] = {}
        for rec in self._real_records:
            by_label.setdefault(rec["_label"], []).append(rec)
        self._real_by_label = by_label
        return True

    # ── public sampling ───────────────────────────────────────────────────────
    def sample(self, label: str | None = None) -> dict:
        """Return one raw flow dict, replaying real traffic when available."""
        if self._real_records:
            if label:
                pool = self._real_by_label.get(label.lower())
                if pool:
                    return dict(random.choice(pool))
                # requested label not in the test set → fall through to synthetic
            else:
                return dict(random.choice(self._real_records))
        return self._synthetic(label)

    def _synthetic(self, label: str | None) -> dict:
        if label is None:
            label = random.choices(_LABELS, weights=_WEIGHTS, k=1)[0]
        is_attack = label != "normal"

        if is_attack:
            src_bytes = random.randint(0, 5000) if random.random() < 0.6 else random.randint(0, 100)
            dst_bytes = random.randint(0, 1000)
            flag = random.choice(["S0", "REJ", "RSTO", "SH"])
            count = random.randint(100, 511)
            serror = round(random.uniform(0.5, 1.0), 2)
        else:
            src_bytes = random.randint(200, 50000)
            dst_bytes = random.randint(200, 20000)
            flag = "SF"
            count = random.randint(1, 100)
            serror = round(random.uniform(0.0, 0.1), 2)

        service = random.choice(SERVICES)
        return {
            "duration": random.randint(0, 60) if not is_attack else 0,
            "protocol_type": random.choice(PROTOCOLS),
            "service": service,
            "flag": flag,
            "src_bytes": src_bytes,
            "dst_bytes": dst_bytes,
            "land": 0,
            "wrong_fragment": random.randint(0, 3) if is_attack else 0,
            "urgent": 0,
            "hot": random.randint(0, 5),
            "num_failed_logins": random.randint(0, 5) if is_attack else 0,
            "logged_in": 0 if is_attack else random.randint(0, 1),
            "num_compromised": random.randint(0, 10) if is_attack else 0,
            "root_shell": 1 if is_attack and random.random() < 0.1 else 0,
            "su_attempted": 0,
            "num_root": 0,
            "num_file_creations": 0,
            "num_shells": 0,
            "num_access_files": 0,
            "num_outbound_cmds": 0,
            "is_host_login": 0,
            "is_guest_login": 0,
            "count": count,
            "srv_count": random.randint(1, count),
            "serror_rate": serror,
            "srv_serror_rate": serror,
            "rerror_rate": round(random.uniform(0, 0.3) if is_attack else 0.0, 2),
            "srv_rerror_rate": 0.0,
            "same_srv_rate": round(
                random.uniform(0.0, 0.5) if is_attack else random.uniform(0.5, 1.0), 2
            ),
            "diff_srv_rate": round(random.uniform(0.0, 0.5), 2),
            "srv_diff_host_rate": round(random.uniform(0.0, 0.5), 2),
            "dst_host_count": random.randint(1, 255),
            "dst_host_srv_count": random.randint(1, 255),
            "dst_host_same_srv_rate": round(random.uniform(0.0, 1.0), 2),
            "dst_host_diff_srv_rate": round(random.uniform(0.0, 0.5), 2),
            "dst_host_same_src_port_rate": round(random.uniform(0.0, 1.0), 2),
            "dst_host_srv_diff_host_rate": round(random.uniform(0.0, 0.5), 2),
            "dst_host_serror_rate": serror,
            "dst_host_srv_serror_rate": serror,
            "dst_host_rerror_rate": 0.0,
            "dst_host_srv_rerror_rate": 0.0,
            "_src_ip": _rand_ip(private=not is_attack),
            "_dst_ip": _rand_ip(private=True),
            "_src_port": random.randint(1024, 65535),
            "_dst_port": SERVICE_PORTS.get(service, random.randint(1024, 65535)),
            "_label": label,
        }
