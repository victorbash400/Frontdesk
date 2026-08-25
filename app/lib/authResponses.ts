export function authenticationRequiredResponse() {
  return Response.json(
    { error: "Authentication is required" },
    { headers: { "X-Front-Desk-Auth-State": "missing-session" }, status: 401 },
  );
}
