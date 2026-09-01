import { exec } from "@swytchcode/runtime";

export const runtime = "nodejs";

/*
 * A plain (non-agent) Swytchcode call looks like this:
 *   const res = await exec("gmail.user.profile.get", { params: { userId: "me" } });
 *   res.data -> the API response
 * Used here just to light the connection dots in the header.
 */
async function callOrNull(id: string, params: Record<string, string>) {
  try {
    return (await exec(id, { params })) as { data?: Record<string, unknown> };
  } catch {
    return null;
  }
}

export async function GET() {
  const [gmail, calendar] = await Promise.all([
    callOrNull("gmail.user.profile.get", { userId: "me" }),
    callOrNull("calendar.me.calendarList.list", { maxResults: "1" }),
  ]);

  return Response.json({
    gmail: Boolean(gmail),
    calendar: Boolean(calendar),
    email: (gmail?.data?.emailAddress as string) ?? null,
  });
}
