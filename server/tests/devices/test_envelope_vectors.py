"""The sync contract's test vectors (section 4.7), checked once for pairing and sync.

The bytes live in tests/contract_vectors.py. Fake data only.
"""

import hashlib
import json

import pytest
from contract_vectors import KEY, PAIR_SK, V1, V2, VECTOR_BODY, VECTOR_CODE
from fake_phone import ACK, LAN_HOST, NOW, PAIR, SNAPSHOT, open_reply
from nacl.secret import SecretBox
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto.b64url import b64u_decode, b64u_encode
from app.errors import ApiError
from app.models import Device, PairingSession
from app.services.devices import envelope
from app.services.devices import phones as device_service


def test_vector_1_request_box_opens():
    plain = SecretBox(KEY).decrypt(b64u_decode(V1["box"]), b64u_decode(V1["nonce"], 24))
    assert plain == (
        b'{"type":"req","ts":1790000000,"method":"POST","path":"/api/sync/snapshot",'
        b'"contract":1,"data":{}}'
    )


def test_vector_3_tampered_box_fails():
    from nacl.exceptions import CryptoError

    box = bytearray(b64u_decode(V1["box"]))
    box[-1] ^= 1
    with pytest.raises(CryptoError):
        SecretBox(KEY).decrypt(bytes(box), b64u_decode(V1["nonce"], 24))


@pytest.mark.parametrize(
    ("text", "length"),
    [
        ("Zk3pR7tQ1xYb9mWc2nLs5a", None),
        ("ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3=", None),
        ("ICEiIyQlJicoKSorLC0uLzAxMjM0NTY+", None),
        ("AAAAA", None),
        ("ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3\n", None),
        ("AAECAwQFBgcICQoLDA0ODxAREhMUFRYX", 32),
        (None, None),
    ],
)
def test_vector_5_strict_base64url_rejects(text, length):
    with pytest.raises(ValueError):
        b64u_decode(text, length)


def test_canonical_value_is_accepted():
    assert b64u_encode(b64u_decode("Zk3pR7tQ1xYb9mWc2nLs5Q", 16)) == "Zk3pR7tQ1xYb9mWc2nLs5Q"


def test_vector_1_request_opens_through_the_envelope_module():
    outer = envelope.parse_outer(V1)
    inner = envelope.open_request(KEY, outer, path=SNAPSHOT)
    assert inner == {
        "type": "req",
        "ts": 1790000000,
        "method": "POST",
        "path": SNAPSHOT,
        "contract": 1,
        "data": {},
    }


def test_vector_1_is_refused_for_another_path():
    with pytest.raises(ApiError) as caught:
        envelope.open_request(KEY, envelope.parse_outer(V1), path=ACK)
    assert caught.value.code == "decrypt_failed"


def test_vector_2_response_decrypts_to_the_expected_text():
    plain = SecretBox(KEY).decrypt(b64u_decode(V2["box"]), b64u_decode(V2["nonce"], 24))
    assert plain.decode("utf-8") == (
        '{"type":"res","ts":1790000001,"re":"ICEiIyQlJicoKSorLC0uLzAxMjM0NTY3","status":200,'
        '"data":{"merchant":"Café Olé","total_cents":1234}}'
    )


def test_seal_makes_a_response_the_phone_can_open():
    reply = envelope.seal(KEY, V1["nonce"], NOW, 200, data={"merchant": "Café Olé"})
    plain = SecretBox(KEY).decrypt(b64u_decode(reply["box"]), b64u_decode(reply["nonce"], 24))
    inner = json.loads(plain)
    assert inner["type"] == "res" and inner["re"] == V1["nonce"] and inner["status"] == 200
    assert inner["data"] == {"merchant": "Café Olé"}


def test_vector_3_tampered_box_is_decrypt_failed():
    box = bytearray(b64u_decode(V1["box"]))
    box[-1] ^= 1
    outer = envelope.parse_outer(V1 | {"box": b64u_encode(bytes(box))})
    with pytest.raises(ApiError) as caught:
        envelope.open_request(KEY, outer, path=SNAPSHOT)
    assert caught.value.code == "decrypt_failed"


def test_contract_vector_4_pairs_and_the_reply_opens_with_shared(app_client):
    dashboard, phone = app_client
    with Session(dashboard.app.state.engine) as session:
        session.add(
            PairingSession(
                code_hash=hashlib.sha256(VECTOR_CODE.encode()).hexdigest(),
                pair_pub="YFpyXSpK3-6xop4X7dYhwbdZPujNvESsbEq24vgF0jw",
                pair_sk=b64u_encode(PAIR_SK),
                created_at=NOW,
                exp=NOW + 600,
            )
        )
        session.commit()

    response = phone.post(PAIR, json=VECTOR_BODY, headers=LAN_HOST)
    assert response.status_code == 200, response.text
    shared = b64u_decode("zSsDtyenL7oJQc53ndiVIG5KaKRYVTL4LHpaOqazn_c", 32)
    reply = open_reply(response, shared, b64u_decode(VECTOR_BODY["nonce"], 24))
    data = reply["data"]
    assert data["device_id"] == 1
    assert data["server_id"] == dashboard.app.state.server_id
    assert data["server_name"] == "Home Base"
    b64u_decode(data["token"], 32)
    b64u_decode(data["sync_key"], 32)
    assert reply["ts"] == NOW

    with Session(dashboard.app.state.engine) as session:
        device = session.scalars(select(Device)).one()
        assert device.name == "Test Phone" and device.platform == "ios"
        assert device.app_version == "1.0.0" and not device.revoked
        # Only the hash of the token is stored; the sync key is the encrypted column.
        assert device.token_hash == hashlib.sha256(data["token"].encode("ascii")).hexdigest()
        assert device.sync_key == data["sync_key"]
        ended = session.scalars(select(PairingSession)).one()
        assert ended.used_at == NOW and ended.pair_sk is None  # private key erased


def test_token_hash_vector():
    token = "YGFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6e3x9fn8"
    assert device_service.hash_token(token) == (
        "128a42f0efc787b4710881a27873ead95dfcf13a9dfbdf9ca1f2f0600ecb9407"
    )
