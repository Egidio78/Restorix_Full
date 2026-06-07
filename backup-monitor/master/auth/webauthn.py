import json, base64
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    ResidentKeyRequirement,
    PublicKeyCredentialDescriptor,
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier
import config

RP_ID = "localhost"
RP_NAME = "BackupMonitor"

def get_registration_options(username: str, user_id_bytes: bytes, existing_credentials: list[dict]) -> dict:
    exclude = [
        PublicKeyCredentialDescriptor(id=base64.b64decode(c["id"]))
        for c in existing_credentials
    ]
    opts = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=user_id_bytes,
        user_name=username,
        exclude_credentials=exclude,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.REQUIRED,
            resident_key=ResidentKeyRequirement.PREFERRED,
        ),
        supported_pub_key_algs=[COSEAlgorithmIdentifier.ECDSA_SHA_256],
    )
    return json.loads(options_to_json(opts))

def get_authentication_options(credentials: list[dict]) -> dict:
    allow = [
        PublicKeyCredentialDescriptor(id=base64.b64decode(c["id"]))
        for c in credentials
    ]
    opts = generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=allow,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return json.loads(options_to_json(opts))
