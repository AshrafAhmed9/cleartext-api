from locust import HttpUser, task, between
import random

COMMENTS = [
    "I hate you so much",
    "You are wonderful",
    "This is terrible",
    "Have a great day",
    "I will destroy you",
    "Thank you for your help",
    "You are the worst",
    "Great job everyone",
]

class ToxicityUser(HttpUser):
    wait_time = between(1, 3)  # each user waits 1-3s between requests
    token = None

    def on_start(self):
        # Each simulated user logs in first
        response = self.client.post("/token", data={
            "username": "admin",
            "password": "secret"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def predict(self):
        text = random.choice(COMMENTS)
        self.client.post("/predict", json={"text": text}, headers=self.headers)

    @task(1)
    def health_check(self):
        self.client.get("/health")
