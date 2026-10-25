"""Create the username/password Secret used by the Helm chart."""
import getpass
import json
import re
import subprocess


def build_secret(username, password):
    # The pinned chart inserts these values into an INI file using sed.
    # This alphabet avoids sed replacement characters and INI interpolation.
    if not re.fullmatch(r"[A-Za-z0-9_.@+-]+", username):
        raise ValueError("Username: use letters, numbers, or _ . @ + -")
    if len(password) < 16 or not re.fullmatch(r"[A-Za-z0-9_.@+-]+", password):
        raise ValueError("Password: use at least 16 characters from letters, numbers, or _ . @ + -")
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "mlflow-auth", "namespace": "mlflow"},
        "type": "Opaque",
        "stringData": {"admin-user": username, "admin-password": password},
    }


def main():
    username = input("MLflow administrator username: ").strip()
    password = getpass.getpass("MLflow administrator password (16+ characters): ")
    secret = build_secret(username, password)
    subprocess.run(["kubectl", "create", "-f", "-"], input=json.dumps(secret), text=True, check=True)
    print("Created mlflow-auth. Credentials were not written to this repository.")


if __name__ == "__main__":
    main()
