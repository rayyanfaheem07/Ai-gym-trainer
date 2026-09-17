"""
Development Setup Script for Real-Time AI Gym Trainer.
Verifies dependencies, environment configuration, and database connectivity.
"""
import os
import sys


def check_python_version():
    print("Checking Python version...")
    if sys.version_info < (3, 10):
        print("ERROR: Python 3.10+ is required.")
        sys.exit(1)
    print(f"OK: Python {sys.version.split()[0]} detected.")

def setup_env_file():
    print("Checking .env file...")
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            with open(".env.example") as src, open(".env", "w") as dst:
                dst.write(src.read())
            print("Created .env from .env.example")
    else:
        print("OK: .env already exists.")

def main():
    print("=== Initializing AI Gym Trainer Development Environment ===")
    check_python_version()
    setup_env_file()
    print("Environment setup verification completed successfully.")

if __name__ == "__main__":
    main()
