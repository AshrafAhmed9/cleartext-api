import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const errorRate = new Rate("errors");
const latency = new Trend("predict_latency", true);

const BASE = __ENV.BASE_URL || "http://localhost:8000";

const COMMENTS = [
  "I hate you so much",
  "You are wonderful and kind",
  "This is terrible garbage",
  "Have a great day friend",
  "I will destroy everything you love",
  "Thank you for your help",
  "You are the worst person alive",
  "Great job everyone keep it up",
  "Nobody likes you go away",
  "What a beautiful morning",
];

export const options = {
  scenarios: {
    ramp: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "15s", target: 50 },
        { duration: "30s", target: 100 },
        { duration: "30s", target: 500 },
        { duration: "15s", target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<2000"],
    errors: ["rate<0.05"],
  },
};

export function setup() {
  const res = http.post(`${BASE}/token`, {
    username: "admin",
    password: "secret",
  });
  check(res, { "login ok": (r) => r.status === 200 });
  return { token: res.json("access_token") };
}

export default function (data) {
  const text = COMMENTS[Math.floor(Math.random() * COMMENTS.length)];
  const headers = {
    Authorization: `Bearer ${data.token}`,
    "Content-Type": "application/json",
  };

  const start = Date.now();
  const res = http.post(
    `${BASE}/predict`,
    JSON.stringify({ text: text }),
    { headers: headers }
  );

  const ok = check(res, {
    "status 200": (r) => r.status === 200,
    "has status field": (r) => r.json("status") !== undefined,
  });

  errorRate.add(!ok);
  latency.add(Date.now() - start);

  // If queued, poll for result
  if (res.status === 200 && res.json("status") === "queued") {
    const taskId = res.json("task_id");
    for (let i = 0; i < 30; i++) {
      sleep(0.5);
      const poll = http.get(`${BASE}/result/${taskId}`, { headers: headers });
      if (poll.json("status") === "completed" || poll.json("status") === "failed") {
        break;
      }
    }
  }

  sleep(Math.random() * 2);
}
