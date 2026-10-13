import { describe, expect, it } from "vitest"
import { Wp12FeedItemDetailSchema } from "./wp12"

describe("Wp12FeedItemDetailSchema", () => {
  it("accepts nullable detail fields from the backend", () => {
    const parsed = Wp12FeedItemDetailSchema.parse({
      attack_id: "atk-001",
      attack_code: "WP12-PI-001",
      canonical_name: "Prompt Injection",
      attack_family: "prompt_injection",
      summary: "summary",
      severity_level: "high",
      last_seen_at: "2026-04-11T00:00:00+00:00",
      primary_cvss_base_score: 8.1,
      primary_cvss_severity_label: "high",
      taxonomy_code: "LLM01",
      taxonomy_name: "Prompt Injection",
      component_name: "langchain",
      asset_name: "seed-asset",
      active: true,
      stix_payload: null,
      component_context: null,
      published_seed_assets: null,
      component_risk_overview: null,
      all_taxonomies: null,
    })

    expect(parsed.stix_payload).toBeNull()
    expect(parsed.component_context).toBeNull()
  })
})
