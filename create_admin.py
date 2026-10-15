import dbase as db

def main():
    uid = int(input("Telegram user_id to promote to admin: ").strip())
    db.upsert_user(uid, username=None, role="admin", days=3650)
    print(f"✅ {uid} is now an admin (lifetime).")

if __name__ == "__main__":
    main()