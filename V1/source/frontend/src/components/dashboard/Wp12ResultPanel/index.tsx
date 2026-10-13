"use client"

import type { Wp12RunResult } from "@/lib/types/wp12"
import styles from "./Wp12ResultPanel.module.css"

interface Wp12ResultPanelProps {
  result: Wp12RunResult | null
}

function stringify(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)) : []
}

export function Wp12ResultPanel({ result }: Wp12ResultPanelProps) {
  if (!result) {
    return (
      <section className={styles.panel} aria-label="WP1-2 结构化结果">
        <div className={styles.header}>
          <h2 className={styles.title}>结构化结果</h2>
        </div>
        <div className={styles.emptyState}>运行完成后，这里会展示 threat understanding、execution assessment、validation 和 artifacts。</div>
      </section>
    )
  }

  const threatUnderstanding = result.threat_understanding ?? {}
  const executionAssessment = result.execution_assessment ?? {}
  const packageValidation = result.package_validation ?? {}
  const artifacts = result.artifacts ?? {}

  return (
    <section className={styles.panel} aria-label="WP1-2 结构化结果">
      <div className={styles.header}>
        <h2 className={styles.title}>结构化结果</h2>
        <span className={styles.subtle}>辅助阅读</span>
      </div>

      <div className={styles.grid}>
        <article className={styles.card}>
          <h3 className={styles.cardTitle}>Threat Understanding</h3>
          <dl className={styles.kvList}>
            <div>
              <dt>Threat Summary</dt>
              <dd>{String(threatUnderstanding.threat_summary ?? "N/A")}</dd>
            </div>
            <div>
              <dt>Attack Mechanism</dt>
              <dd>{String(threatUnderstanding.attack_mechanism ?? "N/A")}</dd>
            </div>
            <div>
              <dt>Target Surface</dt>
              <dd>{String(threatUnderstanding.target_surface ?? "N/A")}</dd>
            </div>
            <div>
              <dt>Taxonomy</dt>
              <dd>{stringify(threatUnderstanding.taxonomy ?? {})}</dd>
            </div>
          </dl>
        </article>

        <article className={styles.card}>
          <h3 className={styles.cardTitle}>Execution Assessment</h3>
          <dl className={styles.kvList}>
            <div>
              <dt>Eligibility</dt>
              <dd>{String(executionAssessment.execution_eligibility ?? "N/A")}</dd>
            </div>
            <div>
              <dt>Readiness</dt>
              <dd>{String(executionAssessment.test_readiness ?? "N/A")}</dd>
            </div>
            <div>
              <dt>Execution Mode</dt>
              <dd>{String(executionAssessment.execution_mode ?? "N/A")}</dd>
            </div>
            <div>
              <dt>Blockers</dt>
              <dd>
                {stringList(executionAssessment.execution_blockers).length > 0
                  ? stringList(executionAssessment.execution_blockers).join("、")
                  : "N/A"}
              </dd>
            </div>
          </dl>
        </article>

        <article className={styles.card}>
          <h3 className={styles.cardTitle}>Package Validation</h3>
          <dl className={styles.kvList}>
            <div>
              <dt>Valid</dt>
              <dd>{packageValidation.valid === false ? "false" : "true"}</dd>
            </div>
            <div>
              <dt>Missing Fields</dt>
              <dd>
                {stringList(packageValidation.missing_fields).length > 0
                  ? stringList(packageValidation.missing_fields).join(", ")
                  : "None"}
              </dd>
            </div>
            <div>
              <dt>Validation Errors</dt>
              <dd>
                {stringList(packageValidation.validation_errors).length > 0
                  ? stringList(packageValidation.validation_errors).join("\n")
                  : "None"}
              </dd>
            </div>
          </dl>
        </article>

        <article className={styles.card}>
          <h3 className={styles.cardTitle}>Artifacts</h3>
          <dl className={styles.kvList}>
            <div>
              <dt>Persistence Path</dt>
              <dd>{artifacts.persistence_path ?? "N/A"}</dd>
            </div>
            <div>
              <dt>Raw State</dt>
              <dd>{artifacts.raw_state_path ?? "N/A"}</dd>
            </div>
            <div>
              <dt>Presentation State</dt>
              <dd>{artifacts.presentation_state_path ?? "N/A"}</dd>
            </div>
            <div>
              <dt>Plan Path</dt>
              <dd>{artifacts.plan_path ?? "N/A"}</dd>
            </div>
          </dl>
        </article>
      </div>
    </section>
  )
}
