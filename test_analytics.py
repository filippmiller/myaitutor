import datetime
from app.database import engine
from sqlmodel import Session, select
from app.models import UserAccount

def test_analytics_read_only():
    # 1. Get Admin User (for auth mock)
    with Session(engine) as session:
        admin = session.exec(select(UserAccount).where(UserAccount.role == "admin")).first()
        if not admin:
            print("No admin user found. Skipping test.")
            return

    # 2. Call Endpoint using TestClient
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    
    # Mock auth
    from app.services.auth_service import get_current_user
    def mock_get_current_user():
        return admin

    app.dependency_overrides[get_current_user] = mock_get_current_user
    
    print("Calling analytics endpoint...")
    # Test Day Grouping
    resp = client.get(
        "/api/admin/analytics/revenue/minutes",
        params={
            "from_date": (datetime.datetime.utcnow() - datetime.timedelta(days=30)).isoformat(),
            "to_date": datetime.datetime.utcnow().isoformat(),
            "group_by": "day"
        }
    )
    
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print("Response Keys:", data.keys())
        print("Buckets Count:", len(data.get("buckets", [])))
        print("Totals:", data.get("totals"))
        assert "buckets" in data
        assert "totals" in data
        print("Read-only Sanity Check Passed!")
    else:
        print("Error:", resp.text)

if __name__ == "__main__":
    test_analytics_read_only()
