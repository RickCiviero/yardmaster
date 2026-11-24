"""The install commands the README documents, exactly. test_manifests.py pins them to the manifests; test_readme.py
(Task 22) pins the README to this list."""

REPO = "RickCiviero/yardmaster"
URL = f"https://github.com/{REPO}"

INSTALL_COMMANDS = [
    f"/plugin marketplace add {REPO}",
    "/plugin install yardmaster@yardmaster",
    f"npx skills add {REPO}",
    f"npx skills add {REPO} -a codex",
    f"npx skills add {REPO} -a github-copilot",
]
