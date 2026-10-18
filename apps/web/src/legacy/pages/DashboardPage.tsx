import { EmptyState, FilterBar, MetricCard, PageActions, DataTableShell } from "../components/ui";
import { ROLE_LABELS } from "../navigation";
import type { UserRole } from "../types";
import { type DashboardRouteKey, PAGE_DEFINITIONS } from "./pageContent";

type DashboardPageProps = {
  routeKey: DashboardRouteKey;
  role: UserRole;
};

export function DashboardPage({ routeKey, role }: DashboardPageProps) {
  const page = PAGE_DEFINITIONS[routeKey];
  const actions = page.actions(role);

  return (
    <section className="page-stack" aria-labelledby="page-title">
      <div className="page-header">
        <div>
          <p className="eyebrow">{page.eyebrow}</p>
          <h2 id="page-title">{page.title}</h2>
          <p className="page-description">{page.description}</p>
        </div>
        <div className="page-header-side">
          <span className="role-scope">{ROLE_LABELS[role]} view</span>
          <PageActions actions={actions} />
        </div>
      </div>

      <FilterBar filters={page.filters} />

      <section className="metric-grid" aria-label={`${page.title} metrics`}>
        {page.metrics.map((metric) => (
          <MetricCard key={metric.label} metric={metric} />
        ))}
      </section>

      <section className="content-grid">
        <article className="panel wide">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Module readiness</p>
              <h3>Data contract and next API work</h3>
            </div>
          </div>
          <DataTableShell columns={page.columns} rows={page.rows} />
        </article>

        <aside className="panel">
          <EmptyState title={page.emptyTitle} message={page.emptyMessage} />
        </aside>
      </section>
    </section>
  );
}
