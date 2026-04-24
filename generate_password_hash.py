#!/usr/bin/env python3
"""
Utility script to generate password hashes for user authentication.

Usage: python generate_password_hash.py
"""
from passlib.context import CryptContext
import getpass

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def main():
    print("Password Hash Generator")
    print("=" * 50)
    
    username = input("Username: ")
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    
    if password != confirm:
        print("\nERROR: Passwords do not match!")
        return
    
    hash_value = pwd_context.hash(password)
    
    print("\n" + "=" * 50)
    print("Add this to config.py USERS_DB:")
    print("=" * 50)
    print(f'"{username}": {{')
    print(f'    "password_hash": "{hash_value}",')
    print(f'    "role": "user"  # or "admin"')
    print(f'}},')
    print("=" * 50)

if __name__ == "__main__":
    main()
