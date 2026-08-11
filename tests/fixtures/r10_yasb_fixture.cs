using System;
using System.IO;

internal static class R10YasbFixture
{
    private const string Valid = "{\"version\":2,\"execution_state\":\"complete\",\"execution_error\":null,\"providers\":[{\"provider\":\"codex\",\"compact_text\":\"Quota 80% remaining; state=available; freshness=fresh\",\"alternate_text\":\"Quota account / day: 80% remaining; state=available; freshness=fresh\",\"tooltip_text\":\"State: available\\nFreshness: fresh\\nQuota: 80% remaining\"},{\"provider\":\"opencode_go\",\"compact_text\":\"Quota 60% remaining; state=available; freshness=fresh\",\"alternate_text\":\"Quota account / day: 60% remaining; state=available; freshness=fresh\",\"tooltip_text\":\"State: available\\nFreshness: fresh\\nQuota: 60% remaining\"}]}";

    public static int Main()
    {
        var statePath = Environment.GetEnvironmentVariable("YASB_R10_FIXTURE_STATE");
        if (!String.IsNullOrEmpty(statePath) && File.Exists(statePath) &&
            String.Equals(File.ReadAllText(statePath).Trim(), "malformed", StringComparison.Ordinal))
        {
            Console.Write("{");
            return 0;
        }

        Console.Write(Valid);
        return 0;
    }
}
