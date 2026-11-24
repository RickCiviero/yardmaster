"""Fake-but-format-valid secrets, assembled at import time so no literal secret lives in the repo
(and push protection / gitleaks never see one). Deterministic. Keys are rule names; `#x` suffix = variant."""

import random
import string

_rnd = random.Random(20261123)
UPPER, DIGITS, ALNUM = string.ascii_uppercase, string.digits, string.ascii_letters + string.digits


def tok(n: int, alphabet: str = ALNUM) -> str:
    return "".join(_rnd.choice(alphabet) for _ in range(n))


def build() -> dict[str, str]:
    return {
        "aws-access-key": "AK" + "IA" + tok(16, UPPER + DIGITS),
        "aws-secret": "aws_secret_access_key = " + tok(40, ALNUM + "/+"),
        "gcp-api-key": "AI" + "za" + tok(35, ALNUM + "_-"),
        "azure-storage-key": "AccountKey=" + tok(86, ALNUM + "+/") + "==",
        "github-pat": "gh" + "p_" + tok(36),
        "github-pat#fine": "github" + "_pat_" + tok(22) + "_" + tok(40),
        "gitlab-pat": "gl" + "pat-" + tok(20, ALNUM + "_-"),
        "slack-token": "xo" + "xb-" + tok(11, DIGITS) + "-" + tok(24),
        "slack-webhook": "https://hooks.slack.com/services/T" + tok(8, UPPER + DIGITS) + "/B" + tok(8, UPPER + DIGITS) + "/" + tok(24),
        "stripe-key": "sk" + "_live_" + tok(24),
        "anthropic-key": "sk-" + "ant-api03-" + tok(60, ALNUM + "_-"),
        "openai-key": "sk-" + "proj-" + tok(48, ALNUM + "_-"),
        "google-oauth": "ya" + "29." + tok(60, ALNUM + "_-"),
        "jwt": "ey" + "J" + tok(20, ALNUM + "_-") + ".ey" + "J" + tok(30, ALNUM + "_-") + "." + tok(43, ALNUM + "_-"),
        "private-key-block": "-----BEGIN RSA PRIVATE KEY-----\n"
        + "\n".join(tok(64, ALNUM + "+/") for _ in range(5))
        + "\n-----END RSA PRIVATE KEY-----",
        "generic-secret": "DB_PASSWORD=" + tok(8, string.ascii_lowercase) + "-" + tok(10, ALNUM),
        "auth-header": "Authorization: Bearer " + tok(40, ALNUM + "._-"),
        "url-credentials": "postgres://admin:" + tok(14) + "@db.internal:5432/app",
        "url-credentials#srv": "mongodb+srv://svc:" + tok(14) + "@cluster0.example.net/app",
        "connection-string": "Server=tcp:db.example.net,1433;Database=app;User Id=sa;Password=" + tok(14) + ";",
        "npm-token": "npm_" + tok(36),
        "pypi-token": "pypi-AgEIcHlwaS5vcmc" + tok(60, ALNUM + "_-"),
    }


SECRETS = build()
