import auth.webauthn as wn
import json

def test_registration_options_shape():
    user_id = b"user123"
    opts = wn.get_registration_options("admin", user_id, [])
    assert "challenge" in opts
    assert "rp" in opts
    assert opts["rp"]["id"] == wn.RP_ID

def test_authentication_options_shape():
    opts = wn.get_authentication_options([])
    assert "challenge" in opts
    assert opts["rpId"] == wn.RP_ID

def test_authentication_options_with_credentials():
    import base64
    fake_cred_id = base64.b64encode(b"fakecredential").decode()
    opts = wn.get_authentication_options([{"id": fake_cred_id}])
    assert "allowCredentials" in opts
    assert len(opts["allowCredentials"]) == 1
