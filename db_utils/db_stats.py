# db_stats.py
import sqlite3

DB_PATH = "apollo_cache.db"

def fetch_one(conn, sql, params=()):
    cur = conn.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else 0

def fetch_all(conn, sql, params=()):
    cur = conn.execute(sql, params)
    return cur.fetchall()

def main():
    conn = sqlite3.connect(DB_PATH)

    # Companies
    companies_total = fetch_one(conn, "SELECT COUNT(*) FROM apollo_companies")
    companies_with_phone = fetch_one(conn, "SELECT COUNT(*) FROM apollo_companies WHERE phone IS NOT NULL AND TRIM(phone) <> ''")
    companies_with_domain = fetch_one(conn, "SELECT COUNT(*) FROM apollo_companies WHERE primary_domain IS NOT NULL AND TRIM(primary_domain) <> ''")

    # People
    people_total = fetch_one(conn, "SELECT COUNT(*) FROM apollo_people")
    people_with_email = fetch_one(conn, "SELECT COUNT(*) FROM apollo_people WHERE email IS NOT NULL AND TRIM(email) <> '' AND email <> 'email_not_unlocked@domain.com'")
    people_with_phone = fetch_one(conn, "SELECT COUNT(*) FROM apollo_people WHERE phone IS NOT NULL AND TRIM(phone) <> ''")
    people_email_no_phone = fetch_one(conn, "SELECT COUNT(*) FROM apollo_people WHERE email IS NOT NULL AND TRIM(email) <> '' AND email <> 'email_not_unlocked@domain.com' AND (phone IS NULL OR TRIM(phone) = '')")

    # Org coverage
    distinct_orgs_in_people = fetch_one(conn, "SELECT COUNT(DISTINCT organization_id) FROM apollo_people WHERE organization_id IS NOT NULL AND TRIM(organization_id) <> ''")
    avg_people_per_org = 0.0
    people_with_org = fetch_one(conn, "SELECT COUNT(*) FROM apollo_people WHERE organization_id IS NOT NULL AND TRIM(organization_id) <> ''")
    if distinct_orgs_in_people > 0:
        avg_people_per_org = round(people_with_org / distinct_orgs_in_people, 2)

    # Freshness
    last_updated_people = fetch_one(conn, "SELECT COALESCE(MAX(last_updated), '') FROM apollo_people")
    last_updated_companies = fetch_one(conn, "SELECT COALESCE(MAX(last_updated), '') FROM apollo_companies")

    # Source breakdown (top 5)
    people_sources = fetch_all(conn, "SELECT COALESCE(source,'unknown') AS src, COUNT(*) FROM apollo_people GROUP BY src ORDER BY COUNT(*) DESC LIMIT 5")
    company_sources = fetch_all(conn, "SELECT COALESCE(source,'unknown') AS src, COUNT(*) FROM apollo_companies GROUP BY src ORDER BY COUNT(*) DESC LIMIT 5")

    # Title distribution (top 10)
    title_dist = fetch_all(conn, "SELECT LOWER(TRIM(title)) AS t, COUNT(*) FROM apollo_people WHERE t IS NOT NULL AND t <> '' GROUP BY t ORDER BY COUNT(*) DESC LIMIT 10")

    conn.close()

    print("=== DATABASE STATS ===")
    print(f"Companies: total={companies_total}, with_domain={companies_with_domain}, with_phone={companies_with_phone}")
    print(f"People: total={people_total}, with_email={people_with_email}, with_phone={people_with_phone}, email_no_phone={people_email_no_phone}")
    print(f"Orgs referenced by people: distinct={distinct_orgs_in_people}, avg_people_per_org={avg_people_per_org}")
    print(f"Last updated: people={last_updated_people}, companies={last_updated_companies}")

    print("\nTop people sources (up to 5):")
    for src, cnt in people_sources:
        print(f"  - {src}: {cnt}")

    print("\nTop company sources (up to 5):")
    for src, cnt in company_sources:
        print(f"  - {src}: {cnt}")

    print("\nTop titles (up to 10):")
    for t, cnt in title_dist:
        print(f"  - {t}: {cnt}")

if __name__ == "__main__":
    main()